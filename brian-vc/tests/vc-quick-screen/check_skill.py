#!/usr/bin/env python3
"""Static policy checks for the vc-quick-screen skill."""

from __future__ import annotations

import re
from pathlib import Path


TEST_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = TEST_DIR.parents[1]
SKILL_DIR = PLUGIN_ROOT / "skills" / "vc-quick-screen"
SKILL_MD = SKILL_DIR / "SKILL.md"
OPENAI_YAML = SKILL_DIR / "agents" / "openai.yaml"
REQUIREMENTS = PLUGIN_ROOT / "requirements.txt"


def main() -> int:
    skill = SKILL_MD.read_text(encoding="utf-8")
    metadata = OPENAI_YAML.read_text(encoding="utf-8")
    requirements = REQUIREMENTS.read_text(encoding="utf-8")

    required_checks = {
        "frontmatter name": "name: vc-quick-screen" in skill,
        "L0 routing": "**L0 薄資料**" in skill,
        "L2 routing": "**L2 完整 data room**" in skill,
        "single-pass execution": "單一 pass，不派 subagent" in skill,
        "internal consistency": "BP 內部一致性驗算" in skill,
        "external query budget": "搜尋 query 合計最多 8 條" in skill
        and "Step 2 與 Step 2.2 共用" in skill,
        "output length floor is hard": "下限 2,500 個非空白字元且 80 行為**硬性**" in skill,
        "output length ceiling is soft": "上限 6,000 字元／180 行是**軟性目標**" in skill
        and "16,000 字元／400 行" in skill,
        "depth must not be trimmed for length": "深度不得為了篇幅被刪" in skill,
        "coefficient tier is mandatory": "係數層（強制，至少 1 列" in skill
        and "加總全過不等於通過" in skill,
        "coefficient tier probes": all(
            probe in skill
            for probe in ("轉換效率", "守恆", "資源可得性", "財務結構守恆", "時程守恆")
        ),
        "consistency table declares tier column": "檢查項 | 層級 | deck 數字" in skill,
        "official MOPS priority": "財務數字與重大訊息先查 MOPS" in skill,
        "official TWSE priority": "上市公司股價、市值與交易資料先查 TWSE" in skill,
        "official TPEx priority": "上櫃／興櫃公司先查 TPEx" in skill,
        "secondary-source limitation": "二手來源只做交叉驗證" in skill,
        "no hard IRR": "不計算 IRR" in skill,
        "literal IRR output contract": "**不計算 IRR。**" in skill,
        "unknown handling": "查不到不硬掰，標 UNKNOWN" in skill,
        "six expert views": "六專家速評" in skill,
        "management questions": "管理層拷問（預設 10 題，必要時最多 15 題）" in skill,
        "graduation checklist": "Graduate-to-DD Checklist" in skill,
        "fixed disclaimer": "本初篩為初步研究觀察，非投資建議" in skill,
        "style resolver path": "../../scripts/resolve_style.py" in skill,
        "neutral style path": "../../assets/styles/neutral/instructions.md" in skill,
        "style contract path": "../vc-investment-evaluator/references/output_style_contract.md"
        in skill,
        "DOCX renderer path": "scripts/render_memo_docx.py" in skill,
        "DOCX dependency contract": "../../requirements.txt" in skill
        and "python-docx" in skill
        and re.search(r"(?m)^python-docx[<>=]", requirements) is not None,
        "canonical output skeleton": "Canonical Markdown 輸出骨架（固定）" in skill
        and "## 0. 文件盤點" in skill
        and "### 2.2 外部足跡速查" in skill
        and "## 8. 初判與升級條件" in skill,
        "numbered management questions": "Step 6 必須用 Markdown 編號清單" in skill,
        "OpenAI metadata": "default_prompt:" in metadata
        and "$vc-quick-screen" in metadata,
    }

    forbidden_checks = {
        "Claude-specific browser/tool names": not re.search(
            r"(?i)Claude(?:-|\s)*in(?:-|\s)*Chrome|web_fetch|\bWebSearch\b|"
            r"Claude.{0,30}Web\s*Search",
            skill,
        ),
        "BrianStyle hard dependency": "brianstyle-deck" not in skill,
    }

    failed = []
    for label, ok in {**required_checks, **forbidden_checks}.items():
        print(f"[{'PASS' if ok else 'FAIL'}] {label}")
        if not ok:
            failed.append(label)

    print(
        f"\nResult: {len(required_checks) + len(forbidden_checks) - len(failed)}/"
        f"{len(required_checks) + len(forbidden_checks)} checks passed"
    )
    if failed:
        print("Failed:", ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
