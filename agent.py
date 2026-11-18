"""
Autonomous ReAct State Loop and Guardrails for Decision-Making Resolution Agent.
Steps 4 & 5: State management, tool dispatching, execution ceiling, and error recovery.
"""

from typing import List, Dict, Any, Optional
import json
import logging
from dataclasses import dataclass, field
from registry import ToolRegistry, build_default_registry
from llm_client import BaseLLMClient, MockResolutionLLM, ModelResponse, ToolCall

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ResolutionAgent")

SYSTEM_PROMPT = """You are an Autonomous Customer Order Resolution Specialist.
Your task is to independently investigate and resolve customer order issues regarding damaged or defective products.

Follow this strict decision-making policy:
1. Always begin by looking up order records using `lookup_order` to retrieve customer identity, item details, and exchange eligibility.
2. If the order is NOT found, politely inform the customer and request verification of their order number.
3. If the order is eligible for exchange, immediately inspect warehouse stock using `check_inventory`.
4. CONDITIONAL BRANCHING:
   - If replacement stock is GREATER THAN 0: confirm the replacement exchange using `confirm_exchange`.
   - If replacement stock is EQUAL TO 0 (out of stock) OR the item is ineligible for exchange: initiate a full financial refund using `process_refund`.
5. FULFILLMENT: Before finalizing, dispatch an official confirmation email via `send_customer_notification`.
6. Conclude with a clear, polite summary detailing the actions taken and reference numbers.
"""


@dataclass
class TrajectoryStep:
    iteration: int
    thought: Optional[str]
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    assistant_content: Optional[str] = None


class ResolutionAgent:
    """
    Autonomous Agent implementing the cyclic ReAct tool loop (Thought -> Action -> Observation)
    with strict guardrails:
    - Maximum iteration ceiling (preventing runaway recursion).
    - Safe tool dispatch with schema validation and authorization gatekeeper.
    - Graceful error containment and self-correcting feedback loop.
    """

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        llm_client: Optional[BaseLLMClient] = None,
        max_iterations: int = 5,
        system_prompt: str = SYSTEM_PROMPT
    ):
        self.registry = registry or build_default_registry()
        self.llm_client = llm_client or MockResolutionLLM()
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt

    def run(self, user_prompt: str) -> Dict[str, Any]:
        """
        Executes the agentic state loop for a given user prompt.

        Args:
            user_prompt: Natural language request from customer (e.g. 'My order ORD-1002 arrived broken').

        Returns:
            Structured dictionary containing final answer, execution trajectory, status, and iteration count.
        """
        logger.info("Initializing Agentic State Loop for customer request.")
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        trajectory: List[TrajectoryStep] = []
        tools_schemas = self.registry.get_schemas()

        for iteration in range(1, self.max_iterations + 1):
            logger.info(f"--- Iteration {iteration}/{self.max_iterations} ---")

            # Model Invocation with Tools
            try:
                response: ModelResponse = self.llm_client.generate_response(
                    messages=messages,
                    tools=tools_schemas
                )
            except Exception as e:
                logger.error(f"Error during model invocation: {e}")
                return {
                    "status": "ERROR",
                    "error": str(e),
                    "final_answer": "An unexpected system error occurred while generating a response. Please try again.",
                    "iterations": iteration,
                    "trajectory": [t.__dict__ for t in trajectory]
                }

            step = TrajectoryStep(
                iteration=iteration,
                thought=response.thought,
                assistant_content=response.content
            )

            # Record assistant turn in state history
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
                "thought": response.thought
            }

            if response.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments
                    }
                    for tc in response.tool_calls
                ]
            messages.append(assistant_msg)

            # Tool Call Detection: If no tool calls, model provided final text answer
            if not response.tool_calls:
                logger.info("Model produced final response without requesting further tools. Exiting loop.")
                trajectory.append(step)
                return {
                    "status": "COMPLETED",
                    "final_answer": response.content or "",
                    "iterations": iteration,
                    "trajectory": [t.__dict__ for t in trajectory],
                    "escalated": False
                }

            # Tool Execution & State Feedback
            for tc in response.tool_calls:
                logger.info(f"Executing requested tool: '{tc.name}' with arguments: {tc.arguments}")
                step.tool_calls.append({"id": tc.id, "name": tc.name, "arguments": tc.arguments})

                # Safe dispatch through registry gatekeeper
                execution_result = self.registry.dispatch(tc.name, tc.arguments)
                logger.info(f"Tool '{tc.name}' output status: {execution_result.get('status')}")

                step.tool_results.append({
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "result": execution_result
                })

                # Append execution result back into conversation history
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": json.dumps(execution_result, indent=2)
                })

            trajectory.append(step)

        # Step 5 Guardrail: Execution Ceiling Reached -> Escalate to Human
        logger.warning(f"Execution ceiling of {self.max_iterations} iterations reached. Escalating session to human.")
        escalation_payload = {
            "status": "ESCALATED_TO_HUMAN",
            "reason": f"Execution loop exceeded maximum limit of {self.max_iterations} iterations without convergence.",
            "final_answer": (
                "Your request requires specialized assistance beyond automated resolution and has been escalated to our Senior Customer Care Specialists. "
                "A human agent will review your order details and contact you directly within 24 hours."
            ),
            "iterations": self.max_iterations,
            "trajectory": [t.__dict__ for t in trajectory],
            "escalated": True
        }
        return escalation_payload
