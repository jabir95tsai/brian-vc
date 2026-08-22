#!/usr/bin/env python3
"""Validate evaluator workbook input and attach canonical IRR/multiple matrices."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from irr_matrix import build_ev_matrix


SCENARIOS = ("conservative", "base", "upside")
MODES = ("full", "degraded", "blocked")
PEER_LIST_SOURCES = ("user_specified", "auto")
# E2 hands F1 a ready-made sentence; F1 must not invent its own wording.
REDTEAM_HANDOFF_MARKERS = ("反對理由", "GP 決策框架已留白供填入")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def is_blocked(payload: dict) -> bool:
    return payload.get("mode") == "blocked"


def finite_number(value: object) -> bool:
    """Return True only for real numeric evidence; null/blank must not become zero."""
    if value in (None, "") or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def comparable_rejection_reasons(row: object) -> list[str]:
    """Explain why a comparable cannot enter the verified CitationTable set."""
    if not isinstance(row, dict):
        return ["row is not an object"]
    reasons = []
    if not str(row.get("company") or "").strip():
        reasons.append("company is missing")
    if not str(row.get("as_of") or "").strip():
        reasons.append("as_of is missing")
    if not str(row.get("source_url") or "").strip():
        reasons.append("source_url is missing")
    if row.get("verification_status") not in (None, "verified"):
        reasons.append(f"verification_status={row.get('verification_status')}")
    if not any(finite_number(row.get(key)) for key in ("revenue", "market_cap", "pe", "ev_revenue")):
        reasons.append("no usable valuation metric")
    return reasons


def normalize_evidence(payload: dict) -> dict:
    """Keep verified evidence separate from company-provided or incomplete rows."""
    verified = []
    rejected = list(payload.get("unverified_comparables") or [])
    for row in payload.get("comparables") or []:
        reasons = comparable_rejection_reasons(row)
        if reasons:
            rejected.append({**row, "rejection_reasons": reasons} if isinstance(row, dict) else {"raw": row, "rejection_reasons": reasons})
        else:
            verified.append(row)
    payload["comparables"] = verified
    payload["unverified_comparables"] = rejected
    if rejected and not any(
        "同業" in str(item.get("item", "")) and item.get("status") != "已完成"
        for item in payload.get("missing_items") or []
        if isinstance(item, dict)
    ):
        payload.setdefault("missing_items", []).append({
            "priority": "P1",
            "item": "官方同業估值查驗",
            "reason": f"{len(rejected)} 筆候選同業缺資料日、來源 URL、驗證狀態或可用估值數字",
            "owner": "Deal team",
            "due": "投委前",
            "status": "待補",
        })
    return payload


def validate(payload: dict) -> None:
    """Validate the case payload.

    `blocked` exists because the pipeline contract requires D2/D3 to report
    `blocked` when round terms are undisclosed, and forbids dressing that up
    with assumptions. Without this mode the builder rejected such a case
    outright, so a real prospectus that states 本次現金增資 "不適用" could not
    produce even its factual deliverables. Blocked keeps every evidence-backed
    sheet and drops only what genuinely cannot be computed.
    """
    payload.setdefault("mode", payload.get("meta", {}).get("mode", "full"))
    normalize_evidence(payload)
    require(payload["mode"] in MODES, f"mode must be one of {', '.join(MODES)}")
    blocked = is_blocked(payload)
    for section in ("meta", "deal", "financial_history", "assumptions"):
        require(section in payload, f"missing required section: {section}")
    meta = payload["meta"]
    for key in ("case_id", "company", "as_of", "currency", "unit"):
        require(meta.get(key) not in (None, ""), f"meta.{key} is required")
    deal = payload["deal"]
    require(deal.get("round") not in (None, ""), "deal.round is required")
    if blocked:
        # Naming what is missing is mandatory: blocked must be an evidenced
        # state, not a way to skip validation.
        require(
            deal.get("blocked_reason") not in (None, ""),
            "deal.blocked_reason is required when mode is blocked",
        )
    else:
        for key in ("investment", "pre_money", "post_money"):
            require(deal.get(key) not in (None, ""), f"deal.{key} is required")
        require(float(deal["investment"]) > 0, "deal.investment must be positive")
        require(float(deal["post_money"]) > 0, "deal.post_money must be positive")
    history = payload["financial_history"]
    require(isinstance(history, list) and history, "financial_history must contain at least one row")
    for row in history:
        require("year" in row and "revenue" in row, "each financial_history row needs year and revenue")

    # D1 must say how the comparable list was chosen. A user-supplied list
    # takes priority over the auto-generated Watchlist, and the two produce
    # very different evidence, so the source has to survive into the payload
    # rather than living only in prose on CitationTable.
    if payload.get("comparables") or payload.get("unverified_comparables"):
        peer_source = payload.get("peer_list_source")
        require(
            peer_source in PEER_LIST_SOURCES,
            "peer_list_source is required when the case carries comparables and "
            f"must be one of {', '.join(PEER_LIST_SOURCES)}",
        )

    # E2's handoff line is part of its payload contract; if RedTeam ran, the
    # sentence F1 quotes has to be present and actually be that sentence.
    deck = payload.get("deck") or {}
    if deck.get("redteam"):
        handoff = str(deck.get("redteam_handoff") or "").strip()
        require(bool(handoff), "deck.redteam_handoff is required once deck.redteam has content")
        missing_markers = [m for m in REDTEAM_HANDOFF_MARKERS if m not in handoff]
        require(
            not missing_markers,
            "deck.redteam_handoff must follow the E2 template from "
            f"references/experts/redteam.md; missing: {', '.join(missing_markers)}",
        )
    assumptions = payload["assumptions"]
    years = assumptions.get("forecast_years", [])
    scenarios = assumptions.get("scenarios", {})
    if blocked and not all(
        isinstance(scenarios.get(name), dict) and "revenue_growth" in scenarios[name]
        for name in SCENARIOS
    ):
        # No usable forecast assumptions: keep the factual sheets, skip the model.
        payload["forecast_available"] = False
        return
    payload["forecast_available"] = True
    require(3 <= len(years) <= 5, "assumptions.forecast_years must contain 3-5 years")
    for name in SCENARIOS:
        require(name in scenarios, f"assumptions.scenarios.{name} is required")
        for key in ("revenue_growth", "gross_margin", "opex_ratio", "tax_rate", "capex_ratio", "exit_revenue_multiple"):
            require(key in scenarios[name], f"assumptions.scenarios.{name}.{key} is required")
        forecast_rows = scenarios[name].get("forecast_rows")
        if forecast_rows is not None:
            require(len(forecast_rows) == len(years), f"{name}.forecast_rows must match forecast_years")
            require([row.get("year") for row in forecast_rows] == years, f"{name}.forecast_rows years must match forecast_years")


def attach_return_matrices(payload: dict) -> dict:
    if is_blocked(payload):
        payload["return_matrix"] = {
            "generator": "scripts/prepare_workbook_input.py",
            "status": "blocked",
            "reason": payload["deal"].get("blocked_reason", "round terms undisclosed"),
            "note": "本輪條件未揭露，IRR 與 Return Multiple 依契約標 blocked，不以假設替代。",
        }
        return payload
    deal = payload["deal"]
    assumptions = payload["assumptions"]
    base_post = float(deal["post_money"])
    stake_pct = float(deal["investment"]) / base_post * 100.0
    exit_values = [
        base_post * float(assumptions["scenarios"][name]["exit_revenue_multiple"])
        for name in SCENARIOS
    ]
    ach_list = [70.0, 85.0, 100.0, 115.0, 130.0]
    irr_rows, multiple_rows = build_ev_matrix(
        investment=float(deal["investment"]),
        stake_pct=stake_pct,
        years=float(assumptions["holding_years"]),
        exit_values=exit_values,
        ach_list=ach_list,
        hurdle_pct=float(assumptions["hurdle_rate"]) * 100.0,
    )
    payload["return_matrix"] = {
        "generator": "scripts/irr_matrix.py",
        "mode": "ev",
        "stake_pct": stake_pct,
        "exit_values": exit_values,
        "achievement_pct": ach_list,
        "irr_rows": irr_rows,
        "multiple_rows": multiple_rows,
    }
    return payload


def attach_independent_forecast(payload: dict) -> dict:
    """Prefer explicit operating-driver rows; retain the ratio proxy as fallback."""
    if not payload.get("forecast_available", True):
        payload["independent_forecast"] = {
            "generator": "scripts/prepare_workbook_input.py",
            "status": "blocked",
            "reason": payload["deal"].get("blocked_reason", "no usable forecast assumptions"),
            "note": "無可用財測假設，獨立財測未建立；歷史財務仍完整呈現。",
            "scenarios": {},
        }
        return payload
    latest = max(payload["financial_history"], key=lambda row: int(row["year"]))
    years = payload["assumptions"]["forecast_years"]
    result = {}
    scenario_methods = {}
    for name in SCENARIOS:
        a = payload["assumptions"]["scenarios"][name]
        uses_driver_model = bool(a.get("forecast_rows"))
        scenario_methods[name] = "driver_model" if uses_driver_model else "ratio_proxy_fallback"
        prior_revenue = float(latest["revenue"])
        rows = []
        explicit_by_year = {row["year"]: row for row in a.get("forecast_rows", [])}
        for year in years:
            explicit = explicit_by_year.get(year, {}) if uses_driver_model else {}
            drivers = explicit.get("drivers", [])
            revenue = explicit.get("revenue")
            if revenue is None and drivers:
                revenue = sum(float(driver["volume"]) * float(driver["price"]) for driver in drivers)
            if revenue is None:
                revenue = prior_revenue * (1.0 + float(a["revenue_growth"]))
            revenue = float(revenue)
            gross_margin = float(explicit.get("gross_margin", a["gross_margin"]))
            gross_profit = float(explicit.get("gross_profit", revenue * gross_margin))
            opex = float(explicit.get("opex", revenue * float(a["opex_ratio"])))
            ebit = gross_profit - opex
            tax = float(explicit.get("tax", max(0.0, ebit * float(a["tax_rate"]))))
            net_income = float(explicit.get("net_income", ebit - tax))
            capex = float(explicit.get("capex", revenue * float(a["capex_ratio"])))
            working_capital_change = float(explicit.get("working_capital_change", 0.0))
            rows.append({
                "year": year,
                "revenue": revenue,
                "gross_profit": gross_profit,
                "gross_margin": gross_margin,
                "opex": opex,
                "ebit": ebit,
                "tax": tax,
                "net_income": net_income,
                "capex": capex,
                "working_capital_change": working_capital_change,
                "fcf_proxy": net_income - capex - working_capital_change,
                "drivers": drivers,
            })
            prior_revenue = revenue
        result[name] = rows
    method_set = set(scenario_methods.values())
    method = next(iter(method_set)) if len(method_set) == 1 else "mixed_driver_and_ratio"
    payload["independent_forecast"] = {
        "generator": "scripts/prepare_workbook_input.py",
        "label": "獨立估計，非公司財測",
        "method": method,
        "scenario_methods": scenario_methods,
        "limitations": [
            f"{name} uses ratio_proxy_fallback because forecast_rows are unavailable"
            for name, scenario_method in scenario_methods.items()
            if scenario_method == "ratio_proxy_fallback"
        ],
        "scenarios": result,
    }
    has_extension_drivers = bool((payload.get("financial_extensions") or {}).get("operating_drivers"))
    fallback_scenarios = [name for name, scenario_method in scenario_methods.items() if scenario_method == "ratio_proxy_fallback"]
    if has_extension_drivers and fallback_scenarios and not any(
        "核心財測連結" in str(item.get("item", ""))
        for item in payload.get("missing_items") or []
        if isinstance(item, dict)
    ):
        payload.setdefault("missing_items", []).append({
            "priority": "P1",
            "item": "營運 driver 與核心財測連結",
            "reason": f"financial_extensions 已有營運量價證據，但 {', '.join(fallback_scenarios)} 情境仍使用 ratio proxy",
            "owner": "Financial DD",
            "due": "投委前",
            "status": "待補",
        })
    return payload


RED_FLAG_STATUSES = {"RED FLAG", "RED_FLAG", "FAIL", "MISMATCH", "CONFLICT"}


def build_risk_rows(payload: dict, missing: list) -> list:
    """Build the risk matrix from what the evidence actually contradicts.

    A gap and a risk are different things: "we have not received the bank
    schedule" is a gap, while "the disclosed interest implies a 1.1% rate" is a
    risk. Deriving risks from ``missing_items`` alone made the memo's risk
    section a verbatim copy of its gap section and silently dropped every red
    flag the model checks had already found.

    Columns match the deck contract: 風險 / 影響 / 機率 / 優先級 / 緩解／驗證.
    """
    rows: list[list[str]] = []
    seen: set[str] = set()

    def add(name: str, impact: str, likelihood: str, priority: str, action: str) -> None:
        key = str(name).strip()
        if not key or key in seen:
            return
        seen.add(key)
        rows.append([key, impact, likelihood, priority, action])

    # 1. Arithmetic and consistency red flags: observed in the company's own
    #    numbers, so likelihood is not speculative.
    for check in (payload.get("financial_extensions") or {}).get("model_checks") or []:
        status = str(check.get("status", "")).upper()
        if status not in RED_FLAG_STATUSES:
            continue
        add(
            f"{check.get('check', '模型檢查未通過')}：{check.get('finding', '與公司數字不一致')}",
            check.get("finding") or "公司自有數字無法勾稽",
            "已觀察",
            "P0",
            "以一手證據反證或要求修正模型",
        )

    # 2. Mutually exclusive sources for the same fact.
    for claim in payload.get("claims") or []:
        if claim.get("status") != "conflicted":
            continue
        add(
            f"來源衝突：{claim.get('claim', '同一事實有互斥來源')}",
            "同一事實有互斥來源，結論不可鎖定",
            "已觀察",
            "P0",
            f"以 {claim.get('source_id', '來源')} {claim.get('locator', '定位')} 對帳並關閉",
        )

    # 3. P0 evidence gaps stay in the matrix because they can overturn the read;
    #    P1 gaps live in the gap register only, so the two lists stop being twins.
    for item in missing:
        if item.get("priority") != "P0":
            continue
        add(
            f"關鍵證據缺口：{item.get('item', '資料缺口')}",
            item.get("reason") or "缺件可能改變目前判讀",
            "未取得",
            "P0",
            "取得直接證據後重算",
        )
    return rows


def attach_deck_scaffold(payload: dict) -> dict:
    """Create a transparent generic deck payload when migrating code-defined cases."""
    if payload.get("deck"):
        payload["deck"].setdefault("generated_by", "case_payload")
        return payload
    missing = payload.get("missing_items", [])
    products = payload.get("products", [])
    customers = payload.get("customers", [])
    suppliers = payload.get("suppliers", [])
    comparables = payload.get("comparables", [])
    scenarios = payload["assumptions"]["scenarios"]
    base_forecast = payload["independent_forecast"].get("scenarios", {}).get("base") or []
    final_revenue = base_forecast[-1]["revenue"] if base_forecast else None

    def number(value: object, default: float = 0.0) -> float:
        try:
            return default if value is None else float(value)
        except (TypeError, ValueError):
            return default

    def metric(label: str, value: object, evidence: str) -> list[object]:
        return [label, value, evidence]

    business_metrics = [
        metric(f"{item.get('name', '產品')}收入占比", f"{number(item.get('revenue_share_pct')):.1%}", item.get("source", "尚待補件"))
        for item in products[:4] if finite_number(item.get("revenue_share_pct"))
    ]
    concentration_customers = [row for row in customers if finite_number(row.get("concentration_pct"))]
    if concentration_customers:
        top = max(concentration_customers, key=lambda row: number(row.get("concentration_pct")))
        business_metrics.append(metric("最大客戶集中", f"{number(top.get('concentration_pct')):.1%}", top.get("source", "尚待補件")))
    if not business_metrics:
        business_metrics = [
            metric(item.get("name", "產品／服務"), item.get("status", "狀態待補"), item.get("source", "尚待補件"))
            for item in products[:4]
        ]
    technology_metrics = [metric(item.get("name", "產品"), item.get("status", "未提供"), item.get("source", "尚待補件")) for item in products[:4]]
    concentration_suppliers = [row for row in suppliers if finite_number(row.get("concentration_pct"))]
    if concentration_suppliers:
        top = max(concentration_suppliers, key=lambda row: number(row.get("concentration_pct")))
        technology_metrics.append(metric("最大供應商集中", f"{number(top.get('concentration_pct')):.1%}", top.get("source", "尚待補件")))
    multiples = [number(row["ev_revenue"]) for row in comparables if row.get("ev_revenue") is not None]
    market_metrics = [metric("已驗證可比公司", f"{len(comparables)} 家", "來源與日期見 CitationTable")]
    if multiples:
        market_metrics.append(metric("EV/Revenue 區間", f"{min(multiples):.1f}–{max(multiples):.1f}x", "只使用 payload 內已驗證值"))
    external_sources = [
        source for source in payload.get("sources") or []
        if str(source.get("url") or "").startswith(("http://", "https://"))
    ]
    market_metrics.extend([
        metric(source.get("name", "外部一手來源"), source.get("as_of", "日期待確認"), source.get("notes") or source.get("url"))
        for source in external_sources[:2]
    ])
    valuation_scenarios = []
    if final_revenue is None:
        valuation_scenarios.append(
            ["blocked", "—", "—", payload["deal"].get("blocked_reason", "本輪條件未揭露，估值不予推估")]
        )
    else:
        for name, label in (("conservative", "保守"), ("base", "基準"), ("upside", "積極")):
            multiple = float(scenarios[name]["exit_revenue_multiple"])
            valuation_scenarios.append([label, f"{multiple:.1f}x", f"{final_revenue * multiple:,.1f}", "獨立情境，非投資建議"])
    risks = build_risk_rows(payload, missing)
    conditions = [item.get("item", "補齊關鍵證據") for item in missing if item.get("priority") == "P0"] or ["補齊影響估值與財務誠信的直接證據"]
    questions = [f"請提供或說明：{item.get('item', '缺件')}；驗證目的：{item.get('reason', '確認事實')}。" for item in missing]
    blocked = is_blocked(payload)
    conflicted_claims = [
        claim for claim in payload.get("claims") or []
        if claim.get("status") == "conflicted"
    ]
    conflict_rows = [
        [claim.get("claim", "衝突主張"), claim.get("source_id", "未定位"), claim.get("locator", "未定位"), "conflicted｜待關閉"]
        for claim in conflicted_claims[:6]
    ]
    redteam = [f"需反證：{claim.get('claim', '高優先衝突')}" for claim in conflicted_claims[:4]]
    if not redteam:
        redteam = ["若主要財務、交易條件或收入來源無法以直接證據驗證，現有情境不得視為已成立。"]
    payload["deck"] = {
        "generated_by": "scripts/prepare_workbook_input.py generic migration scaffold",
        "communication_job": "讓審閱者區分已驗證事實、公司主張、獨立估計與尚待補件，不代替最終決策。",
        "thesis": (
            "本案可繼續事實與風險 DD，但現行交易條件未揭露；估值、IRR 與投資金額依契約維持 blocked。"
            if blocked else
            "本案已建立可追溯的財務與交易情境；投資命題仍以補齊 P0 證據及來源定位為前提。"
        ),
        "decision_status": (
            "BLOCKED｜缺現行 Term Sheet；估值、IRR 與投資金額不可計算"
            if blocked else "研究中；GP 進場、金額與條件留白"
        ),
        "conditions": conditions,
        "business_metrics": business_metrics,
        "technology_metrics": technology_metrics,
        "market_metrics": market_metrics,
        "scores": [["資料完整度", max(0, 100 - len(missing) * 8)], ["財務可追溯", 70 if payload.get("financial_history") else 0], ["市場可比", min(100, len(comparables) * 20)]],
        "valuation_scenarios": valuation_scenarios,
        "risks": risks,
        "conflicts": conflict_rows,
        "redteam": redteam,
        "failure_paths": [[item.get("item", "關鍵資料缺失"), item.get("reason", "可能改變目前判讀"), "補件後重算或降級狀態"] for item in missing],
        "management_questions": questions,
        "copy": {
            "executive_subtitle": (
                "事實 DD 可繼續；本輪條件、估值與報酬模型 blocked。"
                if blocked else "已驗證事實、獨立估計與未完成證據分開呈現。"
            ),
            "full_subtitle": (
                "BLOCKED 邊界、完整證據、資料缺失、風險與反方檢驗"
                if blocked else "完整證據、資料缺失、風險與反方檢驗"
            ),
        },
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        validate(payload)
        payload = attach_return_matrices(payload)
        payload = attach_independent_forecast(payload)
        payload = attach_deck_scaffold(payload)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"prepared: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
