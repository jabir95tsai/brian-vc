# Pipeline contract

本檔定義 `vc-investment-evaluator` 的 Stage、Module、相依關係、產物與完成閘門。新增功能或改變執行順序時先改本檔；專家方法、財測格式與視覺規則分別由對應 reference 管理，不在多處重複定義。

## 1. 契約權責

| 契約 | 唯一負責範圍 |
|---|---|
| `pipeline_contract.md` | Stage、Module ID、相依關係、產物、狀態、完成閘門 |
| `phase0_playbook.md` | 文件／PDF／公說的讀取與萃取細節 |
| `experts/*.md` | 各專家的分析方法、最低輸出與 payload |
| `financial_model_contract.md` | 獨立財測模型工作簿內容與公式責任 |
| `output_style_contract.md` | Executive／Full 的視覺呈現邊界 |

若同一規則出現在兩個檔案，以本表指定的負責檔為準；修正時刪除非權責檔中的重複規則或改成連結。

## 2. 狀態模型

每個 Module 只使用以下狀態：

- `pending`：尚未執行。
- `in_progress`：正在執行，尚無可驗收產物。
- `complete`：所有完成證據均存在並驗證通過。
- `partial`：有產物，但至少一項完成證據失敗。
- `blocked`：缺少關鍵輸入，不能可靠執行。
- `not_applicable`：條件式模組未觸發，且有未觸發證據。

不得只依檔案存在判定 `complete`；必須驗證內容、來源或結構。續跑只能跳過 `complete` 或有證據的 `not_applicable`。

### 重試上限（錯兩次即停）

狀態只有以上六種，重試次數不新增第七種狀態，改以 manifest 的 `failed_attempts` 欄位表達：

- 同一 Module 每被記錄一次 `partial` 或 `blocked`，`failed_attempts` 加一；記錄 `complete` 或 `not_applicable` 時歸零。
- `failed_attempts` 達到 2 即停止重試：該 Module 標 `retry_exhausted`，失敗原因保留在 `reason`，並回報使用者處理，不得繼續自動重跑。
- 已 `retry_exhausted` 的 Module 再次記錄失敗會被 runner 拒絕。只有人工明確把該 Module 設回 `pending`（決定重跑）才清除計數與旗標。
- `verify --invalidate-stale` 造成的降級是產物完整性問題，不是執行失敗，不計入 `failed_attempts`。

### case payload 的 `mode`

Module 狀態描述單一模組；case payload 的 `mode` 描述整案可算到什麼程度，兩者不同層級：

| mode | 適用 | `prepare_workbook_input.py` 行為 |
|---|---|---|
| `full` | 條件與財測齊備 | `deal.investment`／`pre_money`／`post_money` 必填且為正；產生 IRR／Multiple 雙矩陣與三情境獨立財測 |
| `degraded` | 資料不足但使用者要求續行，且明確提供可計算的假設交易條件 | 同 `full` 之必填要求；假設條件與缺口以「使用者提供假設／尚待補件」呈現；不得因使用者只說「繼續」就代填交易條件 |
| `blocked` | 本輪條件未揭露（如公說載明本次現增「不適用」） | `deal` 金額欄位可為 null；`deal.round` 與 `deal.blocked_reason` 必填。`return_matrix` 與 `independent_forecast` 標 `status: blocked` 並記錄理由；歷史財務、客戶供應商、缺件清單等事實類區塊完整保留 |

`blocked` 不是略過驗證的旁路：未填 `blocked_reason` 即驗證失敗，且 `full` 模式仍會拒絕缺值的 deal。此模式存在的理由是——契約要求 D2/D3 在缺關鍵輸入時標 `blocked` 且不得用假設包裝，若 builder 直接拒收，這類案件連事實類交付都產不出來。

`evaluator_replay_report.json` 的狀態分層：`pipeline_status` 表示重播程式是否成功，
`dd_status` 沿用 case mode，`structural_qa_status` 與 `visual_qa_status` 分開，
`delivery_status`／`ready_for_delivery` 只有在本次視覺 QA 有落地證據時才可完成。
禁止以單一 `status=complete` 同時代表這些不同層級。

## 3. Module registry

| ID | 模組 | Owner | 必要輸入 | 主要產物 | 完成證據 | 阻斷下游 |
|---|---|---|---|---|---|---|
| A1 | Preflight | 主控 | 使用者請求、工具環境 | capability log、mode | 配套路徑、模式、agent 能力已記錄 | A2 |
| A2 | Data Gate | 主控 | 初始文件清單 | L0/L1/L2 判定、`case_id` | 分級理由與核心文件狀態 | B；L0/L1 正常分流 quick-screen |
| B1 | Document Index | 主控 | data room | DocumentIndex | 遞迴資料夾數、檔案數、核心文件逐項結果 | B2/B3 |
| B2 | Prospectus Extraction | 獨立 agent 或主控降級 | B1、公說 PDF | case_data、Raw、Factbase、Coverage、35-sheet Excel、Manifest | `/24`、`35/35`、manifest success、內容一致性 | B3；無公說可 N/A |
| B3 | Evidence Base | 主控 | B1、B2（若觸發）、所有一手文件 | ConflictLog、Factbase、FactSheet、Factbase Excel | 關鍵欄位可追溯；估值關鍵衝突為 0 | C/D/E/F |
| B4 | Gap & Questions | 主控 | B1–B3 缺口 | 補件清單、管理層問題 | 優先級、缺失影響、停止條件齊全 | E3；重大誠信問題可阻斷 D |
| C1 | Technology DD | 獨立專家 | FactSheet、Factbase A/E、可選 TechPrimer | Phase1 raw、payload | raw 含 DECK_EXPORT 與最低素材 | E1/F1 |
| C2 | Business DD | 獨立專家 | FactSheet、Factbase E/F | Phase2 raw、payload | raw 含 DECK_EXPORT 與最低素材 | E1/F1 |
| C3 | Industry DD | 獨立專家 | FactSheet、Factbase E、外部研究 | Phase3 raw、payload、Watchlist | raw 含 DECK_EXPORT；Watchlist ≤10 | C4/D1/E1 |
| C4 | Financial DD | 獨立專家 | FactSheet、Factbase D、C3 Watchlist | Phase4 raw、payload、財測移交 | raw 含 DECK_EXPORT；FinanceReview 完成 | D2/D3/E1 |
| D1 | Citation | 主控 | C3 Watchlist、使用者指定同業清單（若有）、官方市場來源 | CitationTable | 數據日、查詢日、URL、來源等級齊全；清單來源標 `user_specified` 或 `auto` | D2/E1/F1 |
| D2 | Valuation | 獨立專家 | FactSheet、D1、C4 移交 | Phase5B raw、估值區間、退出情境 | 只使用可追溯輸入；IRR 由 script 產生 | D3/E1 |
| D3 | Financial Model | 主控或獨立模型 agent | C4、D2、交易條件 | 七分頁財測模型 Excel | 三情境、公式可追溯、開啟與公式 QA 通過 | E3/F1 |
| E1 | Portfolio Synthesis | 獨立專家 | C1–C4、D1–D2 payload | Phase6 raw、六維度、風險矩陣、KPI | raw 含 DECK_EXPORT；GP 欄位留白 | E2/E3 |
| E2 | RedTeam | 獨立 reviewer | E1、C4 可驗證片段 | RedTeam raw、R1–R6 payload | R1–R6 全部存在 | E3/F1 |
| E3 | Content Freeze | 主控 | B3/B4、D1–D3、E1/E2 | ContentFreeze | 六項追溯問題完成；關鍵衝突為 0 | F1/F2 |
| F1 | Canonical Package | 主控 | B–E 全部合格產物 | canonical content、ContextPackage、raw bundle | artifact mapping 完整、版本一致 | F2 |
| F2 | Render | 主控／renderer | F1、style adapter | Executive、Full、Excel | style 未改動內容契約；必要章節存在 | F3 |
| F3 | QA & Delivery | 主控 | F2 產物 | QA log、最終交付 | 結構 QA、視覺 QA、Excel QA 與缺口狀態一致 | 完成 |

### Dependency manifest

以下是 registry 的可機械比對依賴表示；`?` 表示條件式依賴。SKILL.md 的執行圖必須與本區完全一致。

```text
<!-- DEPENDENCY-MANIFEST-BEGIN -->
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
<!-- DEPENDENCY-MANIFEST-END -->
```

### 舊 Phase 對照

| 舊名稱 | 新 Module |
|---|---|
| Preflight | A1–A2 |
| Phase 0 | B1–B3 |
| Phase 0.5 | B4 |
| Phase 1 | C1 |
| Phase 2 | C2 |
| Phase 3 | C3 |
| Phase 4 | C4 |
| Phase 5A | D1 |
| Phase 5B | D2 |
| 獨立財測模型 | D3 |
| Phase 6 投組經理 | E1 |
| RedTeam | E2 |
| IC 整合／ContentFreeze | E3 |
| Phase 7 | F1–F3 |

舊 Phase 檔名目前保留，避免破壞既有輸出、resume 掃描與外部引用。新程式邏輯使用 Module ID。

## 4. Stage gates

### A_GATE｜可以啟動

- `case_id`、執行模式與能力清單已建立。
- 案件為 L2，或已明確記錄 `L2-degraded` 的事實 DD 路由；若本輪條件缺失，case payload 為 `blocked`。只有使用者提供可計算的假設交易條件才使用 `degraded` payload。
- L0/L1 正常轉交 `vc-quick-screen`，不假裝執行完整 DD。

### B_GATE｜證據可供分析

- DocumentIndex 完整且核心文件逐項有證據。
- 公說存在時 B2=`complete`；不存在時 B2=`not_applicable` 且有無命中證據。
- Factbase、FactSheet 與 ConflictLog 已落地。
- 所有估值／IRR 關鍵欄位不存在未解衝突。

### C_GATE｜專家分析可整合

- C1–C4 raw 均含 `## DECK_EXPORT`。
- payload 符合長度與必要欄位。
- C3 Watchlist 已交給 C4 與 D1。
- 任一失敗均以 Module ID 標 `partial` 或 `blocked`。

### D_GATE｜估值與報酬可使用

- CitationTable 的定稿數字可追溯至一手來源；例外使用二手資料時有明確警語。
- `comparables` 只含 verified 列；公司提供、null、缺資料日或缺來源 URL 的候選列留在 `unverified_comparables`，不得計入數量 Gate。
- 同業清單來源已標為 `user_specified` 或 `auto`；使用者指定的個股未被自動補全覆蓋或刪除。
  案件有同業列時，payload 的 `peer_list_source` 必填，`prepare_workbook_input.py` 會擋。
- 估值方法、Hurdle、退出年與倍數都有理由。
- 所有 IRR／Multiple 由 `scripts/irr_matrix.py` 產生。
- 提供 Hurdle 時，IRR 儲存格實際帶達標／未達標／負報酬標記，不只列印圖例。
- 財測模型三情境與公式 QA 通過。

### E_GATE｜內容可凍結

- E1 六維度與風險矩陣完成。
- E2 R1–R6 完整。
- ContentFreeze 六項追溯問題完成。
- GP 決策欄位維持留白，除非 GP 本人明確提供內容。

### F_GATE｜可以回報完成

- Executive、Full、Factbase Excel、獨立財測模型、ContextPackage、raw bundle 均存在。
- PPTX 結構與視覺 QA、Excel QA 通過。
- QA log 的狀態與實際產物一致；不得以舊產物替新生成結果背書。

## 5. 核心 artifact contract

### FactSheet

```json
{
  "meta": {
    "company": "",
    "case_id": "YYYYMMDD_簡稱",
    "eval_date": "YYYY-MM-DD",
    "analyst": "OpenAI/Codex",
    "hurdle_rate": null
  },
  "financials": {
    "revenue_latest": null,
    "revenue_unit": "千元NTD",
    "gross_margin_latest": null,
    "net_income_latest": null,
    "eps_latest": null,
    "cash": null,
    "debt_ratio": null
  },
  "deal": {
    "round": null,
    "price_per_share": null,
    "pre_money": null,
    "post_money": null,
    "raise_amount": null,
    "ipo_target_year": null,
    "underwriter": null,
    "payment_deadline": null
  },
  "forecast_bp": {
    "revenue_1y": null,
    "revenue_3y": null,
    "eps_exit_year": null,
    "growth_assumption": null
  },
  "red_flags": [],
  "missing_items": [],
  "confirmed_clients": [],
  "key_risks": []
}
```

無資料填 `null`，不得推測填值。`hurdle_rate` 依 Fund Profile 設定，不可寫死。

### Expert payload

```text
module_id：C1/C2/C3/C4/D2/E1
評分：★/5
一句結論：≤30 字
deck-ready 核心判斷：≤60 字，含數字／規格／來源
移交數據：結構化區塊；無則填「無」
重大紅旗：≤3 條
raw 檔路徑：/outputs/...
```

### CitationTable

至少包含：公司、代號、股價、市值、最近兩個完整年度營收、營收 YoY、毛利率、營業利益率、淨利率、trailing P/E、forward P/E、數據日期、來源 URL、來源等級、查詢日期。

### ContentFreeze 六問

1. IRR 的退出 EPS／估值基礎是哪一版本？
2. 使用公司 BP、獨立財測或哪個情境？
3. 同業倍數是否採同一基準日？
4. 投前／投後估值是否與股數、單價、募資額勾稽？
5. 股數是否包含本輪新增、ESOP、選擇權與其他攤薄？
6. 核心收入屬已認列、已簽約、LOI/MOU、Pipeline 或管理層預估？

## 6. Factbase Excel 雙路徑

### 有公說

以 `prospectus-extractor` 的固定 35 分頁母版為基底；evaluator 的增資條件／本輪情境、同業估值、補件清單只能作為附加分頁。母版可多不可少，不另建競爭版本。

### 無公說

可建立精簡版：`0_說明`、`1_增資條件`、`2_公司基本`、`3_股東董監`、`4_團隊`、`5_產品市場`、`6_客戶供應商`、`7A_IS明細`、`7B_BS明細`、`9_同業估值`、`11_補件清單`。`0_說明` 必須標「無公說來源、非 35 分頁母版」。財測與 IRR 只放獨立財測模型，不在 Factbase 重複維護。

## 7. 來源衝突規則

- 財務數字：查核／核閱財報 > 官方公說及申報 > 最新自結 > BP／Pitch Deck。
- 日期相同時：細項可勾稽者 > 只有總數者。
- 股數與持股：股東名冊／正式股本文件 > 增資簡報。
- 收入可信度：已認列 > 已簽約 > LOI/MOU > Pipeline > 管理層預估。
- 較新文件不會自動推翻較高證據層級；採用較低層級資料時必須說明原因。

## 8. Context 與 resume

- 主控只保存 FactSheet、payload、狀態與路徑。
- raw 全文以檔案交接；需要簡報素材時只切讀 `## DECK_EXPORT`。
- 完成證據必須與本次來源版本相符。來源檔內容變更後，受影響的下游 Module 全部回到 `pending`。
- 失敗隔離只允許繼續沒有相依關係的 Module；不能讓下游在缺關鍵輸入時得到 `complete`。

## 9. 實作邊界

目前已程式化：

- `scripts/evaluator_runner.py`：Stage／Module 狀態、artifact hash、dependency gate、stale 失效與續跑 manifest。
- `scripts/irr_matrix.py`：IRR／Return Multiple 雙矩陣。
- `scripts/prepare_workbook_input.py`：D3／F2 frozen input 驗證、canonical return matrix 與獨立財測資料。
- `scripts/build_evaluator_workbooks.mjs`：無公說 11 分頁 Factbase 與 D3 七分頁模型；使用平台受管 `@oai/artifact-tool`。
- `scripts/verify_evaluator_workbooks.mjs`：精確分頁、公式錯誤、矩陣與 Checks audit。
- `scripts/assemble_canonical_package.py`：E_GATE 後建立唯一 F1 ContextPackage 並寫回 runner manifest。
- `scripts/build_investment_decks.mjs`：neutral Executive／Full-critical PPTX renderer；只消費 frozen content。
- `scripts/verify_and_record_delivery.py`：整合 workbook audit、PPTX QA、F2/F3 記錄與 F_GATE 驗證。
- `scripts/slice_toolresult.py`：大型文字與 DECK_EXPORT 錨點切片。
- `scripts/qa_deck.py`：PPTX 結構檢查，不是視覺 QA；獨立執行需要 plugin 根目錄 `requirements.txt` 宣告的 `python-pptx`。缺少時 F3 不能通過。
- `prospectus-extractor`：B2 公說萃取與 manifest 驗證。
- plugin `scripts/route_case.py`：L0/L1/L2 與公說條件式三 Skill 分流 preflight。

仍屬 agent 分析工作、不可偽裝成確定性自動化：

- B1–E3 對原始文件的語意判讀、衝突取捨、專家觀察、外部查驗與 ContentFreeze 回答。
- 第三方 style renderer；目前程式化的是 neutral，custom style 失敗時依 style contract fallback。
- 視覺品質的最終人眼／模型判讀；builder 已輸出逐頁 PNG 與 layout JSON，但程式不能取代該判讀。

文件描述完整目標能力時，不得把尚未程式化的模組宣稱為已自動化。新增程式應掛到既有 Module，不建立第二套流程。

## 10. 新功能擴充規則

新增功能時只做以下步驟：

1. 選定 Stage，建立唯一 Module ID；同類模組用字母後綴，例如 `C3a`，不要創造新的 Phase 小數。
2. 在 registry 宣告 Owner、必要輸入、主要產物、完成證據與阻斷範圍。
3. 把領域方法放入單一 reference；確定性計算或檔案轉換放入 `scripts/`。
4. 在 Stage gate 加入必要條件；若為選配，定義 `not_applicable` 證據。
5. 在 F1 artifact mapping 指定哪些報告使用該產物。
6. 新增正向、缺輸入、舊產物與內容損壞測試；綠燈必須驗本次生成結果。
7. Style 只能消費 canonical content，不得成為分析模組的必要依賴。

這套擴充方式讓新功能只修改 registry、單一 domain reference、必要 script/test 與 F1 mapping，不需跨全文插入規則。
