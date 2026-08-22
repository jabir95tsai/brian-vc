# prospectus-extractor 修正完成複驗

日期：2026-07-31  
範圍：2026-07-30 第二次審計的 7 項修正

## 結論

核心修正於兩個 Python runtime 均通過：

| Runtime | Python | PDF backend 狀態 | 結果 |
|---|---:|---|---:|
| Miniconda | 3.13.12 | pypdf + PyMuPDF + openpyxl | 19/19 OK |
| Codex bundled 26.730.11710 | 3.12.13 | pypdf + openpyxl；以 native pdftoppm fallback 轉圖 | 19/19 OK |

OpenAI Skill validator：`Skill is valid!`

## 七項逐條結果

1. Poppler 未宣告硬依賴：已解除。Step 1 使用 pypdf；轉圖使用 PyMuPDF
   或 pdftoppm fallback。缺 backend 時為可讀 exit 2，不出 traceback。
2. Manifest 缺 pdfinfo 永遠 failed：已解除。頁數 backend 回報 `pypdf`。
3. 垃圾 Markdown 假綠燈：已阻擋。Raw、Factbase、Coverage 任一與重新渲染
   結果不同，`content_match=false` 且 manifest failed。
4. W-ID／斜線漂移：section map 已固定 W01-W24；validator 以 NFKC
   正規化全形／半形斜線。
5. Excel 狀態誤標：只辨識各 sheet A2 的固定狀態前綴；完整的
   `00_覆蓋率` 不再進 flagged_not_applicable_pages。
6. `.gitignore` 無作用：runner 設定 `sys.dont_write_bytecode`，開始與結束
   都清理限定範圍的 cache／fixture。
7. 報告遺漏依賴風險：已補 PDF backend、缺依賴與真實公說未驗範圍。

## 額外發現與修正

Codex bundled 的 `pdftoppm.cmd` wrapper 指向不存在的
`native/poppler/bin/pdftoppm.cmd`，但實際 executable 位於
`native/poppler/Library/bin/pdftoppm.exe`。`render_pdf_pages.py` 現在會辨識
bundled runtime layout 並直接使用 native executable；不修改 bundled runtime。

獨立 CLI smoke：

```text
backend: pdftoppm
render status: success
PATH empty Step 1 exit: 0
scanned pages: [1]
manual smoke residue: false
```

## 仍不證明

- 尚未用 100+ 頁真實台灣公開說明書驗證目錄版面、offset、OCR 與財務表格
  萃取品質。
- 尚未完成 35 張 Excel 的逐頁視覺 QA。
- Excel authoring 仍為已宣告的 openpyxl 過渡路徑，尚未遷移
  `@oai/artifact-tool`。

