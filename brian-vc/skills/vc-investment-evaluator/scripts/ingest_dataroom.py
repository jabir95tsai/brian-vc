#!/usr/bin/env python3
"""Ingest data room PDFs and make un-extractable evidence a loud signal.

A signed financial statement that is a pure scan yields no text, and the
evaluator that only reads text layers will quietly build a one-row history from
whichever file happened to be searchable. That silence is the failure: the case
looks thin when it is actually unread. This step classifies every source, renders
the pages a human still has to look at, and emits the gap entries that belong in
the missing-items register so the risk matrix can carry them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Prefer the modern module name: PyMuPDF >= 1.28 still exposes `fitz` but
# prints a deprecation warning to stdout when it is imported under that alias,
# which pollutes machine-readable output. Fall back for older pins.
try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - depends on the installed PyMuPDF
    try:
        import fitz  # PyMuPDF < 1.24.3
    except ImportError:  # pragma: no cover - dependency is declared in requirements.txt
        print("ERROR: ingest_dataroom.py requires PyMuPDF; install brian-vc/requirements.txt", file=sys.stderr)
        raise SystemExit(2)

# A page carrying fewer characters than this is a scan or a divider, not prose we
# can cite. The prospectus extractor uses the same threshold.
MIN_PAGE_CHARS = 40
SCANNED_RENDER_DPI = 200
# Sources whose names suggest audited or statutory financials: these are the ones
# where "unreadable" must never be downgraded to "absent".
FINANCIAL_HINTS = ("財報", "財務報表", "年報", "查核", "財簽", "BS", "IS", "CF", "損益", "資產負債", "現金流量")


def safe_name(text: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", text).strip("._")
    return cleaned or "source"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def looks_financial(path: Path) -> bool:
    return any(hint.lower() in path.name.lower() for hint in FINANCIAL_HINTS)


def classify(pages: int, pages_with_text: int) -> str:
    if pages_with_text == 0:
        return "scanned_only"
    if pages_with_text < pages:
        return "mixed"
    return "text"


def ingest_pdf(pdf: Path, text_dir: Path, render_dir: Path, render: bool, max_render: int) -> dict:
    document = fitz.open(pdf)
    page_stats = []
    chunks = []
    scanned_pages = []
    for index in range(document.page_count):
        text = document[index].get_text("text") or ""
        characters = len(text.strip())
        page_stats.append({"physical_page": index + 1, "characters": characters})
        if characters < MIN_PAGE_CHARS:
            scanned_pages.append(index + 1)
        else:
            chunks.append(f"\n\n===== [p.{index + 1}] =====\n{text}")

    pages = document.page_count
    pages_with_text = pages - len(scanned_pages)
    kind = classify(pages, pages_with_text)
    stem = safe_name(pdf.stem)

    text_dir.mkdir(parents=True, exist_ok=True)
    text_path = text_dir / f"{stem}.txt"
    text_path.write_text("".join(chunks).strip() + "\n", encoding="utf-8")

    rendered: list[str] = []
    if render and scanned_pages:
        target = render_dir / stem
        target.mkdir(parents=True, exist_ok=True)
        matrix = fitz.Matrix(SCANNED_RENDER_DPI / 72, SCANNED_RENDER_DPI / 72)
        for number in scanned_pages[:max_render]:
            image = document[number - 1].get_pixmap(matrix=matrix)
            out = target / f"page-{number:04d}.png"
            image.save(out)
            rendered.append(str(out))
    document.close()

    meta = {
        "source": str(pdf.resolve()),
        "sha256": sha256_file(pdf),
        "pages": pages,
        "pages_with_text": pages_with_text,
        "pages_under_40_chars": len(scanned_pages),
        "kind": kind,
        "financial_source": looks_financial(pdf),
        "scanned_pages": scanned_pages,
        "rendered_pages": rendered,
        "rendered_truncated": len(scanned_pages) > len(rendered) if render else None,
        "text_output": str(text_path.resolve()),
        "page_stats": page_stats,
    }
    (text_dir / f"{stem}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return meta


def gap_entries(sources: list[dict]) -> list[dict]:
    """Turn unreadable evidence into missing_items the risk matrix can carry."""
    entries = []
    for meta in sources:
        if meta["kind"] == "text":
            continue
        name = Path(meta["source"]).name
        financial = meta["financial_source"]
        if meta["kind"] == "scanned_only":
            reason = (
                f"{meta['pages']} 頁全為掃描影像，無文字層；"
                + ("歷史財務無法結構化，不得以其他來源代替。" if financial else "內容未進入事實底稿。")
            )
        else:
            reason = (
                f"{meta['pages_under_40_chars']}/{meta['pages']} 頁無可擷取文字；"
                "已渲染供視覺覆核，未覆核前不得視為已讀。"
            )
        entries.append(
            {
                "item": f"{name} 可搜尋版或視覺覆核",
                "priority": "P0" if financial else "P1",
                "reason": reason,
                "source_kind": meta["kind"],
                "rendered_pages": len(meta["rendered_pages"]),
            }
        )
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataroom", type=Path, help="Directory of source PDFs (searched recursively).")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--no-render", action="store_true", help="Skip PNG rendering of scanned pages.")
    parser.add_argument(
        "--max-render-pages",
        type=int,
        default=40,
        help="Cap rendered pages per source; the cap is recorded, never silent.",
    )
    args = parser.parse_args()

    pdfs = sorted(p for p in args.dataroom.rglob("*.pdf") if p.is_file())
    if not pdfs:
        print(f"ERROR: no PDF found under {args.dataroom}", file=sys.stderr)
        return 2

    text_dir = args.output_dir / "evidence_text"
    render_dir = args.output_dir / "evidence_render"
    sources = [
        ingest_pdf(pdf, text_dir, render_dir, not args.no_render, args.max_render_pages)
        for pdf in pdfs
    ]

    gaps = gap_entries(sources)
    unreadable_financials = [
        Path(meta["source"]).name
        for meta in sources
        if meta["financial_source"] and meta["kind"] == "scanned_only"
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataroom": str(args.dataroom.resolve()),
        "counts": {
            "sources": len(sources),
            "text": sum(1 for m in sources if m["kind"] == "text"),
            "mixed": sum(1 for m in sources if m["kind"] == "mixed"),
            "scanned_only": sum(1 for m in sources if m["kind"] == "scanned_only"),
        },
        "unreadable_financial_sources": unreadable_financials,
        "suggested_missing_items": gaps,
        "sources": [
            {key: meta[key] for key in ("source", "sha256", "pages", "pages_with_text", "kind", "financial_source", "text_output", "rendered_pages")}
            for meta in sources
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "ingest_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("counts", "unreadable_financial_sources")} | {"report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
