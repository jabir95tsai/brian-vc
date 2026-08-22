# Brian VC skills → ChatGPT/Codex plugin 移植紀錄

日期：2026-07-28  
Workspace：`C:\Users\jabir\Hacker_J\brianvc-skill`

## 原始輸入

- `vc-skills-3pack for-ChatGPT 20260725.zip`
- 解壓目錄：`vc-skills-3pack for-ChatGPT 20260725\`
- 原始 ZIP 與解壓目錄保留不動，作為移植前基準。
- ZIP SHA-256：
  `DEF3604ECEA18751E653EC534948D078F26AFC47005E1283F9ACCB2F8F5F3D3C`

原始封裝包含三個 Claude skills：

1. `vc-quick-screen`
2. `prospectus-extractor`
3. `vc-investment-evaluator`

## 建立 OpenAI plugin 骨架

建立：

```text
brian-vc/
├── .codex-plugin/plugin.json
├── assets/
├── scripts/
└── skills/
```

三個原始 skills 已複製到 `brian-vc/skills/`。原始解壓資料未修改。

Plugin 定位改為 style-agnostic：

- Quick screening
- 台灣公開說明書萃取
- 完整 VC due diligence、估值與 IC 交付

尚未建立 marketplace entry，也尚未安裝到全域。

## Skills metadata

三個 skill 均新增：

```text
agents/openai.yaml
```

包含：

- `display_name`
- `short_description`
- 含 `$skill-name` 的 `default_prompt`

目前沒有在 metadata 宣告 MCP 或 Connector 硬依賴。

## Style adapter

移除 BrianStyle 作為核心硬依賴，改為內容與視覺分離。

新增：

```text
brian-vc/
├── scripts/resolve_style.py
└── assets/styles/
    ├── style.schema.json
    └── neutral/
        ├── style.json
        └── instructions.md
```

Style 解析順序：

1. 使用者指定的 style 路徑或目錄
2. `VC_REPORT_STYLE` 指定值
3. Plugin 內建 style id
4. 預設 `neutral`

第三方可以複製 `assets/styles/neutral/`，建立自己的 `style.json` 與
`instructions.md`。Style 只能控制版型、字型、配色與表格外觀，不得修改：

- 計算
- 來源
- 缺失標記
- 風險與 RedTeam 內容
- Executive／Full 內容邊界

新增核心契約：

- `references/output_style_contract.md`
- `references/financial_model_contract.md`

原本的 BrianStyle 規格改名為：

```text
references/legacy_brianstyle_deck.md
```

只在使用者明確選擇相容 style 時才使用。

## vc-quick-screen 依賴盤點

`vc-quick-screen` 的分析流程仍以指令為主，但預設 DOCX 交付已加入本地 renderer：

- 有 `scripts/render_memo_docx.py`
- 無 `references/`
- 無 `assets/`
- 不派 subagent
- 分析與 Markdown 輸出無 Python 套件硬依賴
- 預設 DOCX renderer 硬依賴 `python-docx>=1.2,<2`，宣告於 `brian-vc/requirements.txt`
- 無 MCP／Connector 硬依賴

流程上的軟依賴：

- 讀取 BP、Pitch Deck、PDF 或公開說明書
- Web／Browser／Chrome 查驗
- DOCX 生成
- 選配 PPTX tearsheet
- L2 案件轉交 `vc-investment-evaluator`

Codex／ChatGPT 內優先使用內建 Documents runtime；獨立執行 renderer 時，
需先安裝 `brian-vc/requirements.txt`。缺少 `python-docx` 時 renderer 會輸出
可讀的安裝與 runtime 指引，不再直接暴露 `ModuleNotFoundError`。

Chrome 能力由 Claude-in-Chrome 改為 ChatGPT Chrome plugin（`@Chrome`）的
平台中立設計方向；Chrome 不可用時應依序降級至內建 Browser、Web Search。

## 官方財務資料來源政策

已同步套用至：

- `vc-quick-screen`
- `vc-investment-evaluator`

資料來源優先序：

1. **MOPS**：財務報表、EPS、毛利率、重大訊息、公司揭露。
2. **TWSE**：上市公司股價、市值、成交與官方市場資料。
3. **TPEx**：上櫃／興櫃公司股價、市值、成交與官方市場資料。
4. Yahoo 股市、Goodinfo、鉅亨僅作二手交叉驗證。

規則：

- `@Chrome`、內建 Browser、Web Search 是存取工具，不改變來源優先序。
- 官方來源暫時無法取得時才可使用二手來源。
- 暫用二手來源時標示 `⚠️ 尚待官方來源確認`、資料日期與查詢日期。
- 搜尋摘要不得直接作為定稿數字。

## 已知尚待處理

1. `prospectus-extractor/references/excel_output.md` 原始檔在第 32 張分頁處截斷。
2. 三件／四件／五件輸出契約尚未統一。
3. Coverage 分母 16／24 尚未統一。
4. `29_AI專家`／`29_AI專家預留` 名稱尚未統一。
5. `slice_prospectus.py` 巢狀章節終點算法需修正。
6. `verify_excel.py --eq` 使用 `eval`，且未真正讀取指定 worksheet。
7. `case_data.json` 尚缺正式 schema 與 validator。
8. Claude 專屬路徑、Agent/Task 名稱及部分工具術語仍待全面移植。
9. Excel／PPTX QA 尚需加入公式、視覺渲染與來源追溯驗證。
10. 尚未建立 Connector、MCP Server、自訂 UI、Hooks 或排程範本。

## 驗證紀錄

已通過：

- `prospectus-extractor` skill validation
- `vc-quick-screen` skill validation
- `vc-investment-evaluator` skill validation
- `brian-vc` plugin validation
- `resolve_style.py neutral`

Windows 注意事項：

- Metadata generator 使用系統預設 CP950 時會讀取失敗。
- 目前以 Miniconda Python 搭配 `-X utf8` 成功產生及驗證 metadata。

## 2026-07-29：vc-quick-screen vQS-1.3 歷史實跑

> 本節保留當時紀錄；其中 19/19 為舊關鍵字 evaluator 結果，已於
> 2026-07-30 撤回並由後文 vQS-1.4 語意與負向測試取代。

新增可重跑測試：

```text
brian-vc/tests/vc-quick-screen/
├── fixture_pitch_deck.md
├── check_skill.py
├── evaluate_output.py
├── fixture_expectations.json
├── negative_empty_shell.md
├── run_all_tests.py
├── test-report-2026-07-30.md
├── run-003-vqs-1.3/
└── run-004-independent-vqs-1.3/
```

測試 fixture 刻意放入營收成長率、毛利率、軟體收入、市占、收入橋接及
募資估值矛盾，用來驗證 Skill 是否會重算，而不是照抄 BP。

第一輪實跑：

- 內容評估 18/19。
- 212 行、7,829 個非空白字元。
- 所有財務矛盾、官方來源政策、六專家、估值邊界與管理層問題均通過。
- 唯一失敗為 2–3 頁篇幅代理指標；同時觀察到外部查驗可能耗時過長。

因此將 `vc-quick-screen` 更新為 vQS-1.3：

- 外部查驗預設 5 分鐘，每類來源 1–2 個高訊號查詢。
- 超時或無法取得官方資料時使用 `UNKNOWN`／`⚠️ 尚待官方來源確認`。
- 篇幅目標約 5,500 個非空白字元且最多 180 行。
- 六專家改為壓縮表格，亮點與疑慮各三點。
- 管理層問題預設 10 題，必要時最多 15 題。

當時驗證（已由 vQS-1.4 取代）：

- Skill 靜態契約：22/22。
- OpenAI Skill validator：通過。
- Codex Plugin validator：通過。
- vQS-1.3 控制組：舊 evaluator 19/19，124 行、2,562 個非空白字元、10 題。
- vQS-1.3 獨立實跑：舊 evaluator 19/19，165 行、5,842 個非空白字元、10 題。

獨立實跑未做外部瀏覽，能依契約將不可核驗資料保留為 `UNKNOWN`；第一輪
線上實跑則確認可優先使用官方資料，二手市值資料會標記待官方來源確認。

## 2026-07-30：prospectus-extractor 目標 I/O

先完成目標輸入／輸出契約，尚未改解析程式。完整規格：

```text
migration-notes/2026-07-30-prospectus-extractor-target-io.md
```

核心決策：

- 必須至少輸入一本台灣公開說明書 PDF；財報與 data room 為選配補充來源。
- 只有 BP／Pitch Deck 時改用 `vc-quick-screen`，不假裝成公說萃取。
- `case_data.json` 為單一資料源。
- 正式輸出統一為 5 個業務產物＋1 個 manifest 控制檔。
- whitelist 覆蓋率固定 `/24`；Excel 結構完整度獨立回報 `35/35`。
- `FactSheet.json` 改由 evaluator 在衝突處理後產生，不列為 extractor 輸出。
- Excel 固定採現行程式的 `29_AI專家` 名稱；此頁僅供下游預留。
- `missing` 與 `not_applicable` 分開，避免服務業無產能被誤報為漏件。

## 2026-07-30：vc-quick-screen 審計修正

依二次獨立複核，撤回舊版 evaluator 的「19/19 等於分析品質通過」說法，將 Skill 升級為 vQS-1.4。

主要修正：

- `evaluate_output.py` 不再用全文件裸字串判斷計算。
- 新增 `fixture_expectations.json`，七項預期計算必須在內部一致性表格的同一列命中。
- 新增 `negative_empty_shell.md`；空殼由舊版 19/19 降為 8/20 且 exit 1。
- run-003、run-004 在新版 evaluator 均為 20/20，fixture 計算 7/7；僅作舊版回歸證據。
- 外部查驗改為 Step 2＋2.2 共用最多 8 條搜尋 query；5 分鐘只保留為操作目標。
- Markdown 篇幅契約統一為 2,500–6,000 非空白字元、80–180 行。
- 補上 Style resolver、neutral instructions 與 output contract 的實際相對路徑。
- 新增 `vc-quick-screen/scripts/render_memo_docx.py`，實跑輸出 DOCX。
- DOCX 經 Word→PDF→PNG 三輪逐頁 QA；修正 emoji 缺字、表格孤立表頭與跨章節連號後通過。
- Plugin 三個 `defaultPrompt` 改用 `$vc-quick-screen`、`$prospectus-extractor`、`$vc-investment-evaluator`。
- `check_skill.py` 改為語境化禁用詞 regex，不會誤傷通用 `Web Search`。

後續第三次複核再修正：

- 新增 `brian-vc/requirements.txt`，正式宣告預設 DOCX renderer 的
  `python-docx>=1.2,<2` 依賴；缺依賴時輸出可讀安裝指引。
- `run_all_tests.py` 在生成前刪除舊 DOCX；生成失敗時 smoke 明確
  FAIL/skip，不會再對歷史產物顯示綠燈。
- Skill 明訂 canonical Markdown 骨架（`## 0.` 至 `## 8.`、亮點／疑慮
  子標題、Step 6 編號清單）；evaluator 也相容 `Step N｜`。
- 新增 `run-009-independent-vqs-1.4`：獨立代理未讀舊 `run-*`，最終
  20/20、fixture 7/7、131 行、3,803 個非空白字元。
- run-009 同目錄保留 canonical `.md`、最終 `.docx` 與內部 QA render；
  Word→PDF→PNG 為 3 頁，逐頁檢查通過。
- DOCX 修正 emoji 語意標題重複、兩位數編號缺空格、專家欄過窄及表列
  跨頁；結構 smoke 擴充為 9 項。
- 刪除舊缺陷 `run-008-docx-vqs-1.4-final` 與
  `prospectus-extractor/scripts/__pycache__`；新增 `brian-vc/.gitignore`。
- evaluator 的章節邊界改用固定 ID 白名單；`### 2025 財務 headline`
  與 `### 2026E 財測橋接` 等額外數字子標題不再截斷父章節，並新增
  可重跑回歸測試。
- run-009 的 `2.5` 由 H3 改回 canonical H2；runner 另驗證固定層級與順序。
- Skill 明訂 Step 0 已宣告全文共用單位基準時，正文可省略逐筆重複單位。
- `run-001` 刪除前未被 runner、evaluator 或報告當作測試輸入／證據，
  確認為 vQS-1.2 孤兒後刪除。

完整報告：

```text
brian-vc/tests/vc-quick-screen/test-report-2026-07-30.md
```

## 2026-07-30：prospectus-extractor 核心資料層

已完成第一里程碑：

- 正式 `case_data.schema.json` 與無第三方套件 validator。
- coverage 固定 W01–W24；35 張資料層固定順序。
- 修正巢狀章節切片提前截斷。
- Raw、Coverage、Factbase 由同一 case_data 渲染。
- 新增輸入／輸出 SHA-256 與 OOXML QA manifest。
- Excel 覆蓋率頁由 canonical coverage 產生；missing／not_applicable 分流。
- `verify_excel.py --eq` 改為讀 worksheet/cell，移除 `eval`。
- `openpyxl` 過渡依賴已明確宣告，尚未冒充為無依賴。
- Skill、Excel reference 與 evaluator B.5 統一為 5 個業務產物＋1 個 manifest。
- 核心回歸測試 `13/13 OK`；OpenAI Skill validator 通過。

第二次審計後：

- 移除 Poppler 硬依賴：Step 1／Manifest 用 `pypdf`，轉圖用 `PyMuPDF`
  優先且 `pdftoppm` 僅作 fallback。
- Manifest 重新渲染並比對三份 Markdown，且反查 Excel coverage 24 列。
- section map 補 W01–W24；斜線正規化。
- Excel flags 改為只認 A2 固定前綴。
- runner 自行清除 cache；測試擴充為 `19/19 OK`。

完整紀錄：

```text
migration-notes/2026-07-30-prospectus-extractor-core-implementation.md
brian-vc/tests/prospectus-extractor/test-report-2026-07-30.md
```
