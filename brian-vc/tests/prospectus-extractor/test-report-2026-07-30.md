# prospectus-extractor 核心契約測試報告

日期：2026-07-30  
執行器：`C:\Users\jabir\miniconda3\python.exe 3.13`  
命令：`python -X utf8 brian-vc\tests\prospectus-extractor\run_all_tests.py`

## 結果

```text
Ran 19 tests
OK
```

## 證明範圍

- `case_data` 的 24 項 coverage 與 35 張母版資料契約。
- schema 的主要正向與負向規則。
- 巢狀章節終點不再由子標題截斷。
- Raw／Coverage Markdown 從同一 case_data 產生。
- 過渡 Excel builder 能區分缺失與不適用，並由 coverage 陣列建立 24 列。
- OOXML 結構檢查不依賴 LibreOffice。
- Manifest 對合成 fixture 的缺來源／缺輸出回報 failed，而非假綠燈。
- `verify_excel.py --eq` 已移除 `eval`。
- PATH 設為空字串（`pdfinfo`／`pdftotext`／`pdftoppm`／`pdffonts` 全不可見）
  時，Step 1 仍可用 `pypdf` 完成；有 `PyMuPDF` 時轉圖成功，沒有時必須輸出
  可讀的 backend 安裝指引。
- 正常 PATH 下，renderer 必須實際使用 `PyMuPDF` 或 `pdftoppm` fallback。
- 以 `python -S` 模擬未安裝 `pypdf` 時，Step 1 exit 2、輸出中文安裝指引，
  且不出現 traceback。
- Manifest 以 `pypdf` 取得真實本機 PDF 頁數，不依賴 `pdfinfo`。
- Raw／Factbase／Coverage 任一換成垃圾內容時，Manifest 必須 failed。
- Excel `00_覆蓋率` 反向比對 case_data 24 列。
- `section_map.md` 的 W01–W24 與 contract 完全一致；validator 容忍全形／
  半形斜線。
- Excel 狀態 flags 只讀各 sheet A2 固定前綴，不會把完整的覆蓋率頁誤標。
- runner 在開始與結束時清除自身 `__pycache__` 與固定測試暫存物。

## 不證明

- 不代表真實公開說明書 OCR、表格辨識或財務數字正確。
- 不代表 35 張 Excel 已完成視覺 QA。
- 不代表 `@oai/artifact-tool` 遷移已完成。
- 不代表未安裝 `requirements.txt` 仍可執行；`pypdf`、`PyMuPDF` 與
  `openpyxl` 是已宣告的 Python 依賴。
- 缺 Poppler 的可攜路徑已測，但尚未用一份 100+ 頁真實台灣公說驗證
  `pypdf` 的目錄版面、表格文字層與 offset 品質。
