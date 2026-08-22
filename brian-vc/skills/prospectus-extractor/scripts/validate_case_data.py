# -*- coding: utf-8 -*-
"""Validate prospectus-extractor case_data.json without third-party packages."""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

from prospectus_contract import (
    ALLOWED_STATUSES,
    CASE_DATA_SCHEMA_VERSION,
    COVERAGE_IDS,
    COVERAGE_TITLES,
    SHEET_SKELETON_NAMES,
)


def _is_non_empty(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _normalize_title(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text.split())


def _require_keys(obj: dict[str, Any], keys: tuple[str, ...], path: str, errors: list[str]) -> None:
    for key in keys:
        if key not in obj:
            errors.append(f"{path}.{key}: required")


def validate_data(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return {"status": "failed", "errors": ["$: expected object"], "warnings": []}

    _require_keys(
        data,
        (
            "schema_version",
            "case",
            "sources",
            "coverage",
            "raw_sections",
            "sheets",
            "conflicts",
            "red_flags",
            "missing_items",
            "warnings",
        ),
        "$",
        errors,
    )
    if data.get("schema_version") != CASE_DATA_SCHEMA_VERSION:
        errors.append(
            f"$.schema_version: expected {CASE_DATA_SCHEMA_VERSION!r}, got {data.get('schema_version')!r}"
        )

    case = data.get("case")
    if not isinstance(case, dict):
        errors.append("$.case: expected object")
    else:
        _require_keys(case, ("case_id", "company_name"), "$.case", errors)
        for key in ("case_id", "company_name"):
            if key in case and not _is_non_empty(case[key]):
                errors.append(f"$.case.{key}: must be non-empty")

    sources = data.get("sources")
    source_ids: list[str] = []
    if not isinstance(sources, list) or not sources:
        errors.append("$.sources: expected non-empty array")
    else:
        for i, source in enumerate(sources):
            path = f"$.sources[{i}]"
            if not isinstance(source, dict):
                errors.append(f"{path}: expected object")
                continue
            _require_keys(source, ("source_id", "role", "path_or_url"), path, errors)
            source_id = source.get("source_id")
            if _is_non_empty(source_id):
                source_ids.append(str(source_id))
            if not _is_non_empty(source.get("path_or_url")):
                errors.append(f"{path}.path_or_url: must be non-empty")
        duplicates = sorted({x for x in source_ids if source_ids.count(x) > 1})
        if duplicates:
            errors.append(f"$.sources: duplicate source_id values: {duplicates}")
        if not any(isinstance(s, dict) and s.get("role") == "prospectus" for s in sources):
            errors.append("$.sources: at least one role='prospectus' source is required")
    source_id_set = set(source_ids)

    coverage = data.get("coverage")
    if not isinstance(coverage, list):
        errors.append("$.coverage: expected array")
        coverage = []
    coverage_ids = [str(x.get("id")) for x in coverage if isinstance(x, dict) and "id" in x]
    if len(coverage) != 24:
        errors.append(f"$.coverage: expected exactly 24 items, got {len(coverage)}")
    if coverage_ids != COVERAGE_IDS:
        errors.append("$.coverage: IDs must be exactly W01..W24 in canonical order")
    for i, item in enumerate(coverage):
        path = f"$.coverage[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{path}: expected object")
            continue
        _require_keys(item, ("id", "title", "status", "source_refs", "sheet_names", "reason"), path, errors)
        item_id = item.get("id")
        if (
            item_id in COVERAGE_TITLES
            and _normalize_title(item.get("title")) != _normalize_title(COVERAGE_TITLES[item_id])
        ):
            errors.append(f"{path}.title: expected {COVERAGE_TITLES[item_id]!r}")
        status = item.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{path}.status: invalid status {status!r}")
        refs = item.get("source_refs")
        if not isinstance(refs, list):
            errors.append(f"{path}.source_refs: expected array")
            refs = []
        unknown_refs = sorted({str(ref) for ref in refs if ref not in source_id_set})
        if unknown_refs:
            errors.append(f"{path}.source_refs: unknown source IDs {unknown_refs}")
        if status in ("complete", "partial") and not refs:
            errors.append(f"{path}.source_refs: required for status={status}")
        if status in ("missing", "not_applicable") and not _is_non_empty(item.get("reason")):
            errors.append(f"{path}.reason: required for status={status}")
        sheet_names = item.get("sheet_names")
        if not isinstance(sheet_names, list):
            errors.append(f"{path}.sheet_names: expected array")

    raw_sections = data.get("raw_sections")
    if not isinstance(raw_sections, list):
        errors.append("$.raw_sections: expected array")
    else:
        orders: list[int] = []
        for i, section in enumerate(raw_sections):
            path = f"$.raw_sections[{i}]"
            if not isinstance(section, dict):
                errors.append(f"{path}: expected object")
                continue
            _require_keys(section, ("order", "title", "content", "citations"), path, errors)
            if isinstance(section.get("order"), int):
                orders.append(section["order"])
            else:
                errors.append(f"{path}.order: expected integer")
            if not _is_non_empty(section.get("title")):
                errors.append(f"{path}.title: must be non-empty")
            citations = section.get("citations")
            if not isinstance(citations, list):
                errors.append(f"{path}.citations: expected array")
                citations = []
            for j, citation in enumerate(citations):
                if not isinstance(citation, dict):
                    errors.append(f"{path}.citations[{j}]: expected object")
                    continue
                _require_keys(citation, ("source_id", "physical_page"), f"{path}.citations[{j}]", errors)
                if citation.get("source_id") not in source_id_set:
                    errors.append(f"{path}.citations[{j}].source_id: unknown source ID")
        if orders and orders != sorted(orders):
            errors.append("$.raw_sections: order values must be ascending")
        if len(orders) != len(set(orders)):
            errors.append("$.raw_sections: order values must be unique")

    sheets = data.get("sheets")
    if not isinstance(sheets, list):
        errors.append("$.sheets: expected array")
        sheets = []
    sheet_names = [str(x.get("name")) for x in sheets if isinstance(x, dict) and "name" in x]
    duplicates = sorted({x for x in sheet_names if sheet_names.count(x) > 1})
    if duplicates:
        errors.append(f"$.sheets: duplicate names: {duplicates}")
    core_in_order = [name for name in sheet_names if name in SHEET_SKELETON_NAMES]
    if core_in_order != SHEET_SKELETON_NAMES:
        missing = [name for name in SHEET_SKELETON_NAMES if name not in sheet_names]
        errors.append(
            "$.sheets: first-class skeleton must contain all 35 canonical sheets in order"
            + (f"; missing={missing}" if missing else "")
        )
    for i, sheet in enumerate(sheets):
        path = f"$.sheets[{i}]"
        if not isinstance(sheet, dict):
            errors.append(f"{path}: expected object")
            continue
        _require_keys(sheet, ("name", "status", "header", "rows", "reason"), path, errors)
        status = sheet.get("status")
        if status not in ALLOWED_STATUSES:
            errors.append(f"{path}.status: invalid status {status!r}")
        header = sheet.get("header")
        rows = sheet.get("rows")
        if not isinstance(header, list):
            errors.append(f"{path}.header: expected array")
            header = []
        if not isinstance(rows, list):
            errors.append(f"{path}.rows: expected array")
            rows = []
        for j, row in enumerate(rows):
            if not isinstance(row, list):
                errors.append(f"{path}.rows[{j}]: expected array")
            elif header and len(row) != len(header):
                errors.append(
                    f"{path}.rows[{j}]: expected {len(header)} cells to match header, got {len(row)}"
                )
        if status in ("complete", "partial") and not rows and sheet.get("name") != "00_覆蓋率":
            errors.append(f"{path}.rows: non-empty rows required for status={status}")
        if status in ("missing", "not_applicable") and rows:
            errors.append(f"{path}.rows: must be empty for status={status}")
        if status in ("partial", "missing", "not_applicable") and not _is_non_empty(sheet.get("reason")):
            errors.append(f"{path}.reason: required for status={status}")
        if status == "complete" and _is_non_empty(sheet.get("reason")):
            warnings.append(f"{path}.reason: complete sheet normally leaves reason empty")

    if "29_AI專家" in sheet_names:
        ai_sheet = sheets[sheet_names.index("29_AI專家")]
        if isinstance(ai_sheet, dict) and ai_sheet.get("status") != "not_applicable":
            errors.append("$.sheets[29_AI專家].status: extractor must mark this downstream sheet not_applicable")

    for key in ("conflicts", "red_flags", "missing_items", "warnings"):
        if key in data and not isinstance(data[key], list):
            errors.append(f"$.{key}: expected array")

    return {
        "status": "success" if not errors else "failed",
        "schema_version": data.get("schema_version"),
        "coverage_items": len(coverage),
        "skeleton_sheets": len(core_in_order),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_data")
    parser.add_argument("--report")
    args = parser.parse_args()

    path = Path(args.case_data)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result = validate_data(data)
    except (OSError, json.JSONDecodeError) as exc:
        result = {"status": "failed", "errors": [str(exc)], "warnings": []}

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    sys.exit(0 if result["status"] == "success" else 2)


if __name__ == "__main__":
    main()
