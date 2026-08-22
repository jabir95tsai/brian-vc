#!/usr/bin/env python3
"""Inventory a case directory and route it to one of the three Brian VC skills."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PATTERNS = {
    "prospectus": re.compile(r"公開說明書|公說|prospectus", re.I),
    "audited_fs": re.compile(
        r"查核|核閱|財報|財簽|查核報告|用印|會計師|年報|audited|reviewed|財務報告|financial.?statements?",
        re.I,
    ),
    "cap_table": re.compile(
        r"股東名簿|股東名冊|股本形成|股權結構|資本形成|cap.?table|shareholders?",
        re.I,
    ),
    "term_sheet": re.compile(
        r"增資條件|投資條件|募資條件|認購|term.?sheet|subscription|本輪條件",
        re.I,
    ),
    "detailed_financials": re.compile(
        r"三表|財測底稿|財務底稿|損益表?|資產負債表?|現金流量?表?|試算表|trial.?balance|(?:^|[/_. -])is(?:[/_. -]|$)|(?:^|[/_. -])bs(?:[/_. -]|$)|(?:^|[/_. -])cf(?:[/_. -]|$)",
        re.I | re.M,
    ),
    "pitch": re.compile(r"(?:^|[/_. -])bp(?:[/_. -]|$)|pitch|deck|公司介紹|商業計畫|募資簡報|簡報|完整版|business.?plan", re.I | re.M),
}
SUPPORTED = {".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".md", ".txt", ".json"}


def inventory(case_dir: Path) -> list[dict]:
    rows = []
    for file in sorted(p for p in case_dir.rglob("*") if p.is_file() and ".vc-evaluator" not in p.parts):
        rows.append({
            "path": str(file.resolve()),
            "relative_path": file.relative_to(case_dir).as_posix(),
            "extension": file.suffix.lower(),
            "bytes": file.stat().st_size,
            "supported": file.suffix.lower() in SUPPORTED,
        })
    return rows


def classify(case_dir: Path, requested_skill: str | None = None, allow_degraded: bool = False) -> dict:
    files = inventory(case_dir)
    names = "\n".join(row["relative_path"] for row in files)
    signals = {key: bool(pattern.search(names)) for key, pattern in PATTERNS.items()}
    # A prospectus plus a separately named audited/reviewed financial report is
    # a common Taiwan real-world package (e.g. 示範科技 0000).  The prospectus is
    # expected to carry capital formation/shareholder tables and detailed
    # financial summaries even when those concepts do not appear in its file
    # name.  This remains a filename-level hint only; A2 must still read and
    # confirm the contents before treating either requirement as complete.
    prospectus_core_inference = signals["prospectus"] and signals["audited_fs"]
    effective_signals = dict(signals)
    if prospectus_core_inference:
        effective_signals["cap_table"] = True
        effective_signals["detailed_financials"] = True
    l2_requirements = ["audited_fs", "cap_table", "term_sheet", "detailed_financials"]
    l2_missing = [key for key in l2_requirements if not effective_signals[key]]
    supported_count = sum(1 for row in files if row["supported"])
    if not files:
        level, primary, status = "L0", "vc-quick-screen", "blocked"
        reason = "案件資料夾沒有文件；先提供 BP、Pitch Deck、公說或 data room。"
    elif not l2_missing:
        level, primary, status, mode = "L2", "vc-investment-evaluator", "ready", "full"
        reason = "查核／核閱財報、股本資料、本輪條件與詳細三表皆有檔名證據。"
    elif (
        (requested_skill == "vc-investment-evaluator" or allow_degraded)
        and effective_signals["audited_fs"]
        and effective_signals["cap_table"]
        and effective_signals["detailed_financials"]
    ):
        level, primary, status, mode = "L2-degraded", "vc-investment-evaluator", "ready", "blocked"
        reason = (
            "已具財報、股權與詳細財務資料，可執行事實型 DD；因缺少本輪條件，"
            "case payload 應使用 blocked，保留事實產物並阻擋 IRR／Return Multiple，"
            "不得用假設交易條件包裝成 degraded 完成。"
        )
    elif supported_count <= 1:
        level, primary, status, mode = "L0", "vc-quick-screen", "ready", "quick-screen"
        reason = "只有單一可支援文件，適合先做薄資料初篩。"
    else:
        level, primary, status, mode = "L1", "vc-quick-screen", "ready", "quick-screen"
        reason = "已有部分資料，但未達完整 DD 的四項 L2 證據門檻。"
    if not files:
        mode = "quick-screen"
    return {
        "case_dir": str(case_dir.resolve()),
        "status": status,
        "data_level": level,
        "primary_skill": primary,
        "execution_mode": mode,
        "requested_skill": requested_skill,
        "conditional_skills": ["prospectus-extractor"] if signals["prospectus"] else [],
        "prospectus_triggered": signals["prospectus"],
        "signals": signals,
        "effective_signals": effective_signals,
        "prospectus_core_inference": prospectus_core_inference,
        "l2_missing": l2_missing,
        "reason": reason,
        "file_count": len(files),
        "supported_file_count": supported_count,
        "files": files,
        "warning": (
            "檔名分流只作 preflight；執行 Skill 後仍須讀取內容確認，不能把檔名或"
            "公說的預期章節視為完成證據。"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--requested-skill", choices=("vc-quick-screen", "vc-investment-evaluator", "prospectus-extractor"))
    parser.add_argument("--allow-degraded", action="store_true", help="permit degraded evaluator routing when core financial evidence exists")
    args = parser.parse_args()
    if not args.case_dir.is_dir():
        print(f"ERROR: not a directory: {args.case_dir}", file=sys.stderr)
        return 2
    result = classify(args.case_dir, args.requested_skill, args.allow_degraded)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
