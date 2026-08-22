---
name: prospectus-extractor
description: >
  將台灣公開說明書（TWSE／TPEx／MOPS）及選配查核財報、年報與 data room
  補件，轉成具來源定位的 case_data、Raw、Factbase、24 項 coverage、固定
  35 分頁 Excel 與 QA manifest。適用於使用者上傳或指定公說並要求萃取、
  整理事實底稿、建立 Excel 對帳檔，或 vc-investment-evaluator Phase 0
  命中公開說明書時。不適用於只有 BP／Pitch Deck 的快篩、完整估值、IRR
  或六專家投資判斷。
---

# Prospectus Extractor v2.0

本 Skill 的唯一資料源是 `case_data.json`。所有 Markdown 與 Excel 都從它渲染；
不得分別手工維護。資料與視覺樣式分離，預設使用中性樣式，使用者可另指定
style adapter，但樣式不得改變數字、狀態、來源或結論。

動工前必讀：

- `references/section_map.md`：法定章節與 24 項 whitelist。
- `references/case_data.schema.json`：正式資料契約。
- 需要 Excel 時再讀 `references/excel_output.md`。
- 被 evaluator 呼叫時再讀 `references/integration.md`。

## 邊界與必要輸入

先從 Skill 目錄執行 `python -X utf8 ../../scripts/preflight.py`。若 packaging
檢查失敗，停止並回報缺少的 plugin 資源；缺少 standalone Python 依賴時，依
輸出的 plugin 根目錄單一安裝指令處理。

輸入是資料夾時可先執行 `python -X utf8 ../../scripts/route_case.py CASE_DIR`；
只有 `prospectus_triggered=true` 才執行本 Skill。這個 router 不取代 PDF
內容確認，若實際文件不是台灣公開說明書，回報 `not_applicable`。

必要輸入：

1. 至少一份台灣公開說明書 PDF。
2. `case_id`；未提供時用 `{YYYYMMDD}_{股票代號或公司簡稱}`。
3. 輸出目錄；未提供時用目前工作目錄下的 case 資料夾。

選配輸入：合併／個體查核財報、年報、期中財報、公說修訂版、data room
補件。若只有 BP／Pitch Deck，停止本 Skill 並改用 `$vc-quick-screen`。沒有
公開說明書時回報 `not_applicable`，不可把一般簡報當成公說。

原始輸入唯讀保存，不得覆寫。URL 來源要先保存 PDF 快照，並記錄 URL、取得
日期、頁數與 SHA-256。官方來源優先順序為 MOPS／TWSE／TPEx；搜尋引擎、
Yahoo 或其他二手頁面只可協助定位或交叉驗證，不能取代一手原文。Chrome／
內建 Browser 是取得頁面的工具，不是資料來源本身。

執行前安裝已宣告的 Python 依賴：

```powershell
python -m pip install -r requirements.txt
```

Step 1 不要求 Poppler；頁數、書籤與文字層由 `pypdf` 處理。掃描頁轉圖優先
使用 `PyMuPDF`，僅在它缺少時選配使用系統 `pdftoppm`。不得假設
`pdfinfo`、`pdftotext`、`pdftoppm` 或 `pdffonts` 已在 PATH。

## 正式輸出：5 個業務產物＋1 個控制檔

全部使用同一 `case_id`：

1. `{case_id}_case_data.json`
2. `{case_id}_Prospectus_raw.md`
3. `{case_id}_Factbase.md`
4. `{case_id}_Prospectus_coverage.md`
5. `{case_id}_Prospectus_extract.xlsx`
6. `{case_id}_Prospectus_manifest.json`

`FactSheet.json` 不由 extractor 產生；它由 evaluator 在 ConflictResolver
之後建立。舊文件的三件／四件／第五件說法均不適用。

## 執行流程

### Step 0 — 驗證來源

- 確認至少一個 `role=prospectus` 的 PDF 可讀、頁數大於零且未毀損。
- 多版本須記錄文件日期，不得靜默覆蓋差異。
- 補充資料以語意辨識，不依賴檔名完全相符。
- 每份來源配置唯一 `SRC-NNN`。

### Step 1 — 建章節索引

```powershell
python -X utf8 scripts/slice_prospectus.py INPUT.pdf --outdir WORK --dump-sections
```

產出 `_work/index.json`、`index.md`、`scanned_pages.json` 與 `sections/`。
先檢查壹章通常落在實體第 5–7 頁，並確認 printed-to-physical offset 合理。
後續頁碼一律以 index 的實體頁碼為準。缺少 `pypdf`、PDF 加密或檔案毀損時，
腳本會輸出可讀錯誤與安裝指引，不應出現原始 `FileNotFoundError` traceback。

### Step 2 — 按 24 項 whitelist 定點萃取

依 `section_map.md` 逐項抓取，不略讀整本。每筆事實保留：

- `source_id`
- 實體頁碼；可辨識時另記印刷頁碼
- 表格的工作表／儲存格或段落定位
- 擷取方法：`text_layer`、`ocr`、`vision`、`spreadsheet` 或 `manual`
- 幣別、單位、期間、合併／個體及查核狀態

查核／核閱財報 > 官方公說 > 官方年報／依法揭露 > data room 自結 >
Pitch Deck。衝突不得靜默覆蓋；將候選值、採用值、規則與
`conflict_unresolved` 寫入 `conflicts`。

公司自引的市場規模、市占或預測標 `circular_needs_verification`。供應商／
客戶若只揭露代號，保留代號並標補件，不可猜真名。

### Step 3 — 掃描頁 OCR／Vision

`scanned_pages.json` 的頁面先用可攜 renderer rasterize：

```powershell
python -X utf8 scripts/render_pdf_pages.py INPUT.pdf `
  --outdir WORK/page_images --pages "3,7-10" --dpi 150
```

renderer 回報實際 backend：`pymupdf` 或 `pdftoppm`。兩者都不可用時輸出
可讀安裝指引。中文掃描頁優先使用可讀圖工具／Vision。只有確認 tesseract 已安裝
`chi_tra` 時才使用 `chi_tra+eng`。OCR／Vision 結果仍須保留實體頁碼與方法，
不得把低信心結果標成 `complete`。

### Step 4 — 建立並驗證 case_data

`case_data.json` 必須符合 `references/case_data.schema.json`。coverage 固定
W01–W24 且順序一致；35 張母版 sheet 也須全部存在於資料層。

```powershell
python -X utf8 scripts/validate_case_data.py CASE_DATA.json
```

狀態只允許：

- `complete`
- `partial`
- `missing`
- `not_applicable`

`missing` 與 `not_applicable` 不得混用。服務業無產能可為不適用；文件本應
揭露但沒抓到才是缺失。`29_AI專家` 固定為 `not_applicable`，由 evaluator
下游填寫。

### Step 5 — 從同一資料源渲染 Markdown

```powershell
python -X utf8 scripts/render_case_markdown.py CASE_DATA.json `
  --raw-out CASE_Prospectus_raw.md `
  --coverage-out CASE_Prospectus_coverage.md
python -X utf8 scripts/factbase_from_case.py CASE_DATA.json CASE_Factbase.md
```

coverage 分母永遠是 24。Excel 的 `35/35` 是結構完整度，不能當作資料
覆蓋率。

### Step 6 — 渲染並驗證 Excel

目前相容路徑使用 `requirements.txt` 的 `openpyxl`；這是已宣告的過渡依賴。

```powershell
python -X utf8 scripts/build_excel.py CASE_DATA.json CASE_Prospectus_extract.xlsx
python -X utf8 scripts/verify_excel.py CASE_Prospectus_extract.xlsx
```

35 張母版必須存在且順序固定；附加頁只能放在第 35 張之後。缺失頁保留紅色
缺件標記；不適用頁使用灰色標記。verify 失敗不得交付。

`--eq` 格式為 `工作表:儲存格:預期值`，例如：

```powershell
python -X utf8 scripts/verify_excel.py OUT.xlsx --eq "00_封面:B2:範例股份有限公司"
```

### Step 7 — 建 manifest 與交付閘門

```powershell
python -X utf8 scripts/build_manifest.py CASE_DATA.json CASE_Prospectus_manifest.json `
  --output-dir OUTPUT_DIR
```

manifest 自身不列入雜湊集合，以避免遞迴雜湊；其餘五個業務產物與所有輸入
快照均記錄 SHA-256。Manifest 會從 `case_data` 重新渲染 Raw、Factbase、
Coverage 並逐位元組比對，也會反查 Excel `00_覆蓋率` 的 24 列。舊檔、垃圾
Markdown 或 coverage 漂移都必須使 `validation_status=failed`。只有
`validation_status=success` 才能回報完成。

## 下游精簡回傳

被 evaluator 呼叫時只回：

```text
status: success|failed|not_applicable
coverage: complete n / partial n / missing n / N/A n / 24
excel: 35/35, order=ok|failed
conflicts_unresolved: n
red_flags: 最多 3 項
missing_required: 項目清單
outputs: 六個絕對路徑
```

不得把 Raw 全文帶回主 context。若 manifest 不是 success，evaluator 不得進入
估值或 IRR。
