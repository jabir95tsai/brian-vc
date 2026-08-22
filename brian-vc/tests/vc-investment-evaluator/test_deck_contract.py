#!/usr/bin/env python3
"""Fast source-contract checks for the F2 deck renderer."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVALUATOR = ROOT / "skills" / "vc-investment-evaluator"
FIXTURE = Path(__file__).with_name("fixture_evaluator_case.json")


class DeckContractTests(unittest.TestCase):
    def test_fixture_meets_f3_evidence_minimums(self) -> None:
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(data["comparables"]), 5)
        self.assertGreaterEqual(len(data["team"]), 2)
        self.assertGreaterEqual(len(data["deck"]["risks"]), 3)
        self.assertGreaterEqual(len(data["deck"]["redteam"]), 3)

    def test_renderer_creates_both_variants_and_keeps_gp_blanks(self) -> None:
        source = (EVALUATOR / "scripts" / "build_investment_decks.mjs").read_text(encoding="utf-8")
        self.assertIn('require.resolve("@oai/artifact-tool"', source)
        self.assertIn("CODEX_NODE_MODULES", source)
        self.assertIn('buildDeck(data, "Executive")', source)
        self.assertIn('buildDeck(data, "Full-critical")', source)
        self.assertIn("進場 / 不進場：【GP 填入】", source)
        self.assertIn("scripts/irr_matrix.py", source)
        self.assertNotIn("python-pptx", source)
        self.assertIn("verifiedComparables(data)", source)
        self.assertIn("isFiniteEvidence", source)

    def test_full_variant_keeps_critical_sections(self) -> None:
        source = (EVALUATOR / "scripts" / "build_investment_decks.mjs").read_text(encoding="utf-8")
        for phrase in ("風險矩陣", "RedTeam", "失敗路徑", "資料缺失", "management_questions"):
            self.assertIn(phrase, source)

    def test_generic_renderer_contains_no_fixture_specific_claims(self) -> None:
        source = (EVALUATOR / "scripts" / "build_investment_decks.mjs").read_text(encoding="utf-8")
        for phrase in ("600 百萬元", "1,237", "EdgeBridge", "72% 收入", "財務 74", "治理 58"):
            self.assertNotIn(phrase, source)
        self.assertIn('mode === "full"', source)
        self.assertIn('scenarioUsesDriverModel(data, "base")', source)

    def test_condition_lists_normalize_embedded_line_breaks(self) -> None:
        source = (EVALUATOR / "scripts" / "build_investment_decks.mjs").read_text(encoding="utf-8")
        self.assertIn('.replace(/\\s+/g, " ").trim()', source)
        self.assertIn('`${index + 1}｜${item}`', source)

    def test_redteam_payload_carries_fixed_ic_handoff_template(self) -> None:
        redteam = (EVALUATOR / "references" / "experts" / "redteam.md").read_text(encoding="utf-8")
        self.assertIn(
            "RedTeam 提出 [N] 個反對理由，主要風險點為 [R1 前三反對理由摘要]，"
            "GP 決策框架已留白供填入。",
            redteam,
        )
        self.assertIn("E2→F1 交棒語", redteam)
        contract = (EVALUATOR / "references" / "deck_content_contract.md").read_text(encoding="utf-8")
        self.assertIn("E2→F1", contract)
        # The deck contract must name the field the renderer reads, so the
        # handoff cannot silently become free-form prose written by F1.
        self.assertIn("redteam_handoff", contract)
        self.assertIn("deck.redteam_handoff", redteam)


if __name__ == "__main__":
    unittest.main(verbosity=2)
