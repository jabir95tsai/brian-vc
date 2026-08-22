#!/usr/bin/env python3
"""Validate that the installed brian-vc plugin can start all three workflows."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


REQUIRED_SKILLS = (
    "vc-quick-screen",
    "prospectus-extractor",
    "vc-investment-evaluator",
)

PYTHON_DEPENDENCIES = {
    "docx": "python-docx>=1.2,<2",
    "pptx": "python-pptx>=1.0,<2",
    "pypdf": "pypdf>=5,<7",
    "fitz": "PyMuPDF>=1.24,<2",
    "openpyxl": "openpyxl>=3.1,<4",
}


def check(condition: bool, label: str, detail: str = "") -> dict[str, Any]:
    return {
        "label": label,
        "status": "pass" if condition else "fail",
        "detail": detail,
    }


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def validate_marketplace(repo_root: Path, plugin_root: Path) -> tuple[bool, str]:
    marketplace_path = repo_root / ".agents" / "plugins" / "marketplace.json"
    if not marketplace_path.is_file():
        return False, str(marketplace_path)
    try:
        marketplace = load_json(marketplace_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return False, str(exc)
    for entry in marketplace.get("plugins", []):
        if not isinstance(entry, dict) or entry.get("name") != "brian-vc":
            continue
        source = entry.get("source", {})
        if not isinstance(source, dict):
            return False, "brian-vc source must be an object"
        relative = source.get("path")
        if not isinstance(relative, str) or not relative.startswith("./"):
            return False, "brian-vc source.path must start with ./"
        resolved = (repo_root / relative[2:]).resolve()
        return resolved == plugin_root.resolve(), f"{relative} -> {resolved}"
    return False, "brian-vc entry not found"


def validate_skill(plugin_root: Path, skill_name: str) -> list[dict[str, Any]]:
    skill_root = plugin_root / "skills" / skill_name
    skill_md = skill_root / "SKILL.md"
    metadata = skill_root / "agents" / "openai.yaml"
    results = [
        check(skill_md.is_file(), f"{skill_name}: SKILL.md", str(skill_md)),
        check(metadata.is_file(), f"{skill_name}: agents/openai.yaml", str(metadata)),
    ]
    if skill_md.is_file():
        body = skill_md.read_text(encoding="utf-8")
        results.append(
            check(
                f"name: {skill_name}" in body[:1000],
                f"{skill_name}: frontmatter name",
            )
        )
    if metadata.is_file():
        body = metadata.read_text(encoding="utf-8")
        results.append(
            check(
                f"${skill_name}" in body,
                f"{skill_name}: default prompt",
            )
        )
    return results


def validate_artifact_runtime() -> dict[str, Any]:
    modules = os.environ.get("RUNTIME_NODE_MODULES")
    if not modules:
        return {
            "label": "managed @oai/artifact-tool runtime",
            "status": "managed",
            "detail": "load workspace dependencies before Excel/PPTX authoring",
        }
    package = Path(modules) / "@oai" / "artifact-tool"
    return check(package.exists(), "managed @oai/artifact-tool runtime", str(package))


def run_checks(skip_python_deps: bool, strict_python_deps: bool) -> dict[str, Any]:
    plugin_root = Path(__file__).resolve().parents[1]
    repo_root = plugin_root.parent
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    results: list[dict[str, Any]] = []

    try:
        manifest = load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        manifest = {}
        results.append(check(False, "plugin manifest", str(exc)))
    else:
        results.append(
            check(
                manifest.get("name") == plugin_root.name == "brian-vc",
                "plugin manifest identity",
                f"folder={plugin_root.name}; manifest={manifest.get('name')}",
            )
        )
        results.append(
            check(manifest.get("skills") == "./skills/", "plugin skills path")
        )

    marketplace_path = repo_root / ".agents" / "plugins" / "marketplace.json"
    if marketplace_path.is_file():
        market_ok, market_detail = validate_marketplace(repo_root, plugin_root)
        results.append(check(market_ok, "repo marketplace", market_detail))
    else:
        results.append(
            {
                "label": "repo marketplace",
                "status": "managed",
                "detail": "not present beside installed plugin copy; package-local checks continue",
            }
        )

    for skill_name in REQUIRED_SKILLS:
        results.extend(validate_skill(plugin_root, skill_name))

    shared_files = (
        plugin_root / "assets" / "styles" / "neutral" / "style.json",
        plugin_root / "scripts" / "resolve_style.py",
        plugin_root
        / "skills"
        / "vc-investment-evaluator"
        / "references"
        / "pipeline_contract.md",
    )
    for path in shared_files:
        results.append(check(path.is_file(), f"shared resource: {path.name}", str(path)))

    if not skip_python_deps:
        for module, requirement in PYTHON_DEPENDENCIES.items():
            available = importlib.util.find_spec(module) is not None
            if available:
                results.append(check(True, f"Python dependency: {module}", requirement))
            elif strict_python_deps:
                results.append(check(False, f"Python dependency: {module}", requirement))
            else:
                results.append(
                    {
                        "label": f"Python dependency: {module}",
                        "status": "managed",
                        "detail": f"not in this interpreter; use a managed runtime or install {requirement}",
                    }
                )

    results.append(validate_artifact_runtime())
    failed = [item for item in results if item["status"] == "fail"]
    return {
        "plugin_root": str(plugin_root),
        "status": "pass" if not failed else "fail",
        "results": results,
        "install_command": f'python -m pip install -r "{plugin_root / "requirements.txt"}"',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    dependency_mode = parser.add_mutually_exclusive_group()
    dependency_mode.add_argument(
        "--skip-python-deps",
        action="store_true",
        help="validate packaging without importing optional standalone dependencies",
    )
    dependency_mode.add_argument(
        "--strict-python-deps",
        action="store_true",
        help="fail unless every standalone Python dependency is importable",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    report = run_checks(args.skip_python_deps, args.strict_python_deps)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for item in report["results"]:
            marker = {"pass": "PASS", "fail": "FAIL", "managed": "INFO"}[item["status"]]
            suffix = f" — {item['detail']}" if item.get("detail") else ""
            print(f"[{marker}] {item['label']}{suffix}")
        managed_python = any(
            item["status"] == "managed" and item["label"].startswith("Python dependency:")
            for item in report["results"]
        )
        if report["status"] == "fail" or managed_python:
            print(f"\nStandalone dependency command:\n{report['install_command']}")
        print(f"\nPreflight: {report['status'].upper()}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
