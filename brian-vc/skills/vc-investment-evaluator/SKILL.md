---
name: vc-investment-evaluator
description: >
  對完整 L2 data room 執行 Pre-IPO／早期新創 VC 或 PE 投資盡調。當使用者要求投資評估、DD、due diligence、投資報告、估值、IRR、Pre-IPO 分析、管理層問題、補件清單、投審會簡報，或提供完整公司資料室時使用。工作流涵蓋文件盤點、可追溯事實底稿、獨立專家分析、官方來源同業查驗、財測、估值、IRR、RedTeam、內容凍結與 Executive／Full 交付包；薄資料 L0/L1 應分流至 vc-quick-screen，台灣公開說明書由 prospectus-extractor 處理。
---

# VC 投資評估系統 v5.0

本 Skill 是完整盡調的主控流程，不是投資建議或自動決策器。輸出屬內部研究草稿；「進場／不進場」、投資金額與最終條件由 GP 決定。

## 先讀什麼

先從 Skill 目錄執行 `python -X utf8 ../../scripts/preflight.py`。若 packaging
檢查失敗，停止並回報缺少的 plugin 資源；Excel／PPTX authoring 前另載入平台
受管的 Spreadsheets／Presentations runtime。

輸入是資料夾時，再執行 `python -X utf8 ../../scripts/route_case.py CASE_DIR`。
只有 `data_level=L2` 且 `primary_skill=vc-investment-evaluator` 才走 full 流程。
使用者明確指定本 Skill 時加 `--requested-skill vc-investment-evaluator`；核心財務、股權與詳細三表齊備但缺本輪條件者會進 `L2-degraded`，不得錯退回初篩。其餘 L0/L1 轉 `vc-quick-screen`。若 `prospectus_triggered=true`，B2 必須呼叫
`prospectus-extractor`。router 只是檔名 preflight，A2 仍須讀內容確認四項 L2
證據。`L2-degraded` 描述的是**事實 DD 的資料層級**，不是允許虛構交易條件；
缺 Term Sheet／本輪價格時，case payload 必須用 `mode=blocked`，只有使用者明確
提供可計算的假設交易條件時才可用 `mode=degraded`。

每次執行先讀 `references/pipeline_contract.md`。它是 Stage、Module ID、相依關係、產物與完成閘門的唯一權威。

依情境再讀：

- 文件盤點、PDF 或公說：`references/phase0_playbook.md`
- 專家派工：`references/experts/` 對應角色檔
- 獨立財測 Excel：`references/financial_model_contract.md`
- 舊版功能對照與相容產物：`references/legacy_feature_parity.md`
- 報告渲染：`references/output_style_contract.md`
- BrianStyle：只有使用者明確指定時才讀 `references/legacy_brianstyle_deck.md`

舊版 Phase 編號只作為既有檔名與續跑相容別名。新功能一律掛到 Stage A–F 與 Module ID，不再新增 Phase 5C、6.5 等編號。

## 六段主流程

| Stage | 大管線 | 核心模組 | 通過後得到 |
|---|---|---|---|
| A | 案件啟動與分流 | A1 Preflight、A2 Data Gate | 可執行的 L2 案件與 `case_id` |
| B | 證據底座 | B1 文件索引、B2 公說萃取、B3 衝突與底稿、B4 補件拷問 | Factbase、FactSheet、缺口與衝突狀態 |
| C | 獨立盡調 | C1 技術、C2 商業、C3 產業、C4 財務 | 四份獨立分析與結構化移交 |
| D | 市場查驗與報酬 | D1 Citation、D2 估值、D3 財測模型 | CitationTable、估值、IRR／Multiple、財測模型 |
| E | 決策挑戰與凍結 | E1 投組整合、E2 RedTeam、E3 ContentFreeze | 六維度收斂、反證與凍結內容 |
| F | 交付與 QA | F1 Canonical Package、F2 Render、F3 QA | Executive、Full、Excel 與稽核底稿 |

直接前置依賴圖（`?` 表示條件式；必須與 `pipeline_contract.md` 的 manifest 完全一致）：

```text
<!-- DEPENDENCY-GRAPH-BEGIN -->
A1 <- ROOT
A2 <- A1
B1 <- A2
B2 <- B1
B3 <- B1, B2?
B4 <- B3
C1 <- B3
C2 <- B3
C3 <- B3
C4 <- C3
D1 <- C3
D2 <- C4, D1
D3 <- C4, D2
E1 <- C1, C2, C3, C4, D1, D2
E2 <- E1
E3 <- B3, B4, D1, D2, D3, E1, E2
F1 <- B_GATE, C_GATE, D_GATE, E_GATE
F2 <- F1
F3 <- F2
<!-- DEPENDENCY-GRAPH-END -->
```

## Stage A｜案件啟動與分流

### A1 Preflight

1. 設定 `case_id=YYYYMMDD_簡稱`，再以 `scripts/evaluator_runner.py init CASE_DIR --case-id CASE_ID` 建立本案唯一 artifact manifest。後續每個 Module 都以 `set` 記錄狀態、證據與本次產物，不得另建第二份狀態表。
2. 確認 `vc-quick-screen`、`prospectus-extractor` 與本 Skill scripts 可讀。獨立執行 F3 的 `scripts/qa_deck.py` 前，安裝 `../../requirements.txt` 宣告的 `python-pptx`；平台內建 Presentations runtime 可直接使用其既有環境。
3. 檢查是否能啟動獨立 agent。可用時，C1–C4、D2、E1、E2 優先隔離執行；不可用時按相同契約順序執行並逐模組落地，不能用摘要取代完整 raw。
4. 續跑時沿用原 ID，先執行 runner `verify --invalidate-stale`，只跳過證據仍有效的 `complete` 或 `not_applicable` Module。
5. 判定互動模式或背景模式。互動模式在同業清單與 ContentFreeze 徵求確認；背景模式自行完成並把決策依據寫入 log，不得假裝取得使用者確認。
6. 錯兩次即停：同一 Module 被記錄第二次 `partial` 或 `blocked` 時，runner 標記重試上限已到，第三次失敗會被拒絕。把失敗原因留在 manifest 並回報使用者，不得無限重試；確定要重跑時，先人工把該 Module 設回 `pending`。計數規則見 `references/pipeline_contract.md`。

### A2 Data Gate

先對整個資料室執行一次來源分級，不得只讀「剛好抽得到文字」的檔案：

```powershell
python -X utf8 scripts/ingest_dataroom.py DATAROOM_DIR --output-dir CASE_DIR
```

它把每個 PDF 分為 `text`／`mixed`／`scanned_only`，把無文字層的頁面渲染成 PNG
供視覺讀取，並輸出 `ingest_report.json`。`unreadable_financial_sources` 非空時，
必須把 `suggested_missing_items` 併入本案 `missing_items`（簽證財報為 P0），
再依渲染頁做視覺讀取後才可建立歷史財務。**純掃描的簽證財報不得因為抽不到文字
就當作不存在**：那是未讀，不是缺件，兩者在報告中要分開陳述。


- **L2 完整**：查核／核閱財報、股東名冊或 Cap Table、本輪條件、詳細 IS／BS／CF 齊備，進入 Stage B。
- **L0/L1 薄資料**：只有 BP、公說、Pitch Deck 或單一介紹文件，改用 `vc-quick-screen`。
- 使用者明確要求在資料不足下繼續，且明確提供可計算的假設交易條件時，才可進入 degraded 模式；只有「請繼續／允許 degraded」不等於授權代填投資額、估值或股價。缺少關鍵估值輸入時整案 payload 用 `blocked`，D2/D3 必須標 `blocked`，不可用假設包裝成完成。
- **payload `mode` 三值**：`full`／`degraded`／`blocked`。`blocked` 用於本輪條件未揭露（例如公說載明本次現金增資「不適用」）之案件——`deal` 的金額欄位可為 null，但 `deal.round` 與 `deal.blocked_reason` 仍為必填，缺少理由即驗證失敗。此模式保留全部有證據支撐的事實類產物（歷史財務、客戶供應商、缺件清單），僅將 IRR／Return Multiple 與獨立財測標為 `blocked`，不以假設替代。

## Stage B｜建立證據底座

主控在本 Stage 只提取、核對與標記，不做投資判斷。

### B1 文件索引

- 遞迴列舉所有資料夾與檔案，記錄掃描資料夾數與檔案數。
- 建立 DocumentIndex：文件名稱、類型、日期、讀取狀態、內容疑慮、下游模組。
- 逐項尋找查核財報、股本／股東資料、專利、最新三表、本輪條件；找遍後才能標缺失。
- 辨認控股實體與營運實體，避免把開曼／BVI 控股殼帳當成營運數字。

### B2 台灣公開說明書萃取（條件式）

DocumentIndex 命中公開說明書時，執行 `prospectus-extractor`。依 `references/phase0_playbook.md` 驗收五個業務產物與 manifest；coverage 必須是 24 項 canonical whitelist，Excel 必須包含固定 35 分頁母版且 manifest 為 `success`。

沒有公說時 B2=`not_applicable`，並以 DocumentIndex 無命中作證；不得因公說類型或募集條件不適用而跳過已觸發的 B2。

### B3 衝突解析與事實底稿

來源優先原則：查核／核閱財報 > 官方公說及申報 > 最新自結／data room 原件 > BP／Pitch Deck > 未留證據的口頭說法。特定欄位另依 `references/pipeline_contract.md` 的規則處理。

產出：

- `{case_id}_ConflictLog.md`
- `{case_id}_Factbase.md`：A 公司、B 股東、C 董監、D 財務、E 產品與收益流、F 客戶供應商、G 本輪條件與 IPO
- `{case_id}_FactSheet.json`
- Factbase Excel：有公說時為 35 分頁母版加 evaluator 延伸分頁；無公說時才可使用明確標示的精簡版

任何會影響估值或 IRR 的衝突未解，D2、D3、E3 與 F2 均不得通過。
把「已驗證」與「候選／公司提供」同業分開：只有公司名、資料日、來源 URL
及至少一項可用估值數字齊備，且未標為 unverified 的列可進 `comparables`；其餘
移入 `unverified_comparables` 並保留拒絕原因。null 或空字串不得轉成 0。

### B4 補件與管理層拷問

產出分級補件清單與 15–25 題管理層問題。優先覆蓋財務誠信、BD、研發、護城河、IPO／退場與治理。財務誠信核心問題被迴避時，將案件標為 `blocked`，不要繼續宣稱已完成完整 DD。

## Stage C｜四領域獨立盡調

| Module | 角色 | 主要輸入 | 特別移交 | 角色契約 |
|---|---|---|---|---|
| C1 | 技術顧問 | FactSheet、Factbase A/E、可選 TechPrimer | 技術停止題 | `references/experts/phase1_tech.md` |
| C2 | 商業模式顧問 | FactSheet、Factbase E/F | 致命缺陷 | `references/experts/phase2_business.md` |
| C3 | 產業分析師 | FactSheet、Factbase E、外部研究 | Watchlist ≤10 家 | `references/experts/phase3_industry.md` |
| C4 | 財務分析師 | FactSheet、Factbase D、C3 Watchlist | 退出年 EPS、財測、達成率門檻 | `references/experts/phase4_finance.md` |

C1、C2、C3 可平行；C4 等 C3 Watchlist。每位專家只讀指定證據，不讀其他專家全文。

每個模組必須：

1. 寫入既有相容檔名 `{case_id}_PhaseN_{角色}_raw.md`。
2. 片尾包含 `## DECK_EXPORT`；缺少即不是 `complete`。
3. 回傳 ≤400 字 payload：評分、一句結論、帶數字的 deck-ready 判斷、移交數據、紅旗與 raw 路徑。
4. 外部數字附 URL、資料日期與查詢日期；禁止只以搜尋摘要定稿。

## Stage D｜市場查驗、估值與報酬

### D1 Citation

同業清單有兩種來源，優先序固定：

1. **使用者指定**：使用者已給個股或代號時，以該清單為準；不得用自動清單覆蓋或擅自增刪，需要補充時另列並標明為建議。
2. **自動生成**：沿用 C3 Watchlist，再以同產業龍頭補全到足以比較的家數。

互動情境下自動清單先請使用者過目再查價；背景情境直接產生，不等待確認。兩種情境都必須在 CitationTable 標明清單來源為 `user_specified` 或 `auto`，並逐家記錄納入理由。

以定案清單為骨架，逐家公司查驗同業數字。來源品質順序固定：

1. MOPS：財務報表、EPS、毛利率、重大訊息與公司申報。
2. TWSE：上市公司股價、市值、成交與官方市場資料。
3. TPEx：上櫃／興櫃公司股價、市值、成交與官方市場資料。
4. Yahoo、Goodinfo、鉅亨等只能交叉驗證。官方來源暫時不可得時才可暫用，並標 `⚠️ 尚待官方來源確認`、資料日期與查詢日期。

Browser、Chrome 或 Web Search 是取得資料的工具，不是來源等級。產出 `{case_id}_CitationTable.md`。
公司簡報提供的倍數只可留在 `unverified_comparables`；完成官方查驗後才移入
`comparables`。同業數量 Gate 一律計算 verified 集合，不計候選列。

### D2 估值與退出情境

讀 `references/experts/phase5b_valuation.md`。只能使用 CitationTable 已驗證數字與 C4 移交財測，依案件類型選 P/E、P/B、P/S 或 ARR 倍數，輸出估值區間、價格判定、4–5 個退出情境與合理估值的反推條件。

### D3 獨立財測模型

依 `references/financial_model_contract.md` 產生七分頁核心 Excel。保守／基準／積極情境優先使用 `forecast_rows[].drivers` 的產品量價或案件適用營運驅動；只有資料不足時才可使用明確標示的 `ratio_proxy_fallback`。允許三情境分別採 driver 或 fallback，但必須逐情境記錄 `scenario_methods`，不得因一個情境缺 rows 而把另外兩個已有 driver 的情境一起降級。有現金流、權益變動、債務折舊、營運資金三表或勾稽資料時，透過 `financial_extensions` 加入相容分頁，不得另寫公司專屬 builder。若延伸表已有營運 driver、核心仍為 ratio proxy，必須列為模型整合缺口，不得宣稱 driver-linked。AI 協助建立的預測一律標「獨立估計，非公司財測」。IRR 與 Return Multiple 一律由 `scripts/irr_matrix.py` 產生，禁止手算。傳入 `--hurdle` 時，IRR 儲存格必須實際帶 `✅`（達標）、`⚠️`（非負但未達標）或 `❌`（負報酬）標記。

先把 B3、C4、D1、D2 的 frozen 結構化內容整理成
`references/evaluator_case.schema.json` 的 JSON，再執行：

```powershell
python -X utf8 scripts/prepare_workbook_input.py CASE_INPUT.json CASE_DIR\prepared_case.json
```

這一步會以 `scripts/irr_matrix.py` 附加 canonical 雙矩陣，並建立與 Excel
公式相同口徑的 `independent_forecast`。接著以平台受管 Node 與
`@oai/artifact-tool` 執行 `scripts/build_evaluator_workbooks.mjs`；不得改用
openpyxl 產生新工作簿。builder 產出無公說 11 分頁 Factbase 與七分頁核心模型；有 `financial_extensions` 時可在核心分頁之後加入契約允許的舊版深度分頁；
有公說時 Factbase 必須沿用 extractor 35 分頁母版，不可用精簡版覆蓋。

最後以同一受管 runtime 執行 `scripts/verify_evaluator_workbooks.mjs`，驗收精確
分頁順序、公式錯誤、基準模型公式數、IRR／Multiple 與 Checks。只有 audit
JSON 顯示 `formula_error_count=0`、`model_checks=OK` 才可將 D3 標 complete。

### Fund Profile

| 公司類型 | Hurdle | 主要估值法 | B4／C2／C4 關鍵追問 |
|---|---:|---|---|
| 成熟獲利型 Pre-IPO／製造業 | 15% | P/E，輔以 P/B、P/S | 庫存、毛利結構、供應商集中 |
| SaaS／訂閱型 | 25% | ARR 或 P/S | MRR、Churn、CAC、LTV、NRR |
| 成長型新創（非訂閱） | 25% | P/S 或情境估值 | 單位經濟、回購率、通路效率 |
| Seed／無穩定營收 | 30% | 情境估值 | runway、里程碑、下一輪資金需求 |
| 生技／醫療臨床階段 | 35% | 風險調整情境 | 臨床節點、法規路徑、授權條件 |
| 矽智財／深科技 | 25% | P/E 或 P/S | SBC 正常化、關聯交易、授權集中度 |
| 半導體設備／檢測 | 25–30% | P/E 加 P/S | 良率、客戶驗證週期、Sole-source |
| 氫能／硬體深科技 | 25–30% | P/E 加情境法 | 認證、CapEx、客戶驗證週期 |
| 租賃／汽車金融 | 15% | P/E 加 P/B | 槓桿、利差、期限錯配、covenant |
| AIDC／算力／雲 | 25% | P/S，輔以財測 P/E | 電力、NCP、EPC 合約 |

退出倍數起始值：

- 製造業 Pre-IPO 保守／中性／積極：已驗證同業 P/E × `0.75 / 0.85 / 1.0`。
- 新創 ARR 保守／中性／積極：`5x / 8x / 12x`。
- 其他產業以 D1 已驗證同業區間為起點；任何折溢價都要寫明理由，不得直接套用上述倍數。

有 IPO 時程時，退出年採 IPO 年加一年；否則至少計算 Year 3 與 Year 5。任何覆寫 Hurdle、持有期或退出倍數都要寫入假設表。

## Stage E｜決策挑戰與內容凍結

### E1 投組整合

讀 `references/experts/phase6_pm.md`。整合 C1–C4、D1、D2 的精簡 payload，產出五點盡調觀察、風險矩陣、KPI、IRR／Multiple 雙矩陣與六維度評分。需要細節時只切讀對應 raw 的 `## DECK_EXPORT`。

GP 決策欄位固定留白：

```text
進場 / 不進場：【GP 填入】
前置確認條件：【GP 填入】
建議金額：【GP 填入】
```

### E2 RedTeam

強制執行獨立反方審查，讀 `references/experts/redteam.md`。輸出 R1–R6：反對理由、結論反轉假設、可能美化數字、反方十問、失敗路徑與風險等級。RedTeam 全文只進 Full 版。payload 附帶固定格式的 E2→F1 交棒語（見該檔），F1 組裝 `deck.redteam` 摘要時直接取用，不必主控重寫。

### E3 ContentFreeze

確認 IRR 退出基礎、財測版本、同業日期、投前後估值、股數與攤薄、核心收入可信度。互動模式等使用者確認；背景模式把主控自答與依據寫入 `{case_id}_ContentFreeze.md` 並標示「自動凍結」。未解關鍵衝突不得凍結。

## Stage F｜交付與 QA

### F1 Canonical Content Package

先彙整並凍結 Factbase、FactSheet、Coverage、ConflictLog、專家 raw／payload、CitationTable、財測、IRR、RedTeam 與 ContentFreeze。分析內容是唯一事實來源；渲染器不得改寫計算或證據。

Stage E 各 Gate 完成後執行：

```powershell
python -X utf8 scripts/assemble_canonical_package.py CASE_DIR CASE_DIR\prepared_case.json
```

它只接受 case 目錄內、已 hash 的 prepared content，產生唯一
`{case_id}_ContextPackage.json` 並寫回同一份 artifact manifest 的 F1；不得另建
第二份狀態表。

### F2 Render

讀 `references/output_style_contract.md`。未指定樣式時使用 `neutral`；允許使用者提供 style ID、style 目錄或 `style.json`。樣式只控制字體、顏色、間距、圖表、表格與版面。

兩種報告：

- Executive：投資主張、條件、證據、財務、估值、報酬與決策框架。
- Full-critical：加上衝突、缺件、完整風險、RedTeam、失敗路徑與管理層問題。

full 模式必要內容包括逐項多年財測、至少五家同業、管理團隊學經歷、IRR／Multiple 雙矩陣。degraded 模式允許以明確「尚待官方來源確認／尚待補件」取代不存在的同業或團隊資料，但不得把缺口視為通過證據。生成每頁時從對應 `DECK_EXPORT` 切片取材，不用主控自行補空泛結論。

先讀 `references/deck_content_contract.md`。`scripts/build_investment_decks.mjs` 直接從 Skill 目錄執行，必要時以 `CODEX_NODE_MODULES` 指向平台受管 `@oai/artifact-tool`；不再複製到案件目錄，也不得在通用 builder 內寫入公司名稱、固定交易數字或產業判讀。輸入只能是 F1 frozen content。
預設同時產出至少 15 頁 Executive 與含 conflicts、risk matrix、RedTeam、
failure paths、補件和管理層問題的 Full-critical；少於五家已驗證同業時，full
模式 F2 直接 blocked；degraded 模式顯示缺件狀態，不得為過 QA 杜撰公司。

同一 frozen payload 另執行 `scripts/build_legacy_parity_artifacts.py`，產出舊版相容的 Investment Memo、DD Request Tracker、Management Q&A、Interview Notes、Meeting Minutes 與 Financial Statement Notes。未提供訪談或會議內容時保留可使用模板並標「尚待補件」，不得虛構紀錄。

需要重現整套產物時，使用單一命令：

```powershell
python -X utf8 scripts/replay_evaluator_case.py CASE_INPUT.json OUTPUT_DIR --mode full
```

此命令依序 prepare、build/verify workbooks、build decks、build legacy parity artifacts、執行 mode-aware deck QA，最後寫出 `evaluator_replay_report.json`。報告的 `pipeline_status=complete` 只代表程式化重播成功；另看 `dd_status`、`visual_qa_status`、`delivery_status` 與 `ready_for_delivery`，不得把 pipeline 完成解讀為 DD 或交付完成。它重播的是已凍結且可稽核的 case JSON；原始 data room 的語意讀取與來源定位仍由 Stage A–E 完成，不能假裝已由純腳本自動理解。

### F3 QA 與交付

至少交付並驗證：

- Executive PPTX
- Full-critical PPTX
- Factbase Excel
- 七分頁獨立財測模型 Excel
- ContextPackage
- 專家原始底稿合集與各 raw

以 `scripts/qa_deck.py --mode full|degraded|quick-screen` 做 PPTX 結構檢查；它不取代視覺 QA。Excel 必須可開啟、公式可追溯且沒有公式錯誤。任何要求產物失敗時，整案只能回報 `partial` 或 `blocked`，並列出未完成 Module ID，不得回報完整完成。

先逐頁檢視 builder 輸出的 PNG 與 layout JSON，確認無裁切、重疊或不可讀小字，
再把這次覆核記錄成契約要求的報告：

```powershell
python -X utf8 scripts/record_visual_qa.py CASE_DIR `
  --executive EXECUTIVE.pptx --full-critical FULL.pptx `
  --preview-root CASE_DIR\outputs\previews\decks `
  --reviewer "覆核人姓名" --mode full|degraded|blocked `
  --issue "若看到缺陷就逐項填寫"
```

它不會替人判定通過：沒有 `--reviewer` 就不寫 `status=pass`，任何 `--issue`
一律轉為 `fail`；同時比對每頁 PNG 是否真的存在，沒渲染過的頁不能被宣稱已覆核。

再以具有 `python-pptx` 的平台受管 Python 執行：

```powershell
python -X utf8 scripts/verify_and_record_delivery.py CASE_DIR `
  --context-package CONTEXT.json --factbase FACTBASE.xlsx `
  --financial-model MODEL.xlsx --executive EXECUTIVE.pptx `
  --full-critical FULL.pptx --workbook-audit WORKBOOK_AUDIT.json `
  --visual-qa-report VISUAL_QA.json
```

此步會跑 Executive／Full 結構 QA、驗 workbook audit、依序寫入 F2/F3 並確認
`F_GATE=complete`；`VISUAL_QA.json` 必須有 `status=pass`，且 `reviewed_files`
逐一列出本次兩份 PPTX。只有口頭宣稱「已看過」而無報告時不得完成 F3；任何一項失敗不得手動把 Gate 改成 complete。

`--mode` 必須與本案模式一致，閘門會雙向檢查：`full`／`degraded` 要求 workbook
audit 的 `model_checks=OK`；`blocked` 要求 `BLOCKED_AS_DESIGNED` 且
`formula_count_in_base_forecast=0`。blocked 案報 `OK` 代表模型算了不該算的東西，
同樣不予放行。

交付前執行 `scripts/evaluator_runner.py verify CASE_DIR --invalidate-stale`，再執行 `status`。只有 `F_GATE=complete` 且 verify 通過時可回報完整完成。

## 跨 Stage 強制規則

- **M-CTX-1**：主控只持有 FactSheet、payload 與檔案路徑，不長駐 raw 全文。
- **M-CTX-2**：模組間以落地產物交接，不以對話記憶交接。
- **M-CTX-3**：大 data room 逐檔讀取並即時落地。
- **M-CTX-4**：只在需要時以 `scripts/slice_toolresult.py` 切讀 `## DECK_EXPORT`。
- **M-CTX-5**：單一專家失敗不阻斷可獨立執行的模組，但最終必須列缺口。
- **M-CTX-6**：payload ≤400 字，深度放 raw 與 DECK_EXPORT。
- **M-CTX-7**：無獨立 agent 時順序降級，仍遵守相同產物與閘門。
- 所有事實標來源；所有推測標「推測」或「不確定」；數字標單位與期間。
- 新功能必須依 `references/pipeline_contract.md` 的擴充規則新增 Module，不得把跨階段邏輯散插進多個段落。

## 邊界

- 本 Skill 是 L2 完整 DD；`vc-quick-screen` 是 L0/L1 初篩。
- `prospectus-extractor` 只建立公說事實底座，不負責投資判斷。
- Style adapter 只負責呈現，不負責證據、計算或結論。
- 任一工具可替換，只要模組輸入、輸出、完成證據與來源政策不變。
