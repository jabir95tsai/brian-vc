# -*- coding: utf-8 -*-
"""Portable PDF access for prospectus-extractor.

Step 1 must not depend on Poppler executables being present on PATH.  pypdf is
the required backend for page count, outline access, and text-layer extraction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class PdfBackendError(RuntimeError):
    """Readable PDF/backend failure suitable for CLI output."""


def _load_pypdf():
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise PdfBackendError(
            "缺少必要 Python 套件 pypdf，無法讀取 PDF。"
            "請先執行：python -m pip install -r requirements.txt"
        ) from exc
    return PdfReader


class PdfDocument:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.is_file():
            raise PdfBackendError(f"找不到 PDF：{self.path}")
        PdfReader = _load_pypdf()
        try:
            self.reader = PdfReader(str(self.path))
            if self.reader.is_encrypted:
                try:
                    unlocked = self.reader.decrypt("")
                except Exception as exc:
                    raise PdfBackendError(f"PDF 已加密且無法解鎖：{self.path}") from exc
                if unlocked == 0:
                    raise PdfBackendError(f"PDF 已加密且需要密碼：{self.path}")
            self.pages = len(self.reader.pages)
        except PdfBackendError:
            raise
        except Exception as exc:
            raise PdfBackendError(f"PDF 無法讀取或已毀損：{self.path}（{exc}）") from exc
        if self.pages <= 0:
            raise PdfBackendError(f"PDF 頁數為 0：{self.path}")

    def page_text(self, physical_page: int) -> str:
        if physical_page < 1 or physical_page > self.pages:
            raise PdfBackendError(
                f"PDF 頁碼超出範圍：{physical_page}（有效範圍 1-{self.pages}）"
            )
        page = self.reader.pages[physical_page - 1]
        if "/Contents" not in page:
            return ""
        try:
            try:
                text = page.extract_text(extraction_mode="layout")
            except TypeError:
                text = page.extract_text()
        except Exception as exc:
            raise PdfBackendError(
                f"無法擷取 PDF 實體第 {physical_page} 頁文字：{exc}"
            ) from exc
        return text or ""

    def outline_items(self) -> list[tuple[int, str, int]]:
        items: list[tuple[int, str, int]] = []
        try:
            outline: Any = self.reader.outline
        except Exception:
            return items

        def walk(nodes: Any, depth: int = 0) -> None:
            for item in nodes:
                if isinstance(item, list):
                    walk(item, depth + 1)
                    continue
                try:
                    title = str(item.title).strip()
                    page = self.reader.get_destination_page_number(item) + 1
                    items.append((depth, title, page))
                except Exception:
                    continue

        try:
            walk(outline)
        except Exception:
            return []
        return items


def count_pdf_pages(path: str | Path) -> int:
    return PdfDocument(path).pages
