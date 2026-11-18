"""
Mock Database Module for Decision-Making Resolution Agent.
Provides simulated storage and stateful tracking for Orders, Inventory,
Refunds, Exchanges, and Customer Notifications.
"""

from typing import Dict, Any, Optional, List
import copy
from datetime import datetime


INITIAL_ORDERS: Dict[str, Dict[str, Any]] = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_name": "Alice Smith",
        "customer_email": "alice.smith@example.com",
        "item_id": "ITEM-501",
        "item_name": "Aura Pro Wireless Headphones",
        "quantity": 1,
        "price": 199.99,
        "order_status": "DELIVERED",
        "is_exchange_eligible": True,
        "ineligible_reason": None,
        "payment_method": "Visa ending in 4242"
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_name": "Bob Jones",
        "customer_email": "bob.jones@example.com",
        "item_id": "ITEM-502",
        "item_name": "UltraView 27-inch 4K Monitor",
        "quantity": 1,
        "price": 349.99,
        "order_status": "DELIVERED",
        "is_exchange_eligible": True,
        "ineligible_reason": None,
        "payment_method": "Mastercard ending in 8812"
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_name": "Charlie Brown",
        "customer_email": "charlie.brown@example.com",
        "item_id": "ITEM-503",
        "item_name": "ProClick Mechanical Keyboard",
        "quantity": 1,
        "price": 89.99,
        "order_status": "DELIVERED",
        "is_exchange_eligible": False,
        "ineligible_reason": "Order exceeded 30-day exchange window policy.",
        "payment_method": "PayPal (charlie@example.com)"
    },
    "ORD-1004": {
        "order_id": "ORD-1004",
        "customer_name": "Diana Prince",
        "customer_email": "diana.prince@example.com",
        "item_id": "ITEM-504",
        "item_name": "Apex Ergonomic Mouse",
        "quantity": 1,
        "price": 49.99,
        "order_status": "DELIVERED",
        "is_exchange_eligible": True,
        "ineligible_reason": None,
        "payment_method": "Amex ending in 1004"
    }
}

INITIAL_INVENTORY: Dict[str, Dict[str, Any]] = {
    "ITEM-501": {
        "item_id": "ITEM-501",
        "item_name": "Aura Pro Wireless Headphones",
        "stock_count": 8,
        "warehouse_location": "WH-East-01",
        "is_available": True
    },
    "ITEM-502": {
        "item_id": "ITEM-502",
        "item_name": "UltraView 27-inch 4K Monitor",
        "stock_count": 0,
        "warehouse_location": "WH-West-02",
        "is_available": False
    },
    "ITEM-503": {
        "item_id": "ITEM-503",
        "item_name": "ProClick Mechanical Keyboard",
        "stock_count": 15,
        "warehouse_location": "WH-Central-01",
        "is_available": True
    },
    "ITEM-504": {
        "item_id": "ITEM-504",
        "item_name": "Apex Ergonomic Mouse",
        "stock_count": 0,
        "warehouse_location": "WH-East-02",
        "is_available": False
    }
}


class Database:
    """In-memory database for orders, inventory, refunds, exchanges, and notifications."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset the database to initial seed data."""
        self.orders: Dict[str, Dict[str, Any]] = copy.deepcopy(INITIAL_ORDERS)
        self.inventory: Dict[str, Dict[str, Any]] = copy.deepcopy(INITIAL_INVENTORY)
        self.refunds: List[Dict[str, Any]] = []
        self.exchanges: List[Dict[str, Any]] = []
        self.notifications: List[Dict[str, Any]] = []

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        return self.orders.get(order_id)

    def get_inventory(self, item_id: str) -> Optional[Dict[str, Any]]:
        return self.inventory.get(item_id)

    def add_refund(self, record: Dict[str, Any]) -> None:
        self.refunds.append(record)
        # Update order status in orders
        order_id = record.get("order_id")
        if order_id and order_id in self.orders:
            self.orders[order_id]["order_status"] = "REFUNDED"
            self.orders[order_id]["refund_reference"] = record.get("refund_reference")

    def add_exchange(self, record: Dict[str, Any]) -> None:
        self.exchanges.append(record)
        order_id = record.get("order_id")
        item_id = record.get("item_id")
        if order_id and order_id in self.orders:
            self.orders[order_id]["order_status"] = "EXCHANGED"
            self.orders[order_id]["exchange_reference"] = record.get("exchange_reference")
        # Deduct stock
        if item_id and item_id in self.inventory:
            current_stock = self.inventory[item_id]["stock_count"]
            if current_stock > 0:
                self.inventory[item_id]["stock_count"] = current_stock - 1
                self.inventory[item_id]["is_available"] = (current_stock - 1) > 0

    def add_notification(self, notification: Dict[str, Any]) -> None:
        self.notifications.append(notification)


# Global singleton database instance
db = Database()
