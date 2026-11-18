"""
Interactive Terminal Chat Interface for Decision-Making Resolution Agent.
Allows answering customer questions through the terminal with live ReAct visualization.
Supports both Direct Agent Execution and Remote Backend Client mode.
"""

import sys
import os
import json
import argparse
from typing import Optional, Dict, Any

from database import db
from agent import ResolutionAgent
from registry import build_default_registry


# ANSI Color Codes for enhanced terminal readability
class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def print_banner():
    banner = f"""
{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════════════════════════════════════╗
║               AUTONOMOUS ORDER RESOLUTION AGENT                      ║
║         Course: Agentic AI — Tool-Using Decision-Making Specialist    ║
╚══════════════════════════════════════════════════════════════════════╝{Colors.RESET}
{Colors.DIM}Type your query, pick a preset scenario, or use commands like /orders, /inventory, /help{Colors.RESET}
"""
    print(banner)


def display_trajectory_step(step: Dict[str, Any]):
    iteration = step.get("iteration")
    thought = step.get("thought")
    tool_calls = step.get("tool_calls", [])
    tool_results = step.get("tool_results", [])

    print(f"\n  {Colors.BOLD}{Colors.BLUE}[Iteration {iteration}]{Colors.RESET}")
    if thought:
        print(f"  {Colors.MAGENTA}🧠 Thought:{Colors.RESET} {thought}")

    for tc in tool_calls:
        name = tc.get("name")
        args = tc.get("arguments", {})
        print(f"  {Colors.YELLOW}⚙️  Action Call:{Colors.RESET} {Colors.BOLD}{name}{Colors.RESET}({json.dumps(args)})")

    for tr in tool_results:
        name = tr.get("name")
        res = tr.get("result", {})
        status = res.get("status")
        status_color = Colors.GREEN if status == "success" else Colors.RED
        print(f"  {status_color}📋 Observation ({name}):{Colors.RESET} status={status}")
        if status == "success" and "data" in res:
            data_preview = res["data"]
            # compact display
            print(f"     {Colors.DIM}{json.dumps(data_preview, default=str)}{Colors.RESET}")
        elif status == "error" and "error" in res:
            print(f"     {Colors.RED}{res['error'].get('message')}{Colors.RESET}")


def format_final_answer(answer: str, status: str, iterations: int):
    print(f"\n{Colors.GREEN}{Colors.BOLD}──────────────────────── RESOLUTION SUMMARY ────────────────────────{Colors.RESET}")
    print(f"{Colors.BOLD}Status:{Colors.RESET} {status}  |  {Colors.BOLD}Reasoning Cycles:{Colors.RESET} {iterations}")
    print(f"\n{Colors.BOLD}Agent Response:{Colors.RESET}\n")
    print(answer)
    print(f"\n{Colors.GREEN}{Colors.BOLD}───────────────────────────────────────────────────────────────────{Colors.RESET}\n")


def display_orders():
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== Current Orders Database ==={Colors.RESET}")
    for oid, o in db.orders.items():
        elig = f"{Colors.GREEN}Yes{Colors.RESET}" if o['is_exchange_eligible'] else f"{Colors.RED}No ({o['ineligible_reason']}){Colors.RESET}"
        print(f" • {Colors.BOLD}{oid}{Colors.RESET}: {o['customer_name']} ({o['customer_email']})")
        print(f"   Item: {o['item_name']} ({o['item_id']}) | Qty: {o['quantity']} | Price: ${o['price']} | Status: {o['order_status']}")
        print(f"   Exchange Eligible: {elig}")
    print()


def display_inventory():
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== Warehouse Inventory ==={Colors.RESET}")
    for iid, item in db.inventory.items():
        avail = f"{Colors.GREEN}In Stock ({item['stock_count']}){Colors.RESET}" if item['stock_count'] > 0 else f"{Colors.RED}OUT OF STOCK (0){Colors.RESET}"
        print(f" • {Colors.BOLD}{iid}{Colors.RESET}: {item['item_name']} | Stock: {avail} | Location: {item['warehouse_location']}")
    print()


def print_help():
    print(f"""
{Colors.BOLD}Available Terminal Commands:{Colors.RESET}
  {Colors.YELLOW}/orders{Colors.RESET}        - View all orders and their current status
  {Colors.YELLOW}/inventory{Colors.RESET}     - View real-time warehouse inventory stock levels
  {Colors.YELLOW}/refunds{Colors.RESET}       - View logged financial refunds
  {Colors.YELLOW}/exchanges{Colors.RESET}     - View confirmed replacement exchanges
  {Colors.YELLOW}/notifs{Colors.RESET}        - View dispatched customer emails
  {Colors.YELLOW}/reset{Colors.RESET}         - Reset database to fresh seed state
  {Colors.YELLOW}/help{Colors.RESET}          - Display this command menu
  {Colors.YELLOW}exit{Colors.RESET} or {Colors.YELLOW}quit{Colors.RESET}   - Exit the terminal chat

{Colors.BOLD}Quick Scenarios to Test:{Colors.RESET}
  [1] Stock Available (ORD-1001)   -> Agent independently investigates & confirms replacement
  [2] Out of Stock (ORD-1002)      -> Agent detects 0 stock & automatically issues financial refund
  [3] Policy Ineligible (ORD-1003) -> Agent identifies return policy expiration & issues refund
  [4] Invalid Order (ORD-9999)     -> Agent safely recovers and requests verification
""")


def run_query(query: str, agent: ResolutionAgent, backend_url: Optional[str] = None):
    """Executes query either directly or via backend server."""
    if backend_url:
        import urllib.request
        try:
            req_data = json.dumps({"message": query, "show_trajectory": True}).encode("utf-8")
            req = urllib.request.Request(
                f"{backend_url.rstrip('/')}/api/resolve",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            trajectory = data.get("trajectory", [])
            for step in trajectory:
                display_trajectory_step(step)
            format_final_answer(data["final_answer"], data["status"], data["iterations"])
        except Exception as e:
            print(f"{Colors.RED}Backend communication error: {e}{Colors.RESET}")
            print("Falling back to local direct execution...")
            run_query_direct(query, agent)
    else:
        run_query_direct(query, agent)


def run_query_direct(query: str, agent: ResolutionAgent):
    result = agent.run(query)
    trajectory = result.get("trajectory", [])
    for step in trajectory:
        display_trajectory_step(step)
    format_final_answer(result["final_answer"], result["status"], result["iterations"])


def interactive_terminal(backend_url: Optional[str] = None):
    print_banner()
    if backend_url:
        print(f"{Colors.GREEN}Connected to Backend Server at: {backend_url}{Colors.RESET}\n")
    else:
        print(f"{Colors.GREEN}Running in Standalone Direct Mode (Embedded Agent Backend){Colors.RESET}\n")

    agent = ResolutionAgent()

    print_help()

    while True:
        try:
            user_input = input(f"{Colors.BOLD}{Colors.CYAN}Customer > {Colors.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Exiting Resolution Agent. Goodbye!{Colors.RESET}")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ["exit", "quit", "q"]:
            print(f"{Colors.YELLOW}Exiting Resolution Agent. Goodbye!{Colors.RESET}")
            break
        elif cmd in ["/help", "help", "?"]:
            print_help()
            continue
        elif cmd in ["/orders", "orders"]:
            display_orders()
            continue
        elif cmd in ["/inventory", "inventory"]:
            display_inventory()
            continue
        elif cmd in ["/refunds", "refunds"]:
            print(json.dumps(db.refunds, indent=2))
            continue
        elif cmd in ["/exchanges", "exchanges"]:
            print(json.dumps(db.exchanges, indent=2))
            continue
        elif cmd in ["/notifs", "/notifications"]:
            print(json.dumps(db.notifications, indent=2))
            continue
        elif cmd in ["/reset", "reset"]:
            db.reset()
            print(f"{Colors.GREEN}Database state reset successfully.{Colors.RESET}")
            continue
        elif cmd == "1":
            user_input = "Hi, my headphones from order ORD-1001 arrived with a broken headband. I would like a replacement."
            print(f"{Colors.DIM}Running Preset Scenario [1]: Damaged item with replacement stock in warehouse{Colors.RESET}")
        elif cmd == "2":
            user_input = "Hello, my monitor for order ORD-1002 has a cracked screen and won't turn on. Please help."
            print(f"{Colors.DIM}Running Preset Scenario [2]: Damaged item out of stock (Stock == 0){Colors.RESET}")
        elif cmd == "3":
            user_input = "Order ORD-1003 mechanical keyboard keys are failing. Can you exchange it?"
            print(f"{Colors.DIM}Running Preset Scenario [3]: Order ineligible for exchange under 30-day policy{Colors.RESET}")
        elif cmd == "4":
            user_input = "I need a replacement for my order ORD-9999 which never arrived."
            print(f"{Colors.DIM}Running Preset Scenario [4]: Non-existent order identifier{Colors.RESET}")

        run_query(user_input, agent, backend_url)


def main():
    parser = argparse.ArgumentParser(description="Autonomous Order Resolution Agent Terminal Interface")
    parser.add_argument("query", nargs="?", help="Direct query to resolve without entering interactive loop")
    parser.add_argument("--backend", help="Backend server URL (e.g., http://127.0.0.1:8000)")
    args = parser.parse_args()

    if args.query:
        agent = ResolutionAgent()
        run_query(args.query, agent, args.backend)
    else:
        interactive_terminal(args.backend)


if __name__ == "__main__":
    main()
