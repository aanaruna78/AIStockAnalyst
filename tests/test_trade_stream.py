"""
Integration tests for shared/trade_stream.py — Trade Message Streaming.
Tests InMemoryTradeStream, TradeMessage serialization, and factory.
"""
import asyncio
import pytest
from shared.trade_stream import (
    TradeMessage,
    InMemoryTradeStream,
    create_trade_stream,
    TOPIC_TRADE_REQUEST,
    TOPIC_TRADE_STATUS,
    TOPIC_TRAILING_SL,
)


class TestTradeMessage:
    """Test TradeMessage creation and serialization."""

    def test_create_message(self):
        msg = TradeMessage(
            user_id="user_001",
            user_email="test@example.com",
            action="PLACE",
            symbol="RELIANCE",
            trade_type="BUY",
            quantity=100,
            price=2500.0,
            target=2600.0,
            stop_loss=2400.0,
        )
        assert msg.user_id == "user_001"
        assert msg.action == "PLACE"
        assert msg.symbol == "RELIANCE"
        assert msg.message_id != ""
        assert msg.timestamp != ""

    def test_to_dict(self):
        msg = TradeMessage(
            user_id="u1", user_email="a@b.com",
            action="PLACE", symbol="NIFTY",
            trade_type="BUY", quantity=65,
            price=100.0, lots=1,
        )
        d = msg.to_dict()
        assert d["user_id"] == "u1"
        assert d["action"] == "PLACE"
        assert d["quantity"] == 65
        assert d["lots"] == 1
        assert "message_id" in d
        assert "timestamp" in d

    def test_to_json(self):
        msg = TradeMessage(
            user_id="u2", user_email="b@c.com",
            action="CLOSE", symbol="TCS",
        )
        j = msg.to_json()
        assert '"action": "CLOSE"' in j
        assert '"symbol": "TCS"' in j

    def test_from_dict_roundtrip(self):
        msg = TradeMessage(
            user_id="u3", user_email="c@d.com",
            action="MODIFY_SL", symbol="INFY",
            trade_type="BUY", quantity=200,
            price=1500.0, stop_loss=1450.0,
            iceberg=True, conviction=0.85,
            metadata={"strategy": "momentum"},
        )
        d = msg.to_dict()
        restored = TradeMessage.from_dict(d)
        assert restored.user_id == "u3"
        assert restored.action == "MODIFY_SL"
        assert restored.symbol == "INFY"
        assert restored.iceberg is True
        assert restored.conviction == 0.85
        assert restored.metadata == {"strategy": "momentum"}
        assert restored.message_id == msg.message_id

    def test_default_values(self):
        msg = TradeMessage(
            user_id="u4", user_email="e@f.com",
            action="PLACE", symbol="HDFC",
        )
        assert msg.trade_type == "BUY"
        assert msg.quantity == 0
        assert msg.order_mode == "intraday"
        assert msg.source == "AI"
        assert msg.iceberg is False
        assert msg.broker_config == {}
        assert msg.metadata == {}


class TestInMemoryTradeStream:
    """Test in-memory pub/sub stream."""

    @pytest.mark.asyncio
    async def test_publish_and_consume(self):
        stream = InMemoryTradeStream()
        received = []

        async def handler(msg):
            received.append(msg)

        stream.subscribe(TOPIC_TRADE_REQUEST, handler)
        await stream.start()

        msg = TradeMessage(
            user_id="u10", user_email="x@y.com",
            action="PLACE", symbol="RELIANCE",
            quantity=100, price=2500.0,
        )
        await stream.publish(TOPIC_TRADE_REQUEST, msg)

        # Give consumer time to process
        await asyncio.sleep(0.3)
        await stream.stop()

        assert len(received) == 1
        assert received[0].symbol == "RELIANCE"
        assert received[0].user_id == "u10"

    @pytest.mark.asyncio
    async def test_multiple_messages(self):
        stream = InMemoryTradeStream()
        received = []

        async def handler(msg):
            received.append(msg)

        stream.subscribe(TOPIC_TRADE_STATUS, handler)
        await stream.start()

        for i in range(5):
            msg = TradeMessage(
                user_id=f"u{i}", user_email=f"u{i}@test.com",
                action="PLACE", symbol=f"SYM{i}",
            )
            await stream.publish(TOPIC_TRADE_STATUS, msg)

        await asyncio.sleep(0.5)
        await stream.stop()

        assert len(received) == 5

    @pytest.mark.asyncio
    async def test_multiple_topics(self):
        stream = InMemoryTradeStream()
        trade_msgs = []
        sl_msgs = []

        async def trade_handler(msg):
            trade_msgs.append(msg)

        async def sl_handler(msg):
            sl_msgs.append(msg)

        stream.subscribe(TOPIC_TRADE_REQUEST, trade_handler)
        stream.subscribe(TOPIC_TRAILING_SL, sl_handler)
        await stream.start()

        await stream.publish(
            TOPIC_TRADE_REQUEST,
            TradeMessage("u1", "a@b.com", "PLACE", "NIFTY"),
        )
        await stream.publish(
            TOPIC_TRAILING_SL,
            TradeMessage("u1", "a@b.com", "MODIFY_SL", "NIFTY"),
        )

        await asyncio.sleep(0.3)
        await stream.stop()

        assert len(trade_msgs) == 1
        assert len(sl_msgs) == 1
        assert trade_msgs[0].action == "PLACE"
        assert sl_msgs[0].action == "MODIFY_SL"

    @pytest.mark.asyncio
    async def test_sync_handler(self):
        stream = InMemoryTradeStream()
        received = []

        def sync_handler(msg):
            received.append(msg.symbol)

        stream.subscribe(TOPIC_TRADE_REQUEST, sync_handler)
        await stream.start()

        await stream.publish(
            TOPIC_TRADE_REQUEST,
            TradeMessage("u1", "a@b.com", "PLACE", "TCS"),
        )

        await asyncio.sleep(0.3)
        await stream.stop()

        assert received == ["TCS"]

    @pytest.mark.asyncio
    async def test_stop_prevents_further_consumption(self):
        stream = InMemoryTradeStream()
        received = []

        async def handler(msg):
            received.append(msg)

        stream.subscribe(TOPIC_TRADE_REQUEST, handler)
        await stream.start()
        await stream.stop()

        await stream.publish(
            TOPIC_TRADE_REQUEST,
            TradeMessage("u1", "a@b.com", "PLACE", "SBI"),
        )
        await asyncio.sleep(0.2)

        assert len(received) == 0  # Nothing consumed after stop


class TestTradeStreamFactory:
    """Test create_trade_stream factory."""

    def test_creates_in_memory_when_no_kafka(self):
        """Without KAFKA_BOOTSTRAP_SERVERS, should return InMemoryTradeStream."""
        stream = create_trade_stream()
        assert isinstance(stream, InMemoryTradeStream)


class TestTopicConstants:
    """Test topic name constants."""

    def test_topic_names(self):
        assert TOPIC_TRADE_REQUEST == "signalforge.trades.request"
        assert TOPIC_TRADE_STATUS == "signalforge.trades.status"
        assert TOPIC_TRAILING_SL == "signalforge.trades.trailing_sl"
