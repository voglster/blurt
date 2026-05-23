import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="blurt")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="Run the daemon")
    sub.add_parser("bench-whisper", help="Benchmark Wyoming whisper latency")
    sub.add_parser("bench-cleanup", help="Benchmark Ollama cleanup latency")

    args = parser.parse_args(argv)

    if args.cmd == "run":
        from blurt.daemon import run
        return run()
    if args.cmd == "bench-whisper":
        from blurt.bench.whisper_bench import main as bench
        return bench()
    if args.cmd == "bench-cleanup":
        from blurt.bench.cleanup_bench import main as bench
        return bench()
    return 1


if __name__ == "__main__":
    sys.exit(main())
