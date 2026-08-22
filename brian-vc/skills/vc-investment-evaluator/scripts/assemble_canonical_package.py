#!/usr/bin/env python3
"""Freeze Stage E content into the single F1 ContextPackage and record it."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_GATES = ("B_GATE", "C_GATE", "D_GATE", "E_GATE")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("prepared_content", type=Path)
    parser.add_argument("--style", default="neutral")
    args = parser.parse_args()
    case_dir = args.case_dir.resolve()
    content = args.prepared_content.resolve()
    state_path = case_dir / ".vc-evaluator" / "artifact-manifest.json"
    if not state_path.is_file():
        print("ERROR: evaluator manifest missing; run evaluator_runner.py init first", file=sys.stderr)
        return 2
    if not content.is_file() or not inside(content, case_dir):
        print("ERROR: prepared_content must exist inside case_dir for reproducible hashing", file=sys.stderr)
        return 2
    state = json.loads(state_path.read_text(encoding="utf-8"))
    runner = Path(__file__).with_name("evaluator_runner.py")
    status_result = subprocess.run(
        [sys.executable, str(runner), "status", str(case_dir), "--json"],
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    if status_result.returncode:
        print(status_result.stderr or status_result.stdout, file=sys.stderr)
        return status_result.returncode
    status_report = json.loads(status_result.stdout)
    gates = status_report["gates"]
    incomplete = [gate for gate in REQUIRED_GATES if gates.get(gate) != "complete"]
    if incomplete:
        print(f"ERROR: cannot freeze; incomplete gates: {', '.join(incomplete)}", file=sys.stderr)
        return 2
    payload = json.loads(content.read_text(encoding="utf-8"))
    for key in ("return_matrix", "independent_forecast", "deck"):
        if key not in payload:
            print(f"ERROR: prepared content missing {key}", file=sys.stderr)
            return 2
    artifacts = []
    for module_id, module in state["modules"].items():
        for artifact in module.get("artifacts", []):
            path_value = artifact.get("path") if isinstance(artifact, dict) else artifact
            if path_value:
                artifacts.append({"module_id": module_id, "path": path_value, "sha256": artifact.get("sha256") if isinstance(artifact, dict) else None})
    package = {
        "schema_version": "1.0",
        "case_id": state["case_id"],
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "content_source": {"path": str(content.relative_to(case_dir).as_posix()), "sha256": sha256(content)},
        "style": args.style,
        "gates": {gate: gates[gate] for gate in REQUIRED_GATES},
        "module_artifacts": artifacts,
        "deliverables": {
            "executive_pptx": "pending F2",
            "full_critical_pptx": "pending F2",
            "factbase_xlsx": "pending F2",
            "financial_model_xlsx": "pending F2",
        },
        "gp_decision": {"entry": None, "conditions": None, "amount": None},
        "disclaimer": "內部研究草稿，非投資建議；最終決策由 GP 作成。",
        "content": payload,
    }
    out_dir = case_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{state['case_id']}_ContextPackage.json"
    out_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    command = [
        sys.executable, str(runner), "set", str(case_dir), "F1", "complete",
        "--evidence", str(content), "--artifact", str(out_path),
        "--reason", "Stage E content frozen into canonical ContextPackage",
    ]
    completed = subprocess.run(command, text=True, encoding="utf-8", capture_output=True)
    if completed.returncode:
        out_path.unlink(missing_ok=True)
        print(completed.stderr or completed.stdout, file=sys.stderr)
        return completed.returncode
    print(json.dumps({"status": "complete", "module": "F1", "context_package": str(out_path), "sha256": sha256(out_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
