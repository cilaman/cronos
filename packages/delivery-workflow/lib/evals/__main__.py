"""CLI entry-point for the portable eval-corpus harness.

Usage:
    python -m lib.evals [--repo-root PATH] [--json]

Exit code equals the corpus exit code (0 = green, non-zero = red).
"""
from __future__ import annotations

import argparse
import json
import sys

from .corpus import run_eval_corpus


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the delivery/v1 eval corpus",
        prog="python -m lib.evals",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root directory (default: current working directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit a JSON result object to stdout before exiting",
    )
    args = parser.parse_args()

    result = run_eval_corpus(repo_root=args.repo_root)

    if args.as_json:
        print(
            json.dumps(
                {
                    "passed": result.passed,
                    "exit_code": result.exit_code,
                    "command": result.command,
                    "output_tail": result.output_tail,
                }
            )
        )

    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
