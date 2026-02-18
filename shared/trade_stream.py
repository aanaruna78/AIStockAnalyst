"""
Kafka Trade Message Streaming
==============================
Streams trade messages with user info via Kafka.
Enables user-specific trade processing.

Topics:
  - signalforge.trades.request  — AI/user sends trade request
  - signalforge.trades.status   — Trade status updates
  - signalforge.trades.trailing_sl — Trailing SL updates

If Kafka is not available, falls back to an in-memory async queue
so the system still works without Kafka infrastructure.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Any
from zoneinfo import ZoneInfo

logger = logging.getLogger("trade_stream")
IST = ZoneInfo("Asia/Kolkata")

# Kafka configuration
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
KAFKA_ENABLED = bool(KAFKA_BOOTSTRAP)

# Topics
TOPIC_TRADE_REQUEST = "signalforge.trades.request"
TOPIC_TRADE_STATUS = "signalforge.trades.status"
TOPIC_TRAILING_SL = "signalforge.trades.trailing_sl"


# ──────────────────────────────────────────────────────────────────
# Trade Message Schema
# ──────────────────────────────────────────────────────────────────
class TradeMessage:
    """Standardized trade message for Kafka streaming."""

    def __init__(
        self,
        user_id: str,
        user_email: str,
        action: str,          # "PLACE", "CLOSE", "MODIFY_SL", "SQUARE_OFF"
        symbol: str,
        trade_type: str = "BUY",
        quantity: int = 0,
        price: float = 0.0,
        target: float = 0.0,
        stop_loss: float = 0.0,
        lots: int = 0,
        order_mode: str = "intraday",     # "intraday", "options"
        source: str = "AI",              # "AI" or "MANUAL"
        broker_config: dict = None,
        trade_id: str = "",
        iceberg: bool = False,
        conviction: float = 0.0,
        metadata: dict = None,
    ):
        self.message_id = str(uuid.uuid4())
        self.timestamp = datetime.now(IST).isoformat()
        self.user_id = user_id
        self.user_email = user_email
        self.action = action
        self.symbol = symbol
        self.trade_type = trade_type
        self.quantity = quantity
        self.price = price
        self.target = target
        self.stop_loss = stop_loss
        self.lots = lots
        self.order_mode = order_mode
        self.source = source
        self.broker_config = broker_config or {}
        self.trade_id = trade_id
        self.iceberg = iceberg
        self.conviction = conviction
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "action": self.action,
            "symbol": self.symbol,
            "trade_type": self.trade_type,
            "quantity": self.quantity,
            "price": self.price,
            "target": self.target,
            "stop_loss": self.stop_loss,
            "lots": self.lots,
            "order_mode": self.order_mode,
            "source": self.source,
            "broker_config": self.broker_config,
            "trade_id": self.trade_id,
            "iceberg": self.iceberg,
            "conviction": self.conviction,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, d: dict) -> "TradeMessage":
        msg = cls(
            user_id=d.get("user_id", ""),
            user_email=d.get("user_email", ""),
            action=d.get("action", ""),
            symbol=d.get("symbol", ""),
            trade_type=d.get("trade_type", "BUY"),
            quantity=d.get("quantity", 0),
            price=d.get("price", 0.0),
            target=d.get("target", 0.0),
            stop_loss=d.get("stop_loss", 0.0),
            lots=d.get("lots", 0),
            order_mode=d.get("order_mode", "intraday"),
            source=d.get("source", "AI"),
            broker_config=d.get("broker_config", {}),
            trade_id=d.get("trade_id", ""),
            iceberg=d.get("iceberg", False),
            conviction=d.get("conviction", 0.0),
            metadata=d.get("metadata", {}),
        )
        msg.message_id = d.get("message_id", msg.message_id)
        msg.timestamp = d.get("timestamp", msg.timestamp)
        return msg


# ──────────────────────────────────────────────────────────────────
# In-Memory Queue (Fallback when Kafka isn't available)
# ──────────────────────────────────────────────────────────────────
class InMemoryTradeStream:
    """Async in-memory trade message queue. Fallback when Kafka is not configured."""

    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._handlers: Dict[str, List[Callable]] = {}
        self._running = False
        self._consumer_tasks: List[asyncio.Task] = []

    def _get_queue(self, topic: str) -> asyncio.Queue:
        if topic not in self._queues:
            self._queues[topic] = asyncio.Queue(maxsize=10000)
        return self._queues[topic]

    async def publish(self, topic: str, message: TradeMessage):
        """Publish a trade message to a topic."""
        queue = self._get_queue(topic)
        try:
            queue.put_nowait(message.to_dict())
            logger.debug(f"Published to {topic}: {message.message_id}")
        except asyncio.QueueFull:
            logger.warning(f"Queue full for {topic}, dropping message")

    def subscribe(self, topic: str, handler: Callable):
        """Register a handler for messages on a topic."""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)
        logger.info(f"Subscribed handler to {topic}")

    async def _consume(self, topic: str):
        """Consume messages from a topic and dispatch to handlers."""
        queue = self._get_queue(topic)
        handlers = self._handlers.get(topic, [])

        while self._running:
            try:
                msg_dict = await asyncio.wait_for(queue.get(), timeout=1.0)
                message = TradeMessage.from_dict(msg_dict)
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(message)
                        else:
                            handler(message)
                    except Exception as e:
                        logger.error(f"Handler error on {topic}: {e}")
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Consumer error on {topic}: {e}")
                await asyncio.sleep(1)

    async def start(self):
        """Start consuming all subscribed topics."""
        self._running = True
        for topic in self._handlers:
            task = asyncio.create_task(self._consume(topic))
            self._consumer_tasks.append(task)
        logger.info(f"InMemoryTradeStream started with {len(self._consumer_tasks)} consumers")

    async def stop(self):
        """Stop all consumers."""
        self._running = False
        for task in self._consumer_tasks:
            task.cancel()
        self._consumer_tasks.clear()


# ──────────────────────────────────────────────────────────────────
# Kafka Trade Stream (when Kafka is available)
# ──────────────────────────────────────────────────────────────────
class KafkaTradeStream:
    """Kafka-backed trade message stream."""

    def __init__(self, bootstrap_servers: str = ""):
        self.bootstrap = bootstrap_servers or KAFKA_BOOTSTRAP
        self._producer = None
        self._consumers: Dict[str, Any] = {}
        self._handlers: Dict[str, List[Callable]] = {}
        self._running = False
        self._consumer_tasks: List[asyncio.Task] = []

    async def _init_producer(self):
        """Initialize Kafka producer."""
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap,
                value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            )
            await self._producer.start()
            logger.info("Kafka producer initialized")
        except ImportError:
            logger.warning("aiokafka not installed. Using in-memory fallback.")
            raise
        except Exception as e:
            logger.error(f"Kafka producer init error: {e}")
            raise

    async def publish(self, topic: str, message: TradeMessage):
        """Publish a trade message to Kafka topic."""
        if not self._producer:
            await self._init_producer()
        try:
            await self._producer.send_and_wait(topic, message.to_dict())
            logger.debug(f"Kafka published to {topic}: {message.message_id}")
        except Exception as e:
            logger.error(f"Kafka publish error: {e}")

    def subscribe(self, topic: str, handler: Callable):
        """Register a handler for a Kafka topic."""
        if topic not in self._handlers:
            self._handlers[topic] = []
        self._handlers[topic].append(handler)

    async def _consume(self, topic: str):
        """Consume from Kafka topic."""
        try:
            from aiokafka import AIOKafkaConsumer
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                group_id="signalforge-trading-engine",
                auto_offset_reset="latest",
            )
            await consumer.start()
            self._consumers[topic] = consumer

            handlers = self._handlers.get(topic, [])
            async for msg in consumer:
                if not self._running:
                    break
                message = TradeMessage.from_dict(msg.value)
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(message)
                        else:
                            handler(message)
                    except Exception as e:
                        logger.error(f"Kafka handler error: {e}")

        except ImportError:
            logger.warning("aiokafka not installed")
        except Exception as e:
            logger.error(f"Kafka consumer error on {topic}: {e}")

    async def start(self):
        """Start Kafka consumers."""
        self._running = True
        for topic in self._handlers:
            task = asyncio.create_task(self._consume(topic))
            self._consumer_tasks.append(task)

    async def stop(self):
        """Stop Kafka consumers and producer."""
        self._running = False
        for consumer in self._consumers.values():
            await consumer.stop()
        if self._producer:
            await self._producer.stop()
        for task in self._consumer_tasks:
            task.cancel()


# ──────────────────────────────────────────────────────────────────
# Factory — Returns Kafka or InMemory based on config
# ──────────────────────────────────────────────────────────────────
def create_trade_stream():
    """Create the appropriate trade stream based on configuration."""
    if KAFKA_ENABLED:
        try:
            import aiokafka  # noqa: F401
            logger.info(f"Using Kafka trade stream: {KAFKA_BOOTSTRAP}")
            return KafkaTradeStream(KAFKA_BOOTSTRAP)
        except ImportError:
            logger.warning("aiokafka not installed. Falling back to in-memory stream.")
            return InMemoryTradeStream()
    else:
        logger.info("Kafka not configured. Using in-memory trade stream.")
        return InMemoryTradeStream()


# Singleton stream instance
trade_stream = create_trade_stream()
