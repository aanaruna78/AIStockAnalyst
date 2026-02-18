"""
Integration tests for shared/broker_interface.py — Broker Abstraction Layer.
Tests PaperBroker, BrokerRouter, and serialization.
"""
import pytest
from shared.broker_interface import (
    PaperBroker,
    BrokerRouter,
    BrokerType,
    OrderSide,
    OrderType,
    ProductType,
    ExchangeType,
    OrderResult,
)


class TestOrderResult:
    def test_order_result_to_dict(self):
        r = OrderResult(
            status="filled", order_id="O1", fill_price=150.0,
            fill_quantity=100, broker="paper",
        )
        d = r.to_dict()
        assert d["status"] == "filled"
        assert d["order_id"] == "O1"
        assert d["fill_price"] == 150.0
        assert d["broker"] == "paper"

    def test_order_result_defaults(self):
        r = OrderResult(status="failed", error="timeout")
        assert r.order_id == ""
        assert r.fill_price == 0.0
        assert r.raw_response == {}


class TestPaperBroker:
    """Test PaperBroker — simulated fills."""

    @pytest.fixture
    def broker(self):
        return PaperBroker()

    @pytest.mark.asyncio
    async def test_place_buy_order(self, broker):
        result = await broker.place_order(
            symbol="RELIANCE",
            side=OrderSide.BUY,
            quantity=100,
            price=2500.0,
        )
        assert result.status == "filled"
        assert result.order_id.startswith("PAPER-")
        assert result.fill_quantity == 100
        assert result.broker == "paper"
        # Slippage: fill_price should be slightly above for BUY
        assert result.fill_price >= 2500.0
        assert result.fill_price <= 2500.0 * 1.001

    @pytest.mark.asyncio
    async def test_place_sell_order(self, broker):
        result = await broker.place_order(
            symbol="TCS",
            side=OrderSide.SELL,
            quantity=50,
            price=3300.0,
        )
        assert result.status == "filled"
        # Slippage: fill_price should be slightly below for SELL
        assert result.fill_price <= 3300.0
        assert result.fill_price >= 3300.0 * 0.999

    @pytest.mark.asyncio
    async def test_place_multiple_orders(self, broker):
        """Place multiple orders and check uniqueness."""
        results = []
        for i in range(5):
            r = await broker.place_order("NIFTY", OrderSide.BUY, 100, 20000.0)
            results.append(r)
        order_ids = [r.order_id for r in results]
        assert len(set(order_ids)) == 5  # All unique

    @pytest.mark.asyncio
    async def test_get_positions(self, broker):
        await broker.place_order("INFY", OrderSide.BUY, 100, 1500.0)
        positions = await broker.get_positions()
        assert isinstance(positions, list)
        assert len(positions) >= 1

    @pytest.mark.asyncio
    async def test_cancel_order(self, broker):
        placed = await broker.place_order("HDFC", OrderSide.BUY, 50, 1600.0)
        result = await broker.cancel_order(placed.order_id)
        assert result.status == "cancelled"

    @pytest.mark.asyncio
    async def test_modify_order(self, broker):
        placed = await broker.place_order("WIPRO", OrderSide.BUY, 50, 400.0)
        result = await broker.modify_order(placed.order_id, price=405.0)
        assert result.status in ("modified", "filled")

    @pytest.mark.asyncio
    async def test_update_stop_loss(self, broker):
        placed = await broker.place_order("SBI", OrderSide.BUY, 100, 600.0)
        result = await broker.update_stop_loss(placed.order_id, new_sl=590.0)
        assert result.status in ("updated", "filled", "modified")

    @pytest.mark.asyncio
    async def test_get_order_status(self, broker):
        placed = await broker.place_order("AXIS", OrderSide.BUY, 50, 1100.0)
        result = await broker.get_order_status(placed.order_id)
        assert result.status == "filled"

    @pytest.mark.asyncio
    async def test_is_connected(self, broker):
        assert await broker.is_connected() is True

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self, broker):
        result = await broker.cancel_order("FAKE-ORDER-123")
        assert result.status in ("failed", "not_found")


class TestBrokerRouter:
    """Test BrokerRouter selects correct broker."""

    def test_default_paper_broker(self):
        router = BrokerRouter()
        broker = router.get_broker("paper")
        assert isinstance(broker, PaperBroker)

    def test_unknown_broker_returns_paper(self):
        router = BrokerRouter()
        broker = router.get_broker("unknown_broker_xyz")
        assert isinstance(broker, PaperBroker)

    @pytest.mark.asyncio
    async def test_route_order_via_paper(self):
        router = BrokerRouter()
        result = await router.get_broker("paper").place_order(
            symbol="MARUTI",
            side=OrderSide.BUY,
            quantity=10,
            price=10000.0,
        )
        assert result.status == "filled"


class TestBrokerEnums:
    """Test enum values are correct."""

    def test_order_side(self):
        assert OrderSide.BUY == "BUY"
        assert OrderSide.SELL == "SELL"

    def test_order_type(self):
        assert OrderType.MARKET == "MARKET"
        assert OrderType.LIMIT == "LIMIT"
        assert OrderType.SL == "SL"
        assert OrderType.SL_M == "SL-M"

    def test_product_type(self):
        assert ProductType.INTRADAY == "INTRADAY"
        assert ProductType.DELIVERY == "DELIVERY"
        assert ProductType.MARGIN == "MARGIN"

    def test_exchange_type(self):
        assert ExchangeType.NSE == "NSE"
        assert ExchangeType.NFO == "NFO"

    def test_broker_type(self):
        assert BrokerType.PAPER == "paper"
        assert BrokerType.DHAN == "dhan"
        assert BrokerType.ANGELONE == "angelone"
