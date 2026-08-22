# -*- coding: utf-8 -*-
"""Render selected PDF pages to PNG without requiring Poppler."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pdf_backend import PdfBackendError, count_pdf_pages


def parse_pages(spec: str, total: int) -> list[int]:
    pages: set[int] = set()
    for token in spec.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"頁碼範圍起點大於終點：{token}")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(token))
    invalid = sorted(page for page in pages if page < 1 or page > total)
    if invalid:
        raise ValueError(f"頁碼超出範圍 1-{total}：{invalid}")
    return sorted(pages)


def _render_with_pymupdf(pdf: Path, outdir: Path, pages: list[int], dpi: int) -> list[Path] | None:
    # Prefer the modern module name. PyMuPDF >= 1.28 keeps `fitz` working but
    # prints a deprecation warning to STDOUT, which corrupts the JSON this
    # script writes there. Fall back for pins older than the rename.
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            return None
    outputs: list[Path] = []
    document = fitz.open(str(pdf))
    try:
        scale = dpi / 72
        matrix = fitz.Matrix(scale, scale)
        for page_number in pages:
            pixmap = document.load_page(page_number - 1).get_pixmap(matrix=matrix, alpha=False)
            output = outdir / f"page-{page_number:04d}.png"
            pixmap.save(str(output))
            outputs.append(output)
    finally:
        document.close()
    return outputs


def _find_pdftoppm() -> Path | None:
    candidate = shutil.which("pdftoppm")
    if not candidate:
        return None
    path = Path(candidate)
    # Codex bundled runtimes may expose a .cmd wrapper whose internal path is
    # stale while the native Poppler executable is present beside the runtime.
    for parent in path.parents:
        native = parent / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe"
        if native.is_file():
            return native
    return path


def _render_with_pdftoppm(pdf: Path, outdir: Path, pages: list[int], dpi: int) -> list[Path] | None:
    executable = _find_pdftoppm()
    if executable is None:
        return None
    outputs: list[Path] = []
    for page_number in pages:
        prefix = outdir / f"page-{page_number:04d}"
        command = [
                str(executable),
                "-png",
                "-singlefile",
                "-r",
                str(dpi),
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                str(pdf),
                str(prefix),
            ]
        if executable.suffix.lower() in (".cmd", ".bat"):
            command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", *command]
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if proc.returncode != 0:
            raise PdfBackendError(
                f"pdftoppm 轉圖失敗（physical p.{page_number}）："
                f"{proc.stderr.strip() or proc.stdout.strip()}"
            )
        output = prefix.with_suffix(".png")
        if not output.is_file():
            raise PdfBackendError(f"pdftoppm 未產生預期檔案：{output}")
        outputs.append(output)
    return outputs


def render_pages(pdf: Path, outdir: Path, pages: list[int], dpi: int = 150) -> tuple[str, list[Path]]:
    outdir.mkdir(parents=True, exist_ok=True)
    outputs = _render_with_pymupdf(pdf, outdir, pages, dpi)
    if outputs is not None:
        return "pymupdf", outputs
    outputs = _render_with_pdftoppm(pdf, outdir, pages, dpi)
    if outputs is not None:
        return "pdftoppm", outputs
    raise PdfBackendError(
        "缺少 PDF 轉圖後端。請執行 "
        "python -m pip install -r requirements.txt（安裝 PyMuPDF），"
        "或在系統安裝 pdftoppm。"
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--pages", required=True, help="例如 3,5-8")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()
    try:
        pdf = Path(args.pdf).resolve()
        total = count_pdf_pages(pdf)
        pages = parse_pages(args.pages, total)
        if not pages:
            raise ValueError("--pages 未指定任何頁碼")
        backend, outputs = render_pages(pdf, Path(args.outdir).resolve(), pages, args.dpi)
        print(
            json.dumps(
                {
                    "status": "success",
                    "backend": backend,
                    "pages": pages,
                    "outputs": [str(path) for path in outputs],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except (OSError, ValueError, PdfBackendError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
