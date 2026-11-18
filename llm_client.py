"""
LLM Client Interface and Model Implementations for Resolution Agent.
Provides:
1. BaseLLMClient interface.
2. MockResolutionLLM: Deterministic reasoning engine that accurately reproduces
   multi-step ReAct thought-and-tool calling without requiring external API keys.
3. Live API clients (OpenAI / Gemini) when API keys are provided.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import json
import re
import os
import uuid


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ModelResponse:
    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    thought: Optional[str] = None


class BaseLLMClient:
    """Abstract interface for LLM client providers."""

    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> ModelResponse:
        raise NotImplementedError


class MockResolutionLLM(BaseLLMClient):
    """
    Simulated Language Model that exhibits autonomous ReAct reasoning:
    - Analyzes conversation state and prior tool execution results.
    - Decides next actions conditionally:
      * Order Lookup -> Inventory Inspection -> Branch (Stock > 0 -> Exchange; Stock == 0 -> Refund) -> Notification -> Final Polish
      * Handles Order Not Found with graceful, polite recovery.
      * Handles Ineligible orders with automated refund or policy guidance.
    """

    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> ModelResponse:
        # Extract user input
        user_message = ""
        for m in messages:
            if m.get("role") == "user":
                user_message = m.get("content", "")

        # Collect state from past tool executions in conversation history
        lookup_result: Optional[Dict[str, Any]] = None
        inventory_result: Optional[Dict[str, Any]] = None
        refund_result: Optional[Dict[str, Any]] = None
        exchange_result: Optional[Dict[str, Any]] = None
        notification_result: Optional[Dict[str, Any]] = None
        last_tool_error: Optional[Dict[str, Any]] = None

        executed_tools = []
        for m in messages:
            if m.get("role") == "tool":
                tool_name = m.get("name")
                executed_tools.append(tool_name)
                content = m.get("content")
                if isinstance(content, str):
                    try:
                        parsed = json.loads(content)
                    except Exception:
                        parsed = {"status": "raw", "data": content}
                else:
                    parsed = content

                if parsed.get("status") == "error":
                    last_tool_error = parsed.get("error", {})

                if tool_name == "lookup_order":
                    lookup_result = parsed
                elif tool_name == "check_inventory":
                    inventory_result = parsed
                elif tool_name == "process_refund":
                    refund_result = parsed
                elif tool_name == "confirm_exchange":
                    exchange_result = parsed
                elif tool_name == "send_customer_notification":
                    notification_result = parsed

        # Step 1: Detect if order has been looked up
        if not lookup_result:
            # Extract order ID from user message using regex
            order_match = re.search(r"\bORD-[0-9]{4,6}\b", user_message, re.IGNORECASE)
            order_id = order_match.group(0).upper() if order_match else None

            if not order_id:
                # If no order ID could be extracted, ask the user politely
                return ModelResponse(
                    thought="I need an order identifier to look up the purchase details and policy eligibility.",
                    content="Hello! I would be glad to help resolve the issue with your item. Could you please provide your Order ID (for example, 'ORD-1001') so I can access your order details?"
                )

            return ModelResponse(
                thought=f"Customer reported an issue regarding order {order_id}. I will autonomously look up the order details and policy eligibility.",
                tool_calls=[
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:6]}",
                        name="lookup_order",
                        arguments={"order_id": order_id}
                    )
                ]
            )

        # Step 2: Check result of lookup_order
        if lookup_result.get("status") == "error":
            err_msg = lookup_result.get("error", {}).get("message", "Order not found.")
            return ModelResponse(
                thought="The database reported that the order identifier was not found. I must inform the customer gracefully and request verification.",
                content=(
                    f"I apologize for the inconvenience, but I was unable to locate that order in our system. {err_msg} "
                    "Could you please double-check your order number or receipt and share it with me so I can assist you right away?"
                )
            )

        order_data = lookup_result.get("data", {})
        order_id = order_data.get("order_id")
        customer_name = order_data.get("customer_name", "Valued Customer")
        customer_email = order_data.get("customer_email")
        item_id = order_data.get("item_id")
        item_name = order_data.get("item_name")
        is_exchange_eligible = order_data.get("is_exchange_eligible", True)
        ineligible_reason = order_data.get("ineligible_reason")

        # Step 3: Conditional Branching for Resolution (Refund vs Exchange)
        # Execute resolution only if neither refund nor exchange has been executed yet
        if not refund_result and not exchange_result:
            # Case A: Ineligible for exchange -> Automatically initiate refund
            if not is_exchange_eligible:
                return ModelResponse(
                    thought=(
                        f"Order {order_id} is marked as ineligible for replacement exchange "
                        f"({ineligible_reason}). Per resolution policy, I must automatically trigger a financial refund."
                    ),
                    tool_calls=[
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:6]}",
                            name="process_refund",
                            arguments={
                                "order_id": order_id,
                                "reason": f"Ineligible for physical exchange: {ineligible_reason}"
                            }
                        )
                    ]
                )

            # Case B: Eligible for exchange -> Check inventory if not yet checked
            if not inventory_result:
                return ModelResponse(
                    thought=(
                        f"Order {order_id} is eligible for exchange. I must now inspect real-time warehouse inventory "
                        f"for item {item_id} ({item_name}) to verify if replacement stock is available."
                    ),
                    tool_calls=[
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:6]}",
                            name="check_inventory",
                            arguments={"item_id": item_id}
                        )
                    ]
                )

            inv_data = inventory_result.get("data", {})
            stock_count = inv_data.get("stock_count", 0)

            # Sub-case B1: Replacement stock is 0 (Out of stock) -> Trigger Refund
            if stock_count <= 0:
                return ModelResponse(
                    thought=(
                        f"Warehouse inventory confirms stock count for {item_name} ({item_id}) is 0 (OUT OF STOCK). "
                        "Because replacement units cannot be fulfilled, company policy dictates automatic financial refund."
                    ),
                    tool_calls=[
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:6]}",
                            name="process_refund",
                            arguments={
                                "order_id": order_id,
                                "reason": f"Replacement item '{item_name}' ({item_id}) is currently out of stock."
                            }
                        )
                    ]
                )

            # Sub-case B2: Replacement stock > 0 -> Confirm Exchange
            else:
                return ModelResponse(
                    thought=(
                        f"Warehouse inventory confirms {stock_count} units available for {item_name} ({item_id}). "
                        f"Proceeding to confirm replacement exchange and reserve stock."
                    ),
                    tool_calls=[
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:6]}",
                            name="confirm_exchange",
                            arguments={
                                "order_id": order_id,
                                "item_id": item_id,
                                "reason": "Customer reported product issue/damage."
                            }
                        )
                    ]
                )

        # Step 6: Customer Notification
        if not notification_result:
            if refund_result and refund_result.get("status") == "success":
                ref_data = refund_result.get("data", {})
                subject = f"Refund Confirmation - Order {order_id}"
                body = (
                    f"Dear {customer_name},\n\n"
                    f"We have processed a full refund for your order {order_id} ({item_name}) "
                    f"in the amount of ${ref_data.get('refund_amount', 0):.2f}.\n"
                    f"Refund Reference: {ref_data.get('refund_reference')}\n"
                    f"Credited To: {ref_data.get('payment_method')}\n"
                    f"Reason: {ref_data.get('reason')}\n\n"
                    f"Please allow 3-5 business days for your financial institution to post the funds.\n"
                    f"Sincerely,\nCustomer Resolution Team"
                )
            elif exchange_result and exchange_result.get("status") == "success":
                exc_data = exchange_result.get("data", {})
                subject = f"Replacement Confirmed - Order {order_id}"
                body = (
                    f"Dear {customer_name},\n\n"
                    f"Great news! Your replacement exchange for {item_name} has been confirmed.\n"
                    f"Exchange Reference: {exc_data.get('exchange_reference')}\n"
                    f"Dispatch Facility: {exc_data.get('warehouse_location')}\n\n"
                    f"Your replacement unit has been reserved and prepared for expedited shipping. "
                    f"You will receive tracking information once it leaves our facility.\n\n"
                    f"Sincerely,\nCustomer Resolution Team"
                )
            else:
                subject = f"Resolution Update - Order {order_id}"
                body = f"Dear {customer_name},\n\nYour order {order_id} resolution has been updated."

            return ModelResponse(
                thought=f"Fulfillment policy requires dispatching official confirmation to {customer_email}.",
                tool_calls=[
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:6]}",
                        name="send_customer_notification",
                        arguments={
                            "recipient_email": customer_email,
                            "subject": subject,
                            "message": body
                        }
                    )
                ]
            )

        # Step 7: Final Polite Summary to Customer
        if refund_result and refund_result.get("status") == "success":
            ref_data = refund_result.get("data", {})
            return ModelResponse(
                thought="All actions completed: Order investigated, out-of-stock detected, refund processed, notification sent. Delivering final summary.",
                content=(
                    f"Hello {customer_name},\n\n"
                    f"Thank you for contacting us regarding your order **{order_id}** ({item_name}).\n\n"
                    f"I inspected our real-time warehouse inventory and found that replacement units for {item_name} are currently out of stock. "
                    f"To resolve this promptly for you, I have automatically initiated a full financial refund of **${ref_data.get('refund_amount', 0):.2f}** "
                    f"back to your {ref_data.get('payment_method')}.\n\n"
                    f"• **Refund Reference:** `{ref_data.get('refund_reference')}`\n"
                    f"• **Status:** Completed\n"
                    f"• **Notification:** A confirmation email has been dispatched to `{customer_email}`.\n\n"
                    f"Please allow 3 to 5 business days for the credit to appear on your account. Please let me know if you need anything else!"
                )
            )
        elif exchange_result and exchange_result.get("status") == "success":
            exc_data = exchange_result.get("data", {})
            return ModelResponse(
                thought="All actions completed: Order investigated, stock verified, replacement confirmed, notification sent. Delivering final summary.",
                content=(
                    f"Hello {customer_name},\n\n"
                    f"Thank you for contacting us regarding your order **{order_id}** ({item_name}).\n\n"
                    f"I checked our warehouse inventory and confirmed that replacement units are in stock! "
                    f"I have successfully reserved a replacement unit and confirmed your exchange.\n\n"
                    f"• **Exchange Reference:** `{exc_data.get('exchange_reference')}`\n"
                    f"• **Replacement Item:** {exc_data.get('item_name')} ({exc_data.get('item_id')})\n"
                    f"• **Fulfillment Facility:** {exc_data.get('warehouse_location')}\n"
                    f"• **Notification:** An official confirmation has been emailed to `{customer_email}`.\n\n"
                    f"Your replacement is being packed for expedited delivery. You will receive shipping updates shortly!"
                )
            )
        else:
            return ModelResponse(
                thought="Resolution finalized.",
                content=f"Your request for order {order_id} has been processed. Please check your email ({customer_email}) for details."
            )


class LiveOpenAILLMClient(BaseLLMClient):
    """Client for OpenAI-compatible APIs when an API key is available."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

    def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> ModelResponse:
        import urllib.request
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured.")

        formatted_tools = [
            {"type": "function", "function": tool} for tool in tools
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": formatted_tools,
            "tool_choice": "auto"
        }

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            data=json.dumps(payload).encode("utf-8")
        )

        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        choice = data["choices"][0]["message"]
        content = choice.get("content")
        raw_tool_calls = choice.get("tool_calls", [])

        tool_calls = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                args = {}
            tool_calls.append(ToolCall(
                id=tc.get("id", str(uuid.uuid4())),
                name=fn.get("name"),
                arguments=args
            ))

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            thought=None
        )
