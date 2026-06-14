import sys
import argparse
from .core import HoloChain

def main():
    parser = argparse.ArgumentParser(
        description="Holo/Sim CLI - Tamper-evident append-only chain for continuity",
        prog="python -m holosim.cli"
    )
    parser.add_argument("--file", "-f", default="holo_memory.jsonl",
                        help="Path to the chain file (default: holo_memory.jsonl)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Append
    append_parser = subparsers.add_parser("append", help="Append a new entry")
    append_parser.add_argument("content", nargs="*", help="Content to append")
    append_parser.add_argument("--compress", "-c", action="store_true",
                               help="Compress entry for density")

    # Replay
    subparsers.add_parser("replay", help="Replay and verify full chain")

    # State
    subparsers.add_parser("state", help="Get current state")

    args = parser.parse_args()

    chain = HoloChain(file_path=args.file)

    if args.command == "append":
        content = " ".join(args.content) if args.content else input("Enter content: ")
        if not content.strip():
            print("Error: No content provided.")
            sys.exit(1)
        chain.append(content, compress=args.compress)
    elif args.command == "replay":
        chain.replay()
    elif args.command == "state":
        print(chain.get_state())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()