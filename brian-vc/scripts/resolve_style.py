#!/usr/bin/env python3
"""Resolve a report style without coupling the VC analysis core to a renderer."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BUILTIN_STYLES = PLUGIN_ROOT / "assets" / "styles"
DEFAULT_STYLE = "neutral"
REQUIRED_FIELDS = ("id", "version", "display_name", "instructions", "targets")


def manifest_from_path(path: Path) -> Path:
    if path.is_dir():
        return path / "style.json"
    return path


def resolve_manifest(style: str | None) -> Path:
    requested = style or os.environ.get("VC_REPORT_STYLE") or DEFAULT_STYLE
    candidate = manifest_from_path(Path(requested).expanduser())
    if candidate.is_file():
        return candidate.resolve()

    builtin = BUILTIN_STYLES / requested / "style.json"
    if builtin.is_file():
        return builtin.resolve()

    raise FileNotFoundError(
        f"Unknown style {requested!r}. Pass a style id, a style.json path, "
        "a directory containing style.json, or set VC_REPORT_STYLE."
    )


def load_style(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise ValueError(f"{path} is missing required fields: {', '.join(missing)}")
    if not isinstance(data["targets"], list) or not data["targets"]:
        raise ValueError(f"{path}: targets must be a non-empty list")

    instructions = (path.parent / data["instructions"]).resolve()
    if not instructions.is_file():
        raise FileNotFoundError(f"Style instructions not found: {instructions}")

    result = dict(data)
    result["manifest_path"] = str(path)
    result["style_root"] = str(path.parent)
    result["instructions_path"] = str(instructions)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve a built-in or user-provided VC report style."
    )
    parser.add_argument(
        "style",
        nargs="?",
        help="Style id, style.json path, or directory containing style.json.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact JSON.",
    )
    args = parser.parse_args()

    resolved = load_style(resolve_manifest(args.style))
    print(
        json.dumps(
            resolved,
            ensure_ascii=False,
            indent=None if args.compact else 2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
