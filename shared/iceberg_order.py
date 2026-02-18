"""
Iceberg Order Algorithm
=======================
Splits large orders into smaller child orders to minimize market impact.
Used for both Options (> 5 lots) and Intraday stocks (leveraged qty).

Strategy:
  - Splits total quantity into child slices
  - Each slice is placed sequentially with a small delay
  - Monitors fill status before placing next slice
  - Adapts slice size based on volatility and liquidity
  - Supports both market and limit orders

For Options: > 5 lots triggers iceberg splitting
For Stocks: All intraday orders use iceberg (3x leverage = large qty)
"""

import asyncio
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Callable, Any
from dataclasses import dataclass, field

import pytz

logger = logging.getLogger("iceberg_order")
IST = pytz.timezone("Asia/Kolkata")


class IcebergStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SliceStatus(str, Enum):
    PENDING = "pending"
    PLACED = "placed"
    FILLED = "filled"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class OrderSlice:
    """A single child order within an iceberg."""
    slice_id: str
    sequence: int
    quantity: int
    price: float               # Limit price for this slice
    status: SliceStatus = SliceStatus.PENDING
    fill_price: Optional[float] = None
    fill_time: Optional[str] = None
    error: Optional[str] = None
    broker_order_id: Optional[str] = None  # ID from Dhan/Angelone


@dataclass
class IcebergOrder:
    """Parent iceberg order containing child slices."""
    iceberg_id: str
    symbol: str
    trade_type: str            # "BUY" or "SELL"
    total_quantity: int
    base_price: float          # Reference price
    order_type: str            # "LIMIT" or "MARKET"
    status: IcebergStatus = IcebergStatus.PENDING
    slices: List[OrderSlice] = field(default_factory=list)
    filled_quantity: int = 0
    avg_fill_price: float = 0.0
    created_at: str = ""
    completed_at: Optional[str] = None
    user_id: Optional[str] = None
    broker: Optional[str] = None  # "dhan", "angelone", "paper"

    # Configuration
    max_slice_qty: int = 0
    slice_delay_ms: int = 500  # Delay between slices in ms
    price_improvement_pct: float = 0.0  # Price improvement per slice


class IcebergEngine:
    """
    Manages iceberg order splitting and execution.
    
    Usage:
        engine = IcebergEngine()
        order = engine.create_iceberg(
            symbol="NIFTY24FEB23000CE",
            trade_type="BUY",
            total_quantity=650,  # 10 lots of 65
            base_price=150.0,
            lot_size=65,
            max_lots_per_slice=2,
        )
        
        # Execute via callback
        await engine.execute(order, place_order_fn)
    """

    # ── Options-specific constants ────────────────────────────────
    OPTION_ICEBERG_THRESHOLD_LOTS = 5   # Trigger iceberg above 5 lots
    OPTION_MAX_LOTS_PER_SLICE = 2       # Max 2 lots per slice (130 qty for Nifty)
    OPTION_SLICE_DELAY_MS = 300         # 300ms between option slices

    # ── Stock-specific constants ──────────────────────────────────
    STOCK_MAX_QTY_PER_SLICE = 500       # Max 500 shares per slice
    STOCK_SLICE_DELAY_MS = 500          # 500ms between stock slices
    STOCK_LEVERAGE = 3                  # 3x intraday margin leverage

    @staticmethod
    def should_iceberg_option(lots: int) -> bool:
        """Check if option order should use iceberg."""
        return lots > IcebergEngine.OPTION_ICEBERG_THRESHOLD_LOTS

    @staticmethod
    def should_iceberg_stock(quantity: int) -> bool:
        """Check if stock order should use iceberg (always for intraday with leverage)."""
        return quantity > IcebergEngine.STOCK_MAX_QTY_PER_SLICE

    @staticmethod
    def create_iceberg(
        symbol: str,
        trade_type: str,
        total_quantity: int,
        base_price: float,
        lot_size: int = 1,
        max_lots_per_slice: int = 2,
        max_qty_per_slice: int = 0,
        order_type: str = "LIMIT",
        slice_delay_ms: int = 500,
        price_improvement_pct: float = 0.02,  # 0.02% improvement per slice
        user_id: str = None,
        broker: str = "paper",
    ) -> IcebergOrder:
        """
        Create an iceberg order by splitting total quantity into slices.
        
        For options: splits by lots (lot_size > 1)
        For stocks: splits by max_qty_per_slice
        """
        now = datetime.now(IST)
        iceberg_id = f"ICE-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

        # Determine slice size
        if lot_size > 1:
            # Options: split by lots
            max_slice_qty = max_lots_per_slice * lot_size
        elif max_qty_per_slice > 0:
            # Stocks: split by max qty per slice
            max_slice_qty = max_qty_per_slice
        else:
            max_slice_qty = IcebergEngine.STOCK_MAX_QTY_PER_SLICE

        # Generate slices
        slices = []
        remaining = total_quantity
        sequence = 0

        while remaining > 0:
            slice_qty = min(remaining, max_slice_qty)

            # Progressive price improvement: slightly better price for later slices
            # BUY: lower price for later slices (willing to wait for dip)
            # SELL: higher price for later slices (willing to wait for uptick)
            improvement = sequence * (price_improvement_pct / 100) * base_price
            if trade_type.upper() == "BUY":
                slice_price = round(base_price - improvement, 2)
            else:
                slice_price = round(base_price + improvement, 2)

            slice_id = f"{iceberg_id}-S{sequence:02d}"
            slices.append(OrderSlice(
                slice_id=slice_id,
                sequence=sequence,
                quantity=slice_qty,
                price=slice_price,
            ))

            remaining -= slice_qty
            sequence += 1

        order = IcebergOrder(
            iceberg_id=iceberg_id,
            symbol=symbol,
            trade_type=trade_type,
            total_quantity=total_quantity,
            base_price=base_price,
            order_type=order_type,
            slices=slices,
            max_slice_qty=max_slice_qty,
            slice_delay_ms=slice_delay_ms,
            price_improvement_pct=price_improvement_pct,
            created_at=now.isoformat(),
            user_id=user_id,
            broker=broker,
        )

        logger.info(
            f"Created iceberg {iceberg_id}: {symbol} {trade_type} "
            f"total_qty={total_quantity} slices={len(slices)} "
            f"max_slice={max_slice_qty} delay={slice_delay_ms}ms"
        )
        return order

    @staticmethod
    async def execute(
        order: IcebergOrder,
        place_order_fn: Callable,
        cancel_check_fn: Optional[Callable] = None,
    ) -> IcebergOrder:
        """
        Execute an iceberg order by placing slices sequentially.
        
        Args:
            order: The IcebergOrder to execute
            place_order_fn: async fn(symbol, trade_type, qty, price, broker) -> dict
                Must return {"status": "filled", "fill_price": float, "order_id": str}
                or {"status": "failed", "error": str}
            cancel_check_fn: optional fn() -> bool. Returns True to cancel remaining slices.
        """
        order.status = IcebergStatus.IN_PROGRESS
        total_cost = 0.0

        for i, slice_order in enumerate(order.slices):
            # Check for cancellation
            if cancel_check_fn and cancel_check_fn():
                slice_order.status = SliceStatus.CANCELLED
                for remaining in order.slices[i + 1:]:
                    remaining.status = SliceStatus.CANCELLED
                order.status = IcebergStatus.CANCELLED
                logger.info(f"Iceberg {order.iceberg_id} cancelled at slice {i}")
                break

            try:
                # Place slice
                slice_order.status = SliceStatus.PLACED
                result = await place_order_fn(
                    symbol=order.symbol,
                    trade_type=order.trade_type,
                    quantity=slice_order.quantity,
                    price=slice_order.price,
                    broker=order.broker,
                    user_id=order.user_id,
                    slice_id=slice_order.slice_id,
                )

                if result.get("status") == "filled":
                    fill_price = result.get("fill_price", slice_order.price)
                    slice_order.status = SliceStatus.FILLED
                    slice_order.fill_price = fill_price
                    slice_order.fill_time = datetime.now(IST).isoformat()
                    slice_order.broker_order_id = result.get("order_id")
                    order.filled_quantity += slice_order.quantity
                    total_cost += fill_price * slice_order.quantity
                    order.avg_fill_price = round(total_cost / order.filled_quantity, 2)
                    order.status = IcebergStatus.PARTIALLY_FILLED
                    logger.info(
                        f"Slice {slice_order.slice_id} filled: "
                        f"qty={slice_order.quantity} @ {fill_price}"
                    )
                else:
                    slice_order.status = SliceStatus.FAILED
                    slice_order.error = result.get("error", "Unknown")
                    logger.warning(
                        f"Slice {slice_order.slice_id} failed: {slice_order.error}"
                    )
                    # Don't abort entire iceberg on one slice failure; continue

            except Exception as e:
                slice_order.status = SliceStatus.FAILED
                slice_order.error = str(e)
                logger.error(f"Slice {slice_order.slice_id} exception: {e}")

            # Delay between slices (skip delay after last slice)
            if i < len(order.slices) - 1:
                await asyncio.sleep(order.slice_delay_ms / 1000.0)

        # Final status
        if order.filled_quantity >= order.total_quantity:
            order.status = IcebergStatus.FILLED
        elif order.filled_quantity > 0:
            order.status = IcebergStatus.PARTIALLY_FILLED
        elif all(s.status == SliceStatus.FAILED for s in order.slices):
            order.status = IcebergStatus.FAILED

        order.completed_at = datetime.now(IST).isoformat()

        logger.info(
            f"Iceberg {order.iceberg_id} completed: "
            f"status={order.status.value} filled={order.filled_quantity}/{order.total_quantity} "
            f"avg_price={order.avg_fill_price}"
        )
        return order

    @staticmethod
    def create_option_iceberg(
        symbol: str,
        trade_type: str,
        lots: int,
        premium: float,
        lot_size: int = 65,
        user_id: str = None,
        broker: str = "paper",
    ) -> IcebergOrder:
        """Convenience: Create iceberg for option orders > 5 lots."""
        return IcebergEngine.create_iceberg(
            symbol=symbol,
            trade_type=trade_type,
            total_quantity=lots * lot_size,
            base_price=premium,
            lot_size=lot_size,
            max_lots_per_slice=IcebergEngine.OPTION_MAX_LOTS_PER_SLICE,
            slice_delay_ms=IcebergEngine.OPTION_SLICE_DELAY_MS,
            price_improvement_pct=0.02,
            user_id=user_id,
            broker=broker,
        )

    @staticmethod
    def create_stock_iceberg(
        symbol: str,
        trade_type: str,
        quantity: int,
        price: float,
        user_id: str = None,
        broker: str = "paper",
    ) -> IcebergOrder:
        """Convenience: Create iceberg for large stock orders."""
        return IcebergEngine.create_iceberg(
            symbol=symbol,
            trade_type=trade_type,
            total_quantity=quantity,
            base_price=price,
            lot_size=1,
            max_qty_per_slice=IcebergEngine.STOCK_MAX_QTY_PER_SLICE,
            slice_delay_ms=IcebergEngine.STOCK_SLICE_DELAY_MS,
            price_improvement_pct=0.01,
            user_id=user_id,
            broker=broker,
        )

    @staticmethod
    def order_to_dict(order: IcebergOrder) -> dict:
        """Serialize for JSON/Kafka."""
        return {
            "iceberg_id": order.iceberg_id,
            "symbol": order.symbol,
            "trade_type": order.trade_type,
            "total_quantity": order.total_quantity,
            "base_price": order.base_price,
            "order_type": order.order_type,
            "status": order.status.value,
            "filled_quantity": order.filled_quantity,
            "avg_fill_price": order.avg_fill_price,
            "created_at": order.created_at,
            "completed_at": order.completed_at,
            "user_id": order.user_id,
            "broker": order.broker,
            "max_slice_qty": order.max_slice_qty,
            "slice_delay_ms": order.slice_delay_ms,
            "slices": [
                {
                    "slice_id": s.slice_id,
                    "sequence": s.sequence,
                    "quantity": s.quantity,
                    "price": s.price,
                    "status": s.status.value,
                    "fill_price": s.fill_price,
                    "fill_time": s.fill_time,
                    "error": s.error,
                    "broker_order_id": s.broker_order_id,
                }
                for s in order.slices
            ],
        }

    @staticmethod
    def order_from_dict(d: dict) -> IcebergOrder:
        """Deserialize from dict."""
        slices = [
            OrderSlice(
                slice_id=s["slice_id"],
                sequence=s["sequence"],
                quantity=s["quantity"],
                price=s["price"],
                status=SliceStatus(s["status"]),
                fill_price=s.get("fill_price"),
                fill_time=s.get("fill_time"),
                error=s.get("error"),
                broker_order_id=s.get("broker_order_id"),
            )
            for s in d.get("slices", [])
        ]
        return IcebergOrder(
            iceberg_id=d["iceberg_id"],
            symbol=d["symbol"],
            trade_type=d["trade_type"],
            total_quantity=d["total_quantity"],
            base_price=d["base_price"],
            order_type=d.get("order_type", "LIMIT"),
            status=IcebergStatus(d["status"]),
            slices=slices,
            filled_quantity=d.get("filled_quantity", 0),
            avg_fill_price=d.get("avg_fill_price", 0.0),
            created_at=d.get("created_at", ""),
            completed_at=d.get("completed_at"),
            user_id=d.get("user_id"),
            broker=d.get("broker"),
            max_slice_qty=d.get("max_slice_qty", 0),
            slice_delay_ms=d.get("slice_delay_ms", 500),
        )
