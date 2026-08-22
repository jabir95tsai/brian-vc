#!/usr/bin/env python3
"""Behavioural tests for the delivery gate and the visual QA record it reads.

These exercise the real code paths. The pre-existing contract tests asserted
that certain strings appeared in the scripts' own source, which is why a gate
that rejected every blocked case could sit behind a fully green suite.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "vc-investment-evaluator" / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify = load("verify_and_record_delivery")


def audit(model_checks: str, base_formulas: int = 0) -> dict:
    return {
        "factbase": {"formula_error_count": 0},
        "model": {
            "formula_error_count": 0,
            "formula_count_in_base_forecast": base_formulas,
            "model_checks": model_checks,
        },
    }


def fake_pptx(path: Path, slides: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for index in range(1, slides + 1):
            archive.writestr(f"ppt/slides/slide{index}.xml", "<p:sld/>")
    return path


class WorkbookAuditGateTests(unittest.TestCase):
    def test_blocked_audit_is_deliverable_in_blocked_mode(self) -> None:
        self.assertIsNone(verify.workbook_audit_error(audit("BLOCKED_AS_DESIGNED"), "blocked"))

    def test_ok_audit_is_deliverable_in_full_and_degraded(self) -> None:
        for mode in ("full", "degraded"):
            with self.subTest(mode=mode):
                self.assertIsNone(verify.workbook_audit_error(audit("OK"), mode))

    def test_blocked_verdict_is_rejected_outside_blocked_mode(self) -> None:
        error = verify.workbook_audit_error(audit("BLOCKED_AS_DESIGNED"), "full")
        self.assertIn("model_checks", error or "")

    def test_ok_verdict_is_rejected_in_blocked_mode(self) -> None:
        # A blocked case whose model reports OK has computed something it was
        # told not to compute; the gate must not wave it through.
        error = verify.workbook_audit_error(audit("OK"), "blocked")
        self.assertIn("model_checks", error or "")

    def test_blocked_mode_rejects_base_forecast_formulas(self) -> None:
        error = verify.workbook_audit_error(audit("BLOCKED_AS_DESIGNED", base_formulas=70), "blocked")
        self.assertIn("base-forecast formulas", error or "")

    def test_formula_errors_always_block(self) -> None:
        broken = audit("BLOCKED_AS_DESIGNED")
        broken["model"]["formula_error_count"] = 3
        self.assertIsNotNone(verify.workbook_audit_error(broken, "blocked"))


class VisualQaGateTests(unittest.TestCase):
    def test_report_must_cover_both_decks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            executive = fake_pptx(root / "exec.pptx", 2)
            full = fake_pptx(root / "full.pptx", 3)
            report = {"status": "pass", "reviewed_files": [str(executive.resolve())]}
            self.assertIn("both decks", verify.visual_qa_error(report, executive, full) or "")
            report["reviewed_files"].append(str(full.resolve()))
            self.assertIsNone(verify.visual_qa_error(report, executive, full))

    def test_failed_report_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            executive = fake_pptx(root / "exec.pptx", 1)
            full = fake_pptx(root / "full.pptx", 1)
            report = {
                "status": "fail",
                "reviewed_files": [str(executive.resolve()), str(full.resolve())],
            }
            self.assertIsNotNone(verify.visual_qa_error(report, executive, full))


class RecordVisualQaTests(unittest.TestCase):
    """The recorder must produce exactly what the gate above accepts."""

    def build_case(self, root: Path, rendered_full: int = 3) -> tuple[Path, Path, Path]:
        outputs = root / "outputs"
        executive = fake_pptx(outputs / "exec.pptx", 2)
        full = fake_pptx(outputs / "full.pptx", 3)
        previews = outputs / "previews" / "decks"
        for index in range(1, 3):
            (previews / "executive").mkdir(parents=True, exist_ok=True)
            (previews / "executive" / f"slide-{index:02d}.png").write_bytes(b"png")
        (previews / "full-critical").mkdir(parents=True, exist_ok=True)
        for index in range(1, rendered_full + 1):
            (previews / "full-critical" / f"slide-{index:02d}.png").write_bytes(b"png")
        return executive, full, previews

    def run_recorder(self, root: Path, executive: Path, full: Path, previews: Path, *extra: str):
        return subprocess.run(
            [
                sys.executable, str(SCRIPTS / "record_visual_qa.py"), str(root),
                "--executive", str(executive), "--full-critical", str(full),
                "--preview-root", str(previews), "--mode", "blocked", *extra,
            ],
            capture_output=True, text=True, encoding="utf-8",
        )

    def test_recorded_pass_satisfies_the_delivery_gate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            executive, full, previews = self.build_case(root)
            result = self.run_recorder(root, executive, full, previews, "--reviewer", "Jabir Tsai")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root / "outputs" / "visual_qa_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "pass")
            self.assertIsNone(verify.visual_qa_error(report, executive, full))

    def test_unrendered_slides_cannot_be_attested(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            executive, full, previews = self.build_case(root, rendered_full=2)
            result = self.run_recorder(root, executive, full, previews, "--reviewer", "Jabir Tsai")
            self.assertEqual(result.returncode, 2)
            report = json.loads((root / "outputs" / "visual_qa_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "fail")
            self.assertIsNotNone(verify.visual_qa_error(report, executive, full))

    def test_reviewer_is_mandatory(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            executive, full, previews = self.build_case(root)
            result = self.run_recorder(root, executive, full, previews, "--reviewer", "   ")
            self.assertEqual(result.returncode, 2)

    def test_recorded_issue_forces_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            executive, full, previews = self.build_case(root)
            result = self.run_recorder(
                root, executive, full, previews, "--reviewer", "Jabir Tsai", "--issue", "第 7 頁條件表被裁切",
            )
            self.assertEqual(result.returncode, 2)
            report = json.loads((root / "outputs" / "visual_qa_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "fail")


if __name__ == "__main__":
    unittest.main(verbosity=2)
