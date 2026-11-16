"""Small CLI shared by installed projects and CI."""

import argparse
import json
import sys
from pathlib import Path

from .contracts import ValidationError, validate_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reviewctl", description="Project-owned AI review tools")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate a project configuration")
    validate.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_config(json.loads(args.config.read_text()))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        print(f"reviewctl: {exc}", file=sys.stderr)
        return 2
