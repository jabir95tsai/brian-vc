# prospectus-extractor 目標輸入／輸出契約

狀態：Target contract v1.0（2026-07-30）  
適用目標：OpenAI／Codex Plugin 版 `prospectus-extractor`  
注意：本文件先定義遷移目標，不代表現有 scripts 已全部符合。

## 1. Skill 邊界

`prospectus-extractor` 專責把台灣公開說明書及其補充文件轉成可追溯的結構化事實底稿。它負責文件索引、OCR、定點萃取、來源追溯、覆蓋率與 Excel 渲染，不負責：

- 只有 BP／Pitch Deck 的案件初篩；此類改用 `vc-quick-screen`。
- 完整估值、IRR、六專家投資判斷；此類由 `vc-investment-evaluator` 執行。
- 獨立市場研究或同業查價。
- 將公司自述、市場預測或未查核 data room 數字冒充已驗證事實。

沒有公開說明書時，本 Skill 回報 `not_applicable`，不得用一般簡報假裝成公說。若下游需要對多來源 data room 建 Factbase，應由 evaluator 的一般 Phase 0 流程處理。

## 2. 目標輸入

### 2.1 必要輸入

| 輸入 | 要求 |
|---|---|
| 公開說明書 | 至少 1 份台灣公開說明書 PDF；接受 IPO／上市櫃、現金增資、員工新股等版本 |
| `case_id` | 可由使用者提供；未提供時產生 `{YYYYMMDD}_{股票代號或公司簡稱}` |
| 輸出目錄 | 可由使用者提供；未提供時使用目前工作目錄下的 case 輸出資料夾 |

公開說明書可來自：

- 使用者上傳或本機路徑。
- MOPS、TWSE、TPEx 等官方頁面的直接 PDF URL。

若輸入是 URL，執行前須保存取得的 PDF 快照並記錄 URL、取得日期與檔案雜湊；不得只引用搜尋摘要。

### 2.2 選配補充輸入

| role | 典型格式 | 用途 |
|---|---|---|
| `audited_fs_consolidated` | PDF | 合併查核財報、KAM、逐項 IS／BS／CF |
| `audited_fs_individual` | PDF | 個體查核財報、逐項 IS／BS／CF |
| `annual_report` | PDF | 年報附註、部門資訊、主要客戶／供應商 |
| `interim_fs` | PDF／XLSX | 最新季財務資料；須標查核／核閱／自結 |
| `dataroom_supplement` | PDF／DOCX／XLSX／CSV／PPTX／圖片 | 客戶、供應商、合約、股東與本輪條件補件 |
| `prospectus_revision` | PDF | 舊版／修訂版對照；不得靜默覆蓋差異 |

data room 採語意辨識，不要求檔名精確符合。但每筆採用資料都必須保留原始檔名、頁碼／工作表／儲存格或段落定位。

### 2.3 建議的自動化輸入 manifest

互動操作不強制使用 manifest；批次、重跑或下游派工建議使用：

```json
{
  "schema_version": "1.0",
  "case_id": "20260730_範例公司",
  "company": {
    "name": "範例股份有限公司",
    "stock_code": null
  },
  "output_dir": "outputs/20260730_範例公司",
  "sources": [
    {
      "source_id": "SRC-001",
      "role": "prospectus",
      "path_or_url": "input/prospectus.pdf",
      "document_date": "2026-07-15",
      "period": null
    }
  ],
  "options": {
    "ocr": "auto",
    "keep_work_files": false,
    "language": "zh-TW"
  }
}
```

必要驗證：

- `sources` 至少一筆 `role=prospectus`。
- 檔案可讀、頁數大於零；加密或毀損 PDF 必須停止並回報。
- 原始輸入唯讀保存，不得覆寫。
- 多版本必須記錄文件日期與採用順序。

## 3. 來源與衝突規則

每筆資料都要有 `source_id` 與定位：

```text
SRC-001 physical p.42 / printed p.35
SRC-003 sheet=客戶明細 cell=B12:F18
```

基本優先序：

1. 查核／核閱財務報告。
2. 官方公開說明書原文。
3. 官方年報或最新依法揭露資料。
4. data room 自結資料。
5. Pitch Deck／管理層簡報。

同欄位出現不同值時不得靜默覆蓋；`case_data.json` 必須保存候選值、採用值、採用規則及待確認狀態。仍無法裁定時標 `conflict_unresolved`，交給 evaluator 的 ConflictResolver。

## 4. 中間標準資料：`case_data.json`

`case_data.json` 是唯一資料源；Markdown 與 Excel 均由它產生，不允許各自手工維護。

最小頂層結構：

```json
{
  "schema_version": "1.0",
  "case": {},
  "sources": [],
  "coverage": [],
  "sheets": [],
  "conflicts": [],
  "red_flags": [],
  "missing_items": [],
  "warnings": []
}
```

必要規則：

- `coverage` 固定 24 項，ID 對應 `section_map.md` 的核心 whitelist。
- 每個 sheet 都有 `name`、`status`、`header`、`rows` 與 `reason`。
- `status` 只能是 `complete`、`partial`、`missing`、`not_applicable`。
- `missing` 與 `not_applicable` 必須分開；服務業沒有產能不等於漏抓資料。
- 所有事實列必須有來源；推算值另標公式、輸入值與假設。
- 市場規模、市占等公司自引數字標 `circular_needs_verification`。
- 財務資料標示幣別、單位、期間、合併／個體及查核狀態。

`FactSheet.json` 不由 extractor 直接交付；它應由 evaluator 在衝突處理後，從 `case_data.json`／`Factbase.md` 產生。

## 5. 目標輸出：5 個業務產物＋1 個控制檔

所有檔案使用同一 `case_id`，平放於使用者指定的輸出目錄：

| # | 檔案 | 性質 | 必要 |
|---:|---|---|---|
| 1 | `{case_id}_case_data.json` | 唯一標準資料源 | 是 |
| 2 | `{case_id}_Prospectus_raw.md` | 依法定章節排列的逐項萃取，保留頁碼與原文語意 | 是 |
| 3 | `{case_id}_Factbase.md` | A–G 七類事實底稿，供 evaluator／下游使用 | 是 |
| 4 | `{case_id}_Prospectus_coverage.md` | 24 項 whitelist 的完整／部分／缺失／不適用報告 | 是 |
| 5 | `{case_id}_Prospectus_extract.xlsx` | 固定 35 分頁的人用對帳工作簿 | 是 |
| 6 | `{case_id}_Prospectus_manifest.json` | 輸入清單、雜湊、輸出清單、版本及 QA 結果 | 是 |

這是唯一正式輸出計數。舊文件中的「三件／四件／第五件」說法全部由本契約取代。

### 5.1 Raw Markdown

- 依公說實際章節順序排列。
- 每筆保留 `source_id`、實體頁碼；能辨識時另記印刷頁碼。
- 表格、OCR 與推算資料標示取得方式。
- 不做投資結論，不生成六專家意見。

### 5.2 Factbase Markdown

固定 A–G：

- A 公司基本資料
- B 股東結構
- C 董監事與經營團隊
- D 財務數據
- E 產品、技術與產業
- F 客戶、供應商與重要契約
- G 本輪條件、IPO 規劃與財測

公說沒有 G 區資料時仍保留章節並標缺，不得補猜估值或 IRR。

### 5.3 Coverage

覆蓋率分母固定為 **24**：

```text
核心覆蓋率：complete 18 / partial 3 / missing 2 / not_applicable 1 / total 24
```

Excel 結構完整度另行回報：

```text
Excel 母版：35/35，順序正確
```

不得再使用 `/16`，也不得把 `35/35` 說成資料覆蓋率。

### 5.4 Excel

固定沿用 `build_excel.py` 的 35 張分頁名稱與順序：

```text
00_封面
00_覆蓋率
01_公司沿革
02_股本形成
03_董監事
04_經營團隊
05_主要股東
06_產品營收比重
07_目前產品與服務
08_未來新產品服務
09_未來研發計畫
10_研發成功技術
11_研發人員學經歷
12_從業員工人數
13_產品用途
14_產製過程
15_毛利率變化
16_銷售地區
17_主要供應商
18_主要客戶
19_銷售量值
20_生產量值
21_產能利用率
22_產業概況
23_中下游關聯
24_競爭情勢
25_轉投資
26_重要契約
27_歷年財務摘要5年
28甲_損益表
28乙_資產負債表
28丙_現金流量表
29_AI專家
查核意見_明細
紅旗
```

規則：

- 35 張必須存在且順序固定；附加頁只能接在第 35 張之後。
- `29_AI專家` 僅作下游預留，extractor 不填投資意見；標 `not_applicable` 或「由 evaluator 產生」。
- 缺資料的 sheet 仍存在並明確標 `missing`。
- 不適用的 sheet 標 `not_applicable`，不得用紅色「須補件」誤導。
- 表內所有事實列保留來源欄。
- 樣式採中性可讀格式；分析內容與樣式分離。

### 5.5 Manifest／QA

`Prospectus_manifest.json` 至少記錄：

- `contract_version`、`case_data_schema_version`、執行日期。
- 輸入文件的路徑／URL、角色、日期、頁數、SHA-256。
- 文字層、OCR、Vision 使用情況與失敗頁。
- 六個必要輸出是否存在及 SHA-256。
- whitelist 是否正好 24 項。
- Excel 是否 35/35、順序正確、無公式錯誤字串。
- coverage.md、Excel `00_覆蓋率` 與 case_data 狀態是否一致。
- `validation_status`：`success`／`failed`。

只有 `validation_status=success` 才能回報完成；否則回報失敗原因與可補救動作。

## 6. 工作檔，不計入交付件數

下列放在 `{output_dir}/_work/`，預設可在成功後刪除或由選項保留：

```text
index.json
index.md
scanned_pages.json
sections/
page_images/
ocr/
```

這些是可重跑與除錯材料，不是正式投資資料產物。

## 7. 下游回傳契約

被 evaluator 呼叫時，只回傳精簡 payload，不把 raw 全文放回主 context：

```text
status: success
coverage: complete n / partial n / missing n / N/A n / 24
excel: 35/35, order=ok
conflicts_unresolved: n
red_flags: 最多 3 項
missing_required: 項目清單
outputs: 六個絕對路徑
```

若 `status` 不是 `success`，evaluator 不得進入估值或 IRR。

## 8. 後續實作順序

1. 建立並驗證 `case_data.schema.json`。
2. 修正 `slice_prospectus.py` 的巢狀章節終點。
3. 讓 raw、Factbase、coverage 與 Excel 全部只從 `case_data.json` 渲染。
4. 補完 Excel 35 分頁規格並統一 `29_AI專家` 名稱。
5. 重寫 `verify_excel.py --eq`，移除 `eval` 並真正讀取指定 worksheet／cell。
6. 產生 manifest 並加入跨產物一致性驗證。
7. 更新 `prospectus-extractor`、`vc-investment-evaluator` 的舊三／四／五件與 `/16` 說法。
