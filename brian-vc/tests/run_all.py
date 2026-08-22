#!/usr/bin/env python3
"""Deterministic regression suite for the complete three-skill plugin."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    ["scripts/preflight.py", "--skip-python-deps"],
    ["tests/plugin/test_preflight.py"],
    ["tests/plugin/test_route_case.py"],
    ["tests/plugin/test_prompt_routing_contract.py"],
    ["tests/plugin/test_install_copy.py"],
    ["tests/vc-quick-screen/run_all_tests.py"],
    ["tests/prospectus-extractor/run_all_tests.py"],
    ["tests/vc-investment-evaluator/check_architecture.py"],
    ["tests/vc-investment-evaluator/test_runner.py"],
    ["tests/vc-investment-evaluator/test_workbook_contract.py"],
    ["tests/vc-investment-evaluator/test_deck_contract.py"],
    ["tests/vc-investment-evaluator/test_canonical_package.py"],
    ["tests/vc-investment-evaluator/test_replay_contract.py"],
    ["tests/vc-investment-evaluator/test_delivery_gate.py"],
    ["tests/vc-investment-evaluator/test_dataroom_ingest.py"],
]


def main() -> int:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    failures = []
    for index, relative in enumerate(COMMANDS, start=1):
        command = [sys.executable, *[str(ROOT / relative[0]), *relative[1:]]]
        print(f"\n[{index:02d}/{len(COMMANDS):02d}] {' '.join(relative)}", flush=True)
        result = subprocess.run(command, cwd=ROOT, env=env, check=False)
        if result.returncode:
            failures.append((relative[0], result.returncode))
            break
    if failures:
        print(f"\nPLUGIN REGRESSION: FAIL — {failures}")
        return 1
    print(f"\nPLUGIN REGRESSION: PASS — {len(COMMANDS)}/{len(COMMANDS)} commands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
