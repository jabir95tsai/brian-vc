# vc-quick-screen vQS-1.4 自我檢測報告

測試日期：2026-07-30  
測試案例：虛構公司「星橋邊緣運算股份有限公司」

## 修正結論

舊版「19/19」僅能證明關鍵字存在，不能證明有完成分析；該結論撤回。vQS-1.4 改用章節結構、表格列內計算、實質內容門檻與負向測試。空殼文件只有 8/20 且以非零 exit code 被拒絕。另以未讀取既有 `run-*` 的獨立 forward-test 產生 vQS-1.4 正向 fixture；最終為 20/20、七項勾稽 7/7、131 行、3,803 個非空白字元，並從同一份 canonical Markdown 生成 3 頁 DOCX。

## 可重跑結果

| 測試 | 結果 | 證明範圍 |
|---|---:|---|
| Skill 靜態契約 | 28/28 | 路由、來源政策、查詢預算、篇幅、IRR、Style、DOCX 依賴、固定輸出骨架與禁用詞 |
| run-009 vQS-1.4 獨立 forward-test | 20/20；7/7 | 未讀取舊輸出；131 行、3,803 非空白字元；canonical `.md` 與 `.docx` 同目錄 |
| run-003／run-004 舊版回歸 | 各 20/20；7/7 | 確認 evaluator 更新沒有破壞兩種既有有效格式；不再把它們當 vQS-1.4 正向證據 |
| 空殼負向測試 | 8/20；exit 1 | 明文照抄、空專家、空亮點／疑慮、短問題與篇幅不足均被拒絕 |
| `Step N｜` 標題相容測試 | 20/20；7/7 | evaluator 同時接受固定 numeric skeleton 與相容的 `Step N｜` 寫法 |
| 額外數字子標題回歸 | 20/20；7/7 | 插入 `### 2025 財務 headline` 與 `### 2026E 財測橋接` 後仍保留完整公司快照；未知數字不再成為章節邊界 |
| run-009 canonical 層級 | 通過 | runner 逐項核對固定標題層級與順序；`2.5` 使用 H2 |
| 預設 DOCX 結構測試 | 9/9 | OOXML、6 張以上表、免責、標籤不重複、編號空格、專家欄寬、清單隔離及表列不跨頁 |
| 預設 DOCX 視覺測試 | 通過 | Microsoft Word 匯出，Letter 3 頁；三頁逐頁檢查無裁切、重疊、表格破版、缺字或錯誤續號 |
| 無 `python-docx` 強制失敗測試 | 正確 FAIL | 生成前刪除舊檔；renderer 顯示安裝指引；smoke 明確 FAIL/skip，不再對舊產物給綠燈 |
| Plugin prompt routing | 通過 | 三個 `defaultPrompt` 均使用 `$skill-name` |
| OpenAI Skill／Codex Plugin 外部 validator | 通過 | 環境工具路徑、執行器與 SHA-256 如下 |

完整本地測試入口：

```powershell
python -X utf8 brian-vc/tests/vc-quick-screen/run_all_tests.py
```

環境具備外部 validator 時：

```powershell
python -X utf8 brian-vc/tests/vc-quick-screen/run_all_tests.py --include-external
```

即使呼叫端為未安裝 `python-docx` 的 Miniconda Python，預設測試入口也會找到 Codex Documents runtime；若要強制驗證缺依賴失敗分支，可指定：

```powershell
python -X utf8 brian-vc/tests/vc-quick-screen/run_all_tests.py `
  --docx-python C:\Users\jabir\miniconda3\python.exe
```

此命令預期整體 `FAIL`，且 DOCX smoke 必須顯示 `skipped: no fresh DOCX was generated in this run`。

## DOCX 依賴契約

- `brian-vc/requirements.txt` 宣告 `python-docx>=1.2,<2`。
- `render_memo_docx.py` 捕捉缺少 `docx` 的錯誤，提供 Documents runtime 與安裝 requirements 的可讀指引。
- `run_all_tests.py` 的預設優先序為：`--docx-python`／`VC_QUICK_SCREEN_DOCX_PYTHON` 明示值；否則使用 Codex Documents runtime；最後才檢查呼叫端 Python。
- Plugin manifest 不虛構不支援的 Python 依賴欄位；執行依賴由 requirements、Skill 契約與 runner 共同承接。

## 外部 validator 的證據邊界

下列兩支不是 repo 內容，屬目前 Codex 環境工具。報告只把它們列為「環境驗證」，不再宣稱是 repo 內可重跑證據：

| Validator | 執行器 | SHA-256 | 2026-07-30 |
|---|---|---|---:|
| `C:\Users\jabir\.codex\skills\.system\skill-creator\scripts\quick_validate.py` | `C:\Users\jabir\miniconda3\python.exe -X utf8` | `5347A0A09CFB546BBA1C0D1A30DAE0A233D9A05F57BD4E7877155C588BCDABF7` | 通過 |
| `C:\Users\jabir\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py` | `C:\Users\jabir\miniconda3\python.exe -X utf8` | `4E84C911479E4D158D723ED8CCC881D3499E580FBF5650E60D379A1A25AC3186` | 通過 |

使用 Miniconda Python 是因 Codex workspace Python 未含 PyYAML；`run_all_tests.py` 會把外部工具路徑與 hash 印出，找不到時標 `SKIP`。

## A–H 修正對照

| 項目 | 修正 |
|---|---|
| A 假 19/19 | 拆成一般結構檢查與 `fixture_expectations.json`；fixture 數字必須在同一驗算表列；新增空殼負向測試 |
| B validator 不在 repo | 報告註明外部路徑、執行器與 SHA-256；本地核心測試不依賴它們 |
| C 5 分鐘不可執行 | Step 2＋2.2 共用最多 8 條搜尋 query；官方頁面開啟最多 12 次；5 分鐘降為說明性目標 |
| D 無篇幅下限 | 契約統一為 2,500–6,000 非空白字元、80–180 行，不再隱藏 5,500／6,000 容差 |
| E Style 懸空 | 明列 `../../scripts/resolve_style.py`、neutral instructions 與 output style contract 路徑 |
| F DOCX 零覆蓋 | 新增 `scripts/render_memo_docx.py`；完成結構測試與 3 頁視覺 QA |
| G 禁用詞脆弱 | 改用語境化 regex，只禁止 Claude 專屬工具 token；保留合法的通用 `Web Search` |
| H 小問題 | 升版 vQS-1.4、補齊版本說明、移除過時「vQS-1.2 新增」、消除關鍵句中換行、明訂 `**不計算 IRR。**` |

## 本輪新增問題修正

| 問題 | 修正與證據 |
|---|---|
| 1. `python-docx` 未宣告 | 新增 `brian-vc/requirements.txt`、Skill 依賴說明與可讀 ImportError；普通 Miniconda 強制分支會正確失敗 |
| 2. smoke 吃舊 DOCX | 生成前 `unlink(missing_ok=True)`；生成失敗時 smoke 不執行，改記 FAIL/skip |
| 3. evaluator 偷定義標題 | Skill 明訂 `## 0.` 至 `## 8.`、Step 3 子標題與 Step 6 編號清單；parser 同時接受 `Step N｜` |
| 4. 沒有 vQS-1.4 正向 fixture | 新增 `run-009-independent-vqs-1.4`；獨立代理只讀 Skill 與 fixture，最終 20/20、7/7 |
| 5. DOCX 三項視覺瑕疵 | 消除 `[亮點] 亮點`／`[紅旗] 疑慮`；numbering 加 `w:suff=space` 並加寬 hanging；專家欄固定 1,800 DXA |
| 6. 建置產物殘留 | 刪除 `prospectus-extractor/scripts/__pycache__`，新增 `brian-vc/.gitignore` 防止 `__pycache__/`、`*.py[cod]` |
| 表列跨頁的新發現 | 所有 DOCX table row 加 `w:cantSplit`；最終三頁未見半列殘留 |
| 數字子標題誤切章節 | evaluator 只把固定 ID `0/1/1.5/2/2.2/2.5/3/4/5/6/7/8` 視為邊界；新增 `### 2025 財務 headline` 與 `### 2026E 財測橋接` 回歸測試 |
| run-009 `2.5` 層級漂移 | 由 H3 修正為固定骨架規定的 H2；runner 新增 canonical 層級與順序檢查 |
| 單位措辭張力 | Skill 明訂 Step 0 已宣告全文共用基準時，可省略逐筆重複單位；單位改變時仍須重標 |
| run-001 孤兒 | 刪除前確認 runner、evaluator、報告均未把它當作測試輸入或證據；歷史結果仍保留於 migration notes 文字敘述 |

## DOCX 視覺 QA 過程

本輪先以 Documents skill 的 canonical `render_docx.py` 嘗試；Windows 暫存 profile 遇到 ACL 錯誤，故依 fallback 使用已安裝的 Microsoft Word 隱藏模式匯出 PDF，再以 bundled Poppler 轉成 PNG。

以 run-009 canonical Markdown 產生的第一版為 5 頁；逐頁發現表格列可跨頁，且內容密度不符 2–3 頁目標。後續採兩類修正：

- 內容端由同一獨立代理刪除跨章節重複敘述，保留所有 evaluator 契約後收斂為 131 行、3,803 非空白字元。
- 渲染端加寬 neutral quick-screen 表格、壓縮非實質間距、固定專家欄、禁止表列跨頁並修正兩位數編號。

最終 Word→PDF→PNG 為 Letter 3 頁。三頁逐頁檢查：亮點／疑慮標題不重複；`10. 治理／升級` 有正確空格；六個專家名稱不折行；沒有半列、裁切、重疊、缺字或續號錯誤。舊的缺陷 `run-008-docx-vqs-1.4-final` 已刪除，避免再被誤認為最終證據。

## 仍然不代表什麼

- 20/20 證明 fixture 與輸出契約，不證明真實公司的外部數字正確。
- `fixture_expectations.json` 是星橋案例專用；換 BP 要換 expectations。未提供 expectations 時，evaluator 只做一般結構與實質性檢查。
- 真實 MOPS／TWSE／TPEx 查詢仍需用另一組 online fixture 測來源日期、URL 與查詢上限。
- 選配 PPTX tearsheet 尚未做渲染測試。
