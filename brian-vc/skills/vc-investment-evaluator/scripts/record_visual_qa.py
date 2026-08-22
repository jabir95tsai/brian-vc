#!/usr/bin/env python3
"""Record an evidenced visual QA pass in the shape verify_and_record_delivery.py reads.

Visual QA is a human judgement, so this script never invents the verdict: it
refuses to write ``status=pass`` unless a reviewer is named. What it does add is
the part a human claim cannot supply on its own -- proof that every slide the
reviewer attests to was actually rendered to a PNG they could look at.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

SLIDE_XML = re.compile(r"ppt/slides/slide(\d+)\.xml$")
SLIDE_PNG = re.compile(r"slide-(\d+)\.png$", re.I)


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def slide_count(pptx: Path) -> int:
    with zipfile.ZipFile(pptx) as archive:
        return sum(1 for name in archive.namelist() if SLIDE_XML.search(name))


def rendered_slides(preview_dir: Path) -> set[int]:
    if not preview_dir.is_dir():
        return set()
    found = set()
    for item in preview_dir.iterdir():
        match = SLIDE_PNG.search(item.name)
        if match:
            found.add(int(match.group(1)))
    return found


def check_deck(label: str, pptx: Path, preview_dir: Path) -> tuple[dict, list[str]]:
    total = slide_count(pptx)
    rendered = rendered_slides(preview_dir)
    missing = sorted(set(range(1, total + 1)) - rendered)
    errors = []
    if not total:
        errors.append(f"{label}: {pptx.name} contains no slides")
    if missing:
        errors.append(
            f"{label}: {len(missing)} slide(s) were never rendered for review "
            f"(missing {missing[:10]}{'...' if len(missing) > 10 else ''}) in {preview_dir}"
        )
    return (
        {
            "variant": label,
            "pptx": str(pptx.resolve()),
            "slides": total,
            "rendered_previews": len(rendered),
            "preview_dir": str(preview_dir.resolve()),
            "unreviewed_slides": missing,
        },
        errors,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--executive", type=Path, required=True)
    parser.add_argument("--full-critical", type=Path, required=True)
    parser.add_argument(
        "--preview-root",
        type=Path,
        required=True,
        help="Directory holding the rendered deck previews (…/previews/decks).",
    )
    parser.add_argument(
        "--reviewer",
        required=True,
        help="Who inspected the renders. Visual QA is not passed by a script.",
    )
    parser.add_argument("--mode", choices=("full", "degraded", "blocked"), default="full")
    parser.add_argument(
        "--issue",
        action="append",
        default=[],
        help="A rendering defect the reviewer observed. Any issue forces status=fail.",
    )
    parser.add_argument(
        "--note", action="append", default=[], help="Free-text reviewer note; does not affect status."
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    case_dir = args.case_dir.resolve()
    if not args.reviewer.strip():
        print("ERROR: --reviewer must name the person who inspected the renders", file=sys.stderr)
        return 2

    output = (args.output or case_dir / "outputs" / "visual_qa_report.json").resolve()
    if not inside(output, case_dir):
        print(f"ERROR: visual QA report must be written inside case_dir: {output}", file=sys.stderr)
        return 2

    decks = [("executive", args.executive), ("full-critical", args.full_critical)]
    errors: list[str] = []
    for _, pptx in decks:
        if not pptx.is_file():
            errors.append(f"missing deck: {pptx}")
        elif not inside(pptx, case_dir):
            errors.append(f"deck must live inside case_dir: {pptx}")
    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 2

    coverage = []
    for label, pptx in decks:
        entry, deck_errors = check_deck(label, pptx, args.preview_root / label)
        coverage.append(entry)
        errors.extend(deck_errors)

    status = "pass" if not errors and not args.issue else "fail"
    report = {
        "status": status,
        "mode": args.mode,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": args.reviewer.strip(),
        "reviewed_files": [str(pptx.resolve()) for _, pptx in decks],
        "coverage": coverage,
        "issues": list(args.issue),
        "notes": list(args.note),
        "blocking_errors": errors,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if status != "pass":
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        for item in args.issue:
            print(f"ERROR: reviewer recorded issue: {item}", file=sys.stderr)
        print(json.dumps({"status": status, "report": str(output)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({"status": status, "report": str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
