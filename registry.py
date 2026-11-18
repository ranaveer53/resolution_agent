"""
Tool Registry and Safe Dispatcher for Decision-Making Resolution Agent.
Step 3: Whitelist registry, execution gatekeeper, and authorization checks.
"""

from typing import Dict, Any, Callable, List, Optional
import inspect
import json


class ToolRegistry:
    """
    Centralized dispatch registry providing:
    - Tool registration with declarative schemas.
    - Strict whitelist enforcement (authorization gatekeeper).
    - Input argument validation against declared schemas.
    - Safe deterministic execution with controlled error containment.
    """

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, func: Callable, schema: Dict[str, Any]) -> None:
        """Register a tool function alongside its declarative schema contract."""
        self._tools[name] = func
        self._schemas[name] = schema

    def is_authorized(self, tool_name: str) -> bool:
        """Check if a tool is present in the authorized whitelist."""
        return tool_name in self._tools

    def get_authorized_tool_names(self) -> List[str]:
        """Return list of all registered tool names."""
        return list(self._tools.keys())

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Return all declarative schemas registered."""
        return list(self._schemas.values())

    def validate_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validates arguments against the tool schema requirements.
        Returns an error payload if validation fails, or None if valid.
        """
        schema = self._schemas.get(tool_name)
        if not schema:
            return {
                "status": "error",
                "error": {
                    "code": "SCHEMA_NOT_FOUND",
                    "message": f"No schema contract found for tool '{tool_name}'."
                }
            }

        parameters_meta = schema.get("parameters", {})
        required_fields = parameters_meta.get("required", [])

        if not isinstance(arguments, dict):
            return {
                "status": "error",
                "error": {
                    "code": "INVALID_ARGUMENT_FORMAT",
                    "message": f"Arguments for tool '{tool_name}' must be a dictionary/object, received {type(arguments).__name__}."
                }
            }

        missing = [param for param in required_fields if param not in arguments or arguments[param] is None]
        if missing:
            return {
                "status": "error",
                "error": {
                    "code": "MISSING_REQUIRED_ARGUMENTS",
                    "message": (
                        f"Invocation of tool '{tool_name}' failed validation: Missing required argument(s): {missing}. "
                        f"Expected required arguments: {required_fields}. Received: {list(arguments.keys())}."
                    )
                }
            }

        return None

    def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gatekeeper execution dispatcher.
        1. Checks authorization whitelist.
        2. Validates incoming arguments against schema.
        3. Executes tool deterministically and safely catches exceptions.
        """
        # Step 3.1: Authorization Check
        if not self.is_authorized(tool_name):
            return {
                "status": "error",
                "error": {
                    "code": "UNAUTHORIZED_TOOL",
                    "message": (
                        f"Execution rejected by security gatekeeper: Tool '{tool_name}' is not in the authorized registry. "
                        f"Authorized tools: {self.get_authorized_tool_names()}."
                    )
                }
            }

        # Step 5: Argument Validation Guardrail
        validation_error = self.validate_arguments(tool_name, arguments)
        if validation_error:
            return validation_error

        # Step 3.2: Safe execution
        func = self._tools[tool_name]
        try:
            result = func(**arguments)
            # Ensure return payload is structured dict
            if not isinstance(result, dict):
                return {
                    "status": "success",
                    "data": {"result": result}
                }
            return result
        except TypeError as te:
            return {
                "status": "error",
                "error": {
                    "code": "ARGUMENT_TYPE_ERROR",
                    "message": f"Type mismatch or invalid parameter call in tool '{tool_name}': {str(te)}"
                }
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": {
                    "code": "TOOL_EXECUTION_EXCEPTION",
                    "message": f"Unexpected runtime error during execution of tool '{tool_name}': {str(exc)}"
                }
            }


def build_default_registry() -> ToolRegistry:
    """Build and populate the default registry with all functional tools."""
    from tools import (
        lookup_order,
        check_inventory,
        process_refund,
        confirm_exchange,
        send_customer_notification
    )
    from schemas import (
        LOOKUP_ORDER_SCHEMA,
        CHECK_INVENTORY_SCHEMA,
        PROCESS_REFUND_SCHEMA,
        CONFIRM_EXCHANGE_SCHEMA,
        SEND_CUSTOMER_NOTIFICATION_SCHEMA
    )

    registry = ToolRegistry()
    registry.register("lookup_order", lookup_order, LOOKUP_ORDER_SCHEMA)
    registry.register("check_inventory", check_inventory, CHECK_INVENTORY_SCHEMA)
    registry.register("process_refund", process_refund, PROCESS_REFUND_SCHEMA)
    registry.register("confirm_exchange", confirm_exchange, CONFIRM_EXCHANGE_SCHEMA)
    registry.register("send_customer_notification", send_customer_notification, SEND_CUSTOMER_NOTIFICATION_SCHEMA)
    return registry
