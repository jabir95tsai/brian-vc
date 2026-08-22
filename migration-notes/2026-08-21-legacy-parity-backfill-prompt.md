# 任務 Prompt — 補回舊版有、現行版沒有的 5 項功能

## 你的任務

在 `C:\Users\jabir\Hacker_J\brianvc-skill` 這個 repo，把 5 項「2026-07-25 舊版 Claude Skill 有、但現行 `brian-vc/` Codex plugin 沒有」的功能補回去。**一項一個 commit**，每項都要有契約、敘述、測試、CHANGELOG 四件事。

分支：`master`（主分支是 `main`）。**不要 push，不要開 PR**，除非我另外要求。

---

## 環境

- 現行版本：`brian-vc/`（Codex plugin，evaluator v5.2）
- 舊版基準：`vc-skills-3pack for-ChatGPT 20260725/`（Claude Skill v4.2，**唯讀，禁止修改**）
- 三個 skill：`vc-quick-screen`（L0/L1 初篩）、`prospectus-extractor`（台灣公說萃取 v2.0）、`vc-investment-evaluator`（L2 完整 DD，Stage A–F）

### 權威檔（改東西前必讀）

| 檔案 | 唯一負責範圍 |
|---|---|
| `brian-vc/skills/vc-investment-evaluator/references/pipeline_contract.md` | Stage、Module ID、相依關係、產物、狀態、完成閘門 |
| `brian-vc/skills/vc-investment-evaluator/SKILL.md` | 執行敘述；含 `<!-- DEPENDENCY-GRAPH-BEGIN -->` 區塊，必須與 pipeline_contract 的 Module registry 完全一致（有測試逐邊比對） |
| `references/phase0_playbook.md` | 文件／PDF／公說讀取與萃取細節 |
| `references/experts/*.md` | 各專家分析方法、最低輸出、payload（≤400 字） |
| `references/financial_model_contract.md` | 七分頁財測模型內容與公式責任 |
| `references/output_style_contract.md` | Executive／Full 視覺呈現邊界 |
| `references/deck_content_contract.md` | F2 deck 的 frozen payload 欄位 |

`pipeline_contract.md` 第 1 節明訂：同一規則出現在兩個檔案時以權責表為準，修正時要**刪除非權責檔中的重複規則或改成連結**。補功能時遵守這條，不要到處複製規則。

---

## 開始前先自己驗一次

**不要直接相信下面的缺口清單。** 先自己確認每一項在現行版本確實不存在：

```bash
cd "C:/Users/jabir/Hacker_J/brianvc-skill"
grep -rn "關鍵字" brian-vc/skills/vc-investment-evaluator/
```

若發現某項其實已存在（可能藏在別的措辭裡），**跳過該項並回報**，不要重複實作。

---

## 五項缺口

### #1 案件類型自動調整表（優先做這項）

**現況**：`SKILL.md:177` 只剩一句「依案件類型選 P/E、P/B、P/S 或 ARR 倍數」。CHANGELOG v5.0 宣稱「還原製造業 P/E 折價、ARR 倍數與案件類型關鍵追問」，但**整張對照表不在任何 reference 檔**。這是唯一會直接影響 hurdle rate 與估值主法選擇的缺口。

**舊版原文**（`vc-skills-3pack for-ChatGPT 20260725/vc-investment-evaluator/SKILL.md` 第 260 行起）：

| 類型 | Hurdle | 估值主法 | 關鍵追問 |
|------|--------|---------|---------|
| 製造業 Pre-IPO | 15% | P/E 法 | 庫存/毛利結構/供應商集中 |
| SaaS/訂閱型 | 25% | ARR 倍數法 | MRR/Churn/CAC/LTV/NRR |
| 矽智財 IP | 25% | P/E（財測 EPS）| SBC 正常化/關聯交易 |
| 半導體設備/檢測 | 25–30% | P/E + P/S | 良率/客戶驗證週期/Sole-source |
| 租賃/汽車金融 | 15% | P/E + P/B | 槓桿/利差/期限錯配/covenant |
| AIDC / 算力 / 雲 | 25% | P/S(主)+P/E(財測) | 電力/NCP/EPC 合約 |

**注意**：舊版另有一份 FUND_PROFILE hurdle 表（成熟獲利 Pre-IPO 15%／成長型新創 25%／早期新創 30%／生技臨床 35%／矽智財 25%／氫能硬體 25–30%／AIDC 25%）。現行版 hurdle 有 14 個檔案命中，**先確認現行 hurdle 規則長什麼樣，兩張表如何併存或哪張是權威**，不要製造第二個互相矛盾的來源。

**落點建議**：新增 `references/case_type_matrix.md`，由 A2（Data Gate，決定 hurdle）與 D2（Valuation，決定估值主法）引用；B4 的管理層拷問引用「關鍵追問」欄。要在 `pipeline_contract.md` 第 1 節權責表加一列。

**驗收**：`check_architecture.py` 加檢查——六種案件類型都在、每列四欄齊全、hurdle 與現行規則不衝突。

---

### #2 Phase 5A 同業清單雙模式

**現況**：`grep -rn "使用者指定\|雙模式\|龍頭"` → 0 命中。D1 只有「C3 Watchlist ≤10」，沒有「使用者指定個股優先」這條。

**舊版原文**：

> **同業清單（雙模式）**：① 使用者指定優先（Brian 給個股/代號以此為準）；② 自動模式＝沿用 Phase 3 Watchlist＋龍頭補全；互動情境請使用者過目，背景情境直接產生並註明清單來源。

**落點建議**：`pipeline_contract.md` 的 D1 Module registry「必要輸入」欄加入「使用者指定同業清單（若有）」；SKILL.md D1 段落補雙模式與清單來源標註規則。

**注意**：舊版的三層查價優先序（Claude-in-Chrome → web_fetch → WebSearch）是 Claude 專屬工具鏈，現行版已刻意改成平台無關的官方來源政策。**只補「清單怎麼決定」與「來源要標註」，不要把 Claude 工具鏈搬回來。**

**驗收**：D1 的完成證據要能區分「使用者指定」與「自動生成」兩種清單來源。

---

### #3 錯兩次即停

**現況**：0 命中。

**重要**：舊版 SKILL.md 第 142 行**只引用了**「依『錯兩次即停』升級處理」，但**全套舊版檔案裡從來沒有定義過這條規則**（我已 grep 過整個 `vc-skills-3pack` 目錄）。所以這不是搬運，是**新寫**一條重試上限規則。

**要定義的**：同一 Module 連續失敗 2 次後停止重試，狀態標 `partial` 或 `blocked`，把失敗原因寫進 manifest，回報使用者而不是無限重試。

**落點建議**：`pipeline_contract.md` 第 2 節「狀態模型」加重試上限；`scripts/evaluator_runner.py` 的 module 狀態記錄加 attempt 計數；SKILL.md A1 提及。

**注意**：現行狀態模型已有 `pending`／`in_progress`／`complete`／`partial`／`blocked`／`not_applicable` 六種。**不要新增第七種狀態**，用既有狀態加 attempt 欄位表達。

**驗收**：`test_runner.py` 加測試——同一 module 第 3 次 set 失敗時 runner 拒絕或標記升級。

---

### #4 Context 防爆規則 M-CTX-1／2／3

**現況**：「防爆」0 命中。但**七條裡有四條其實還活著**，先確認再補：

| 規則 | 現況 |
|---|---|
| M-CTX-4 錨點切片讀（`## DECK_EXPORT`） | **存活**（13 檔命中 DECK_EXPORT，`scripts/slice_toolresult.py` 仍在） |
| M-CTX-6 payload ≤400 字 | **存活**（`references/experts/*.md` 每支都有「## 回傳 payload（≤400 字）」） |
| M-CTX-5 失敗隔離 | 部分被 `evaluator_runner.py` module 狀態機取代 |
| M-CTX-7 降級模式落地 | 部分被 SKILL.md A1 第 3 點取代（「不可用時按相同契約順序執行並逐模組落地，不能用摘要取代完整 raw」） |
| **M-CTX-1 主控零原文** | **缺** |
| **M-CTX-2 全產物落地** | **缺** |
| **M-CTX-3 Phase 0 分批讀** | **缺** |

**舊版原文**（只補這三條）：

> - **M-CTX-1 主控零原文**：主控只持有 FactSheet + 各 payload + 落地檔路徑。
> - **M-CTX-2 全產物落地**：每 Phase 完整輸出都寫檔，以讀檔串接，不以記憶串接。
> - **M-CTX-3 Phase 0 分批讀**：大型 data room 逐檔提取、即時寫入事實底稿，原始文件不長駐 context。

**落點建議**：SKILL.md「六段主流程」表格之前，寫成 3 條具名規則。**用新版語彙改寫**：「Phase 0」→「Stage B」，「每 Phase」→「每個 Module」，`/outputs/` 路徑 → evaluator_runner manifest 記錄的產物路徑。

**驗收**：`check_architecture.py` 加檢查三條規則的具名 ID 存在。

---

### #5 ICDecisionAgent 交棒語

**現況**：0 命中。`deck_content_contract.md` 有 "GP decision blanks" 的概念與 E1 的「GP 欄位留白」完成證據，但沒有 E2→F1 的具體交棒句式。

**舊版原文**：

> **ICDecisionAgent 銜接（主控整合）**：「RedTeam 提出 [N] 個反對理由，主要風險點為 [列表]，GP 決策框架已留白供填入」。

**落點建議**：SKILL.md E2 段落，或 `references/experts/redteam.md` 的 payload 格式。這是五項裡最輕的，可與 #3 合併一個 commit。

**驗收**：E2 payload 要能被 F1 直接取用，不需主控自寫。

---

## 不得補回去的三件事（刻意移除，補回即退步）

1. **vc-quick-screen 的長度上限**：亮點/疑慮已從「各 3–5 點」收成「各 3 點」，管理層拷問從「10–15 題」收成「預設 10 題，必要時最多 15 題」。commit `60190c1` 標題就是「length ceiling earns out」。**這是設計決定，不是遺漏。**
2. **BrianStyle 從預設降為 optional**：`references/legacy_brianstyle_deck.md` 開頭明寫「Do not read or apply this file unless the user explicitly selects a BrianStyle-compatible adapter」，active 契約是 `output_style_contract.md`。不要把 BrianStyle 改回主路徑。
3. **`phase7_deck.md` 被刪除**：內容已拆進 `deck_content_contract.md` + `financial_model_contract.md` + `legacy_brianstyle_deck.md` 三份。**不是遺失，不要復原這個檔案。**

---

## 硬規則

1. **語彙轉換**：舊版規則用 Claude Skill 語彙寫（subagent 派工、`/outputs/{case_id}_*` 路徑、Phase 0–7 編號）。SKILL.md 明訂「新功能一律掛到 Stage A–F 與 Module ID，不再新增 Phase 5C、6.5 等編號」。**必須改寫，不能整段貼。**
2. **單一狀態表**：SKILL.md A1 明訂「後續每個 Module 都以 `set` 記錄狀態、證據與本次產物，**不得另建第二份狀態表**」。#3 的 attempt 計數要掛在既有 manifest 裡。
3. **DEPENDENCY-GRAPH 同步**：若動到 Module 相依，SKILL.md 的 `<!-- DEPENDENCY-GRAPH-BEGIN -->` 區塊與 `pipeline_contract.md` Module registry 必須同步，`check_architecture.py` 會逐邊比對。
4. **不改舊版目錄**：`vc-skills-3pack for-ChatGPT 20260725/` 是移植前基準（ZIP SHA-256 已記錄在 `migration-notes/2026-07-28-openai-port-changes.md`），唯讀。
5. **不碰 `cases/`**：那是實測案件資料，不是程式碼。

---

## 每項的標準程序

1. 改 `pipeline_contract.md`（契約）
2. 改 `SKILL.md`（敘述）
3. 加測試到 `brian-vc/tests/vc-investment-evaluator/` 對應檔
4. 在 `references/CHANGELOG.md` 頂端 v5.3 區塊記一列（格式照現有 v5.2）
5. 跑全套回歸
6. commit（訊息格式照 `git log` 現有慣例，例如 `evaluator: restore case-type hurdle and valuation matrix`）

## 驗證指令

```bash
python -X utf8 brian-vc/tests/run_all.py
```

這會跑 15 個檢查（preflight + 4 個 plugin 測試 + 三個 skill 的測試 + evaluator 的 7 個契約測試）。**每個 commit 前都要 PASS。**

單跑架構檢查：

```bash
python -X utf8 brian-vc/tests/vc-investment-evaluator/check_architecture.py
```

---

## 交付

做完回報：

- 每項的實際落點（檔案:行號）
- 哪幾項在自驗時發現「其實已存在」而跳過
- `run_all.py` 最終結果
- 五個（或合併後四個）commit 的 hash 與訊息

**若某項在補的過程中發現會和現行契約衝突（例如 #1 的兩張 hurdle 表打架），停下來回報衝突點，不要自己選一邊硬做。**
