#!/usr/bin/env python3
"""Behavioural tests for data room ingestion.

The failure these guard against is silence: a signed financial statement with no
text layer used to contribute nothing and say nothing, so a case looked thin when
it was simply unread.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "vc-investment-evaluator" / "scripts"

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None

spec = importlib.util.spec_from_file_location("ingest_dataroom", SCRIPTS / "ingest_dataroom.py")
ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest)


def make_pdf(path: Path, text_pages: int, blank_pages: int) -> Path:
    document = fitz.open()
    for index in range(text_pages):
        page = document.new_page()
        page.insert_text((72, 72), f"Statement of financial position page {index + 1}. " * 6)
    for _ in range(blank_pages):
        document.new_page()
    path.parent.mkdir(parents=True, exist_ok=True)
    document.save(path)
    document.close()
    return path


@unittest.skipIf(fitz is None, "PyMuPDF not installed")
class ClassificationTests(unittest.TestCase):
    def test_kinds(self) -> None:
        self.assertEqual(ingest.classify(10, 0), "scanned_only")
        self.assertEqual(ingest.classify(10, 4), "mixed")
        self.assertEqual(ingest.classify(10, 10), "text")

    def test_financial_names_are_recognised(self) -> None:
        self.assertTrue(ingest.looks_financial(Path("附件5 示範能源2023財報签字版.pdf")))
        self.assertTrue(ingest.looks_financial(Path("示範能源11506BS.pdf")))
        self.assertFalse(ingest.looks_financial(Path("公司章程.pdf")))

    def test_unreadable_financials_are_p0_and_readable_ones_are_absent(self) -> None:
        sources = [
            {"source": "/x/附件5 示範能源2023財報签字版.pdf", "kind": "scanned_only", "pages": 22,
             "pages_under_40_chars": 22, "financial_source": True, "rendered_pages": ["a"]},
            {"source": "/x/公司章程.pdf", "kind": "scanned_only", "pages": 3,
             "pages_under_40_chars": 3, "financial_source": False, "rendered_pages": []},
            {"source": "/x/簡報.pdf", "kind": "text", "pages": 10,
             "pages_under_40_chars": 0, "financial_source": False, "rendered_pages": []},
        ]
        gaps = ingest.gap_entries(sources)
        by_priority = {gap["item"]: gap["priority"] for gap in gaps}
        self.assertEqual(len(gaps), 2, "fully readable sources must not create gaps")
        self.assertEqual(by_priority["附件5 示範能源2023財報签字版.pdf 可搜尋版或視覺覆核"], "P0")
        self.assertEqual(by_priority["公司章程.pdf 可搜尋版或視覺覆核"], "P1")

    def test_scanned_financial_statement_is_rendered_and_reported(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            dataroom = root / "dataroom"
            make_pdf(dataroom / "附件5 示範能源2023財報签字版.pdf", text_pages=0, blank_pages=3)
            make_pdf(dataroom / "公司章程.pdf", text_pages=2, blank_pages=0)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "ingest_dataroom.py"), str(dataroom),
                 "--output-dir", str(root / "out")],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((root / "out" / "ingest_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["counts"], {"sources": 2, "text": 1, "mixed": 0, "scanned_only": 1})
            self.assertEqual(report["unreadable_financial_sources"], ["附件5 示範能源2023財報签字版.pdf"])
            renders = list((root / "out" / "evidence_render").rglob("page-*.png"))
            self.assertEqual(len(renders), 3, "every unreadable page must be rendered for review")

    def test_render_cap_is_recorded_not_silent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            dataroom = root / "dataroom"
            make_pdf(dataroom / "年報.pdf", text_pages=0, blank_pages=5)
            subprocess.run(
                [sys.executable, str(SCRIPTS / "ingest_dataroom.py"), str(dataroom),
                 "--output-dir", str(root / "out"), "--max-render-pages", "2"],
                capture_output=True, text=True, encoding="utf-8", check=True,
            )
            meta = json.loads((root / "out" / "evidence_text" / "年報.meta.json").read_text(encoding="utf-8"))
            self.assertTrue(meta["rendered_truncated"])
            self.assertEqual(len(meta["rendered_pages"]), 2)
            self.assertEqual(len(meta["scanned_pages"]), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
