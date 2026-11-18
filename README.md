# Autonomous Decision-Making Resolution Agent

An autonomous, tool-using resolution agent designed to handle customer order inquiries, inspect real-time warehouse inventory, execute conditional resolutions (exchange vs. refund), and dispatch customer notifications.

---

## Architecture Overview

```
                      +-----------------------------+
                      |   Terminal Chat / REST API  |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |       ResolutionAgent       |
                      |   (ReAct Loop & Guardrails) |
                      +--------------+--------------+
                                     |
                  +------------------+------------------+
                  |                                     |
                  v                                     v
        +-------------------+                 +-------------------+
        |  Tool Registry &  |                 |     LLM Client    |
        |  Safe Gatekeeper  |                 | (Mock/Deterministic|
        +---------+---------+                 |  or Live OpenAI)  |
                  |                           +-------------------+
    +-------------+-------------+
    |             |             |
    v             v             v
lookup_order  check_inventory  process_refund / confirm_exchange / send_customer_notification
```

---

## Project Structure

- `agent.py`: Cyclical ReAct state loop, iteration counter ceiling, and error escalation.
- `tools.py`: Deterministic functional tools returning structured dictionary payloads.
- `schemas.py`: Declarative JSON Schema contracts defining names, arguments, and required fields.
- `registry.py`: Centralized tool registry, authorization gatekeeper, and parameter validator.
- `llm_client.py`: Reasoning client supporting deterministic simulated ReAct reasoning out of the box and live APIs.
- `backend_server.py`: FastAPI backend exposing REST endpoints for resolution and state inspection.
- `terminal_chat.py`: Interactive command-line chat interface with live reasoning traces.
- `main.py`: Unified CLI entry point for running terminal chat, single queries, the server, or tests.
- `test_agent.py`: Automated test suite verifying all acceptance criteria.
- `database.py`: Simulated in-memory database with orders, warehouse inventory, and logs.

---

## Quick Start

### 1. Requirements

Install standard dependencies:

```bash
pip install -r requirements.txt
```

### 2. Run in Terminal (Direct Chat)

Start the interactive terminal interface:

```bash
python main.py
```

Or pass a direct customer inquiry:

```bash
python main.py "My order ORD-1001 arrived damaged, can I get a replacement?"
```

Available terminal commands:
- `/orders`: View all mock orders
- `/inventory`: Check warehouse stock counts
- `/refunds`: View processed refund records
- `/exchanges`: View confirmed exchanges
- `/reset`: Reset the in-memory database
- `1` to `4`: Run predefined test scenarios
- `exit`: Quit the terminal

### 3. Run Backend API Server

Start the FastAPI server:

```bash
python main.py --server
```

The server runs on `http://127.0.0.1:8000`. You can inspect endpoints and interactive API documentation at `http://127.0.0.1:8000/docs`.

To connect the terminal chat to the running backend server:

```bash
python main.py --backend http://127.0.0.1:8000
```

### 4. Run Automated Test Suite

Run unit tests covering all branching conditions, invalid order handling, and safety guardrails:

```bash
python main.py --test
```

---

## Test Scenarios Covered

1. **Exchange Confirmed (`ORD-1001`)**: Item is eligible and replacement stock is available (> 0). The agent autonomously verifies inventory, confirms the exchange, reserves stock, and emails the customer.
2. **Automatic Refund (`ORD-1002`)**: Item is out of stock (stock == 0). The agent detects zero inventory, triggers a financial refund, and notifies the customer.
3. **Policy Ineligibility (`ORD-1003`)**: Order is past the exchange window. The agent detects policy restriction and issues a refund.
4. **Invalid Order (`ORD-9999`)**: Order does not exist. The agent gracefully informs the customer and asks for verification without crashing.
5. **Guardrails**: Unauthorized tool execution prevention, argument validation, and maximum iteration ceiling escalation.
