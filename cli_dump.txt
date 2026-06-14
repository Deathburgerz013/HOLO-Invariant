import sys
from .core import HoloChain

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m holosim.cli [append <content> | replay | state]")
        sys.exit(1)

    chain = HoloChain()  # You can customize file_path here if needed

    cmd = sys.argv[1]
    if cmd == "append":
        content = " ".join(sys.argv[2:]) or input("Enter content: ")
        chain.append(content)
    elif cmd == "replay":
        chain.replay()
    elif cmd == "state":
        print(chain.get_state())
    else:
        print("Unknown command. Use: append, replay, or state")

if __name__ == "__main__":
    main()
