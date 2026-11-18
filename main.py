"""
Unified Entry Point for Decision-Making Resolution Agent.
Supports:
  - Interactive Terminal Chat: python main.py
  - Direct Query Resolution:   python main.py "My order ORD-1002 arrived damaged"
  - Backend API Server:        python main.py --server
  - Automated Test Suite:      python main.py --test
"""

import sys
import argparse
import unittest


def run_tests():
    print("Running automated test suite for Resolution Agent...")
    loader = unittest.TestLoader()
    suite = loader.discover(".", pattern="test_agent.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Order Resolution Specialist Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                              # Launch interactive terminal chat
  python main.py "My order ORD-1001 arrived damaged"  # Single-query resolution
  python main.py --server                     # Start FastAPI backend server
  python main.py --test                       # Run all acceptance criteria tests
        """
    )
    parser.add_argument("query", nargs="?", help="Direct customer prompt to resolve")
    parser.add_argument("--server", action="store_true", help="Launch FastAPI REST backend server")
    parser.add_argument("--port", type=int, default=8000, help="Port for FastAPI backend (default: 8000)")
    parser.add_argument("--test", action="store_true", help="Run automated test suite and exit")
    parser.add_argument("--backend", help="Connect terminal to running backend URL (e.g., http://127.0.0.1:8000)")

    args = parser.parse_args()

    if args.test:
        run_tests()
    elif args.server:
        from backend_server import start_server
        start_server(port=args.port)
    else:
        from terminal_chat import interactive_terminal, run_query
        from agent import ResolutionAgent
        if args.query:
            agent = ResolutionAgent()
            run_query(args.query, agent, args.backend)
        else:
            interactive_terminal(args.backend)


if __name__ == "__main__":
    main()
