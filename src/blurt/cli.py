import argparse
import fcntl
import os
import sys
from pathlib import Path


_LOCK_PATH = Path.home() / ".cache" / "blurt" / "blurt.lock"


def _acquire_singleton_lock() -> int | None:
    """Try to take an exclusive lock so only one blurt daemon runs at a time.

    Returns the open fd on success (caller must keep it alive — closing it or
    process exit releases the lock). Returns None if another instance holds
    the lock.
    """
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(_LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode())
    return fd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="blurt")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="Run the daemon")
    sub.add_parser("bench-whisper", help="Benchmark Wyoming whisper latency")
    sub.add_parser("bench-cleanup", help="Benchmark Ollama cleanup latency")

    args = parser.parse_args(argv)

    if args.cmd == "run":
        lock_fd = _acquire_singleton_lock()
        if lock_fd is None:
            try:
                existing_pid = _LOCK_PATH.read_text().strip()
            except OSError:
                existing_pid = "?"
            print(
                f"\nblurt: another instance is already running (pid {existing_pid}).\n"
                f"Stop it first:  systemctl --user stop blurt   "
                f"or  kill {existing_pid}\n",
                file=sys.stderr,
            )
            return 2
        from blurt.daemon import run
        try:
            return run()
        finally:
            os.close(lock_fd)
    if args.cmd == "bench-whisper":
        from blurt.bench.whisper_bench import main as bench
        return bench()
    if args.cmd == "bench-cleanup":
        from blurt.bench.cleanup_bench import main as bench
        return bench()
    return 1


if __name__ == "__main__":
    sys.exit(main())
