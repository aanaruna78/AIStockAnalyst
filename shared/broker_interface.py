"""
Broker API Interface — Unified Broker Abstraction
===================================================
Provides a unified interface for placing orders across:
  - Paper Trading (default)
  - Dhan API (https://dhanhq.co)
  - AngelOne / Angel Broking (SmartAPI)

Each broker implements the BaseBroker interface.
The BrokerRouter selects the correct broker based on user config.
"""

import asyncio
import httpx
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Dict
from zoneinfo import ZoneInfo

logger = logging.getLogger("broker")
IST = ZoneInfo("Asia/Kolkata")


# ──────────────────────────────────────────────────────────────────
# Broker Enum
# ──────────────────────────────────────────────────────────────────
class BrokerType(str, Enum):
    PAPER = "paper"
    DHAN = "dhan"
    ANGELONE = "angelone"


# ──────────────────────────────────────────────────────────────────
# Order Types
# ──────────────────────────────────────────────────────────────────
class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"


class ProductType(str, Enum):
    INTRADAY = "INTRADAY"    # MIS
    DELIVERY = "DELIVERY"    # CNC
    MARGIN = "MARGIN"        # NRML (F&O)


class ExchangeType(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NFO = "NFO"              # NSE F&O
    MCX = "MCX"


# ──────────────────────────────────────────────────────────────────
# Unified Order Result
# ──────────────────────────────────────────────────────────────────
class OrderResult:
    def __init__(
        self,
        status: str,          # "filled", "pending", "failed", "rejected"
        order_id: str = "",
        fill_price: float = 0.0,
        fill_quantity: int = 0,
        error: str = "",
        broker: str = "paper",
        raw_response: dict = None,
    ):
        self.status = status
        self.order_id = order_id
        self.fill_price = fill_price
        self.fill_quantity = fill_quantity
        self.error = error
        self.broker = broker
        self.raw_response = raw_response or {}

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "order_id": self.order_id,
            "fill_price": self.fill_price,
            "fill_quantity": self.fill_quantity,
            "error": self.error,
            "broker": self.broker,
        }


# ──────────────────────────────────────────────────────────────────
# Base Broker Interface
# ──────────────────────────────────────────────────────────────────
class BaseBroker(ABC):
    """Abstract base class for all broker integrations."""

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float,
        order_type: OrderType = OrderType.LIMIT,
        product: ProductType = ProductType.INTRADAY,
        exchange: ExchangeType = ExchangeType.NSE,
        trigger_price: float = 0.0,
        tag: str = "",
    ) -> OrderResult:
        pass

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        quantity: int = 0,
        price: float = 0.0,
        trigger_price: float = 0.0,
        order_type: OrderType = None,
    ) -> OrderResult:
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> OrderResult:
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderResult:
        pass

    @abstractmethod
    async def get_positions(self) -> list:
        pass

    @abstractmethod
    async def update_stop_loss(
        self,
        order_id: str,
        new_sl: float,
    ) -> OrderResult:
        """Update trailing stop loss on an existing order."""
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        pass


# ──────────────────────────────────────────────────────────────────
# Paper Trading Broker
# ──────────────────────────────────────────────────────────────────
class PaperBroker(BaseBroker):
    """Paper trading — simulates order fills with slippage."""

    def __init__(self):
        import numpy as np
        self.np = np
        self._orders: Dict[str, dict] = {}

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float,
        order_type: OrderType = OrderType.LIMIT,
        product: ProductType = ProductType.INTRADAY,
        exchange: ExchangeType = ExchangeType.NSE,
        trigger_price: float = 0.0,
        tag: str = "",
    ) -> OrderResult:
        # Simulate slippage (0.01% - 0.03%)
        slippage = self.np.random.uniform(0.0001, 0.0003)
        if side == OrderSide.BUY:
            fill_price = round(price * (1 + slippage), 2)
        else:
            fill_price = round(price * (1 - slippage), 2)

        order_id = f"PAPER-{datetime.now(IST).strftime('%H%M%S')}-{self.np.random.randint(1000, 9999)}"

        # Simulate latency
        await asyncio.sleep(self.np.random.uniform(0.05, 0.15))

        self._orders[order_id] = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side.value,
            "quantity": quantity,
            "price": price,
            "fill_price": fill_price,
            "status": "filled",
            "time": datetime.now(IST).isoformat(),
        }

        return OrderResult(
            status="filled",
            order_id=order_id,
            fill_price=fill_price,
            fill_quantity=quantity,
            broker="paper",
        )

    async def modify_order(self, order_id: str, **kwargs) -> OrderResult:
        if order_id in self._orders:
            self._orders[order_id].update(kwargs)
            return OrderResult(status="modified", order_id=order_id, broker="paper")
        return OrderResult(status="failed", error="Order not found", broker="paper")

    async def cancel_order(self, order_id: str) -> OrderResult:
        if order_id in self._orders:
            self._orders[order_id]["status"] = "cancelled"
            return OrderResult(status="cancelled", order_id=order_id, broker="paper")
        return OrderResult(status="failed", error="Order not found", broker="paper")

    async def get_order_status(self, order_id: str) -> OrderResult:
        order = self._orders.get(order_id)
        if order:
            return OrderResult(
                status=order["status"],
                order_id=order_id,
                fill_price=order.get("fill_price", 0),
                fill_quantity=order.get("quantity", 0),
                broker="paper",
            )
        return OrderResult(status="not_found", order_id=order_id, broker="paper")

    async def get_positions(self) -> list:
        return [v for v in self._orders.values() if v["status"] == "filled"]

    async def update_stop_loss(self, order_id: str, new_sl: float) -> OrderResult:
        if order_id in self._orders:
            self._orders[order_id]["stop_loss"] = new_sl
            return OrderResult(status="modified", order_id=order_id, broker="paper")
        return OrderResult(status="failed", error="Order not found", broker="paper")

    async def is_connected(self) -> bool:
        return True


# ──────────────────────────────────────────────────────────────────
# Dhan Broker
# ──────────────────────────────────────────────────────────────────
class DhanBroker(BaseBroker):
    """
    Dhan API Integration.
    Docs: https://dhanhq.co/docs/v2/
    
    Required env/config:
      - DHAN_CLIENT_ID
      - DHAN_ACCESS_TOKEN
    """

    BASE_URL = "https://api.dhan.co/v2"

    # Dhan exchange segment mapping
    EXCHANGE_MAP = {
        ExchangeType.NSE: "NSE_EQ",
        ExchangeType.BSE: "BSE_EQ",
        ExchangeType.NFO: "NSE_FNO",
        ExchangeType.MCX: "MCX_COMM",
    }

    PRODUCT_MAP = {
        ProductType.INTRADAY: "INTRADAY",
        ProductType.DELIVERY: "CNC",
        ProductType.MARGIN: "MARGIN",
    }

    ORDER_TYPE_MAP = {
        OrderType.MARKET: "MARKET",
        OrderType.LIMIT: "LIMIT",
        OrderType.SL: "STOP_LOSS",
        OrderType.SL_M: "STOP_LOSS_MARKET",
    }

    def __init__(self, client_id: str = "", access_token: str = ""):
        self.client_id = client_id or os.getenv("DHAN_CLIENT_ID", "")
        self.access_token = access_token or os.getenv("DHAN_ACCESS_TOKEN", "")
        self._headers = {
            "Content-Type": "application/json",
            "access-token": self.access_token,
        }

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float,
        order_type: OrderType = OrderType.LIMIT,
        product: ProductType = ProductType.INTRADAY,
        exchange: ExchangeType = ExchangeType.NSE,
        trigger_price: float = 0.0,
        tag: str = "",
    ) -> OrderResult:
        payload = {
            "dhanClientId": self.client_id,
            "transactionType": side.value,
            "exchangeSegment": self.EXCHANGE_MAP.get(exchange, "NSE_EQ"),
            "productType": self.PRODUCT_MAP.get(product, "INTRADAY"),
            "orderType": self.ORDER_TYPE_MAP.get(order_type, "LIMIT"),
            "validity": "DAY",
            "tradingSymbol": symbol,
            "quantity": quantity,
            "price": price,
            "triggerPrice": trigger_price,
            "disclosedQuantity": 0,
            "afterMarketOrder": False,
            "correlationId": tag or f"SF-{datetime.now(IST).strftime('%H%M%S')}",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/orders",
                    headers=self._headers,
                    json=payload,
                )
                data = resp.json()

                if resp.status_code == 200 and data.get("orderId"):
                    return OrderResult(
                        status="pending",  # Dhan returns pending; poll for fill
                        order_id=data["orderId"],
                        fill_price=price,
                        fill_quantity=quantity,
                        broker="dhan",
                        raw_response=data,
                    )
                else:
                    return OrderResult(
                        status="failed",
                        error=data.get("remarks", str(data)),
                        broker="dhan",
                        raw_response=data,
                    )
        except Exception as e:
            return OrderResult(status="failed", error=str(e), broker="dhan")

    async def modify_order(
        self,
        order_id: str,
        quantity: int = 0,
        price: float = 0.0,
        trigger_price: float = 0.0,
        order_type: OrderType = None,
    ) -> OrderResult:
        payload = {
            "dhanClientId": self.client_id,
            "orderId": order_id,
        }
        if quantity > 0:
            payload["quantity"] = quantity
        if price > 0:
            payload["price"] = price
        if trigger_price > 0:
            payload["triggerPrice"] = trigger_price
        if order_type:
            payload["orderType"] = self.ORDER_TYPE_MAP.get(order_type, "LIMIT")

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.put(
                    f"{self.BASE_URL}/orders/{order_id}",
                    headers=self._headers,
                    json=payload,
                )
                data = resp.json()
                if resp.status_code == 200:
                    return OrderResult(status="modified", order_id=order_id, broker="dhan", raw_response=data)
                return OrderResult(status="failed", error=data.get("remarks", str(data)), broker="dhan")
        except Exception as e:
            return OrderResult(status="failed", error=str(e), broker="dhan")

    async def cancel_order(self, order_id: str) -> OrderResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.delete(
                    f"{self.BASE_URL}/orders/{order_id}",
                    headers=self._headers,
                )
                if resp.status_code == 200:
                    return OrderResult(status="cancelled", order_id=order_id, broker="dhan")
                data = resp.json()
                return OrderResult(status="failed", error=data.get("remarks", ""), broker="dhan")
        except Exception as e:
            return OrderResult(status="failed", error=str(e), broker="dhan")

    async def get_order_status(self, order_id: str) -> OrderResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/orders/{order_id}",
                    headers=self._headers,
                )
                data = resp.json()
                status = data.get("orderStatus", "UNKNOWN").lower()
                fill_price = data.get("price", 0)
                fill_qty = data.get("filledQty", 0)

                mapped_status = "filled" if status == "traded" else status
                return OrderResult(
                    status=mapped_status,
                    order_id=order_id,
                    fill_price=fill_price,
                    fill_quantity=fill_qty,
                    broker="dhan",
                    raw_response=data,
                )
        except Exception as e:
            return OrderResult(status="failed", error=str(e), broker="dhan")

    async def get_positions(self) -> list:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/positions",
                    headers=self._headers,
                )
                return resp.json() if resp.status_code == 200 else []
        except Exception:
            return []

    async def update_stop_loss(self, order_id: str, new_sl: float) -> OrderResult:
        """Modify the SL order with new trigger price."""
        return await self.modify_order(
            order_id=order_id,
            trigger_price=new_sl,
            price=new_sl,
            order_type=OrderType.SL,
        )

    async def is_connected(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/funds",
                    headers=self._headers,
                )
                return resp.status_code == 200
        except Exception:
            return False


# ──────────────────────────────────────────────────────────────────
# AngelOne (SmartAPI) Broker
# ──────────────────────────────────────────────────────────────────
class AngelOneBroker(BaseBroker):
    """
    AngelOne SmartAPI Integration.
    Docs: https://smartapi.angelone.in/docs
    
    Required config:
      - ANGELONE_API_KEY
      - ANGELONE_CLIENT_ID
      - ANGELONE_PASSWORD
      - ANGELONE_TOTP_SECRET (for auto-login)
    """

    BASE_URL = "https://apiconnect.angelone.in"

    EXCHANGE_MAP = {
        ExchangeType.NSE: "NSE",
        ExchangeType.BSE: "BSE",
        ExchangeType.NFO: "NFO",
        ExchangeType.MCX: "MCX",
    }

    PRODUCT_MAP = {
        ProductType.INTRADAY: "INTRADAY",
        ProductType.DELIVERY: "DELIVERY",
        ProductType.MARGIN: "CARRYFORWARD",
    }

    ORDER_TYPE_MAP = {
        OrderType.MARKET: "MARKET",
        OrderType.LIMIT: "LIMIT",
        OrderType.SL: "STOPLOSS_LIMIT",
        OrderType.SL_M: "STOPLOSS_MARKET",
    }

    def __init__(
        self,
        api_key: str = "",
        client_id: str = "",
        jwt_token: str = "",
    ):
        self.api_key = api_key or os.getenv("ANGELONE_API_KEY", "")
        self.client_id = client_id or os.getenv("ANGELONE_CLIENT_ID", "")
        self.jwt_token = jwt_token or os.getenv("ANGELONE_JWT_TOKEN", "")
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.api_key,
            "Authorization": f"Bearer {self.jwt_token}",
        }

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float,
        order_type: OrderType = OrderType.LIMIT,
        product: ProductType = ProductType.INTRADAY,
        exchange: ExchangeType = ExchangeType.NSE,
        trigger_price: float = 0.0,
        tag: str = "",
    ) -> OrderResult:
        payload = {
            "variety": "NORMAL",
            "tradingsymbol": symbol,
            "symboltoken": "",  # Must be resolved from symbol master
            "transactiontype": side.value,
            "exchange": self.EXCHANGE_MAP.get(exchange, "NSE"),
            "ordertype": self.ORDER_TYPE_MAP.get(order_type, "LIMIT"),
            "producttype": self.PRODUCT_MAP.get(product, "INTRADAY"),
            "duration": "DAY",
            "price": str(price),
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(quantity),
            "triggerprice": str(trigger_price) if trigger_price else "0",
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/placeOrder",
                    headers=self._headers,
                    json=payload,
                )
                data = resp.json()

                if data.get("status") and data.get("data", {}).get("orderid"):
                    return OrderResult(
                        status="pending",
                        order_id=data["data"]["orderid"],
                        fill_price=price,
                        fill_quantity=quantity,
                        broker="angelone",
                        raw_response=data,
                    )
                else:
                    return OrderResult(
                        status="failed",
                        error=data.get("message", str(data)),
                        broker="angelone",
                        raw_response=data,
                    )
        except Exception as e:
            return OrderResult(status="failed", error=str(e), broker="angelone")

    async def modify_order(
        self,
        order_id: str,
        quantity: int = 0,
        price: float = 0.0,
        trigger_price: float = 0.0,
        order_type: OrderType = None,
    ) -> OrderResult:
        payload = {
            "variety": "NORMAL",
            "orderid": order_id,
        }
        if quantity > 0:
            payload["quantity"] = str(quantity)
        if price > 0:
            payload["price"] = str(price)
        if trigger_price > 0:
            payload["triggerprice"] = str(trigger_price)
        if order_type:
            payload["ordertype"] = self.ORDER_TYPE_MAP.get(order_type, "LIMIT")

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/modifyOrder",
                    headers=self._headers,
                    json=payload,
                )
                data = resp.json()
                if data.get("status"):
                    return OrderResult(status="modified", order_id=order_id, broker="angelone")
                return OrderResult(status="failed", error=data.get("message", ""), broker="angelone")
        except Exception as e:
            return OrderResult(status="failed", error=str(e), broker="angelone")

    async def cancel_order(self, order_id: str) -> OrderResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/cancelOrder",
                    headers=self._headers,
                    json={"variety": "NORMAL", "orderid": order_id},
                )
                data = resp.json()
                if data.get("status"):
                    return OrderResult(status="cancelled", order_id=order_id, broker="angelone")
                return OrderResult(status="failed", error=data.get("message", ""), broker="angelone")
        except Exception as e:
            return OrderResult(status="failed", error=str(e), broker="angelone")

    async def get_order_status(self, order_id: str) -> OrderResult:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/details/{order_id}",
                    headers=self._headers,
                )
                data = resp.json()
                order_data = data.get("data", {})
                status = order_data.get("orderstatus", "").lower()
                mapped = "filled" if status == "complete" else status
                return OrderResult(
                    status=mapped,
                    order_id=order_id,
                    fill_price=float(order_data.get("averageprice", 0)),
                    fill_quantity=int(order_data.get("filledshares", 0)),
                    broker="angelone",
                    raw_response=data,
                )
        except Exception as e:
            return OrderResult(status="failed", error=str(e), broker="angelone")

    async def get_positions(self) -> list:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/rest/secure/angelbroking/order/v1/getPosition",
                    headers=self._headers,
                )
                data = resp.json()
                return data.get("data", []) if data.get("status") else []
        except Exception:
            return []

    async def update_stop_loss(self, order_id: str, new_sl: float) -> OrderResult:
        return await self.modify_order(
            order_id=order_id,
            trigger_price=new_sl,
            price=new_sl,
            order_type=OrderType.SL,
        )

    async def is_connected(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/rest/secure/angelbroking/user/v1/getProfile",
                    headers=self._headers,
                )
                return resp.status_code == 200
        except Exception:
            return False


# ──────────────────────────────────────────────────────────────────
# Broker Router — Selects broker based on user config
# ──────────────────────────────────────────────────────────────────
class BrokerRouter:
    """
    Routes order placement to the correct broker based on user config.
    Falls back to paper trading if no broker is configured.
    """

    _instances: Dict[str, BaseBroker] = {}

    @classmethod
    def get_broker(cls, broker_type: str, config: dict = None) -> BaseBroker:
        """Get or create a broker instance."""
        config = config or {}

        if broker_type == BrokerType.DHAN:
            key = f"dhan_{config.get('client_id', '')}"
            if key not in cls._instances:
                cls._instances[key] = DhanBroker(
                    client_id=config.get("client_id", ""),
                    access_token=config.get("access_token", ""),
                )
            return cls._instances[key]

        elif broker_type == BrokerType.ANGELONE:
            key = f"angelone_{config.get('client_id', '')}"
            if key not in cls._instances:
                cls._instances[key] = AngelOneBroker(
                    api_key=config.get("api_key", ""),
                    client_id=config.get("client_id", ""),
                    jwt_token=config.get("jwt_token", ""),
                )
            return cls._instances[key]

        # Default: Paper trading
        if "paper" not in cls._instances:
            cls._instances["paper"] = PaperBroker()
        return cls._instances["paper"]

    @classmethod
    def resolve_broker_for_user(cls, user_config: dict) -> BaseBroker:
        """
        Given a user's broker configuration, return the appropriate broker.
        
        user_config example:
        {
            "broker": "dhan",
            "dhan_client_id": "...",
            "dhan_access_token": "...",
        }
        or
        {
            "broker": "angelone",
            "angelone_api_key": "...",
            "angelone_client_id": "...",
            "angelone_jwt_token": "...",
        }
        """
        broker_type = user_config.get("broker", "paper")

        if broker_type == "dhan" and user_config.get("dhan_client_id"):
            return cls.get_broker(BrokerType.DHAN, {
                "client_id": user_config["dhan_client_id"],
                "access_token": user_config.get("dhan_access_token", ""),
            })

        if broker_type == "angelone" and user_config.get("angelone_client_id"):
            return cls.get_broker(BrokerType.ANGELONE, {
                "api_key": user_config.get("angelone_api_key", ""),
                "client_id": user_config["angelone_client_id"],
                "jwt_token": user_config.get("angelone_jwt_token", ""),
            })

        # No broker configured → paper trade
        return cls.get_broker(BrokerType.PAPER)
