"""
End-to-end integration tests — Full trade lifecycle.
Tests the flow: TradeMessage → IcebergEngine → PaperBroker → TrailingStopLossEngine
"""
import asyncio
import pytest
from shared.trailing_sl import TrailingStopLossEngine, TrailConfig, TrailStrategy
from shared.iceberg_order import IcebergEngine, IcebergStatus
from shared.broker_interface import PaperBroker, BrokerRouter, OrderSide
from shared.trade_stream import TradeMessage, InMemoryTradeStream, TOPIC_TRADE_REQUEST
from shared.models import BrokerType, BrokerConfig


class TestE2EOptionsTrade:
    """
    Simulates: User requests 10-lot options BUY →
    Iceberg splits into slices → PaperBroker fills → Trailing SL tracks.
    """

    @pytest.mark.asyncio
    async def test_full_options_lifecycle(self):
        broker = PaperBroker()

        # 1) Create iceberg order for 10-lot option
        lots = 10
        lot_size = 65
        premium = 150.0
        assert IcebergEngine.should_iceberg_option(lots) is True

        order = IcebergEngine.create_option_iceberg(
            symbol="NIFTY24FEB23000CE",
            trade_type="BUY",
            lots=lots,
            premium=premium,
            lot_size=lot_size,
        )
        assert order.total_quantity == lots * lot_size  # 650
        assert len(order.slices) == 5  # 2 lots per slice

        # 2) Execute via PaperBroker
        async def broker_fill(symbol, trade_type, quantity, price, **kwargs):
            result = await broker.place_order(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=quantity,
                price=price,
            )
            return {
                "status": result.status,
                "fill_price": result.fill_price,
                "order_id": result.order_id,
            }

        filled_order = await IcebergEngine.execute(order, broker_fill)
        assert filled_order.status == IcebergStatus.FILLED
        assert filled_order.filled_quantity == 650
        assert filled_order.avg_fill_price > 0

        # 3) Start trailing SL
        avg_price = filled_order.avg_fill_price
        initial_sl = avg_price * 0.95  # 5% SL
        state = TrailingStopLossEngine.create_state(
            trade_id=filled_order.iceberg_id,
            trade_type="BUY",
            entry_price=avg_price,
            stop_loss=initial_sl,
        )

        config = TrailConfig(strategy=TrailStrategy.HYBRID)

        # 4) Simulate price movement
        prices = [
            avg_price * 1.005,  # 0.5% up
            avg_price * 1.01,   # 1% up
            avg_price * 1.02,   # 2% up
            avg_price * 1.015,  # pulls back to 1.5%
            avg_price * 1.03,   # 3% up
        ]

        sl_values = [state.current_sl]
        for p in prices:
            TrailingStopLossEngine.compute_new_sl(state, p, config)
            sl_values.append(state.current_sl)

        # SL should have moved up from initial
        assert state.current_sl > initial_sl
        # SL should be below the highest price
        assert state.current_sl < prices[-1]
        # Should have made at least one adjustment
        assert state.adjustments >= 1
        # Trail should be activated
        assert state.trail_activated is True

    @pytest.mark.asyncio
    async def test_stream_to_iceberg_to_fill(self):
        """Test TradeMessage → Stream → IcebergEngine → PaperBroker."""
        stream = InMemoryTradeStream()
        broker = PaperBroker()
        results = []

        async def trade_handler(msg: TradeMessage):
            if msg.iceberg and msg.lots > 5:
                order = IcebergEngine.create_option_iceberg(
                    symbol=msg.symbol,
                    trade_type=msg.trade_type,
                    lots=msg.lots,
                    premium=msg.price,
                )

                async def fill(symbol, trade_type, quantity, price, **kwargs):
                    result = await broker.place_order(
                        symbol=symbol, side=OrderSide.BUY,
                        quantity=quantity, price=price,
                    )
                    return {
                        "status": result.status,
                        "fill_price": result.fill_price,
                        "order_id": result.order_id,
                    }

                filled = await IcebergEngine.execute(order, fill)
                results.append(filled)

        stream.subscribe(TOPIC_TRADE_REQUEST, trade_handler)
        await stream.start()

        # Publish trade request
        msg = TradeMessage(
            user_id="user_001",
            user_email="trader@example.com",
            action="PLACE",
            symbol="NIFTY24FEB23000CE",
            trade_type="BUY",
            quantity=650,
            price=150.0,
            lots=10,
            order_mode="options",
            iceberg=True,
        )
        await stream.publish(TOPIC_TRADE_REQUEST, msg)

        # Give time for handlers + iceberg execution (5 slices x 300ms + overhead)
        await asyncio.sleep(3.0)
        await stream.stop()

        assert len(results) == 1
        assert results[0].status == IcebergStatus.FILLED
        assert results[0].filled_quantity == 650


class TestE2EStockTrade:
    """
    Simulates: Large intraday stock order (3x leverage) →
    Iceberg splits → PaperBroker fills → Trailing SL activates.
    """

    @pytest.mark.asyncio
    async def test_leveraged_stock_lifecycle(self):
        # 3x leverage: capital 5L → can buy 15L worth
        capital = 500_000
        price = 2500.0
        base_qty = int(capital / price)  # 200 shares
        leveraged_qty = base_qty * 3     # 600 shares

        assert IcebergEngine.should_iceberg_stock(leveraged_qty) is True

        order = IcebergEngine.create_stock_iceberg(
            symbol="RELIANCE",
            trade_type="BUY",
            quantity=leveraged_qty,
            price=price,
        )
        assert order.total_quantity == 600
        assert len(order.slices) == 2  # 500 + 100

        broker = PaperBroker()

        async def broker_fill(symbol, trade_type, quantity, price, **kwargs):
            result = await broker.place_order(
                symbol=symbol, side=OrderSide.BUY,
                quantity=quantity, price=price,
            )
            return {
                "status": result.status,
                "fill_price": result.fill_price,
                "order_id": result.order_id,
            }

        filled = await IcebergEngine.execute(order, broker_fill)
        assert filled.status == IcebergStatus.FILLED
        assert filled.filled_quantity == 600

        # Set up trailing SL with step trail (good for intraday)
        state = TrailingStopLossEngine.create_state(
            trade_id=filled.iceberg_id,
            trade_type="BUY",
            entry_price=filled.avg_fill_price,
            stop_loss=filled.avg_fill_price * 0.97,  # 3% SL
        )
        config = TrailConfig(
            strategy=TrailStrategy.STEP_TRAIL,
            step_size_pct=0.5,
            step_lock_pct=0.3,
        )

        # Price rises in steps
        entry = filled.avg_fill_price
        for mult in [1.006, 1.012, 1.018, 1.025]:
            TrailingStopLossEngine.compute_new_sl(state, entry * mult, config)

        # SL should have stepped up
        assert state.step_level >= 2
        assert state.current_sl > entry * 0.97
        # Serialize and restore
        d = TrailingStopLossEngine.state_to_dict(state)
        restored = TrailingStopLossEngine.state_from_dict(d)
        assert restored.step_level == state.step_level
        assert restored.current_sl == state.current_sl


class TestE2EBrokerSelection:
    """Test broker routing with user config."""

    def test_broker_config_model(self):
        config = BrokerConfig(
            broker_type=BrokerType.DHAN,
            dhan_client_id="test_client",
            dhan_access_token="test_token",
        )
        assert config.broker_type == BrokerType.DHAN
        assert config.dhan_client_id == "test_client"
        assert config.dhan_access_token == "test_token"

    def test_broker_config_paper_default(self):
        config = BrokerConfig()
        assert config.broker_type == BrokerType.NONE

    @pytest.mark.asyncio
    async def test_router_paper_order(self):
        router = BrokerRouter()
        broker = router.get_broker("paper")
        result = await broker.place_order(
            "NIFTY", OrderSide.BUY, 100, 20000.0,
        )
        assert result.status == "filled"


class TestE2EShortTrade:
    """Test short/SELL trade flow with trailing SL."""

    @pytest.mark.asyncio
    async def test_short_sell_with_trailing_sl(self):
        broker = PaperBroker()

        # Short sell NIFTY futures
        order = IcebergEngine.create_stock_iceberg(
            "NIFTY25FEB", "SELL", quantity=600, price=23000.0,
        )

        async def broker_fill(symbol, trade_type, quantity, price, **kwargs):
            result = await broker.place_order(
                symbol=symbol, side=OrderSide.SELL,
                quantity=quantity, price=price,
            )
            return {
                "status": result.status,
                "fill_price": result.fill_price,
                "order_id": result.order_id,
            }

        filled = await IcebergEngine.execute(order, broker_fill)
        assert filled.status == IcebergStatus.FILLED

        # Trailing SL for short: SL moves DOWN as price drops
        state = TrailingStopLossEngine.create_state(
            "SHORT-001", "SELL",
            entry_price=filled.avg_fill_price,
            stop_loss=filled.avg_fill_price * 1.03,  # 3% above 
        )
        config = TrailConfig(strategy=TrailStrategy.PERCENTAGE, activation_pct=0.3, trail_pct=0.5)

        # Price drops (good for short)
        entry = filled.avg_fill_price
        new_sl = TrailingStopLossEngine.compute_new_sl(state, entry * 0.98, config)
        assert new_sl is not None
        assert new_sl < entry * 1.03  # SL tightened


class TestE2ESerializationAcrossModules:
    """Test that serialized data from one module can be used by another."""

    @pytest.mark.asyncio
    async def test_iceberg_order_serialization_with_trail_state(self):
        """Simulate persisting trade state to JSON and restoring."""
        # Create and fill iceberg
        order = IcebergEngine.create_option_iceberg(
            "BANKNIFTY", "BUY", lots=8, premium=200.0, lot_size=25,
        )
        broker = PaperBroker()

        async def fill(symbol, trade_type, quantity, price, broker_name, user_id, slice_id):
            r = await broker.place_order(symbol, OrderSide.BUY, quantity, price)
            return {"status": r.status, "fill_price": r.fill_price, "order_id": r.order_id}

        await IcebergEngine.execute(order, fill)

        # Serialize iceberg state
        order_dict = IcebergEngine.order_to_dict(order)

        # Create trail state from filled order
        trail = TrailingStopLossEngine.create_state(
            order_dict["iceberg_id"], "BUY",
            order_dict["avg_fill_price"],
            order_dict["avg_fill_price"] * 0.95,
        )
        trail_dict = TrailingStopLossEngine.state_to_dict(trail)

        # Create message
        msg = TradeMessage(
            user_id="user_x", user_email="x@y.com",
            action="PLACE", symbol="BANKNIFTY",
            trade_type="BUY", quantity=200,
            price=order_dict["avg_fill_price"],
            lots=8, iceberg=True,
            metadata={
                "iceberg_id": order_dict["iceberg_id"],
                "trail_state": trail_dict,
            },
        )
        msg_dict = msg.to_dict()

        # Restore everything
        restored_msg = TradeMessage.from_dict(msg_dict)
        restored_trail = TrailingStopLossEngine.state_from_dict(
            restored_msg.metadata["trail_state"]
        )
        restored_order = IcebergEngine.order_from_dict(order_dict)

        assert restored_msg.user_id == "user_x"
        assert restored_trail.trade_id == order.iceberg_id
        assert restored_order.filled_quantity == order.filled_quantity
