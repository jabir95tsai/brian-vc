#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IRR / Return Multiple 雙矩陣計算器（vc-investment-evaluator）。

用途：D2、D3、E1、F 與獨立財測模型的 IRR 矩陣一律由本 script 產生，禁止手算。

兩種模式：
  pe    製造業/獲利型：退出股價 = 退出年 EPS × 達成率 × 退出 P/E
        IRR = (退出股價 / 入股價)^(1/n) - 1
  ev    新創：IRR = (退出估值 × 持股% / 投入)^(1/n) - 1（單點，不做矩陣達成率軸時給 --exit-values）

輸出：markdown 雙表（IRR% 矩陣 + Multiple 矩陣）＋可供任意渲染器使用的 JSON rows（--json）。

範例：
  python irr_matrix.py pe --entry 65 --eps 8.5 --years 4 \
      --pe-list 10,12,15,18 --ach-list 50,60,70,80,90,100,120 \
      --dividend-per-year 1.0 --hurdle 15
"""
import argparse
import json
import sys


def irr_from_multiple(multiple: float, years: float) -> float:
    if multiple <= 0:
        return -1.0
    return multiple ** (1.0 / years) - 1.0


def format_irr(irr: float, hurdle_pct: float | None = None) -> str:
    """格式化 IRR；提供 hurdle 時在儲存格實際加上狀態標記。"""
    value = f"{irr * 100:.1f}%"
    if hurdle_pct is None:
        return value
    if irr * 100 >= hurdle_pct:
        return f"✅ {value}"
    if irr >= 0:
        return f"⚠️ {value}"
    return f"❌ {value}"


def build_pe_matrix(entry, eps, years, pe_list, ach_list, dividend_per_year=0.0, hurdle_pct=None):
    """回傳 (irr_rows, mult_rows)：list-of-lists，首列表頭。"""
    header = ["達成率＼退出P/E"] + [f"{pe:g}x" for pe in pe_list]
    irr_rows, mult_rows = [header], [list(header)]
    total_div = dividend_per_year * years
    for ach in ach_list:
        irr_row = [f"{ach:g}%"]
        mult_row = [f"{ach:g}%"]
        for pe in pe_list:
            exit_price = eps * (ach / 100.0) * pe + total_div
            mult = exit_price / entry
            irr = irr_from_multiple(mult, years)
            irr_row.append(format_irr(irr, hurdle_pct))
            mult_row.append(f"{mult:.2f}x")
        irr_rows.append(irr_row)
        mult_rows.append(mult_row)
    return irr_rows, mult_rows


def build_ev_matrix(investment, stake_pct, years, exit_values, ach_list=None, hurdle_pct=None):
    """新創模式：exit_values（退出估值清單）× 達成率（可選）。"""
    ach_list = ach_list or [100.0]
    header = ["達成率＼退出估值"] + [f"{v:,.0f}" for v in exit_values]
    irr_rows, mult_rows = [header], [list(header)]
    for ach in ach_list:
        irr_row = [f"{ach:g}%"]
        mult_row = [f"{ach:g}%"]
        for v in exit_values:
            proceeds = v * (ach / 100.0) * (stake_pct / 100.0)
            mult = proceeds / investment
            irr = irr_from_multiple(mult, years)
            irr_row.append(format_irr(irr, hurdle_pct))
            mult_row.append(f"{mult:.2f}x")
        irr_rows.append(irr_row)
        mult_rows.append(mult_row)
    return irr_rows, mult_rows


def to_markdown(rows, title):
    lines = [f"**{title}**", ""]
    lines.append("| " + " | ".join(str(c) for c in rows[0]) + " |")
    lines.append("|" + "---|" * len(rows[0]))
    for r in rows[1:]:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(lines)


def parse_floats(s):
    return [float(x) for x in s.split(",") if x.strip()]


def main():
    p = argparse.ArgumentParser(description="IRR/Multiple 雙矩陣")
    p.add_argument("mode", choices=["pe", "ev"])
    p.add_argument("--entry", type=float, help="入股價/股（pe 模式）")
    p.add_argument("--eps", type=float, help="退出年 EPS（100%% 達成，pe 模式）")
    p.add_argument("--investment", type=float, help="投入金額（ev 模式）")
    p.add_argument("--stake", type=float, help="持股 %%（ev 模式）")
    p.add_argument("--exit-values", type=parse_floats, help="退出估值清單（ev 模式）")
    p.add_argument("--years", type=float, required=True, help="持有年限 n")
    p.add_argument("--pe-list", type=parse_floats, default=[10, 12, 15, 18])
    p.add_argument("--ach-list", type=parse_floats, default=[50, 60, 70, 80, 90, 100, 120])
    p.add_argument("--dividend-per-year", type=float, default=0.0, help="每股年股利（計入退出報酬）")
    p.add_argument("--hurdle", type=float, default=None, help="Hurdle %%（提供時標記每個 IRR 儲存格）")
    p.add_argument("--json", action="store_true", help="輸出 JSON（rows 可直接餵 deck 引擎）")
    a = p.parse_args()

    if a.mode == "pe":
        if a.entry is None or a.eps is None:
            p.error("pe 模式需 --entry 與 --eps")
        irr_rows, mult_rows = build_pe_matrix(
            a.entry, a.eps, a.years, a.pe_list, a.ach_list,
            a.dividend_per_year, a.hurdle,
        )
        params = {"mode": "pe", "entry": a.entry, "eps_100pct": a.eps, "years": a.years,
                  "pe_list": a.pe_list, "ach_list": a.ach_list,
                  "dividend_per_year": a.dividend_per_year, "hurdle_pct": a.hurdle}
    else:
        if a.investment is None or a.stake is None or not a.exit_values:
            p.error("ev 模式需 --investment、--stake、--exit-values")
        irr_rows, mult_rows = build_ev_matrix(
            a.investment, a.stake, a.years, a.exit_values, a.ach_list, a.hurdle
        )
        params = {"mode": "ev", "investment": a.investment, "stake_pct": a.stake,
                  "years": a.years, "exit_values": a.exit_values,
                  "ach_list": a.ach_list, "hurdle_pct": a.hurdle}

    if a.json:
        print(json.dumps({"params": params, "irr_rows": irr_rows, "multiple_rows": mult_rows},
                         ensure_ascii=False, indent=2))
    else:
        print(to_markdown(irr_rows, f"IRR 矩陣（n={a.years:g} 年）"))
        print()
        print(to_markdown(mult_rows, "Return Multiple 矩陣"))
        if a.hurdle is not None:
            print(f"\n儲存格標記：Hurdle Rate = {a.hurdle:g}%；✅ ≥Hurdle　⚠️ 0–Hurdle　❌ <0%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
