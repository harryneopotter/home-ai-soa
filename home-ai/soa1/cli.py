import argparse

from agent import SOA1Agent


def main():
    parser = argparse.ArgumentParser(description="SOA1 CLI")
    parser.add_argument("query", nargs="*", help="Question to ask the SOA1 agent")
    args = parser.parse_args()

    agent = SOA1Agent()

    if args.query:
        q = " ".join(args.query)
        result = agent.ask(q)
        print("\n=== Answer ===\n")
        print(result["answer"])
    else:
        print("Interactive mode. Type 'exit' to quit.")
        while True:
            q = input("\nYou: ").strip()
            if q.lower() in {"exit", "quit"}:
                break
            if not q:
                continue
            result = agent.ask(q)
            print("\nSOA1:\n", result["answer"])


if __name__ == "__main__":
    main()

