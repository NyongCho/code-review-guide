"""Small CLI shared by installed projects and CI."""

import argparse
import json
import sys
from pathlib import Path

from .contracts import ValidationError, validate_config
from .install import apply_install, plan_install


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reviewctl", description="Project-owned AI review tools")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate a project configuration")
    validate.add_argument("--config", type=Path, required=True)
    install = sub.add_parser("install", help="install or propose an update, preserving user edits")
    install.add_argument("--target", type=Path, required=True)
    install.add_argument("--config", type=Path, required=True)
    install.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parents[2])
    mode = install.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_config(json.loads(args.config.read_text()))
        elif args.command == "install":
            proposal = plan_install(args.target, args.bundle, json.loads(args.config.read_text()))
            result = apply_install(args.target, proposal) if args.apply else proposal
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        print(f"reviewctl: {exc}", file=sys.stderr)
        return 2
