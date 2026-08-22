# prospectus-extractor 核心資料層實作紀錄

日期：2026-07-30  
範圍：第一里程碑（資料契約、切片、Markdown、過渡 Excel、Manifest、測試）

## 結果

本里程碑把 `prospectus-extractor` 從提示詞與鬆散 JSON，改成可驗證、可重跑的
核心流程。原始 Claude ZIP／解壓縮來源未修改。

已完成：

1. 新增正式 `references/case_data.schema.json`。
2. 新增無第三方套件的 `validate_case_data.py`，驗證：
   - 至少一筆 `role=prospectus`。
   - W01–W24 正好 24 項且順序固定。
   - 35 張母版資料層完整且順序固定。
   - `complete`／`partial`／`missing`／`not_applicable` 語意。
   - `29_AI專家` 在 extractor 固定為 `not_applicable`。
   - source ID、raw citation、row/header 長度及基本型別。
3. 修正 `slice_prospectus.assign_end_pages()`：
   - 父章節不再被第一個子標題提早截斷。
   - 同頁父子標題仍保留有效範圍。
4. 新增 `render_case_markdown.py`：
   - Raw 與 Coverage 均從同一 `case_data` 渲染。
   - Coverage 分母固定 24。
5. 更新 `factbase_from_case.py`：
   - 先驗 schema。
   - 分開呈現缺失與不適用。
6. 新增 `build_manifest.py`：
   - 記錄輸入／五個業務產物的 SHA-256、大小與 QA。
   - 以 OOXML 直接檢查 35 張名稱、順序與 Excel 錯誤字串。
   - Manifest 自身不雜湊，避免遞迴雜湊。
7. 修正過渡 Excel 路徑：
   - build 前強制驗 `case_data`。
   - `00_覆蓋率` 直接由 canonical `coverage` 產生，不保存第二份人工表。
   - `missing` 用紅色缺件；`not_applicable` 用灰色不適用。
   - `verify_excel.py --eq` 改為真正讀 `worksheet/cell`，移除 `eval`。
   - 額外 sheet 只能在固定 35 張之後。
   - 新增 `requirements.txt`，明確宣告 `openpyxl>=3.1,<4`。
8. 重寫 Skill 執行說明與 references：
   - 正式輸出統一為 5 個業務產物＋1 個控制檔。
   - 移除 `/16`、舊三／四／第五件、Claude 暫存路徑。
   - BP/Pitch-only 案件不再誤觸發 extractor。
   - 官方來源優先 MOPS／TWSE／TPEx。
   - `FactSheet.json` 明確交由 evaluator 衝突處理後產生。

## 測試

執行：

```powershell
C:\Users\jabir\miniconda3\python.exe -X utf8 `
  brian-vc\tests\prospectus-extractor\run_all_tests.py
```

結果：`13/13 OK`。

覆蓋：

- schema 與 canonical fixture。
- 少於 24 項 coverage 的負向測試。
- 35 張資料層亂序的負向測試。
- missing／not_applicable 分流。
- Raw／Coverage 同源渲染。
- 父子章節切片邊界。
- OOXML 35 張順序檢查。
- Manifest 對缺輸入／缺輸出誠實回報 failed。
- 過渡 Excel 的 24 項 coverage、自動分頁與 N/A 標記。
- `verify_excel.py` 不再含 `eval(`。

另跑 OpenAI Skill validator：

```text
Skill is valid!
```

## 尚未完成／不得過度宣稱

1. 尚未以一份真實台灣公開說明書完成六件產物的 production end-to-end。
2. `slice_prospectus.py` 的 PDF 書籤、印刷目錄 offset、掃描頁偵測仍需真實 PDF
   fixture 回歸。
3. Excel authoring 目前仍是已宣告的 `openpyxl` 過渡路徑；尚未遷移到
   OpenAI/Codex 的 `@oai/artifact-tool`。
4. 尚未對 35 張工作簿逐頁／逐區塊做視覺 QA。
5. Manifest 尚未解析工作簿 `00_覆蓋率` 儲存格做反向一致性比對；目前由
   builder 單向從 canonical coverage 產生，並以輸出 SHA-256 防止未記錄修改。
6. 官方 URL 下載、快照、OCR／Vision 與 Chrome 登入頁流程尚未用真實來源測試。

## 2026-07-30 第二次審計修正

依缺 Poppler 與交付假綠燈審計，完成：

1. Step 1 改用已宣告的 `pypdf`，不再呼叫 `pdfinfo`／`pdftotext`。
2. 新增 `render_pdf_pages.py`：`PyMuPDF` 優先、`pdftoppm` 選配 fallback。
3. `requirements.txt` 新增 `pypdf` 與 `PyMuPDF`；缺 backend 時輸出中文可讀
   安裝指引。
4. Manifest 頁數改用 `pypdf`，缺 Poppler 不再使交付閘門永久 failed。
5. Manifest 從 case_data 重新渲染三份 Markdown 並逐位元組比對；三份任一
   被換成垃圾時 validation failed。
6. Manifest 反查 Excel `00_覆蓋率` 24 列是否與 case_data 一致。
7. `section_map.md` 補 W01–W24 並統一全形斜線；validator 另做 NFKC
   正規化，容忍半形斜線輸入。
8. `verify_excel.py` 只用 A2 固定前綴辨識整頁狀態，不掃全簿裸字串。
9. test runner 啟用 `sys.dont_write_bytecode` 並在開始／結束清除限定範圍的
   cache 與測試暫存物，不依賴非 repo 的 `.gitignore`。
10. 測試擴充為 19 項，包含 PATH 完全空白、缺 pypdf／轉圖 backend 可讀
    指引、正常 PATH renderer fallback、垃圾 Markdown、真實一頁 PDF 頁數及
    Excel coverage 反查。

## 2026-07-31 雙 runtime 複驗

- Miniconda Python 3.13.12：19/19 OK。
- Codex bundled Python 3.12.13：19/19 OK。
- 複驗發現 bundled `pdftoppm.cmd` wrapper 的內部相對路徑失效；實際 native
  executable 位於 `native/poppler/Library/bin/pdftoppm.exe`。
- `render_pdf_pages.py` 改為辨識 bundled layout 並直接使用 native
  executable；未修改 Codex bundled runtime。
- 獨立 CLI smoke 確認 backend=`pdftoppm`、PATH 空白 Step 1 exit 0、清理後
  residue=false。

證據：`brian-vc/tests/prospectus-extractor/test-report-2026-07-31.md`。
