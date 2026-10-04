"""Drive QEMU's serial pipes on Linux/WSL; keep exact output as boot evidence."""
import os
from pathlib import Path
import selectors
import shlex
import subprocess
import time


def check_console():
    command = shlex.split(os.environ.get("QEMU", "qemu-system-i386")) + [
        "-accel", "tcg", "-m", "32M", "-kernel", "build/console.elf",
        "-display", "none", "-serial", "stdio", "-monitor", "none",
        "-no-reboot", "-nic", "none",
        "-device", "isa-debug-exit,iobase=0xf4,iosize=4",
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 10
    output = bytearray()
    pending = bytearray()
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)

    def remaining():
        value = deadline - time.monotonic()
        if value <= 0:
            raise RuntimeError("console deadline exceeded")
        return value

    def read_line():
        while b"\n" not in pending:
            if not selector.select(remaining()):
                raise RuntimeError("console response timeout")
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                raise RuntimeError("console exited before response")
            output.extend(chunk)
            if len(output) > 65536:
                raise RuntimeError("console output bound exceeded")
            pending.extend(chunk)
        line, _, rest = pending.partition(b"\n")
        pending[:] = rest
        return bytes(line)

    def send_bytes(data):
        # Pace bytes for the polled UART; no guest flow-control claim.
        for byte in data:
            remaining()
            os.write(process.stdin.fileno(), bytes([byte]))
            time.sleep(0.002)
    def exchange(data, expected):
        send_bytes(data)
        actual = read_line()
        if actual != expected:
            raise RuntimeError(f"expected {expected!r}, received {actual!r}")

    try:
        while read_line() != b"CONSOLE ready":
            pass
        exchange(b"help\n", b"OK help: help status quit")
        status = b"STATUS ready=0 running=0 blocked=0 unused=8 retired=1"
        send_bytes(b"sta")
        if pending or selector.select(min(0.05, remaining())):
            raise RuntimeError("unterminated command produced output")
        exchange(b"tus\n", status)
        exchange(b"status\r\n", status)
        exchange(b"\n\r\nhelp\r", b"OK help: help status quit")
        exchange(b"HELP\n", b"ERR unknown command")
        exchange(b"help extra\n", b"ERR unknown command")
        exchange(b" help\n", b"ERR unknown command")
        exchange(b"help \n", b"ERR unknown command")
        exchange(b"x" * 31 + b"\n", b"ERR unknown command")
        exchange(b"x" * 32 + b"quit\n", b"ERR line too long")
        exchange(b"x" * 128 + b"help\r\n", b"ERR line too long")
        exchange(b"help\n", b"OK help: help status quit")
        exchange(b"he\x00lp\n", b"ERR invalid input")
        exchange(b"\tquit\r\n", b"ERR invalid input")
        exchange(b"\xffstatus\n", b"ERR invalid input")
        exchange(b"status\n", status)
        exchange(b"quit\n", b"CONSOLE bye")
        code = process.wait(timeout=remaining())
        # The child has exited, so drain all remaining output without blocking.
        tail = process.stdout.read()
        output.extend(tail)
        if code != 33 or pending or tail or len(output) > 65536:
            raise RuntimeError(f"console exit/output mismatch: status {code}")
        lines = bytes(output).splitlines()
        expected_pass = [b"PASS idle allocator capacity exit",
                         b"PASS two tasks yield resume exit reuse",
                         b"PASS block wake idle stale handle reuse"]
        if [line for line in lines if line.startswith(b"PASS ")] != expected_pass:
            raise RuntimeError("console boot markers mismatch")
        if any(line.startswith((b"FAIL:", b"FAULT ")) for line in lines):
            raise RuntimeError("console faulted")
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        selector.close()
        process.stdin.close()
        process.stdout.close()
        Path("build/console.log").write_bytes(output)
    print("PASS serial console commands rejection recovery")


if __name__ == "__main__":
    check_console()
