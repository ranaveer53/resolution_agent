"""
Automated Test Suite for Decision-Making Resolution Agent.
Validates all Acceptance Criteria, Guardrails, and Security Controls.
"""

import unittest
import json
from database import db
from registry import ToolRegistry, build_default_registry
from agent import ResolutionAgent
from tools import lookup_order, check_inventory, process_refund, confirm_exchange, send_customer_notification
from schemas import LOOKUP_ORDER_SCHEMA, CHECK_INVENTORY_SCHEMA
from llm_client import BaseLLMClient, ModelResponse, ToolCall


class TestResolutionAgent(unittest.TestCase):
    def setUp(self):
        """Reset database to initial clean seed state before each test."""
        db.reset()
        self.agent = ResolutionAgent()

    # =========================================================================
    # Acceptance Criterion 1 & 2B: Stock > 0 -> Autonomous Exchange Confirmed
    # =========================================================================
    def test_branch_exchange_when_stock_available(self):
        """
        Acceptance Criterion 1 & 2B:
        Order ORD-1001: Item ITEM-501 has 8 units in stock.
        The agent must independently:
        1. Look up order ORD-1001
        2. Check warehouse stock for ITEM-501
        3. Confirm exchange (stock > 0)
        4. Send customer notification to alice.smith@example.com
        5. Deliver polite final summary
        """
        prompt = "Hi, my headphones from order ORD-1001 arrived with a broken headband. I would like a replacement."
        result = self.agent.run(prompt)

        self.assertEqual(result["status"], "COMPLETED")
        self.assertFalse(result["escalated"])

        trajectory = result["trajectory"]
        tool_names_called = [
            call["name"]
            for step in trajectory
            for call in step.get("tool_calls", [])
        ]

        # Verify autonomous sequence
        self.assertIn("lookup_order", tool_names_called)
        self.assertIn("check_inventory", tool_names_called)
        self.assertIn("confirm_exchange", tool_names_called)
        self.assertNotIn("process_refund", tool_names_called)
        self.assertIn("send_customer_notification", tool_names_called)

        # Verify stateful database updates
        order_record = db.get_order("ORD-1001")
        self.assertEqual(order_record["order_status"], "EXCHANGED")
        self.assertIsNotNone(order_record.get("exchange_reference"))

        # Verify notification was logged
        self.assertTrue(any(n["recipient_email"] == "alice.smith@example.com" for n in db.notifications))

        # Verify final polite summary
        self.assertIn("Alice", result["final_answer"])
        self.assertIn("ORD-1001", result["final_answer"])
        self.assertIn("exchange", result["final_answer"].lower())

    # =========================================================================
    # Acceptance Criterion 2A: Stock == 0 -> Automatic Refund Initiated
    # =========================================================================
    def test_branch_refund_when_stock_zero(self):
        """
        Acceptance Criterion 2A:
        Order ORD-1002: Item ITEM-502 has 0 units in stock (out of stock).
        The agent must independently:
        1. Look up order ORD-1002
        2. Check warehouse stock for ITEM-502
        3. Detect out of stock and trigger process_refund
        4. Send customer notification to bob.jones@example.com
        5. Deliver polite final summary with refund reference
        """
        prompt = "Hello, my 4K monitor from order ORD-1002 arrived cracked. Can you please replace it?"
        result = self.agent.run(prompt)

        self.assertEqual(result["status"], "COMPLETED")
        self.assertFalse(result["escalated"])

        trajectory = result["trajectory"]
        tool_names_called = [
            call["name"]
            for step in trajectory
            for call in step.get("tool_calls", [])
        ]

        # Verify autonomous sequence
        self.assertIn("lookup_order", tool_names_called)
        self.assertIn("check_inventory", tool_names_called)
        self.assertIn("process_refund", tool_names_called)
        self.assertNotIn("confirm_exchange", tool_names_called)
        self.assertIn("send_customer_notification", tool_names_called)

        # Verify database state updated
        order_record = db.get_order("ORD-1002")
        self.assertEqual(order_record["order_status"], "REFUNDED")
        self.assertIsNotNone(order_record.get("refund_reference"))

        # Verify refund entry recorded with correct amount ($349.99)
        self.assertTrue(any(r["order_id"] == "ORD-1002" and r["refund_amount"] == 349.99 for r in db.refunds))

        # Verify notification logged
        self.assertTrue(any(n["recipient_email"] == "bob.jones@example.com" for n in db.notifications))

        # Verify final summary
        self.assertIn("Bob", result["final_answer"])
        self.assertIn("refund", result["final_answer"].lower())
        self.assertIn("349.99", result["final_answer"])

    # =========================================================================
    # Acceptance Criterion 4: Resilience -> Invalid Order ID Graceful Recovery
    # =========================================================================
    def test_resilience_invalid_order_id(self):
        """
        Acceptance Criterion 4:
        Order ORD-9999 does not exist in the database.
        The agent must NOT crash, but gracefully inform the customer and request verification.
        """
        prompt = "I need help with a damaged product in order ORD-9999."
        result = self.agent.run(prompt)

        self.assertEqual(result["status"], "COMPLETED")
        self.assertFalse(result["escalated"])

        trajectory = result["trajectory"]
        tool_names_called = [
            call["name"]
            for step in trajectory
            for call in step.get("tool_calls", [])
        ]

        self.assertEqual(tool_names_called, ["lookup_order"])

        # Final answer must explain order was not found and ask for verification
        self.assertIn("unable to locate that order", result["final_answer"].lower())
        self.assertIn("verify", result["final_answer"].lower())

    # =========================================================================
    # Policy Ineligibility Branch: Order ineligible for exchange
    # =========================================================================
    def test_ineligible_for_exchange_triggers_refund(self):
        """
        Order ORD-1003 is past the 30-day return window (is_exchange_eligible = False).
        Agent must identify ineligibility and automatically trigger financial refund.
        """
        prompt = "Order ORD-1003 keyboard stopped working. I want an exchange."
        result = self.agent.run(prompt)

        self.assertEqual(result["status"], "COMPLETED")
        trajectory = result["trajectory"]
        tool_names_called = [
            call["name"]
            for step in trajectory
            for call in step.get("tool_calls", [])
        ]

        self.assertIn("lookup_order", tool_names_called)
        self.assertIn("process_refund", tool_names_called)
        self.assertNotIn("confirm_exchange", tool_names_called)
        self.assertIn("send_customer_notification", tool_names_called)

    # =========================================================================
    # Step 3 Security Guardrail: Gatekeeper Whitelist Check
    # =========================================================================
    def test_security_gatekeeper_rejects_unauthorized_tool(self):
        """
        Tests that registry dispatcher blocks any unregistered/unauthorized tool calls.
        """
        registry = build_default_registry()
        unauthorized_attempt = registry.dispatch("delete_all_orders", {"confirm": True})

        self.assertEqual(unauthorized_attempt["status"], "error")
        self.assertEqual(unauthorized_attempt["error"]["code"], "UNAUTHORIZED_TOOL")
        self.assertIn("rejected by security gatekeeper", unauthorized_attempt["error"]["message"].lower())

    # =========================================================================
    # Step 5 Guardrail: Argument Validation
    # =========================================================================
    def test_argument_validation_missing_parameters(self):
        """
        Tests that dispatcher catches missing required arguments and returns structured error.
        """
        registry = build_default_registry()
        # process_refund requires 'order_id' and 'reason'
        missing_arg_attempt = registry.dispatch("process_refund", {"order_id": "ORD-1001"})

        self.assertEqual(missing_arg_attempt["status"], "error")
        self.assertEqual(missing_arg_attempt["error"]["code"], "MISSING_REQUIRED_ARGUMENTS")
        self.assertIn("reason", missing_arg_attempt["error"]["message"])

    # =========================================================================
    # Step 5 Guardrail: Execution Ceiling and Human Escalation
    # =========================================================================
    def test_execution_ceiling_triggers_human_escalation(self):
        """
        Simulate an LLM that repeatedly calls a tool without converging.
        The agent must strictly halt at max_iterations (e.g. 3) and escalate to human.
        """
        class InfiniteLoopMockLLM(BaseLLMClient):
            def generate_response(self, messages, tools):
                # Always requests lookup_order repeatedly
                return ModelResponse(
                    thought="Looping forever without concluding.",
                    tool_calls=[
                        ToolCall(id="loop_call", name="lookup_order", arguments={"order_id": "ORD-1001"})
                    ]
                )

        agent = ResolutionAgent(llm_client=InfiniteLoopMockLLM(), max_iterations=3)
        result = agent.run("Please help with ORD-1001.")

        self.assertEqual(result["status"], "ESCALATED_TO_HUMAN")
        self.assertTrue(result["escalated"])
        self.assertEqual(result["iterations"], 3)
        self.assertIn("escalated", result["final_answer"].lower())
        self.assertIn("Senior Customer Care", result["final_answer"])


if __name__ == "__main__":
    unittest.main()
