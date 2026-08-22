#!/usr/bin/env python3
"""Run final PPTX checks, validate workbook audit, and record F2/F3."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# A blocked case is delivered on the strength of its refusals, so the gate asserts
# the mode invariant in both directions: a blocked audit must not read "OK", and a
# full/degraded audit must not hide behind the blocked verdict.
MODEL_CHECKS_BY_MODE = {
    "full": "OK",
    "degraded": "OK",
    "blocked": "BLOCKED_AS_DESIGNED",
}


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def workbook_audit_error(audit: dict, mode: str) -> str | None:
    """Return why this audit cannot be delivered in ``mode``, or None if it can.

    Kept as a pure function so the gate can be tested without building real
    workbooks -- the mode/verdict mismatch that made blocked cases undeliverable
    was invisible to tests that only grepped this file's source.
    """
    if audit.get("factbase", {}).get("formula_error_count") != 0:
        return "Factbase formula audit failed"
    model_audit = audit.get("model", {})
    if model_audit.get("formula_error_count") != 0:
        return "financial model formula audit failed"
    expected = MODEL_CHECKS_BY_MODE.get(mode)
    actual = model_audit.get("model_checks")
    if actual != expected:
        return (
            f"financial model audit failed: mode={mode} requires "
            f"model_checks={expected!r}, got {actual!r}"
        )
    if mode == "blocked" and model_audit.get("formula_count_in_base_forecast") != 0:
        return (
            "blocked mode must not emit base-forecast formulas; got "
            f"{model_audit.get('formula_count_in_base_forecast')!r}"
        )
    return None


def visual_qa_error(visual_qa: dict, executive: Path, full_critical: Path) -> str | None:
    """Return why this visual QA report cannot close F3, or None if it can."""
    if visual_qa.get("status") != "pass":
        return "visual QA report must have status=pass"
    reviewed_files = {
        Path(item).resolve()
        for item in visual_qa.get("reviewed_files", [])
        if isinstance(item, str) and item
    }
    missing = [
        item for item in (executive.resolve(), full_critical.resolve())
        if item not in reviewed_files
    ]
    if missing:
        return f"visual QA report does not cover both decks: {missing}"
    return None


def run_qa(script: Path, pptx: Path, full: bool, mode: str) -> dict:
    command = [sys.executable, str(script), str(pptx), "--mode", mode] + (["--full"] if full else [])
    result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True)
    return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def runner_set(runner: Path, case_dir: Path, module: str, evidence: list[Path], artifacts: list[Path], reason: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(runner), "set", str(case_dir), module, "complete", "--reason", reason]
    for item in evidence:
        command.extend(["--evidence", str(item)])
    for item in artifacts:
        command.extend(["--artifact", str(item)])
    return subprocess.run(command, text=True, encoding="utf-8", capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--context-package", type=Path, required=True)
    parser.add_argument("--factbase", type=Path, required=True)
    parser.add_argument("--financial-model", type=Path, required=True)
    parser.add_argument("--executive", type=Path, required=True)
    parser.add_argument("--full-critical", type=Path, required=True)
    parser.add_argument("--workbook-audit", type=Path, required=True)
    parser.add_argument("--visual-qa-report", type=Path, required=True)
    parser.add_argument("--mode", choices=("full", "degraded", "blocked"), default="full")
    args = parser.parse_args()
    case_dir = args.case_dir.resolve()
    paths = [args.context_package, args.factbase, args.financial_model, args.executive, args.full_critical, args.workbook_audit, args.visual_qa_report]
    for item in paths:
        if not item.is_file() or not inside(item, case_dir):
            print(f"ERROR: required delivery file must exist inside case_dir: {item}", file=sys.stderr)
            return 2
    audit = json.loads(args.workbook_audit.read_text(encoding="utf-8"))
    audit_error = workbook_audit_error(audit, args.mode)
    if audit_error:
        print(f"ERROR: {audit_error}", file=sys.stderr)
        return 2
    visual_qa = json.loads(args.visual_qa_report.read_text(encoding="utf-8"))
    visual_error = visual_qa_error(visual_qa, args.executive, args.full_critical)
    if visual_error:
        print(f"ERROR: {visual_error}", file=sys.stderr)
        return 2
    qa_script = Path(__file__).with_name("qa_deck.py")
    executive_qa = run_qa(qa_script, args.executive, False, args.mode)
    full_qa = run_qa(qa_script, args.full_critical, True, args.mode)
    report = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "workbook_audit": audit,
        "executive_qa": executive_qa,
        "full_critical_qa": full_qa,
        "visual_qa_required": True,
        "visual_qa": visual_qa,
        "visual_qa_report": str(args.visual_qa_report.resolve()),
    }
    report_path = case_dir / "outputs" / "delivery_qa.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if executive_qa["returncode"] or full_qa["returncode"]:
        print(json.dumps(report, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2
    runner = Path(__file__).with_name("evaluator_runner.py")
    f2 = runner_set(
        runner, case_dir, "F2", [args.context_package],
        [args.factbase, args.financial_model, args.executive, args.full_critical],
        "Neutral style render completed from frozen ContextPackage",
    )
    if f2.returncode:
        print(f2.stderr or f2.stdout, file=sys.stderr)
        return f2.returncode
    f3 = runner_set(
        runner, case_dir, "F3", [args.workbook_audit, args.visual_qa_report, report_path], [report_path],
        "Workbook audit, PPTX structural QA, and evidenced visual preview inspection complete",
    )
    if f3.returncode:
        print(f3.stderr or f3.stdout, file=sys.stderr)
        return f3.returncode
    verify = subprocess.run([sys.executable, str(runner), "verify", str(case_dir), "--json"], text=True, encoding="utf-8", capture_output=True)
    if verify.returncode:
        print(verify.stderr or verify.stdout, file=sys.stderr)
        return verify.returncode
    status = json.loads(verify.stdout)
    if status.get("gates", {}).get("F_GATE") != "complete":
        print("ERROR: delivery recorded but F_GATE is not complete", file=sys.stderr)
        return 2
    print(json.dumps({"status": "complete", "F_GATE": "complete", "delivery_qa": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
