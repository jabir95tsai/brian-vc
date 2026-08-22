#!/usr/bin/env python3
"""Prompt fixtures for later model forward-tests plus deterministic coverage."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PromptRoutingContractTests(unittest.TestCase):
    def test_every_skill_has_positive_cases_and_default_prompt(self) -> None:
        payload = json.loads((ROOT / "evals" / "routing_cases.json").read_text(encoding="utf-8"))
        expected = {"vc-quick-screen", "prospectus-extractor", "vc-investment-evaluator"}
        actual = {case["expected_skill"] for case in payload["cases"]}
        self.assertEqual(actual, expected)
        for skill in expected:
            metadata = (ROOT / "skills" / skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
            self.assertIn(f"${skill}", metadata)

    def test_boundary_case_prevents_fabricated_irr(self) -> None:
        payload = json.loads((ROOT / "evals" / "routing_cases.json").read_text(encoding="utf-8"))
        case = next(row for row in payload["cases"] if row["id"] == "BOUNDARY-01")
        self.assertEqual(case["expected_skill"], "vc-quick-screen")
        quick = (ROOT / "skills" / "vc-quick-screen" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("不硬算 IRR", quick)
        self.assertIn("vc-investment-evaluator", quick)


if __name__ == "__main__":
    unittest.main(verbosity=2)
