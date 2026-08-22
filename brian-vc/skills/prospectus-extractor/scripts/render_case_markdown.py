# -*- coding: utf-8 -*-
"""Render Raw and Coverage Markdown from canonical case_data.json."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from prospectus_contract import status_label
from validate_case_data import validate_data


def _citation_text(citation: dict[str, Any]) -> str:
    source_id = citation["source_id"]
    parts = [source_id]
    if citation.get("physical_page") is not None:
        parts.append(f"physical p.{citation['physical_page']}")
    if citation.get("printed_page") is not None:
        parts.append(f"printed p.{citation['printed_page']}")
    if citation.get("sheet"):
        parts.append(f"sheet={citation['sheet']}")
    if citation.get("cell_or_range"):
        parts.append(f"cell={citation['cell_or_range']}")
    if citation.get("method"):
        parts.append(f"method={citation['method']}")
    return " / ".join(parts)


def render_raw(data: dict[str, Any]) -> str:
    case = data["case"]
    lines = [
        f"# {case['title']} — Prospectus Raw",
        "",
        "> 本檔由 case_data.json 渲染；保留來源與定位，不含投資結論。",
        "",
        "## 來源索引",
        "",
        "| source_id | role | path_or_url | document_date |",
        "|---|---|---|---|",
    ]
    for source in data["sources"]:
        lines.append(
            f"| {source['source_id']} | {source['role']} | "
            f"{str(source['path_or_url']).replace('|', '/')} | {source.get('document_date') or '未提供'} |"
        )

    for section in sorted(data["raw_sections"], key=lambda item: item["order"]):
        lines.extend(["", f"## {section['title']}", "", section["content"].rstrip()])
        citations = section.get("citations", [])
        if citations:
            lines.extend(["", "來源：" + "；".join(_citation_text(c) for c in citations)])
        else:
            lines.extend(["", "來源：⚠️ 未提供定位"])
    return "\n".join(lines).rstrip() + "\n"


def render_coverage(data: dict[str, Any]) -> str:
    counts = Counter(item["status"] for item in data["coverage"])
    case = data["case"]
    lines = [
        f"# {case['title']} — Prospectus Coverage",
        "",
        (
            "核心覆蓋率："
            f"complete {counts['complete']} / partial {counts['partial']} / "
            f"missing {counts['missing']} / not_applicable {counts['not_applicable']} / total 24"
        ),
        "",
        "> Excel 母版完整度是獨立 QA 指標；不得以 35/35 取代資料覆蓋率。",
        "",
        "| ID | 項目 | 狀態 | 對應分頁 | 來源／缺因 |",
        "|---|---|---|---|---|",
    ]
    for item in data["coverage"]:
        refs_or_reason = ", ".join(item["source_refs"]) or item.get("reason") or ""
        sheets = ", ".join(item["sheet_names"])
        lines.append(
            f"| {item['id']} | {item['title']} | {status_label(item['status'])} | "
            f"{sheets.replace('|', '/')} | {refs_or_reason.replace('|', '/')} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_data")
    parser.add_argument("--raw-out", required=True)
    parser.add_argument("--coverage-out", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.case_data).read_text(encoding="utf-8"))
    result = validate_data(data)
    if result["status"] != "success":
        raise SystemExit("case_data validation failed:\n" + "\n".join(result["errors"]))

    Path(args.raw_out).write_bytes(render_raw(data).encode("utf-8"))
    Path(args.coverage_out).write_bytes(render_coverage(data).encode("utf-8"))
    print(f"WROTE raw={args.raw_out}")
    print(f"WROTE coverage={args.coverage_out}")


if __name__ == "__main__":
    main()
