#!/usr/bin/env python3
"""Static and deterministic checks for the evaluator architecture contract."""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

PLUGIN = Path(__file__).resolve().parents[2]
SKILL = PLUGIN / "skills" / "vc-investment-evaluator"
MAIN = SKILL / "SKILL.md"
PIPELINE = SKILL / "references" / "pipeline_contract.md"
REQUIREMENTS = PLUGIN / "requirements.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def dependency_block(text: str, begin: str, end: str) -> dict[str, tuple[str, ...]]:
    match = re.search(
        rf"{re.escape(begin)}\s*(.*?)\s*{re.escape(end)}", text, flags=re.DOTALL
    )
    if not match:
        return {}
    dependencies: dict[str, tuple[str, ...]] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue
        downstream, separator, upstream = line.partition("<-")
        if not separator:
            return {}
        dependencies[downstream.strip()] = tuple(
            item.strip() for item in upstream.split(",") if item.strip()
        )
    return dependencies


def run() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, bool(ok), detail))

    required = [
        MAIN,
        PIPELINE,
        SKILL / "references" / "phase0_playbook.md",
        SKILL / "references" / "output_style_contract.md",
        SKILL / "references" / "financial_model_contract.md",
        SKILL / "scripts" / "irr_matrix.py",
        SKILL / "scripts" / "qa_deck.py",
        SKILL / "scripts" / "slice_toolresult.py",
        REQUIREMENTS,
    ]
    check("required architecture files", all(p.exists() for p in required))

    main = read(MAIN)
    pipeline = read(PIPELINE)
    stage_labels = [
        "## Stage A｜",
        "## Stage B｜",
        "## Stage C｜",
        "## Stage D｜",
        "## Stage E｜",
        "## Stage F｜",
    ]
    stage_positions = [main.find(label) for label in stage_labels]
    check(
        "Stage A-F present once and ordered",
        all(pos >= 0 for pos in stage_positions)
        and stage_positions == sorted(stage_positions)
        and all(main.count(label) == 1 for label in stage_labels),
        str(stage_positions),
    )

    expected_modules = [
        "A1", "A2", "B1", "B2", "B3", "B4", "C1", "C2", "C3", "C4",
        "D1", "D2", "D3", "E1", "E2", "E3", "F1", "F2", "F3",
    ]
    registry_modules = re.findall(
        r"^\|\s*((?:A|B|C|D|E|F)\d)\s*\|", pipeline, flags=re.MULTILINE
    )
    check(
        "module registry is complete and unique",
        registry_modules == expected_modules,
        ",".join(registry_modules),
    )

    graph = dependency_block(
        main, "<!-- DEPENDENCY-GRAPH-BEGIN -->", "<!-- DEPENDENCY-GRAPH-END -->"
    )
    manifest = dependency_block(
        pipeline,
        "<!-- DEPENDENCY-MANIFEST-BEGIN -->",
        "<!-- DEPENDENCY-MANIFEST-END -->",
    )
    check(
        "SKILL dependency graph matches canonical manifest",
        bool(graph) and graph == manifest and list(graph) == expected_modules,
        f"graph={len(graph)} manifest={len(manifest)}",
    )
    parallelism_ok = (
        graph.get("C4") == ("C3",)
        and graph.get("D1") == ("C3",)
        and {"C1", "C2"}.issubset(graph.get("E1", ()))
        and "D3" not in graph.get("E1", ())
        and "D3" in graph.get("E3", ())
    )
    check("DAG preserves C1/C2/C4 parallelism", parallelism_ok)

    mappings = {
        "phase1_tech.md": "# C1｜",
        "phase2_business.md": "# C2｜",
        "phase3_industry.md": "# C3｜",
        "phase4_finance.md": "# C4｜",
        "phase5b_valuation.md": "# D2｜",
        "phase6_pm.md": "# E1｜",
        "redteam.md": "# E2｜",
    }
    expert_dir = SKILL / "references" / "experts"
    expert_ok = True
    for filename, heading in mappings.items():
        content = read(expert_dir / filename)
        expert_ok &= content.startswith(heading)
        if filename != "redteam.md":
            expert_ok &= "## DECK_EXPORT" in content
    check("expert files map to one Module ID", expert_ok)

    broken: list[str] = []
    for source in (MAIN, PIPELINE):
        for token in set(re.findall(r"`([^`]+)`", read(source))):
            if token.startswith(("references/", "scripts/")):
                target = SKILL / token
            elif source == PIPELINE and (
                token.endswith(".md") or token.startswith("experts/")
            ):
                target = PIPELINE.parent / token
            else:
                continue
            if "*" in str(target):
                if not list(target.parent.glob(target.name)):
                    broken.append(f"{source.name}:{token}")
            elif not target.exists():
                broken.append(f"{source.name}:{token}")
    check("SKILL and pipeline local references resolve", not broken, ", ".join(broken))

    scan_paths = sorted(
        path for path in SKILL.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".py", ".yaml", ".yml", ".txt"}
    )
    forbidden = {
        "Claude runtime path": r"(?i)\.claude(?:/|\\)",
        "Claude-only subagent": r"(?i)subagent_type[^\n]*claude",
        "Claude forecast label": r"Claude\s*(?:/CFA)?\s*財測",
        "stale pdffonts chain": r"pdffonts\s*→",
        "tool-specific web_search": r"\bweb_search\b",
    }
    hits = []
    for path in scan_paths:
        content = read(path)
        for name, pattern in forbidden.items():
            if re.search(pattern, content):
                hits.append(f"{path.relative_to(SKILL)}:{name}")
    check("whole skill tree has no vendor-specific stale terms", not hits, ", ".join(hits))

    redteam_text = read(SKILL / "references" / "experts" / "redteam.md")
    handoff_template = "RedTeam 提出 [N] 個反對理由，主要風險點為 [R1 前三反對理由摘要]，GP 決策框架已留白供填入。"
    handoff_ok = (
        handoff_template in redteam_text
        and "E2→F1 交棒語" in redteam_text
        and "E2→F1" in main
        and "E2→F1" in read(SKILL / "references" / "deck_content_contract.md")
    )
    check(
        "E2 payload carries a fixed E2->F1 RedTeam handoff template",
        handoff_ok,
    )

    peer_modes = (
        "使用者指定" in main
        and "自動生成" in main
        and "龍頭" in main
        and "`user_specified`" in main
        and "`auto`" in main
        and main.find("使用者指定") < main.find("自動生成")
        and "user_specified" in pipeline
        and "使用者指定同業清單" in pipeline
    )
    check(
        "D1 peer list has user-specified and auto modes with a recorded source",
        peer_modes,
    )

    # PyMuPDF >= 1.28 prints a deprecation warning to stdout when imported as
    # `fitz`, which corrupts any machine-readable stdout the script emits.
    bare_fitz = []
    for path in (SKILL / "scripts").glob("*.py"):
        body = read(path)
        if re.search(r"^\s*import fitz(\s|$)", body, flags=re.MULTILINE) and (
            "import pymupdf" not in body
        ):
            bare_fitz.append(path.name)
    check(
        "PyMuPDF is imported under its modern name, not bare fitz",
        not bare_fitz,
        ", ".join(bare_fitz),
    )

    source_positions = [main.find(term) for term in ("1. MOPS", "2. TWSE", "3. TPEx")]
    check(
        "official Taiwan source order is fixed",
        all(pos >= 0 for pos in source_positions) and source_positions == sorted(source_positions),
        str(source_positions),
    )

    check(
        "Factbase Excel has two explicit paths",
        "### 有公說" in pipeline
        and "### 無公說" in pipeline
        and "固定 35 分頁母版" in pipeline
        and "非 35 分頁母版" in pipeline,
    )

    check(
        "structural QA is not presented as visual QA",
        "不取代視覺 QA" in read(SKILL / "scripts" / "qa_deck.py")
        and "它不取代視覺 QA" in main,
    )

    requirements = read(REQUIREMENTS)
    qa_text = read(SKILL / "scripts" / "qa_deck.py")
    dependency_ok = (
        re.search(r"^python-pptx>=1\.0,<2$", requirements, flags=re.MULTILINE)
        and "brian-vc/requirements.txt" in qa_text
        and "break-system-packages" not in qa_text
        and "python-pptx" in pipeline
    )
    check("python-pptx is declared and documented", bool(dependency_ok))

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    guard = subprocess.run(
        [sys.executable, "-S", str(SKILL / "scripts" / "qa_deck.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    guard_output = guard.stdout + guard.stderr
    check(
        "qa_deck missing-dependency guard is actionable",
        guard.returncode == 2
        and "python-pptx" in guard_output
        and "brian-vc/requirements.txt" in guard_output
        and "Traceback" not in guard_output,
        f"exit={guard.returncode}",
    )

    # The legacy Claude Skill carried a case-type table (hurdle, primary
    # valuation method, key follow-ups) and a separate FUND_PROFILE hurdle
    # list. Both are merged into this single table; keep it that way so the
    # two cannot drift back into conflicting sources.
    fund_header = "| 公司類型 | Hurdle | 主要估值法 | B4／C2／C4 關鍵追問 |"
    fund_rows: list[list[str]] = []
    single_table = main.count(fund_header) == 1
    if single_table:
        for line in main.split(fund_header, 1)[1].splitlines()[2:]:
            stripped = line.strip()
            if not stripped.startswith("|"):
                break
            fund_rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
    legacy_case_types = {
        "製造業": "15%",
        "SaaS": "25%",
        "矽智財": "25%",
        "半導體設備": "25–30%",
        "租賃": "15%",
        "AIDC": "25%",
    }
    bad_rows = []
    for key, hurdle in legacy_case_types.items():
        row = next((item for item in fund_rows if key in item[0]), None)
        if row is None or len(row) != 4 or not all(row) or row[1] != hurdle:
            bad_rows.append(f"{key}({row[1] if row and len(row) > 1 else 'missing'})")
    check(
        "case-type matrix keeps the six legacy rows in one table",
        single_table and not bad_rows,
        ", ".join(bad_rows),
    )

    missing_mctx = [f"M-CTX-{n}" for n in range(1, 8) if f"**M-CTX-{n}**" not in main]
    check(
        "cross-Stage context rules M-CTX-1..7 are named",
        not missing_mctx,
        ", ".join(missing_mctx),
    )

    check(
        "valuation exit-multiple defaults are preserved",
        "0.75 / 0.85 / 1.0" in main and "5x / 8x / 12x" in main,
    )
    sector_terms = [
        "MRR、Churn、CAC、LTV、NRR",
        "良率、客戶驗證週期、Sole-source",
        "槓桿、利差、期限錯配、covenant",
        "SBC 正常化、關聯交易",
        "庫存、毛利結構、供應商集中",
    ]
    missing_sector_terms = [term for term in sector_terms if term not in main]
    check(
        "sector-specific diligence questions are preserved",
        not missing_sector_terms,
        ", ".join(missing_sector_terms),
    )

    scripts_compile = True
    compile_errors: list[str] = []
    for path in (SKILL / "scripts").glob("*.py"):
        try:
            compile(read(path), str(path), "exec")
        except SyntaxError as exc:
            scripts_compile = False
            compile_errors.append(f"{path.name}:{exc.lineno}")
    check("all bundled scripts compile", scripts_compile, ", ".join(compile_errors))

    irr_path = SKILL / "scripts" / "irr_matrix.py"
    spec = importlib.util.spec_from_file_location("evaluator_irr_matrix", irr_path)
    irr_ok = False
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        irr_rows, mult_rows = module.build_pe_matrix(100, 10, 1, [10], [100])
        baseline_ok = irr_rows[1][1] == "0.0%" and mult_rows[1][1] == "1.00x"
        marked_rows, _ = module.build_pe_matrix(
            100, 10, 1, [2, 11, 20], [100], hurdle_pct=15
        )
        hurdle_ok = marked_rows[1][1:] == ["❌ -80.0%", "⚠️ 10.0%", "✅ 100.0%"]
        irr_ok = baseline_ok and hurdle_ok
    check("IRR baseline and hurdle markers are deterministic", irr_ok)

    metadata = read(SKILL / "agents" / "openai.yaml")
    check("agent metadata invokes skill", "$vc-investment-evaluator" in metadata)

    for name, ok, detail in results:
        suffix = f" — {detail}" if detail else ""
        print(f"[{'PASS' if ok else 'FAIL'}] {name}{suffix}")
    passed = sum(ok for _, ok, _ in results)
    print(f"\nResult: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(run())
