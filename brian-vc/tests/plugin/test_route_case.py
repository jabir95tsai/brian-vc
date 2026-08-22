#!/usr/bin/env python3
"""Routing tests for the three-skill plugin entrypoint."""

from __future__ import annotations

import importlib.util
import shutil
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "route_case.py"
spec = importlib.util.spec_from_file_location("route_case", SCRIPT)
route = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(route)


class RouteCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = Path(__file__).with_name(".route-test-runtime") / uuid.uuid4().hex
        self.runtime.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.runtime, ignore_errors=True)

    def touch(self, name: str) -> None:
        path = self.runtime / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")

    def test_single_pitch_routes_quick_screen(self) -> None:
        self.touch("Company_Pitch_Deck.pdf")
        result = route.classify(self.runtime)
        self.assertEqual((result["data_level"], result["primary_skill"]), ("L0", "vc-quick-screen"))

    def test_complete_data_room_routes_evaluator(self) -> None:
        for name in ("2025_查核財務報告.pdf", "CapTable.xlsx", "TermSheet.pdf", "三表明細.xlsx"):
            self.touch(name)
        result = route.classify(self.runtime)
        self.assertEqual((result["data_level"], result["primary_skill"]), ("L2", "vc-investment-evaluator"))
        self.assertEqual(result["execution_mode"], "full")

    def test_chinese_real_world_names_route_evaluator_degraded(self) -> None:
        for name in ("110-112年財簽用印版.pdf", "股東名簿_最新.xlsx", "財測底稿_BS_IS_CF.xlsx", "募資簡報完整版.pptx"):
            self.touch(name)
        result = route.classify(self.runtime, requested_skill="vc-investment-evaluator")
        self.assertEqual((result["data_level"], result["primary_skill"]), ("L2-degraded", "vc-investment-evaluator"))
        self.assertEqual(result["execution_mode"], "blocked")
        self.assertEqual(result["l2_missing"], ["term_sheet"])

    def test_prospectus_plus_audited_reports_routes_fact_dd_but_blocks_returns(self) -> None:
        self.touch("0000_現增公開說明書_202606.pdf")
        self.touch("0000_114年報_合併_查核財務報告.pdf")
        result = route.classify(self.runtime, requested_skill="vc-investment-evaluator")
        self.assertTrue(result["prospectus_core_inference"])
        self.assertFalse(result["signals"]["cap_table"])
        self.assertTrue(result["effective_signals"]["cap_table"])
        self.assertTrue(result["effective_signals"]["detailed_financials"])
        self.assertEqual(result["data_level"], "L2-degraded")
        self.assertEqual(result["execution_mode"], "blocked")
        self.assertEqual(result["l2_missing"], ["term_sheet"])

    def test_same_partial_room_stays_quick_screen_without_explicit_evaluator(self) -> None:
        for name in ("會計師查核報告.pdf", "股權結構.xlsx", "損益表_資產負債表_現金流量表.xlsx"):
            self.touch(name)
        result = route.classify(self.runtime)
        self.assertEqual(result["primary_skill"], "vc-quick-screen")

    def test_prospectus_is_conditional_skill(self) -> None:
        self.touch("初次上市公開說明書.pdf")
        result = route.classify(self.runtime)
        self.assertEqual(result["primary_skill"], "vc-quick-screen")
        self.assertEqual(result["conditional_skills"], ["prospectus-extractor"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
