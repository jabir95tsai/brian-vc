#!/usr/bin/env python3
"""
slice_prospectus.py - Taiwan prospectus (公開說明書) sectioniser.

Turns a 100+ page prospectus into a navigable section -> page-range index so the
agent can extract one whitelisted section at a time instead of skimming the whole
file (which loses detail and blows up context).

Outputs (to --outdir):
  index.json        : {meta, sections:[{level,num? ,title,start_page,end_page,scanned}]}
  index.md          : human-readable section -> page map
  sections/NN_*.txt : extracted text per top-level section (text-layer pages only)
  scanned_pages.json: page numbers with little/no text layer (need OCR/Vision)

Usage:
  python slice_prospectus.py INPUT.pdf --outdir OUT [--dump-sections]

Key gotcha handled: TOC page numbers are PRINTED numbers while PDF APIs use
PHYSICAL page indices; front-matter offset is auto-detected and applied.
"""
import sys, os, re, json, argparse

from pdf_backend import PdfBackendError, PdfDocument

CJK_NUM = "一二三四五六七八九十"
TOP = "壹貳參肆伍陸柒捌玖拾"

def detect_scanned(document, n, threshold=60):
    out = []
    for p in range(1, n + 1):
        if len(re.sub(r"\s", "", document.page_text(p))) < threshold:
            out.append(p)
    return out

def parse_printed_toc(document, toc_pages=6):
    txt = "".join(document.page_text(p) for p in range(1, min(toc_pages, document.pages) + 1))
    items = []
    for m in re.finditer(rf"([{TOP}])、([^\.\n]+?)\s*\.{{3,}}\s*(\d+)", txt):
        items.append((0, f"{m.group(1)}、{m.group(2).strip()}", int(m.group(3))))
    for m in re.finditer(rf"^\s*([{CJK_NUM}]+)、([^\.\n]+?)\s*\.{{3,}}\s*(\d+)", txt, re.M):
        items.append((1, f"{m.group(1)}、{m.group(2).strip()}", int(m.group(3))))
    seen = {}
    for lvl, title, pg in items:
        k = (title, pg)
        if k not in seen or lvl < seen[k][0]:
            seen[k] = (lvl, title, pg)
    out = list(seen.values())
    out.sort(key=lambda x: x[2])
    return out

def detect_offset(document, n, scan=15):
    """physical = printed + offset. Find physical page whose top is body '壹、' (not TOC)."""
    for p in range(1, min(scan, n) + 1):
        head = "\n".join(document.page_text(p).splitlines()[:4])
        if re.search(r"^\s*壹、", head, re.M) and "...." not in head:
            return p - 1
    return 0

def assign_end_pages(items, n):
    """End a section at the next sibling/ancestor boundary, not at its first child.

    The old implementation used the next page number at any nesting level.  A
    top-level section beginning on p.10 with its first child on p.11 therefore
    ended on p.10 and lost the rest of the section when --dump-sections ran.
    """
    ordered = sorted(items, key=lambda item: (item[2], item[0]))
    res = []
    for idx, (lvl, title, sp) in enumerate(ordered):
        next_boundaries = [
            later_start
            for later_level, _later_title, later_start in ordered[idx + 1 :]
            if later_level <= lvl and later_start > sp
        ]
        ep = (min(next_boundaries) - 1) if next_boundaries else n
        res.append({"level": lvl, "title": title, "start_page": sp, "end_page": max(sp, ep)})
    return res

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--dump-sections", action="store_true")
    ap.add_argument("--toc-pages", type=int, default=6)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    try:
        document = PdfDocument(args.pdf)
    except PdfBackendError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
    n = document.pages

    items = document.outline_items(); method = "outline"
    if len(items) < 3:
        items = parse_printed_toc(document, args.toc_pages); method = "printed_toc"

    offset = detect_offset(document, n) if method == "printed_toc" else 0
    if offset:
        items = [(l, t, p + offset) for (l, t, p) in items]

    sections = assign_end_pages(items, n) if items else []
    scanned = detect_scanned(document, n)
    sset = set(scanned)
    for s in sections:
        rng = range(s["start_page"], s["end_page"] + 1)
        s["scanned"] = len(rng) > 0 and all(p in sset for p in rng)

    index = {"meta": {"pdf": os.path.basename(args.pdf), "pages": n, "toc_method": method,
                      "printed_to_physical_offset": offset, "section_count": len(sections),
                      "scanned_page_count": len(scanned)},
             "sections": sections}
    with open(os.path.join(args.outdir, "index.json"), "w", encoding="utf-8") as handle:
        json.dump(index, handle, ensure_ascii=False, indent=2)
    with open(os.path.join(args.outdir, "scanned_pages.json"), "w", encoding="utf-8") as handle:
        json.dump(scanned, handle, ensure_ascii=False)

    lines = [f"# Prospectus section map - {index['meta']['pdf']}",
             f"pages={n} | toc={method} | offset=+{offset} | sections={len(sections)} | scanned={len(scanned)}", ""]
    for s in sections:
        pad = "  " * s["level"]
        flag = "  [SCANNED->OCR]" if s.get("scanned") else ""
        lines.append(f"{pad}- p{s['start_page']:>3}-{s['end_page']:<3} {s['title']}{flag}")
    if scanned:
        lines += ["", f"## Scanned/image pages (need OCR or Vision): {scanned}"]
    with open(os.path.join(args.outdir, "index.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))

    if args.dump_sections:
        sd = os.path.join(args.outdir, "sections"); os.makedirs(sd, exist_ok=True)
        tops = [x for x in sections if x["level"] == 0]
        for i, s in enumerate(tops):
            safe = re.sub(r"[^0-9A-Za-z一-鿿]+", "_", s["title"])[:40]
            txt = "".join(document.page_text(p) for p in range(s["start_page"], s["end_page"] + 1))
            with open(os.path.join(sd, f"{i:02d}_{safe}.txt"), "w", encoding="utf-8") as handle:
                handle.write(txt)

    with open(os.path.join(args.outdir, "index.md"), encoding="utf-8") as handle:
        print(handle.read())

if __name__ == "__main__":
    main()
