#!/usr/bin/env python3
"""Evaluate structure and fixture-specific reasoning in a quick-screen memo."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


EXPERT_ROLES = (
    "技術顧問",
    "產業分析師",
    "商業模式顧問",
    "財務分析師",
    "估值師",
    "投組經理",
)

SECTION_IDS = frozenset(
    ("0", "1", "1.5", "2", "2.2", "2.5", "3", "4", "5", "6", "7", "8")
)

SECTION_HEADING_RE = re.compile(
    r"(?m)^#{2,3}\s*(?:Step\s*)?(\d+(?:\.\d+)?)"
    r"\s*(?:[.．｜|:：]\s*)?.*$",
    re.I,
)


def section(text: str, number: str) -> str:
    headings = [
        heading
        for heading in SECTION_HEADING_RE.finditer(text)
        if heading.group(1) in SECTION_IDS
    ]
    for index, heading in enumerate(headings):
        if heading.group(1) != number:
            continue
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        return text[start:end].strip()
    return ""


def subsection(text: str, heading_pattern: str) -> str:
    match = re.search(
        # Keep the heading match on one physical line.  The former DOTALL
        # ``.*`` could start at the 亮點 heading, consume the later 疑慮
        # heading, and return the wrong block when the section title itself
        # contained both words (``亮點與疑慮``).
        rf"(?ms)^###\s*[^\n]*(?:{heading_pattern})[^\n]*\n(.*?)(?=^###\s|\Z)",
        text,
    )
    return match.group(1).strip() if match else ""


def table_rows(text: str) -> list[str]:
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        if re.fullmatch(r"\|[\s:|-]+\|", stripped):
            continue
        rows.append(stripped)
    return rows


def table_cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip("|").split("|")]


def numbered_items(text: str) -> list[str]:
    return re.findall(r"(?m)^\d+\.\s+(.+)$", text)


def bullet_items(text: str) -> list[str]:
    return re.findall(r"(?m)^\s*[-*]\s+(.+)$", text)


def fixture_expectations(scope: str, path: Path | None) -> tuple[bool, str]:
    """Match each expected finding against a single table row.

    Scope is the whole memo, not just 1.5: a coefficient defect may legitimately
    surface in external verification (2.2) rather than internal consistency.
    Requiring all patterns in one row still proves the finding was tabulated
    rather than name-dropped in prose.
    """
    if path is None:
        return True, "not requested"
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = table_rows(scope)
    failures = []
    for item in data["row_expectations"]:
        patterns = [re.compile(pattern, re.I) for pattern in item["patterns"]]
        if not any(all(pattern.search(row) for pattern in patterns) for row in rows):
            failures.append(item["label"])
    return not failures, (
        f"{len(data['row_expectations']) - len(failures)}/{len(data['row_expectations'])}"
        if not failures
        else "missing: " + ", ".join(failures)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--expectations",
        type=Path,
        help="Fixture-specific row expectations; omitted for generic structural checks.",
    )
    parser.add_argument(
        "--legacy-contract",
        action="store_true",
        help=(
            "Evaluate a memo produced before vQS-1.5: skips the coefficient-tier "
            "requirement, which did not exist when that memo was written."
        ),
    )
    args = parser.parse_args()

    text = args.output.read_text(encoding="utf-8")
    compact = re.sub(r"\s+", "", text)
    line_count = len(text.splitlines())

    sections = {number: section(text, number) for number in SECTION_IDS}
    inventory_rows = table_rows(sections["0"])
    inventory_items = bullet_items(sections["0"])
    snapshot_rows = table_rows(sections["1"])
    consistency_rows = table_rows(sections["1.5"])
    expert_rows = [
        table_cells(row)
        for row in table_rows(sections["2.5"])
        if any(role in row for role in EXPERT_ROLES)
    ]
    highlights = numbered_items(subsection(sections["3"], "亮點|值得保留"))
    concerns = numbered_items(subsection(sections["3"], "疑慮"))
    questions = numbered_items(sections["6"])
    checklist_items = bullet_items(sections["7"])
    checklist_table_rows = [
        row
        for row in table_rows(sections["7"])
        if re.search(r"(?:🔴|🟡|🟢|P[0-2]|必要|重要|補充)", row, re.I)
        and not re.search(r"\|\s*(?:優先|priority)\s*\|", row, re.I)
    ]
    expectation_ok, expectation_detail = fixture_expectations(
        text, args.expectations
    )

    expert_content_ok = (
        len(expert_rows) == 6
        and {row[0] for row in expert_rows if len(row) >= 4} == set(EXPERT_ROLES)
        and all(
            len(row) >= 4
            and len(re.sub(r"\s+", "", row[1])) >= 12
            and len(re.sub(r"\s+", "", row[2])) >= 10
            and re.search(r"[？?]|請|能否|是否|何|多少|提供|究竟", row[2])
            # A score may be written numerically (2.0/5) or as filled stars
            # (★★☆☆☆); SKILL.md mandates a ★/5 rating, not a digit.
            and re.search(r"(?:[0-5](?:\.\d)?(?:/5)?|[★☆]{5})", row[3])
            for row in expert_rows
        )
    )
    # A memo can pass every vertical-sum check and still miss the findings that
    # matter: forecast models are typically precise on the revenue side and
    # hand-filled on the coefficient side. Rows tagged 係數 are where a claim is
    # tested against a physical, resource or structural limit rather than
    # against another cell in the same table.
    coefficient_rows = [
        row
        for row in consistency_rows
        # the tier cell may carry markdown emphasis, e.g. "| **係數** |"
        if re.search(r"\|\s*[*_`]*\s*係數\s*[*_`]*\s*\|", row)
    ]
    coefficient_challenges = [
        row
        for row in coefficient_rows
        if re.search(r"[=×÷/%]|\d", row)
        and re.search(
            r"效率|守恆|熱值|轉換|產出比|耗用|可得|供給|物理|理論|反推|隱含"
            r"|稼動|良率|人均|上限|互斥|時程",
            row,
        )
    ]
    # Depth earns length: a memo carrying two or more coefficient-level
    # refutations is doing the work the soft 2-3 page target was never meant to
    # forbid, so the ceiling lifts. The floor never moves -- thin is still thin.
    depth_earned = len(coefficient_challenges) >= 2
    char_ceiling = 16000 if depth_earned else 6000
    line_ceiling = 400 if depth_earned else 180

    consistency_content_ok = (
        len(consistency_rows) >= 6
        and sum(bool(re.search(r"[=×÷/%]|(?:差|非|應為|推得)", row)) for row in consistency_rows)
        >= 5
        and sum(bool(re.search(r"[🔴🟡🟢✅]", row)) for row in consistency_rows) >= 5
    )
    self_disqualifying = re.search(
        r"未經驗算.{0,20}(?:照抄|抄錄)|直接照抄\s*BP|亮點[：:]\s*無|疑慮[：:]\s*無",
        text,
    )

    checks = {
        "all required sections": all(
            sections[number]
            for number in ("0", "1", "1.5", "2", "2.5", "3", "4", "5", "6", "7", "8")
        ),
        "L0/L1/L2 classification": bool(
            re.search(r"\bL[012]\b", sections["0"])
        ),
        # Step 0 says "列出" rather than mandating a table.  A header plus one
        # data row or two substantive bullets are both contract-compliant.
        "document inventory has data": (
            len(inventory_rows) >= 2 or len(inventory_items) >= 2
        ),
        "company snapshot has substance": len(snapshot_rows) >= 5,
        "internal consistency has calculations": consistency_content_ok,
        "fixture calculations match expected rows": expectation_ok,
        "no self-disqualifying language": self_disqualifying is None,
        "external evidence boundary": (
            "UNKNOWN" in (sections["2"] + sections["2.2"])
            and bool(
                re.search(
                    r"MOPS|TWSE|TPEx|官方|未外部查驗|本次不瀏覽|均未查詢",
                    sections["2"] + sections["2.2"],
                )
            )
        ),
        "six expert rows have analysis": expert_content_ok,
        "three substantive highlights": (
            len(highlights) == 3
            and all(len(re.sub(r"\s+", "", item)) >= 18 for item in highlights)
        ),
        "three substantive concerns": (
            len(concerns) == 3
            and all(len(re.sub(r"\s+", "", item)) >= 18 for item in concerns)
        ),
        "scale analysis is substantive": len(re.sub(r"\s+", "", sections["4"])) >= 80,
        "explicit valuation and IRR boundary": (
            "不計算 IRR" in sections["5"]
            and not re.search(r"IRR\s*[=:：]\s*[-+]?\d", sections["5"])
        ),
        "management questions 10-15": 10 <= len(questions) <= 15,
        "management questions are actionable": all(
            len(re.sub(r"\s+", "", item)) >= 18
            and re.search(r"[？?]|請|能否|是否|何|多少|提供|究竟", item)
            for item in questions
        ),
        "graduation checklist has priorities": (
            len(checklist_items) + len(checklist_table_rows) >= 3
            and bool(
                re.search(r"[🔴🟡🟢]|\bP[0-2]\b|必要|重要|補充", sections["7"], re.I)
            )
        ),
        "decision is explicit": bool(
            re.search(r"初判|進一步\s*DD|觀望|Pass", sections["8"], re.I)
        ),
        "reverse and upgrade conditions": (
            "反向條件" in sections["8"] and "升級條件" in sections["8"]
        ),
        "fixed disclaimer": (
            "本初篩為初步研究觀察，非投資建議；數字多未經查核，投資決策由 GP 自行判斷。"
            in text
        ),
        # vQS-1.5 requirement. Memos produced by earlier versions predate the
        # 層級 column and are evaluated with --legacy-contract, which drops this
        # check rather than retroactively failing a valid historical artifact.
        **(
            {}
            if args.legacy_contract
            else {
                "coefficient-level challenge present": (
                    len(coefficient_rows) >= 1 and len(coefficient_challenges) >= 1
                )
            }
        ),
        "declared Markdown length contract": (
            2500 <= len(compact) <= char_ceiling
            and 80 <= line_count <= line_ceiling
        ),
    }

    failed = []
    for label, ok in checks.items():
        detail = (
            f" ({expectation_detail})"
            if label == "fixture calculations match expected rows"
            else ""
        )
        print(f"[{'PASS' if ok else 'FAIL'}] {label}{detail}")
        if not ok:
            failed.append(label)

    print(
        f"\nQuestions: {len(questions)}; expert rows: {len(expert_rows)}; "
        f"consistency rows: {len(consistency_rows)} "
        f"(係數 {len(coefficient_rows)}, 反證 {len(coefficient_challenges)}); "
        f"lines: {line_count}/{line_ceiling}; "
        f"non-whitespace chars: {len(compact)}/{char_ceiling}"
        f"{' [depth-earned ceiling]' if depth_earned else ''}"
    )
    print(f"Result: {len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        print("Failed:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
