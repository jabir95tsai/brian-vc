# Legacy BrianStyle deck specification

This file is retained only as an optional legacy style reference. The OpenAI
port does not require BrianStyle. Do not read or apply this file unless the
user explicitly selects a BrianStyle-compatible adapter. For the active,
style-agnostic contract, read `output_style_contract.md`.

## 1. BrianStyle（說服版）母版骨架（固定骨架，可增減頁）

| 頁 | 內容 |
|---|------|
| P1 | 封面（公司/輪次/報告類型/基金/機密） |
| P2 | 建議投資原因（≥5 亮點：粗藍標題＋補充；每點掛〔領域〕標籤、可追溯到某專家素材；底部建議/投資條件一行） |
| P3 | 投資/增資架構（張數·單價·金額·投前後估值·用途·條件） |
| P4 | 公司基本資料 |
| P5 | 公司沿革（逐條不刪減） |
| P6 | 股本形成 / Cap table |
| P7 | 股東結構（含增資後 % 變化） |
| P8 | 經營團隊（姓名/職務/學歷 分欄；可 1–2 頁）【不可省】 |
| P9–P13 | 產品/技術說明（1–5 頁依案件伸縮，可留生圖版位）；產品線進度地圖、專利（若有） |
| P14 | 技術競品比較（○/×/△） |
| P15 | 產業分析 + 上下游 |
| P16 | 市場規模（TAM/SAM/SOM 標準表） |
| P17 | 供應商 / P18 客戶 |
| P19 | 歷史 IS（≥10 科目逐項） |
| P20 | 歷史 BS（≥30 科目逐項） |
| P21 | 財務預測（逐項多年；獨立財測模型/CFA agent）【不可省】 |
| P22 | 同業比較估值（≥5 家）【不可省】 |
| P23 | 報酬率分析 IRR + Multiple 雙矩陣【不可省】 |
| P24 | 結論與投資建議（含六專家收斂評分表） |
| P25+ | 附錄：轉投資/契約/詳細財報等（可選） |

無資料的頁保留標題、內容留空。deck 吃完整 case_data（合併+個體財報、董監、轉投資、契約、員工、六專家）。

## 2. 視覺規格（BrianStyle v2，鎖定）

純白 10×5.625；Microsoft JhengHei。標題 24pt 粗深藍 #17375B＋灰副標 #6C757D＋細藍橫線＋右下頁碼 n/總頁。表格＝表頭 #1F4E79 白字、**表身斑馬紋**（淡藍 #E8F1F8/白 交替）、首欄粗體、紅旗紅字 #C0392B。封面公司名 40pt 粗藍左對齊。建議投資原因＝粗藍標題 12.2pt＋墨色補充 9.1pt＋底部淡藍框建議行。KPI 扁平。**IRR/Multiple 雙矩陣＝純斑馬紋無熱區色**。無裝飾/陰影/emoji。內文字級下限 10pt；長表自動分頁「（續）」。

## 3. 引擎呼叫（brianstyle-deck，優先）

1. 主控把 Factbase A–G＋六專家 DECK_EXPORT 素材＋Phase 5/6 估值/IRR＋獨立 CFA/財測結果，整理成一份 `D` dict。欄位/頁型對照見 brianstyle-deck `references/格式規範與套用指南.md`；填法範本見其 `examples/data_heyun_real.py`（真實案）與 `examples/data_testco_full.py`（全頁型）。引擎接法另見其 `references/phase7_patch_v2.md`。
2. `from brianstyle_deck import build_deck; build_deck(D, "/outputs/{case_id}_BrianStyle.pptx")`。
3. 引擎需支援 blocks/save 頁型；未安裝或版本過舊 → 退回逐頁手刻（照本檔視覺規格）。
4. **Full（批判版）**：沿用同引擎，母版後插入 Red Flag／靈魂拷問／失敗點／資料缺失頁（皆 table/blocks 頁型），內容取自 E1 風險矩陣、E2 RedTeam R1–R6、B4 補件清單。

## 4. 頁面素材對照（強制；生成每頁以 `## DECK_EXPORT` 錨點切片讀對應 raw）

| deck 頁 | 素材來源 |
|---|---|
| 技術/產品說明、競品比較 | Phase1 DECK_EXPORT（規格表/TRL/護城河） |
| 產業上下游、市場規模 | Phase3 DECK_EXPORT |
| 商業模式/客戶/供應商 note | Phase2 DECK_EXPORT |
| 歷史 IS/BS、財務預測 note | Phase4 DECK_EXPORT |
| 同業比較、報酬率分析 | 5A CitationTable＋5B DECK_EXPORT |
| 結論頁六專家收斂表 | 各 payload 評分＋一句結論 |

各頁 note/sub2 必須由對應專家素材填（tech←技術、compete/market←產業、product/毛利率←商業、is/bs/forecast←財務、comps←估值）；**主控不得自寫通用語**。各頁素材規格＝「專家表格＋註」，不是一句話。

## 5. 獨立財測模型 Excel

工作簿內容與七分頁名稱以 `financial_model_contract.md` 為唯一權威。
BrianStyle adapter 只能套用顏色、字體、欄寬與表格樣式，不得改寫模型公式、
情境、分頁或把獨立估計改稱公司財測。
