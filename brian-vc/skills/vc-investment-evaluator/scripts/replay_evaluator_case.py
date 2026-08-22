#!/usr/bin/env python3
"""One-command deterministic replay from frozen evaluator JSON to all deliverables and QA."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


SCRIPT_DIR = Path(__file__).resolve().parent


class ReplayError(RuntimeError):
    pass


# Modules this script can honestly satisfy on its own. Everything else is a
# semantic reading of the data room, so replay records that they are still open
# instead of stamping them complete.
SCRIPTED_MODULES = frozenset({"F2", "F3"})


def ensure_case_manifest(case_dir: Path, payload: dict[str, Any], mode: str) -> dict[str, Any]:
    """Create the Stage A-F ledger if absent and report what is still open.

    Without this the replay leaves no manifest at all, so the delivery verifier
    fails with "manifest not initialized" and no report explains why the case can
    never reach ready_for_delivery.
    """
    runner = SCRIPT_DIR / "evaluator_runner.py"
    manifest = case_dir / ".vc-evaluator" / "artifact-manifest.json"
    if not manifest.is_file():
        case_id = payload.get("meta", {}).get("case_id") or case_dir.resolve().name
        case_dir.mkdir(parents=True, exist_ok=True)
        run([sys.executable, str(runner), "init", str(case_dir), "--case-id", str(case_id), "--mode", mode])
    status = parse_json_output(run([sys.executable, str(runner), "status", str(case_dir), "--json"]))
    modules = status.get("modules", {})
    open_modules = sorted(
        name for name, state in modules.items()
        if (state.get("status") if isinstance(state, dict) else state) not in {"complete", "not_applicable"}
    )
    return {"manifest": str(manifest.resolve()), "gates": status.get("gates", {}), "open_modules": open_modules}


def run(command: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    child_env = (env or os.environ.copy()).copy()
    child_env["PYTHONUTF8"] = "1"
    result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, env=child_env)
    if result.returncode:
        raise ReplayError(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stderr or result.stdout}")
    return result


def parse_json_output(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    text = (result.stdout or "").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        start = text.rfind("\n{")
        if start >= 0:
            try:
                value = json.loads(text[start + 1 :])
            except json.JSONDecodeError:
                raise ReplayError(f"expected JSON output, got:\n{text}") from exc
        else:
            raise ReplayError(f"expected JSON output, got:\n{text}") from exc
    if not isinstance(value, dict):
        raise ReplayError("expected a JSON object from builder")
    return value


def discover_node(explicit: Path | None) -> Path:
    if explicit:
        return explicit.resolve()
    found = shutil.which("node")
    if found:
        return Path(found).resolve()
    candidate = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe"
    if candidate.is_file():
        return candidate
    raise ReplayError("Node.js not found; pass --node or run inside the Codex managed runtime")


def discover_modules(explicit: Path | None, node: Path) -> Path:
    candidates = [
        explicit,
        Path(os.environ["CODEX_NODE_MODULES"]) if os.environ.get("CODEX_NODE_MODULES") else None,
        node.parent.parent / "node_modules",
        Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules",
    ]
    for candidate in candidates:
        if candidate and (candidate / "@oai/artifact-tool").exists():
            return candidate.resolve()
    raise ReplayError("@oai/artifact-tool not found; pass --node-modules")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="frozen evaluator case JSON")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--mode", choices=("full", "degraded", "blocked"))
    parser.add_argument("--node", type=Path)
    parser.add_argument("--node-modules", type=Path)
    parser.add_argument("--skip-preview", action="store_true")
    parser.add_argument(
        "--case-dir",
        type=Path,
        default=None,
        help="Case root holding .vc-evaluator/. Defaults to the parent of --output-dir.",
    )
    args = parser.parse_args()
    if args.case_dir is None:
        args.case_dir = args.output_dir.parent

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "evaluator_replay_report.json"
    report: dict[str, Any] = {
        "status": "in_progress",
        "status_scope": "pipeline_execution",
        "pipeline_status": "in_progress",
        "dd_status": "unknown",
        "structural_qa_status": "not_run",
        "visual_qa_status": "required_not_recorded",
        "delivery_status": "pending_pipeline",
        "ready_for_delivery": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "steps": [],
    }
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if args.mode:
            payload["mode"] = args.mode
        mode = payload.get("mode", payload.get("meta", {}).get("mode", "full"))
        report["mode"] = mode
        report["dd_status"] = mode
        replay_dir = args.output_dir / ".replay"
        replay_dir.mkdir(parents=True, exist_ok=True)
        normalized = replay_dir / "input_case.json"
        normalized.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        prepared = replay_dir / "prepared_case.json"
        run([sys.executable, str(SCRIPT_DIR / "prepare_workbook_input.py"), str(normalized), str(prepared)])
        report["steps"].append({"name": "prepare", "status": "pass", "output": str(prepared)})

        node = discover_node(args.node)
        modules = discover_modules(args.node_modules, node)
        env = os.environ.copy()
        env["CODEX_NODE_MODULES"] = str(modules)
        preview_args = [] if args.skip_preview else ["--preview-dir", str(args.output_dir / "previews" / "workbooks")]
        workbook_result = parse_json_output(run([
            str(node), str(SCRIPT_DIR / "build_evaluator_workbooks.mjs"),
            "--input", str(prepared), "--output-dir", str(args.output_dir), *preview_args,
        ], env))
        report["steps"].append({"name": "workbooks", "status": "pass", "outputs": workbook_result})

        audit_path = args.output_dir / "workbook_audit.json"
        audit = parse_json_output(run([
            str(node), str(SCRIPT_DIR / "verify_evaluator_workbooks.mjs"),
            "--factbase", workbook_result["factbase"], "--model", workbook_result["financial_model"], "--output", str(audit_path),
            "--mode", mode,
        ], env))
        report["steps"].append({"name": "workbook_qa", "status": "pass", "output": str(audit_path), "summary": audit})

        deck_args = [] if args.skip_preview else ["--preview-dir", str(args.output_dir / "previews" / "decks")]
        deck_result = parse_json_output(run([
            str(node), str(SCRIPT_DIR / "build_investment_decks.mjs"),
            "--input", str(prepared), "--output-dir", str(args.output_dir), *deck_args,
        ], env))
        report["steps"].append({"name": "decks", "status": "pass", "outputs": deck_result})

        legacy = parse_json_output(run([
            sys.executable, str(SCRIPT_DIR / "build_legacy_parity_artifacts.py"), str(prepared), str(args.output_dir / "legacy-parity"),
        ]))
        report["steps"].append({"name": "legacy_parity", "status": "pass", "outputs": legacy})

        qa_outputs = {}
        for variant, full in (("executive", False), ("full", True)):
            qa_path = args.output_dir / f"deck_qa_{variant}.json"
            command = [sys.executable, str(SCRIPT_DIR / "qa_deck.py"), deck_result[variant]["output"], "--mode", mode, "--json-output", str(qa_path)]
            if full:
                command.append("--full")
            qa_outputs[variant] = parse_json_output(run(command))
        report["steps"].append({"name": "deck_qa", "status": "pass", "outputs": qa_outputs})

        ledger = ensure_case_manifest(args.case_dir, payload, mode)
        report["steps"].append({"name": "case_manifest", "status": "pass", "output": ledger["manifest"]})
        report["case_dir"] = str(args.case_dir.resolve())
        report["gates"] = ledger["gates"]
        report["open_modules"] = ledger["open_modules"]
        report["analyst_owned_open_modules"] = [
            module for module in ledger["open_modules"] if module not in SCRIPTED_MODULES
        ]

        report["status"] = "complete"
        report["pipeline_status"] = "complete"
        report["structural_qa_status"] = "pass"
        report["delivery_status"] = "pending_visual_qa"
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        report["outputs"] = {
            "prepared_case": str(prepared),
            "factbase": workbook_result["factbase"],
            "financial_model": workbook_result["financial_model"],
            "executive_deck": deck_result["executive"]["output"],
            "full_critical_deck": deck_result["full"]["output"],
            "legacy_parity_manifest": legacy["manifest"],
            "workbook_audit": str(audit_path),
        }
    except (OSError, KeyError, ValueError, json.JSONDecodeError, ReplayError) as exc:
        report["status"] = "failed"
        report["pipeline_status"] = "failed"
        report["delivery_status"] = "blocked"
        report["error"] = str(exc)
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
