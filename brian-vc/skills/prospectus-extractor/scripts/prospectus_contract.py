# -*- coding: utf-8 -*-
"""Canonical contract constants shared by prospectus-extractor scripts."""

from __future__ import annotations

CONTRACT_VERSION = "1.0"
CASE_DATA_SCHEMA_VERSION = "1.0"

ALLOWED_STATUSES = ("complete", "partial", "missing", "not_applicable")

SHEET_SKELETON_NAMES = [
    "00_封面",
    "00_覆蓋率",
    "01_公司沿革",
    "02_股本形成",
    "03_董監事",
    "04_經營團隊",
    "05_主要股東",
    "06_產品營收比重",
    "07_目前產品與服務",
    "08_未來新產品服務",
    "09_未來研發計畫",
    "10_研發成功技術",
    "11_研發人員學經歷",
    "12_從業員工人數",
    "13_產品用途",
    "14_產製過程",
    "15_毛利率變化",
    "16_銷售地區",
    "17_主要供應商",
    "18_主要客戶",
    "19_銷售量值",
    "20_生產量值",
    "21_產能利用率",
    "22_產業概況",
    "23_中下游關聯",
    "24_競爭情勢",
    "25_轉投資",
    "26_重要契約",
    "27_歷年財務摘要5年",
    "28甲_損益表",
    "28乙_資產負債表",
    "28丙_現金流量表",
    "29_AI專家",
    "查核意見_明細",
    "紅旗",
]

COVERAGE_ITEMS = [
    ("W01", "公司沿革"),
    ("W02", "未來研發計畫"),
    ("W03", "董監事"),
    ("W04", "經營團隊"),
    ("W05", "主要股東"),
    ("W06", "股本形成"),
    ("W07", "主要產品營收比重"),
    ("W08", "產業概況"),
    ("W09", "中下游關聯性"),
    ("W10", "競爭情勢"),
    ("W11", "研發人員與學經歷"),
    ("W12", "研發成功的技術或成果"),
    ("W13", "銷售地區"),
    ("W14", "產品之用途"),
    ("W15", "產品之產製過程"),
    ("W16", "主要原料供應商"),
    ("W17", "主要銷貨／客戶"),
    ("W18", "銷售量值"),
    ("W19", "從業員工人數"),
    ("W20", "產品別／部門別毛利率變化"),
    ("W21", "轉投資狀況"),
    ("W22", "重要契約"),
    ("W23", "歷年財務摘要"),
    ("W24", "附件財務報表"),
]

COVERAGE_IDS = [item_id for item_id, _ in COVERAGE_ITEMS]
COVERAGE_TITLES = dict(COVERAGE_ITEMS)

EXPECTED_BUSINESS_OUTPUT_SUFFIXES = [
    "_case_data.json",
    "_Prospectus_raw.md",
    "_Factbase.md",
    "_Prospectus_coverage.md",
    "_Prospectus_extract.xlsx",
]


def status_label(status: str) -> str:
    return {
        "complete": "✅ 完整",
        "partial": "🟡 部分",
        "missing": "🔴 缺失",
        "not_applicable": "⚪ 不適用",
    }.get(status, status)


def coverage_excel_rows(coverage: list[dict]) -> list[list[str]]:
    """Canonical rows for Excel 00_覆蓋率; never maintain a second manual copy."""
    return [
        [
            item["id"],
            item["title"],
            status_label(item["status"]),
            ", ".join(item["sheet_names"]),
            ", ".join(item["source_refs"]) or item.get("reason") or "",
        ]
        for item in coverage
    ]
