"""CLI script to dump the FastAPI OpenAPI schema to a JSON file.

Usage:
    python -m app.export_openapi [--out PATH]

Default output path: frontend/openapi.json (relative to the repo root,
i.e. one directory above the backend/ package). The file is used as the
committed snapshot that openapi-typescript consumes in the frontend build.
"""

import argparse
import json
import os
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Export FastAPI OpenAPI schema to JSON")
    parser.add_argument(
        "--out",
        default=None,
        help="Output path (default: <repo-root>/frontend/openapi.json)",
    )
    args = parser.parse_args()

    # Resolve default output path relative to repo root (one level above backend/)
    if args.out is None:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        out_path = os.path.join(repo_root, "frontend", "openapi.json")
    else:
        out_path = args.out

    # Import here so that calling `python -m app.export_openapi --help` does not
    # trigger the full app startup; the actual openapi() call is pure (no I/O).
    from app.main import app  # noqa: PLC0415

    schema = app.openapi()

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"OpenAPI schema written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
