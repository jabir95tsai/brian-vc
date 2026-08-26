#!/usr/bin/env python3
"""Create and maintain the Stage A-F evaluator artifact manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


# Module names, reasons and evidence are written in Chinese, and print_status
# joins them with an em dash. On a Windows console whose locale is not UTF-8
# (cp950 here) Python would encode that output in the locale codec, so a caller
# capturing stdout as UTF-8 gets a decode error and — because the failure lands
# in subprocess's reader thread — an empty capture next to a zero exit code.
# Pin the streams to UTF-8 so output does not depend on the caller's locale.
for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")


VALID_STATES = {
    "pending",
    "in_progress",
    "complete",
    "partial",
    "blocked",
    "not_applicable",
}
TERMINAL_OK = {"complete", "not_applicable"}
FAILURE_STATES = {"partial", "blocked"}
# Some modules owe a specific, machine-checkable fact at completion, not just
# "some evidence". Enforcing it here catches the omission when the module
# claims to be done, instead of much later when the workbook is assembled.
# Each entry maps a module to (evidence key, accepted values or markers, hint).
PEER_LIST_SOURCES = ("user_specified", "auto")
REDTEAM_HANDOFF_MARKER = "GP 決策框架已留白供填入"
# match="exact": the value must be one of the accepted tokens outright. A
# substring test here would accept "not_auto_at_all" because it contains
# "auto". match="contains": the value is free prose that must carry a marker.
COMPLETION_EVIDENCE_KEYS = {
    "D1": (
        "peer_list_source",
        PEER_LIST_SOURCES,
        "exact",
        "record how the comparable list was chosen, e.g. "
        "--evidence peer_list_source=user_specified",
    ),
    "E2": (
        "redteam_handoff",
        (REDTEAM_HANDOFF_MARKER,),
        "contains",
        "record the E2 handoff sentence from references/experts/redteam.md, e.g. "
        "--evidence \"redteam_handoff=RedTeam 提出 5 個反對理由，...，"
        f"{REDTEAM_HANDOFF_MARKER}。\"",
    ),
}
MAX_FAILED_ATTEMPTS = 2
NOT_APPLICABLE_MODULES = {"B2"}
GATE_MODULES = {
    "A_GATE": ("A1", "A2"),
    "B_GATE": ("B1", "B2", "B3"),
    "C_GATE": ("C1", "C2", "C3", "C4"),
    "D_GATE": ("D1", "D2", "D3"),
    "E_GATE": ("E1", "E2", "E3"),
    "F_GATE": ("F1", "F2", "F3"),
}

SCRIPT = Path(__file__).resolve()
SKILL_ROOT = SCRIPT.parents[1]
PLUGIN_ROOT = SCRIPT.parents[3]
PIPELINE_CONTRACT = SKILL_ROOT / "references" / "pipeline_contract.md"
PLUGIN_MANIFEST = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
STATE_DIR = ".vc-evaluator"
STATE_FILE = "artifact-manifest.json"


class RunnerError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RunnerError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RunnerError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def parse_dependency_manifest(text: str) -> dict[str, list[str]]:
    match = re.search(
        r"<!-- DEPENDENCY-MANIFEST-BEGIN -->\s*(.*?)\s*"
        r"<!-- DEPENDENCY-MANIFEST-END -->",
        text,
        flags=re.DOTALL,
    )
    if not match:
        raise RunnerError("pipeline dependency manifest is missing")
    dependencies: dict[str, list[str]] = {}
    for raw in match.group(1).splitlines():
        line = raw.strip()
        if not line:
            continue
        module_id, separator, upstream = line.partition("<-")
        if not separator:
            raise RunnerError(f"invalid dependency line: {line}")
        dependencies[module_id.strip()] = [
            item.strip() for item in upstream.split(",") if item.strip()
        ]
    return dependencies


def parse_registry(text: str) -> dict[str, dict[str, str]]:
    registry: dict[str, dict[str, str]] = {}
    for raw in text.splitlines():
        if not re.match(r"^\|\s*[A-F]\d\s*\|", raw):
            continue
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        if len(cells) != 7:
            raise RunnerError(f"invalid module registry row: {raw}")
        module_id, name, owner, inputs, artifacts, evidence, blocks = cells
        registry[module_id] = {
            "name": name,
            "owner": owner,
            "required_inputs": inputs,
            "declared_artifacts": artifacts,
            "completion_contract": evidence,
            "blocks": blocks,
        }
    if len(registry) != 19:
        raise RunnerError(f"expected 19 modules, found {len(registry)}")
    return registry


def load_contract() -> tuple[str, dict[str, dict[str, str]], dict[str, list[str]]]:
    text = PIPELINE_CONTRACT.read_text(encoding="utf-8")
    registry = parse_registry(text)
    dependencies = parse_dependency_manifest(text)
    if list(registry) != list(dependencies):
        raise RunnerError("module registry and dependency manifest order differ")
    return text, registry, dependencies


def state_path(case_root: Path) -> Path:
    return case_root / STATE_DIR / STATE_FILE


def normalize_case_root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def load_state(case_root: Path) -> dict[str, Any]:
    path = state_path(case_root)
    if not path.is_file():
        raise RunnerError(f"manifest not initialized: {path}")
    state = read_json(path)
    if state.get("case_root") != str(case_root):
        raise RunnerError("manifest case_root does not match requested directory")
    return state


def gate_status(state: dict[str, Any], gate: str) -> str:
    modules = state["modules"]
    statuses = [modules[module_id]["status"] for module_id in GATE_MODULES[gate]]
    if all(status in TERMINAL_OK for status in statuses):
        return "complete"
    if any(status == "blocked" for status in statuses):
        return "blocked"
    if any(status == "partial" for status in statuses):
        return "partial"
    if any(status == "in_progress" for status in statuses):
        return "in_progress"
    return "pending"


def all_gate_statuses(state: dict[str, Any]) -> dict[str, str]:
    return {gate: gate_status(state, gate) for gate in GATE_MODULES}


def dependency_satisfied(state: dict[str, Any], token: str) -> bool:
    if token == "ROOT":
        return True
    optional = token.endswith("?")
    base = token[:-1] if optional else token
    if base in GATE_MODULES:
        return gate_status(state, base) == "complete"
    status = state["modules"][base]["status"]
    if optional:
        return status in TERMINAL_OK
    return status == "complete"


def unmet_dependencies(state: dict[str, Any], module_id: str) -> list[str]:
    return [
        token
        for token in state["modules"][module_id]["dependencies"]
        if not dependency_satisfied(state, token)
    ]


def artifact_record(case_root: Path, raw_path: str) -> dict[str, Any]:
    path = Path(raw_path)
    if not path.is_absolute():
        path = case_root / path
    path = path.resolve()
    try:
        relative = path.relative_to(case_root)
    except ValueError as exc:
        raise RunnerError(f"artifact must stay inside case directory: {path}") from exc
    if not path.is_file():
        raise RunnerError(f"artifact does not exist: {path}")
    return {
        "path": relative.as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "recorded_at": now_iso(),
    }


def init_state(case_root: Path, case_id: str, mode: str, force: bool) -> dict[str, Any]:
    path = state_path(case_root)
    if path.exists() and not force:
        raise RunnerError(f"manifest already exists: {path}")
    case_root.mkdir(parents=True, exist_ok=True)
    contract_text, registry, dependencies = load_contract()
    plugin = read_json(PLUGIN_MANIFEST)
    timestamp = now_iso()
    modules: dict[str, dict[str, Any]] = {}
    for module_id, contract in registry.items():
        modules[module_id] = {
            **contract,
            "stage": module_id[0],
            "dependencies": dependencies[module_id],
            "status": "pending",
            "reason": "",
            "evidence": [],
            "artifacts": [],
            "failed_attempts": 0,
            "retry_exhausted": False,
            "updated_at": timestamp,
        }
    state = {
        "schema_version": 2,
        "case_id": case_id,
        "case_root": str(case_root),
        "mode": mode,
        "plugin": {"name": plugin.get("name"), "version": plugin.get("version")},
        "contract": {
            "path": str(PIPELINE_CONTRACT.relative_to(PLUGIN_ROOT).as_posix()),
            "sha256": hashlib.sha256(contract_text.encode("utf-8")).hexdigest(),
        },
        "created_at": timestamp,
        "updated_at": timestamp,
        "modules": modules,
    }
    write_json(path, state)
    return state


def missing_completion_evidence(module_id: str, evidence_values: list[str]) -> str | None:
    """Return an actionable message when a module completes without its key fact."""
    requirement = COMPLETION_EVIDENCE_KEYS.get(module_id)
    if requirement is None:
        return None
    key, accepted, match, hint = requirement
    prefix = f"{key}="
    declared = [item for item in evidence_values if item.startswith(prefix)]
    if not declared:
        return f"{module_id} complete requires evidence '{prefix}...'; {hint}"
    value = declared[0][len(prefix):].strip()
    if match == "exact":
        ok = value in accepted
        expectation = "expected exactly one of: " + ", ".join(accepted)
    else:
        ok = any(token in value for token in accepted)
        expectation = "expected it to contain: " + ", ".join(accepted)
    if not ok:
        return f"{module_id} evidence '{prefix}{value}' is not acceptable; {expectation}"
    return None


def set_module_state(
    state: dict[str, Any],
    case_root: Path,
    module_id: str,
    status: str,
    reason: str,
    evidence: Iterable[str],
    artifacts: Iterable[str],
) -> None:
    if module_id not in state["modules"]:
        raise RunnerError(f"unknown module: {module_id}")
    if status not in VALID_STATES:
        raise RunnerError(f"invalid state: {status}")
    module = state["modules"][module_id]
    evidence_values = [item.strip() for item in evidence if item.strip()]
    artifact_values = [artifact_record(case_root, item) for item in artifacts]

    if status in {"in_progress", "complete", "not_applicable"}:
        unmet = unmet_dependencies(state, module_id)
        if unmet:
            raise RunnerError(f"{module_id} has unmet dependencies: {', '.join(unmet)}")
    if status == "complete" and (not evidence_values or not artifact_values):
        raise RunnerError("complete requires at least one evidence item and artifact")
    if status == "complete":
        problem = missing_completion_evidence(module_id, evidence_values)
        if problem:
            raise RunnerError(problem)
    if status == "not_applicable":
        if module_id not in NOT_APPLICABLE_MODULES:
            raise RunnerError(f"not_applicable is not allowed for {module_id}")
        if not reason or not evidence_values:
            raise RunnerError("not_applicable requires reason and evidence")
    if status in FAILURE_STATES and not reason:
        raise RunnerError(f"{status} requires a reason")
    if status in FAILURE_STATES and module.get("retry_exhausted"):
        raise RunnerError(
            f"{module_id} already failed {MAX_FAILED_ATTEMPTS} times "
            f"({module.get('reason') or 'no reason recorded'}); retry limit reached. "
            "Report the failure to the user, or reset the module to pending to rerun it."
        )

    if status == "pending":
        module["evidence"] = []
        module["artifacts"] = []
    else:
        if evidence_values:
            module["evidence"] = evidence_values
        if artifact_values:
            module["artifacts"] = artifact_values
    if status in FAILURE_STATES:
        module["failed_attempts"] = int(module.get("failed_attempts", 0)) + 1
        module["retry_exhausted"] = module["failed_attempts"] >= MAX_FAILED_ATTEMPTS
    elif status in TERMINAL_OK or status == "pending":
        module["failed_attempts"] = 0
        module["retry_exhausted"] = False

    module["status"] = status
    module["reason"] = reason
    module["updated_at"] = now_iso()
    state["updated_at"] = module["updated_at"]


def reverse_dependencies(state: dict[str, Any], changed: str) -> list[str]:
    affected: list[str] = []
    queue = [changed]
    while queue:
        upstream = queue.pop(0)
        for module_id, module in state["modules"].items():
            if module_id in affected or module_id == changed:
                continue
            tokens = {token.rstrip("?") for token in module["dependencies"]}
            direct = upstream in tokens
            gate_hit = any(
                gate in tokens and upstream in GATE_MODULES[gate] for gate in GATE_MODULES
            )
            if direct or gate_hit:
                affected.append(module_id)
                queue.append(module_id)
    return affected


def verify_state(state: dict[str, Any], case_root: Path, invalidate: bool) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    contract_text = PIPELINE_CONTRACT.read_text(encoding="utf-8")
    current_contract_hash = hashlib.sha256(contract_text.encode("utf-8")).hexdigest()
    if current_contract_hash != state["contract"]["sha256"]:
        issues.append({"scope": "contract", "detail": "pipeline contract changed"})

    stale_modules: set[str] = set()
    for module_id, module in state["modules"].items():
        if module.get("retry_exhausted"):
            issues.append(
                {
                    "scope": module_id,
                    "detail": (
                        f"retry limit reached after {module.get('failed_attempts', 0)} "
                        f"failed attempts: {module.get('reason') or 'no reason recorded'}"
                    ),
                }
            )
        if module["status"] == "complete":
            unmet = unmet_dependencies(state, module_id)
            if unmet:
                issues.append(
                    {
                        "scope": module_id,
                        "detail": f"completed with unmet dependencies: {', '.join(unmet)}",
                    }
                )
                stale_modules.add(module_id)
        for artifact in module["artifacts"]:
            path = (case_root / artifact["path"]).resolve()
            if not path.is_file():
                issues.append({"scope": module_id, "detail": f"missing {artifact['path']}"})
                stale_modules.add(module_id)
                continue
            digest = sha256_file(path)
            if digest != artifact["sha256"]:
                issues.append({"scope": module_id, "detail": f"changed {artifact['path']}"})
                stale_modules.add(module_id)

    if invalidate and stale_modules:
        timestamp = now_iso()
        for module_id in sorted(stale_modules):
            module = state["modules"][module_id]
            module["status"] = "partial"
            module["reason"] = "recorded artifact is missing or changed"
            module["updated_at"] = timestamp
            for downstream in reverse_dependencies(state, module_id):
                target = state["modules"][downstream]
                target["status"] = "pending"
                target["reason"] = f"invalidated by stale upstream {module_id}"
                target["evidence"] = []
                target["artifacts"] = []
                target["updated_at"] = timestamp
        state["updated_at"] = timestamp
        write_json(state_path(case_root), state)

    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "gates": all_gate_statuses(state),
    }


def status_report(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": state["case_id"],
        "mode": state["mode"],
        "updated_at": state["updated_at"],
        "gates": all_gate_statuses(state),
        "modules": {
            module_id: {
                "name": module["name"],
                "status": module["status"],
                "reason": module["reason"],
                "artifact_count": len(module["artifacts"]),
                "failed_attempts": int(module.get("failed_attempts", 0)),
                "retry_exhausted": bool(module.get("retry_exhausted")),
                "unmet_dependencies": unmet_dependencies(state, module_id),
            }
            for module_id, module in state["modules"].items()
        },
    }


def print_status(report: dict[str, Any]) -> None:
    print(f"case_id: {report['case_id']}")
    print(f"mode: {report['mode']}")
    print("gates: " + ", ".join(f"{key}={value}" for key, value in report["gates"].items()))
    for module_id, module in report["modules"].items():
        detail = f" — {module['reason']}" if module["reason"] else ""
        if module.get("retry_exhausted"):
            detail += (
                f" [retry limit reached after {module['failed_attempts']} attempts"
                " — escalate, do not rerun automatically]"
            )
        print(f"{module_id} {module['status']}: {module['name']}{detail}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="initialize an evaluator case manifest")
    init.add_argument("case_dir")
    init.add_argument("--case-id", required=True)
    init.add_argument("--mode", choices=("full", "degraded", "blocked"), default="full")
    init.add_argument("--force", action="store_true")
    init.add_argument("--json", action="store_true")

    set_state = subparsers.add_parser("set", help="record a module state transition")
    set_state.add_argument("case_dir")
    set_state.add_argument("module_id")
    set_state.add_argument("status", choices=sorted(VALID_STATES))
    set_state.add_argument("--reason", default="")
    set_state.add_argument("--evidence", action="append", default=[])
    set_state.add_argument("--artifact", action="append", default=[])
    set_state.add_argument("--json", action="store_true")

    verify = subparsers.add_parser("verify", help="verify recorded artifacts and dependencies")
    verify.add_argument("case_dir")
    verify.add_argument("--invalidate-stale", action="store_true")
    verify.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="show module and gate status")
    status.add_argument("case_dir")
    status.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    case_root = normalize_case_root(args.case_dir)
    try:
        if args.command == "init":
            state = init_state(case_root, args.case_id, args.mode, args.force)
            report = status_report(state)
        elif args.command == "set":
            state = load_state(case_root)
            set_module_state(
                state,
                case_root,
                args.module_id,
                args.status,
                args.reason,
                args.evidence,
                args.artifact,
            )
            write_json(state_path(case_root), state)
            report = status_report(state)
        elif args.command == "verify":
            state = load_state(case_root)
            report = verify_state(state, case_root, args.invalidate_stale)
        else:
            report = status_report(load_state(case_root))
    except RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif args.command == "verify":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_status(report)
    return 0 if report.get("status", "pass") != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
