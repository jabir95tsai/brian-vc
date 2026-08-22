#!/usr/bin/env python3
"""Contract checks for one-click replay and legacy-parity outputs."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "vc-investment-evaluator" / "scripts"


class ReplayContractTests(unittest.TestCase):
    def test_replay_calls_all_generation_and_qa_stages(self) -> None:
        source = (SCRIPTS / "replay_evaluator_case.py").read_text(encoding="utf-8")
        for script in ("prepare_workbook_input.py", "build_evaluator_workbooks.mjs", "verify_evaluator_workbooks.mjs", "build_investment_decks.mjs", "build_legacy_parity_artifacts.py", "qa_deck.py"):
            self.assertIn(script, source)
        self.assertIn("evaluator_replay_report.json", source)
        for field in ("pipeline_status", "dd_status", "structural_qa_status", "visual_qa_status", "delivery_status", "ready_for_delivery"):
            self.assertIn(field, source)

    def test_delivery_verifier_requires_evidenced_visual_qa(self) -> None:
        source = (SCRIPTS / "verify_and_record_delivery.py").read_text(encoding="utf-8")
        self.assertIn('"--visual-qa-report"', source)
        self.assertIn('visual_qa.get("status") != "pass"', source)
        self.assertIn('visual_qa.get("reviewed_files", [])', source)

    def test_legacy_builder_preserves_old_artifact_types(self) -> None:
        source = (SCRIPTS / "build_legacy_parity_artifacts.py").read_text(encoding="utf-8")
        for artifact in ("Investment_Memo.docx", "DD_Request_Tracker.xlsx", "Management_QA.docx", "Interview_Notes.docx", "Meeting_Minutes.docx", "Financial_Statement_Notes.docx"):
            self.assertIn(artifact, source)

    def test_mode_aware_qa_has_four_profiles(self) -> None:
        source = (SCRIPTS / "qa_deck.py").read_text(encoding="utf-8")
        for mode in ('"full"', '"degraded"', '"blocked"', '"quick-screen"'):
            self.assertIn(mode, source)

    def test_replay_cli_accepts_blocked_case_payloads(self) -> None:
        source = (SCRIPTS / "replay_evaluator_case.py").read_text(encoding="utf-8")
        self.assertIn('choices=("full", "degraded", "blocked")', source)
        self.assertIn('"--mode", mode', source)
        self.assertIn('reconfigure(encoding="utf-8")', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
