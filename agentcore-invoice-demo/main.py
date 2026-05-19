"""Local interactive test for the invoice processing agent."""

from orchestrator import create_orchestrator


def main():
    agent = create_orchestrator()
    print("Invoice Processing Agent (type 'quit' to exit)")
    print("=" * 50)
    print("Try: 'What's the status of INV-001?'")
    print("     'Validate invoice INV-003'")
    print("     'Show me all overdue invoices'")
    print("=" * 50)

    while True:
        user_input = input("\n> ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue
        response = agent(user_input)
        print(f"\n{response}")


if __name__ == "__main__":
    main()
