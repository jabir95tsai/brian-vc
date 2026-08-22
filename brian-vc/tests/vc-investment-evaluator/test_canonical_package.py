#!/usr/bin/env python3
"""End-to-end state/gate test through the F1 canonical package."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "vc-investment-evaluator" / "scripts"
RUNNER = SCRIPTS / "evaluator_runner.py"
PREPARE = SCRIPTS / "prepare_workbook_input.py"
ASSEMBLE = SCRIPTS / "assemble_canonical_package.py"
FIXTURE = Path(__file__).with_name("fixture_evaluator_case.json")
MODULES_TO_E_GATE = ["A1", "A2", "B1", "B3", "B4", "C1", "C2", "C3", "C4", "D1", "D2", "D3", "E1", "E2", "E3"]


class CanonicalPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case_dir = Path(__file__).with_name(".canonical-test-runtime") / uuid.uuid4().hex
        self.case_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.case_dir, ignore_errors=True)

    def run_cmd(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, *args], text=True, encoding="utf-8", capture_output=True, check=False)

    def test_f1_freeze_records_context_package(self) -> None:
        init = self.run_cmd(str(RUNNER), "init", str(self.case_dir), "--case-id", "20260815_E2E")
        self.assertEqual(init.returncode, 0, init.stderr)
        evidence_dir = self.case_dir / "evidence"
        evidence_dir.mkdir()
        for module in MODULES_TO_E_GATE:
            artifact = evidence_dir / f"{module}.md"
            artifact.write_text(f"# {module}\nverified fixture evidence\n", encoding="utf-8")
            done = self.run_cmd(str(RUNNER), "set", str(self.case_dir), module, "complete", "--evidence", str(artifact), "--artifact", str(artifact))
            self.assertEqual(done.returncode, 0, f"{module}: {done.stderr or done.stdout}")
            if module == "B1":
                b2_evidence = evidence_dir / "B2-not-applicable.md"
                b2_evidence.write_text("DocumentIndex contains no prospectus", encoding="utf-8")
                b2 = self.run_cmd(str(RUNNER), "set", str(self.case_dir), "B2", "not_applicable", "--evidence", str(b2_evidence), "--reason", "no prospectus in DocumentIndex")
                self.assertEqual(b2.returncode, 0, b2.stderr or b2.stdout)
        prepared = self.case_dir / "prepared_case.json"
        prep = self.run_cmd(str(PREPARE), str(FIXTURE), str(prepared))
        self.assertEqual(prep.returncode, 0, prep.stderr)
        assembled = self.run_cmd(str(ASSEMBLE), str(self.case_dir), str(prepared))
        self.assertEqual(assembled.returncode, 0, assembled.stderr or assembled.stdout)
        report = json.loads(assembled.stdout)
        package = Path(report["context_package"])
        self.assertTrue(package.is_file())
        state = json.loads((self.case_dir / ".vc-evaluator" / "artifact-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(state["modules"]["F1"]["status"], "complete")
        status = self.run_cmd(str(RUNNER), "status", str(self.case_dir), "--json")
        self.assertEqual(json.loads(status.stdout)["gates"]["E_GATE"], "complete")


if __name__ == "__main__":
    unittest.main(verbosity=2)
