"""
Integration tests for shared/iceberg_order.py — Iceberg Order Engine.
Tests order splitting, execution, serialization, and edge cases.
"""
import asyncio
import pytest
from shared.iceberg_order import (
    IcebergEngine,
    IcebergOrder,
    IcebergStatus,
    OrderSlice,
    SliceStatus,
)


class TestIcebergThresholds:
    """Test should_iceberg_* logic."""

    def test_option_below_threshold(self):
        assert IcebergEngine.should_iceberg_option(3) is False
        assert IcebergEngine.should_iceberg_option(5) is False

    def test_option_above_threshold(self):
        assert IcebergEngine.should_iceberg_option(6) is True
        assert IcebergEngine.should_iceberg_option(10) is True

    def test_stock_below_threshold(self):
        assert IcebergEngine.should_iceberg_stock(200) is False
        assert IcebergEngine.should_iceberg_stock(500) is False

    def test_stock_above_threshold(self):
        assert IcebergEngine.should_iceberg_stock(501) is True
        assert IcebergEngine.should_iceberg_stock(1500) is True


class TestIcebergCreation:
    """Test create_iceberg and convenience methods."""

    def test_option_iceberg_split(self):
        order = IcebergEngine.create_option_iceberg(
            symbol="NIFTY24FEB23000CE",
            trade_type="BUY",
            lots=10,
            premium=150.0,
            lot_size=65,
        )
        assert order.total_quantity == 650
        assert order.symbol == "NIFTY24FEB23000CE"
        assert order.trade_type == "BUY"
        assert order.status == IcebergStatus.PENDING
        # Max 2 lots per slice (130 qty), so 5 slices
        assert len(order.slices) == 5
        for s in order.slices:
            assert s.quantity == 130
            assert s.status == SliceStatus.PENDING

    def test_stock_iceberg_split(self):
        order = IcebergEngine.create_stock_iceberg(
            symbol="RELIANCE",
            trade_type="BUY",
            quantity=1500,
            price=2500.0,
        )
        assert order.total_quantity == 1500
        # Max 500 per slice → 3 slices
        assert len(order.slices) == 3
        total_qty = sum(s.quantity for s in order.slices)
        assert total_qty == 1500

    def test_uneven_split(self):
        """Last slice gets remaining qty."""
        order = IcebergEngine.create_stock_iceberg(
            symbol="TCS",
            trade_type="BUY",
            quantity=700,
            price=3300.0,
        )
        assert len(order.slices) == 2
        assert order.slices[0].quantity == 500
        assert order.slices[1].quantity == 200

    def test_price_improvement_buy(self):
        """BUY: later slices should have lower prices (aggressive improvement)."""
        order = IcebergEngine.create_stock_iceberg(
            symbol="INFY",
            trade_type="BUY",
            quantity=1500,
            price=1500.0,
        )
        prices = [s.price for s in order.slices]
        # Each successive slice should have equal or lower price
        for i in range(1, len(prices)):
            assert prices[i] <= prices[i - 1]

    def test_price_improvement_sell(self):
        """SELL: later slices should have higher prices."""
        order = IcebergEngine.create_stock_iceberg(
            symbol="INFY",
            trade_type="SELL",
            quantity=1500,
            price=1500.0,
        )
        prices = [s.price for s in order.slices]
        for i in range(1, len(prices)):
            assert prices[i] >= prices[i - 1]

    def test_iceberg_id_format(self):
        order = IcebergEngine.create_option_iceberg(
            "NIFTY", "BUY", lots=8, premium=100.0,
        )
        assert order.iceberg_id.startswith("ICE-")
        assert order.created_at != ""

    def test_single_slice_when_exactly_at_max(self):
        """If qty <= max per slice, only one slice."""
        order = IcebergEngine.create_stock_iceberg(
            "HDFC", "BUY", quantity=500, price=1600.0,
        )
        assert len(order.slices) == 1
        assert order.slices[0].quantity == 500


class TestIcebergExecution:
    """Test async execution with mock place_order_fn."""

    @pytest.fixture
    def success_order_fn(self):
        """Mock that always fills successfully."""
        async def place_order(symbol, trade_type, quantity, price, broker, user_id, slice_id):
            return {
                "status": "filled",
                "fill_price": price,
                "order_id": f"ORD-{slice_id}",
            }
        return place_order

    @pytest.fixture
    def partial_fail_fn(self):
        """Mock that fails on 2nd slice."""
        call_count = {"n": 0}
        async def place_order(symbol, trade_type, quantity, price, broker, user_id, slice_id):
            call_count["n"] += 1
            if call_count["n"] == 2:
                return {"status": "failed", "error": "Insufficient margin"}
            return {
                "status": "filled",
                "fill_price": price,
                "order_id": f"ORD-{slice_id}",
            }
        return place_order

    @pytest.mark.asyncio
    async def test_full_execution_success(self, success_order_fn):
        order = IcebergEngine.create_stock_iceberg(
            "RELIANCE", "BUY", quantity=1000, price=2500.0,
        )
        result = await IcebergEngine.execute(order, success_order_fn)
        assert result.status == IcebergStatus.FILLED
        assert result.filled_quantity == 1000
        assert result.avg_fill_price > 0
        assert result.completed_at is not None
        for s in result.slices:
            assert s.status == SliceStatus.FILLED

    @pytest.mark.asyncio
    async def test_partial_fill(self, partial_fail_fn):
        order = IcebergEngine.create_stock_iceberg(
            "TCS", "BUY", quantity=1500, price=3300.0,
        )
        result = await IcebergEngine.execute(order, partial_fail_fn)
        assert result.status == IcebergStatus.PARTIALLY_FILLED
        assert result.filled_quantity == 1000  # 2 of 3 slices filled
        failed_slices = [s for s in result.slices if s.status == SliceStatus.FAILED]
        assert len(failed_slices) == 1

    @pytest.mark.asyncio
    async def test_cancel_check(self, success_order_fn):
        order = IcebergEngine.create_stock_iceberg(
            "INFY", "BUY", quantity=1500, price=1500.0,
        )
        # cancel_check_fn is called at the start of each slice iteration.
        # Return False for the first slice (let it fill), True for slice 2+.
        fill_count = {"n": 0}
        def cancel_after_first():
            fill_count["n"] += 1
            return fill_count["n"] > 1  # Allow 1st iteration, cancel from 2nd

        result = await IcebergEngine.execute(
            order, success_order_fn, cancel_check_fn=cancel_after_first,
        )
        # After 1st slice fills, cancel_check returns True on 2nd → cancels remaining
        filled = [s for s in result.slices if s.status == SliceStatus.FILLED]
        cancelled = [s for s in result.slices if s.status == SliceStatus.CANCELLED]
        assert len(filled) >= 1
        assert len(cancelled) >= 1
        assert result.status in (IcebergStatus.CANCELLED, IcebergStatus.PARTIALLY_FILLED)

    @pytest.mark.asyncio
    async def test_avg_fill_price_calculation(self, success_order_fn):
        order = IcebergEngine.create_stock_iceberg(
            "HDFC", "BUY", quantity=1000, price=1600.0,
        )
        result = await IcebergEngine.execute(order, success_order_fn)
        # All slices at same price → avg should be close to base
        assert abs(result.avg_fill_price - 1600.0) < 1.0


class TestIcebergSerialization:
    """Test order serialization/deserialization."""

    def test_order_roundtrip(self):
        order = IcebergEngine.create_option_iceberg(
            "NIFTY24FEB23000CE", "BUY", lots=8, premium=200.0,
        )
        d = IcebergEngine.order_to_dict(order)
        restored = IcebergEngine.order_from_dict(d)
        assert restored.iceberg_id == order.iceberg_id
        assert restored.total_quantity == order.total_quantity
        assert len(restored.slices) == len(order.slices)
        assert restored.status == order.status

    @pytest.mark.asyncio
    async def test_filled_order_roundtrip(self):
        async def mock_fill(symbol, trade_type, quantity, price, broker, user_id, slice_id):
            return {"status": "filled", "fill_price": price, "order_id": "X1"}

        order = IcebergEngine.create_stock_iceberg("A", "BUY", 1000, 100.0)
        await IcebergEngine.execute(order, mock_fill)

        d = IcebergEngine.order_to_dict(order)
        restored = IcebergEngine.order_from_dict(d)
        assert restored.status == IcebergStatus.FILLED
        assert restored.filled_quantity == 1000
        for s in restored.slices:
            assert s.status == SliceStatus.FILLED
