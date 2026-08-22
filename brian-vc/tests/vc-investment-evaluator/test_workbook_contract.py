#!/usr/bin/env python3
"""Fast contract tests for the evaluator workbook builders."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EVALUATOR = ROOT / "skills" / "vc-investment-evaluator"
SCRIPTS = EVALUATOR / "scripts"
FIXTURE = Path(__file__).with_name("fixture_evaluator_case.json")

sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("prepare_workbook_input", SCRIPTS / "prepare_workbook_input.py")
prepare = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(prepare)


class RiskMatrixTests(unittest.TestCase):
    """A gap register and a risk matrix must not be the same list.

    Deriving risks from missing_items alone made the memo's risk section a
    verbatim copy of its gap section and dropped every red flag the model
    checks had already found.
    """

    PAYLOAD = {
        "financial_extensions": {
            "model_checks": [
                {"check": "收入加總", "status": "OK", "difference": 0},
                {"check": "熱電效率邊界", "status": "RED FLAG", "finding": "92%-105% 未扣廠用電"},
            ]
        },
        "claims": [
            {"claim": "毛利率跳升 7.54pp", "status": "conflicted", "source_id": "S1", "locator": "p.12"},
            {"claim": "客戶集中度 46.7%", "status": "verified", "source_id": "S1", "locator": "p.9"},
        ],
    }
    MISSING = [
        {"item": "現行 Term Sheet", "priority": "P0", "reason": "解除估值 blocked"},
        {"item": "銀行核貸與利率表", "priority": "P1", "reason": "利息無法勾稽"},
    ]

    def rows(self):
        return prepare.build_risk_rows(self.PAYLOAD, self.MISSING)

    def test_red_flag_model_checks_become_risks(self) -> None:
        joined = " ".join(row[0] for row in self.rows())
        self.assertIn("熱電效率邊界", joined)
        self.assertNotIn("收入加總", joined)

    def test_conflicted_claims_become_risks(self) -> None:
        joined = " ".join(row[0] for row in self.rows())
        self.assertIn("毛利率跳升 7.54pp", joined)
        self.assertNotIn("客戶集中度", joined)

    def test_only_p0_gaps_enter_the_risk_matrix(self) -> None:
        joined = " ".join(row[0] for row in self.rows())
        self.assertIn("現行 Term Sheet", joined)
        self.assertNotIn("銀行核貸", joined)

    def test_risks_are_not_a_copy_of_the_gap_list(self) -> None:
        risk_names = [row[0] for row in self.rows()]
        gap_names = [item["item"] for item in self.MISSING]
        self.assertNotEqual(risk_names, gap_names)

    def test_impact_and_likelihood_are_not_placeholders(self) -> None:
        for row in self.rows():
            self.assertEqual(len(row), 5, row)
            self.assertNotEqual(row[1], "待評估", row)
            self.assertNotEqual(row[2], "待評估", row)

    def test_duplicate_findings_are_collapsed(self) -> None:
        names = [row[0] for row in self.rows()]
        self.assertEqual(len(names), len(set(names)))


class WorkbookContractTests(unittest.TestCase):
    def test_fixture_validates_and_matrix_comes_from_canonical_script(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        prepare.validate(payload)
        prepared = prepare.attach_return_matrices(payload)
        prepared = prepare.attach_independent_forecast(prepared)
        self.assertEqual(prepared["return_matrix"]["generator"], "scripts/irr_matrix.py")
        self.assertEqual(len(prepared["return_matrix"]["irr_rows"]), 6)
        self.assertTrue(any("✅" in str(cell) for row in prepared["return_matrix"]["irr_rows"] for cell in row))
        self.assertEqual(prepared["independent_forecast"]["label"], "獨立估計，非公司財測")
        self.assertEqual(len(prepared["independent_forecast"]["scenarios"]["base"]), 5)

    def test_builder_uses_artifact_tool_and_exact_sheet_contracts(self) -> None:
        source = (SCRIPTS / "build_evaluator_workbooks.mjs").read_text(encoding="utf-8")
        self.assertIn('require.resolve("@oai/artifact-tool"', source)
        self.assertIn("CODEX_NODE_MODULES", source)
        for name in ["0_說明", "11_補件清單", "①假設參數", "⑥CapEx與資金接力"]:
            self.assertIn(f'"{name}"', source)
        self.assertNotIn("openpyxl", source)
        self.assertIn("scripts/irr_matrix.py", source)
        for name in ["7C_CF明細", "⑦營運量價", "⑧債務折舊", "⑨營運資金三表", "⑪勾稽驗算"]:
            self.assertIn(name, source)

    def test_explicit_driver_rows_replace_ratio_proxy(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        years = payload["assumptions"]["forecast_years"]
        for scenario in payload["assumptions"]["scenarios"].values():
            scenario["forecast_rows"] = [
                {"year": year, "drivers": [{"name": "產品A", "volume": 10 + index, "price": 20}], "gross_margin": 0.5}
                for index, year in enumerate(years)
            ]
        prepare.validate(payload)
        prepared = prepare.attach_independent_forecast(payload)
        self.assertEqual(prepared["independent_forecast"]["method"], "driver_model")
        self.assertEqual(prepared["independent_forecast"]["scenarios"]["base"][0]["revenue"], 200)

    def test_mixed_scenario_methods_preserve_available_driver_rows(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        years = payload["assumptions"]["forecast_years"]
        payload["assumptions"]["scenarios"]["base"]["forecast_rows"] = [
            {"year": year, "drivers": [{"name": "產品A", "volume": 10 + index, "price": 20}], "gross_margin": 0.5}
            for index, year in enumerate(years)
        ]
        prepare.validate(payload)
        prepared = prepare.attach_independent_forecast(payload)
        self.assertEqual(prepared["independent_forecast"]["method"], "mixed_driver_and_ratio")
        self.assertEqual(prepared["independent_forecast"]["scenario_methods"]["base"], "driver_model")
        self.assertEqual(prepared["independent_forecast"]["scenario_methods"]["conservative"], "ratio_proxy_fallback")
        self.assertEqual(prepared["independent_forecast"]["scenarios"]["base"][0]["revenue"], 200)
        self.assertNotEqual(prepared["independent_forecast"]["scenarios"]["conservative"][0]["revenue"], 200)

    def test_extension_drivers_without_core_mapping_create_an_explicit_gap(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        prepare.validate(payload)
        prepared = prepare.attach_independent_forecast(payload)
        self.assertEqual(prepared["independent_forecast"]["method"], "ratio_proxy_fallback")
        gaps = [item for item in prepared["missing_items"] if item.get("item") == "營運 driver 與核心財測連結"]
        self.assertEqual(len(gaps), 1)
        self.assertIn("ratio proxy", gaps[0]["reason"])

    def test_incomplete_or_unverified_comparables_are_quarantined(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["comparables"] = [
            {"company": "只有名稱", "revenue": None, "market_cap": None, "pe": None, "ev_revenue": None, "as_of": "", "source_url": ""},
            {"company": "公司提供倍數", "pe": 30.0, "as_of": "2026-08-14", "source_url": "https://example.com/company-deck", "verification_status": "company_provided"},
        ]
        payload["suppliers"] = [{"name": "供應商甲", "concentration_pct": None, "source": "待補"}]
        payload.pop("deck")
        prepare.validate(payload)
        self.assertEqual(payload["comparables"], [])
        self.assertEqual(len(payload["unverified_comparables"]), 2)
        prepared = prepare.attach_return_matrices(payload)
        prepared = prepare.attach_independent_forecast(prepared)
        prepared = prepare.attach_deck_scaffold(prepared)
        self.assertIn(["已驗證可比公司", "0 家", "來源與日期見 CitationTable"], prepared["deck"]["market_metrics"])
        self.assertFalse(any(row[0] == "最大供應商集中" for row in prepared["deck"]["technology_metrics"]))

    def _blocked_payload(self) -> dict:
        """A real shape: 示範科技 0000, whose prospectus states 本次現金增資 不適用."""
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["mode"] = "blocked"
        payload["deal"].update(
            {
                "investment": None,
                "pre_money": None,
                "post_money": None,
                "price_per_share": None,
                "blocked_reason": "公說載明本次現金增資應記載事項不適用；價格與股數未揭露",
            }
        )
        payload["assumptions"]["scenarios"] = {
            name: {"note": "blocked"} for name in prepare.SCENARIOS
        }
        return payload

    def test_blocked_mode_keeps_facts_and_refuses_to_invent_valuation(self) -> None:
        payload = self._blocked_payload()
        prepare.validate(payload)
        prepared = prepare.attach_return_matrices(payload)
        prepared = prepare.attach_independent_forecast(prepared)
        self.assertFalse(prepared["forecast_available"])
        self.assertEqual(prepared["return_matrix"]["status"], "blocked")
        self.assertNotIn("irr_rows", prepared["return_matrix"])
        self.assertEqual(prepared["independent_forecast"]["status"], "blocked")
        # Evidence-backed sections must survive; only the uncomputable is dropped.
        self.assertTrue(prepared["financial_history"])

    def test_blocked_mode_requires_a_stated_reason(self) -> None:
        payload = self._blocked_payload()
        payload["deal"].pop("blocked_reason")
        with self.assertRaises(ValueError):
            prepare.validate(payload)

    def test_blocked_scaffold_marks_valuation_rather_than_estimating_it(self) -> None:
        payload = self._blocked_payload()
        payload.pop("deck")
        prepare.validate(payload)
        prepared = prepare.attach_return_matrices(payload)
        prepared = prepare.attach_independent_forecast(prepared)
        prepared = prepare.attach_deck_scaffold(prepared)
        self.assertEqual(prepared["deck"]["valuation_scenarios"][0][0], "blocked")
        self.assertIn("BLOCKED", prepared["deck"]["decision_status"])
        self.assertIn("估值、IRR", prepared["deck"]["thesis"])

    def test_generic_scaffold_surfaces_conflicted_claims_and_external_sources(self) -> None:
        payload = self._blocked_payload()
        payload.pop("deck")
        payload["claims"] = [{"claim": "公司係數不閉合", "source_id": "S1", "locator": "p.8", "status": "conflicted"}]
        payload["sources"].append({"id": "S3", "name": "官方來源", "as_of": "2026-08-17", "url": "https://example.com/official", "notes": "一手資料"})
        prepare.validate(payload)
        prepared = prepare.attach_return_matrices(payload)
        prepared = prepare.attach_independent_forecast(prepared)
        prepared = prepare.attach_deck_scaffold(prepared)
        self.assertEqual(prepared["deck"]["conflicts"][0][0], "公司係數不閉合")
        self.assertTrue(any("公司係數不閉合" in item for item in prepared["deck"]["redteam"]))
        self.assertTrue(any(row[0] == "官方來源" for row in prepared["deck"]["market_metrics"]))

    def test_full_mode_still_rejects_missing_deal_terms(self) -> None:
        payload = self._blocked_payload()
        payload["mode"] = "full"
        with self.assertRaises(ValueError):
            prepare.validate(payload)

    def test_legacy_case_without_deck_gets_generic_data_scaffold(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload.pop("deck")
        prepare.validate(payload)
        prepared = prepare.attach_return_matrices(payload)
        prepared = prepare.attach_independent_forecast(prepared)
        prepared = prepare.attach_deck_scaffold(prepared)
        self.assertIn("deck", prepared)
        self.assertIn("generic migration scaffold", prepared["deck"]["generated_by"])
        self.assertTrue(prepared["deck"]["management_questions"])

    def test_schema_declares_required_sections(self) -> None:
        schema = json.loads((EVALUATOR / "references" / "evaluator_case.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["required"], ["meta", "deal", "financial_history", "assumptions"])
        self.assertIn("financial_extensions", schema["properties"])
        self.assertIn("legacy_outputs", schema["properties"])
        self.assertIn("blocked", schema["properties"]["mode"]["enum"])
        self.assertIn("unverified_comparables", schema["properties"])
        self.assertEqual(schema["properties"]["comparables"]["items"]["properties"]["verification_status"]["const"], "verified")
        blocked_rule = schema["allOf"][0]
        self.assertEqual(blocked_rule["then"]["properties"]["deal"]["required"], ["round", "blocked_reason"])
        self.assertEqual(
            blocked_rule["else"]["properties"]["deal"]["required"],
            ["round", "investment", "pre_money", "post_money"],
        )
        scenario_shape = schema["properties"]["assumptions"]["properties"]["scenarios"]
        self.assertNotIn("required", scenario_shape["additionalProperties"])
        nonblocked_scenarios = blocked_rule["else"]["properties"]["assumptions"]["properties"]["scenarios"]["properties"]
        self.assertIn("revenue_growth", nonblocked_scenarios["base"]["required"])


class BackfilledContractEnforcementTests(unittest.TestCase):
    """The restored D1 and E2 rules must bind the payload, not just the prose.

    Both started as narrative contract text, which nothing mechanical could
    check. These pin the machine-readable half so a case cannot reach the
    builders without saying how its comparable list was chosen or handing F1
    the RedTeam sentence E2 owes it.
    """

    def _payload(self) -> dict:
        return json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_fixture_declares_both_backfilled_fields(self) -> None:
        payload = self._payload()
        prepare.validate(payload)
        self.assertIn(payload["peer_list_source"], ("user_specified", "auto"))
        self.assertIn("GP 決策框架已留白供填入", payload["deck"]["redteam_handoff"])

    def test_comparables_require_a_declared_peer_list_source(self) -> None:
        payload = self._payload()
        payload.pop("peer_list_source")
        with self.assertRaises(ValueError) as caught:
            prepare.validate(payload)
        self.assertIn("peer_list_source", str(caught.exception))

    def test_peer_list_source_rejects_an_unknown_value(self) -> None:
        payload = self._payload()
        payload["peer_list_source"] = "guessed"
        with self.assertRaises(ValueError):
            prepare.validate(payload)

    def test_user_specified_peer_list_is_accepted(self) -> None:
        payload = self._payload()
        payload["peer_list_source"] = "user_specified"
        prepare.validate(payload)
        self.assertEqual(payload["peer_list_source"], "user_specified")

    def test_a_case_without_comparables_need_not_declare_a_source(self) -> None:
        payload = self._payload()
        payload.pop("peer_list_source")
        payload["comparables"] = []
        payload["unverified_comparables"] = []
        prepare.validate(payload)

    def test_redteam_content_requires_the_handoff_sentence(self) -> None:
        payload = self._payload()
        payload["deck"].pop("redteam_handoff")
        with self.assertRaises(ValueError) as caught:
            prepare.validate(payload)
        self.assertIn("redteam_handoff", str(caught.exception))

    def test_handoff_must_follow_the_e2_template(self) -> None:
        payload = self._payload()
        payload["deck"]["redteam_handoff"] = "RedTeam 有一些意見。"
        with self.assertRaises(ValueError) as caught:
            prepare.validate(payload)
        self.assertIn("redteam.md", str(caught.exception))

    def test_no_redteam_content_means_no_handoff_requirement(self) -> None:
        payload = self._payload()
        payload["deck"]["redteam"] = []
        payload["deck"].pop("redteam_handoff")
        prepare.validate(payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
