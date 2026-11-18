"""
Functional Tools for Decision-Making Resolution Agent.
Step 1: Isolated, deterministic functions returning structured data.
"""

from typing import Dict, Any
import uuid
from datetime import datetime
from database import db


def lookup_order(order_id: str) -> Dict[str, Any]:
    """
    Accesses the database to retrieve order details, customer identity,
    purchased item details, order status, and exchange eligibility status.

    Args:
        order_id: The unique identifier for the order (e.g., 'ORD-1001').

    Returns:
        Structured dictionary containing order details or an error indicator.
    """
    if not order_id or not isinstance(order_id, str):
        return {
            "status": "error",
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": "Order identifier must be a non-empty string."
            }
        }

    clean_order_id = order_id.strip().upper()
    order = db.get_order(clean_order_id)

    if not order:
        return {
            "status": "error",
            "error": {
                "code": "ORDER_NOT_FOUND",
                "message": f"Order with ID '{order_id}' was not found in the database. Please verify the order number."
            }
        }

    return {
        "status": "success",
        "data": {
            "order_id": order["order_id"],
            "customer_name": order["customer_name"],
            "customer_email": order["customer_email"],
            "item_id": order["item_id"],
            "item_name": order["item_name"],
            "quantity": order["quantity"],
            "price": order["price"],
            "total_amount": round(order["price"] * order["quantity"], 2),
            "order_status": order["order_status"],
            "is_exchange_eligible": order["is_exchange_eligible"],
            "ineligible_reason": order["ineligible_reason"],
            "payment_method": order["payment_method"]
        }
    }


def check_inventory(item_id: str) -> Dict[str, Any]:
    """
    Checks real-time warehouse inventory to determine stock count
    and availability for replacement units.

    Args:
        item_id: The unique identifier of the product item (e.g., 'ITEM-501').

    Returns:
        Structured dictionary containing inventory stock count and availability.
    """
    if not item_id or not isinstance(item_id, str):
        return {
            "status": "error",
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": "Item identifier must be a non-empty string."
            }
        }

    clean_item_id = item_id.strip().upper()
    item = db.get_inventory(clean_item_id)

    if not item:
        return {
            "status": "error",
            "error": {
                "code": "ITEM_NOT_FOUND",
                "message": f"Inventory item '{item_id}' not found in warehouse catalogue."
            }
        }

    return {
        "status": "success",
        "data": {
            "item_id": item["item_id"],
            "item_name": item["item_name"],
            "stock_count": item["stock_count"],
            "warehouse_location": item["warehouse_location"],
            "is_available": item["stock_count"] > 0
        }
    }


def process_refund(order_id: str, reason: str) -> Dict[str, Any]:
    """
    Issues a financial refund to the customer's original payment method
    for the designated order. Used when replacement units are unavailable
    or the order is ineligible for exchange.

    Args:
        order_id: The unique identifier of the order to be refunded.
        reason: The reason for issuing the refund (e.g., 'Replacement item out of stock').

    Returns:
        Structured dictionary confirming refund transaction details or error.
    """
    if not order_id or not isinstance(order_id, str):
        return {
            "status": "error",
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": "Order identifier must be a non-empty string."
            }
        }

    if not reason or not isinstance(reason, str):
        return {
            "status": "error",
            "error": {
                "code": "INVALID_ARGUMENT",
                "message": "A valid refund reason must be specified."
            }
        }

    clean_order_id = order_id.strip().upper()
    order = db.get_order(clean_order_id)

    if not order:
        return {
            "status": "error",
            "error": {
                "code": "ORDER_NOT_FOUND",
                "message": f"Cannot process refund: Order '{order_id}' was not found."
            }
        }

    if order.get("order_status") == "REFUNDED":
        return {
            "status": "error",
            "error": {
                "code": "ALREADY_REFUNDED",
                "message": f"Order '{clean_order_id}' has already been refunded under reference {order.get('refund_reference')}."
            }
        }

    refund_amount = round(order["price"] * order["quantity"], 2)
    refund_reference = f"REF-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now().isoformat()

    record = {
        "refund_reference": refund_reference,
        "order_id": clean_order_id,
        "customer_name": order["customer_name"],
        "customer_email": order["customer_email"],
        "refund_amount": refund_amount,
        "payment_method": order["payment_method"],
        "reason": reason,
        "timestamp": timestamp,
        "status": "COMPLETED"
    }

    db.add_refund(record)

    return {
        "status": "success",
        "data": {
            "refund_reference": refund_reference,
            "order_id": clean_order_id,
            "customer_name": order["customer_name"],
            "refund_amount": refund_amount,
            "payment_method": order["payment_method"],
            "reason": reason,
            "timestamp": timestamp,
            "message": f"Refund of ${refund_amount:.2f} successfully initiated to {order['payment_method']}."
        }
    }


def confirm_exchange(order_id: str, item_id: str, reason: str = "Defective/damaged replacement") -> Dict[str, Any]:
    """
    Confirms an item replacement exchange, reserves a replacement unit
    from warehouse stock, and logs the exchange transaction.

    Args:
        order_id: The unique identifier of the order to exchange.
        item_id: The item identifier of the replacement product.
        reason: Explanation for exchange request (e.g., 'Item arrived damaged').

    Returns:
        Structured dictionary confirming the exchange transaction details or error.
    """
    clean_order_id = order_id.strip().upper() if isinstance(order_id, str) else ""
    clean_item_id = item_id.strip().upper() if isinstance(item_id, str) else ""

    order = db.get_order(clean_order_id)
    if not order:
        return {
            "status": "error",
            "error": {
                "code": "ORDER_NOT_FOUND",
                "message": f"Cannot confirm exchange: Order '{order_id}' was not found."
            }
        }

    if not order.get("is_exchange_eligible", False):
        return {
            "status": "error",
            "error": {
                "code": "INELIGIBLE_FOR_EXCHANGE",
                "message": f"Order '{clean_order_id}' is not eligible for exchange: {order.get('ineligible_reason', 'Policy restriction')}."
            }
        }

    inventory = db.get_inventory(clean_item_id)
    if not inventory or inventory.get("stock_count", 0) <= 0:
        return {
            "status": "error",
            "error": {
                "code": "OUT_OF_STOCK",
                "message": f"Cannot exchange: Item '{clean_item_id}' is currently out of stock."
            }
        }

    exchange_reference = f"EXC-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now().isoformat()

    record = {
        "exchange_reference": exchange_reference,
        "order_id": clean_order_id,
        "item_id": clean_item_id,
        "item_name": inventory["item_name"],
        "customer_name": order["customer_name"],
        "customer_email": order["customer_email"],
        "reason": reason,
        "timestamp": timestamp,
        "warehouse_location": inventory["warehouse_location"],
        "status": "CONFIRMED"
    }

    db.add_exchange(record)

    return {
        "status": "success",
        "data": {
            "exchange_reference": exchange_reference,
            "order_id": clean_order_id,
            "item_id": clean_item_id,
            "item_name": inventory["item_name"],
            "customer_name": order["customer_name"],
            "warehouse_location": inventory["warehouse_location"],
            "timestamp": timestamp,
            "message": f"Exchange confirmed! Replacement {inventory['item_name']} reserved for shipment."
        }
    }


def send_customer_notification(recipient_email: str, subject: str, message: str) -> Dict[str, Any]:
    """
    Dispatches an official resolution confirmation email to the customer.

    Args:
        recipient_email: The customer's destination email address.
        subject: The subject line of the notification email.
        message: The detailed body text of the confirmation message.

    Returns:
        Structured dictionary confirming dispatch status and notification ID.
    """
    if not recipient_email or "@" not in str(recipient_email):
        return {
            "status": "error",
            "error": {
                "code": "INVALID_EMAIL",
                "message": f"Invalid recipient email address: '{recipient_email}'."
            }
        }

    if not message or not isinstance(message, str):
        return {
            "status": "error",
            "error": {
                "code": "EMPTY_MESSAGE",
                "message": "Notification message body cannot be empty."
            }
        }

    notification_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now().isoformat()

    record = {
        "notification_id": notification_id,
        "recipient_email": recipient_email.strip(),
        "subject": subject.strip() if subject else "Order Resolution Update",
        "message": message.strip(),
        "timestamp": timestamp,
        "delivery_status": "DELIVERED"
    }

    db.add_notification(record)

    return {
        "status": "success",
        "data": {
            "notification_id": notification_id,
            "recipient_email": recipient_email.strip(),
            "subject": record["subject"],
            "delivery_status": "DELIVERED",
            "timestamp": timestamp,
            "message": f"Confirmation notification successfully dispatched to {recipient_email.strip()}."
        }
    }
