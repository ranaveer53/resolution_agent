"""
Declarative Tool Contracts (Schemas) for Decision-Making Resolution Agent.
Step 2: Formal interface definitions for the LLM tool-calling layer.
"""

from typing import List, Dict, Any

LOOKUP_ORDER_SCHEMA: Dict[str, Any] = {
    "name": "lookup_order",
    "description": (
        "Retrieves comprehensive order records from the database using an order identifier. "
        "Provides customer identity (name, email), purchased item details (item_id, item_name, price), "
        "order status, payment method, and exchange policy eligibility status. "
        "Always call this tool first when a customer reports an issue with an order."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "The unique order identifier provided by the customer (e.g., 'ORD-1001')."
            }
        },
        "required": ["order_id"]
    }
}

CHECK_INVENTORY_SCHEMA: Dict[str, Any] = {
    "name": "check_inventory",
    "description": (
        "Inspects real-time warehouse inventory to retrieve current stock levels and item availability "
        "for a specific product item identifier. Call this tool after looking up an order to check if "
        "a replacement unit is physically in stock (stock_count > 0) before deciding between exchange or refund."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "item_id": {
                "type": "string",
                "description": "The unique product item identifier retrieved from the order record (e.g., 'ITEM-501')."
            }
        },
        "required": ["item_id"]
    }
}

PROCESS_REFUND_SCHEMA: Dict[str, Any] = {
    "name": "process_refund",
    "description": (
        "Issues an automated financial refund to the customer's original payment method and logs a refund reference. "
        "CRITICAL POLICY REQUIREMENT: Invoke this tool when a replacement item is NOT exchangeable—specifically "
        "when replacement stock is out of stock (stock_count is 0), when the item is unavailable, or when the order "
        "is explicitly ineligible for exchange under company policy. Do NOT invoke this if replacement stock is available."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "The unique identifier of the order to refund (e.g., 'ORD-1002')."
            },
            "reason": {
                "type": "string",
                "description": "Clear reason for issuing the refund (e.g., 'Replacement item out of stock in warehouse' or 'Order ineligible for exchange')."
            }
        },
        "required": ["order_id", "reason"]
    }
}

CONFIRM_EXCHANGE_SCHEMA: Dict[str, Any] = {
    "name": "confirm_exchange",
    "description": (
        "Confirms an item replacement exchange, reserves a replacement unit from warehouse stock, "
        "and generates an official exchange reference. "
        "CRITICAL POLICY REQUIREMENT: Invoke this tool ONLY when the order is exchange eligible AND "
        "warehouse inventory has confirmed replacement stock count is greater than 0."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "The unique identifier of the original order being exchanged (e.g., 'ORD-1001')."
            },
            "item_id": {
                "type": "string",
                "description": "The product item identifier for the replacement unit to reserve (e.g., 'ITEM-501')."
            },
            "reason": {
                "type": "string",
                "description": "Customer's reason for the exchange request (e.g., 'Damaged product upon delivery')."
            }
        },
        "required": ["order_id", "item_id"]
    }
}

SEND_CUSTOMER_NOTIFICATION_SCHEMA: Dict[str, Any] = {
    "name": "send_customer_notification",
    "description": (
        "Dispatches an official resolution confirmation email to the customer with full transaction details. "
        "MUST be invoked at the end of every resolution workflow (whether exchange confirmed or refund processed) "
        "to satisfy fulfillment requirements before concluding the session."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "recipient_email": {
                "type": "string",
                "description": "The customer's email address retrieved from the order record (e.g., 'alice.smith@example.com')."
            },
            "subject": {
                "type": "string",
                "description": "Subject line summarizing the resolution (e.g., 'Replacement Confirmed for Order ORD-1001' or 'Refund Initiated for Order ORD-1002')."
            },
            "message": {
                "type": "string",
                "description": "Comprehensive body of the notification containing reference numbers, resolution summary, and next steps for the customer."
            }
        },
        "required": ["recipient_email", "subject", "message"]
    }
}

ALL_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    LOOKUP_ORDER_SCHEMA,
    CHECK_INVENTORY_SCHEMA,
    PROCESS_REFUND_SCHEMA,
    CONFIRM_EXCHANGE_SCHEMA,
    SEND_CUSTOMER_NOTIFICATION_SCHEMA
]
