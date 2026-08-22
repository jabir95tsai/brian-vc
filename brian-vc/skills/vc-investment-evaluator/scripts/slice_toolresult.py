#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""超長檔錨點切片（M-CTX-4）。

情境一：外部讀檔工具回傳的完整內容另存為本機 JSON，內容位於指定欄位。
情境二：Stage E/F 只需讀某 raw 檔的 ## DECK_EXPORT 區塊，不讀全文。

一律用 str.find 切片，勿用 Grep（單行超長會被標 Omitted）。

用法：
  python slice_toolresult.py <file> --start "肆、財務概況" --end "伍、"          # 章節切片
  python slice_toolresult.py <file> --start "## DECK_EXPORT"                    # 切到檔尾
  python slice_toolresult.py <file> --json-field fileContent --start "..."      # tool-result JSON
  python slice_toolresult.py <file> --list-anchors "壹,貳,參,肆,伍,## "         # 列錨點位置驗收章節命中
"""
import argparse
import json
import sys


def load_text(path, json_field=None):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    if json_field:
        data = json.loads(raw)
        # tool-result 可能是 dict 或 list-of-parts
        if isinstance(data, dict):
            return str(data.get(json_field, ""))
        if isinstance(data, list):
            return "\n".join(str(d.get(json_field, "")) for d in data if isinstance(d, dict))
    return raw


def main():
    p = argparse.ArgumentParser()
    p.add_argument("file")
    p.add_argument("--start", help="起始錨點（含）")
    p.add_argument("--end", help="結束錨點（不含；省略＝切到檔尾）")
    p.add_argument("--json-field", help="檔案為 JSON 時取此欄位（如 fileContent）")
    p.add_argument("--list-anchors", help="逗號分隔錨點清單，只列出現位置（章節命中驗收）")
    p.add_argument("--max-chars", type=int, default=60000, help="輸出上限（防再爆 context）")
    a = p.parse_args()

    text = load_text(a.file, a.json_field)
    print(f"# 全文長度：{len(text):,} 字元", file=sys.stderr)

    if a.list_anchors:
        for anchor in [x.strip() for x in a.list_anchors.split(",") if x.strip()]:
            pos = text.find(anchor)
            status = f"命中 @ {pos:,}" if pos >= 0 else "⚠️ 未命中"
            print(f"{anchor}: {status}")
        return 0

    if not a.start:
        p.error("需 --start 或 --list-anchors")
    i = text.find(a.start)
    if i < 0:
        print(f"⚠️ 起始錨點未命中：{a.start}", file=sys.stderr)
        return 1
    j = len(text)
    if a.end:
        j2 = text.find(a.end, i + len(a.start))
        if j2 >= 0:
            j = j2
        else:
            print(f"# 結束錨點未命中，切到檔尾", file=sys.stderr)
    out = text[i:j]
    if len(out) > a.max_chars:
        print(f"# 已截斷輸出至 {a.max_chars:,} 字元（原 {len(out):,}）", file=sys.stderr)
        out = out[: a.max_chars]
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
