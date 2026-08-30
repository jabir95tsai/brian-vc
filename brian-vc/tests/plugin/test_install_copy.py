#!/usr/bin/env python3
"""Smoke-test the layout Codex `plugin/install` actually unpacks.

The installer copies the package to `<marketplace cache>/brian-vc/<version>/`,
so the plugin root is the version string and there is no repo beside it. Copying
to a folder named `brian-vc` instead would test a layout no install produces.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2]


class InstallCopyTests(unittest.TestCase):
    def setUp(self) -> None:
        manifest = json.loads((SOURCE / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.runtime = SOURCE.parent / ".install-test-runtime" / uuid.uuid4().hex
        self.plugin = self.runtime / "brian-vc" / manifest["version"]
        shutil.copytree(
            SOURCE,
            self.plugin,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "artifact-output", "artifact-preview", "deck-output", "deck-preview", "prepared_fixture.json", "node_modules"),
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.runtime, ignore_errors=True)

    def run_cmd(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, *args], cwd=self.plugin, text=True, encoding="utf-8", capture_output=True, check=False)

    def test_installed_copy_preflight_and_core_tests(self) -> None:
        preflight = self.run_cmd(str(self.plugin / "scripts" / "preflight.py"), "--skip-python-deps", "--json")
        self.assertEqual(preflight.returncode, 0, preflight.stderr or preflight.stdout)
        report = json.loads(preflight.stdout)
        self.assertEqual(report["status"], "pass")
        marketplace = next(row for row in report["results"] if row["label"] == "repo marketplace")
        self.assertEqual(marketplace["status"], "managed")
        for relative in (
            "tests/vc-quick-screen/check_skill.py",
            "tests/prospectus-extractor/test_contract.py",
            "tests/vc-investment-evaluator/check_architecture.py",
            "tests/plugin/test_route_case.py",
        ):
            result = self.run_cmd(str(self.plugin / relative))
            self.assertEqual(result.returncode, 0, f"{relative}: {result.stderr or result.stdout}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
