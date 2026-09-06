# 專案指南

使用入口見 [README](../README.md)，安裝入口見 [INSTALL](../INSTALL.md)。本頁提供 AI 與開發者需要的架構地圖。

## 先讀什麼

| 任務 | 閱讀入口 |
|---|---|
| 安裝與環境檢查 | [INSTALL](../INSTALL.md)、[preflight.py](../brian-vc/scripts/preflight.py) |
| 初篩 BP／簡報 | [vc-quick-screen/SKILL.md](../brian-vc/skills/vc-quick-screen/SKILL.md) |
| 萃取台灣公說 | [prospectus-extractor/SKILL.md](../brian-vc/skills/prospectus-extractor/SKILL.md) |
| 完整盡調 | [vc-investment-evaluator/SKILL.md](../brian-vc/skills/vc-investment-evaluator/SKILL.md)，再讀 [pipeline_contract.md](../brian-vc/skills/vc-investment-evaluator/references/pipeline_contract.md) |
| 調整報告外觀 | [output_style_contract.md](../brian-vc/skills/vc-investment-evaluator/references/output_style_contract.md) |

先讀對應 Skill，再依其中連結讀所需 references；無須一次載入所有測試與歷史筆記。`SKILL.md` 定義行為，`agents/openai.yaml` 定義 Skill 的顯示與呼叫資訊，plugin manifest 定義整包入口。

## 分流與資料權責

資料夾先經 [route_case.py](../brian-vc/scripts/route_case.py) 提供初步分流，AI 再閱讀文件確認資料門檻。檔名分類不代替證據查驗。

- L0／L1 薄資料走初篩，產出 2–3 頁備忘、疑慮與升級補件清單。
- 台灣公說可單獨萃取，也可支援完整盡調 B2；產出 sourced case data、Raw／Factbase、24 項 coverage、固定 35 分頁 Excel 與 QA manifest。
- L2 證據齊備後走完整盡調。核心財務資料齊備但缺交易條件時，依 evaluator 的 `L2-degraded`／blocked 規則保留可做的事實 DD，列明估值與 IRR 限制。

原始文件唯讀，保留來源定位、衝突與缺口。台灣市場資料優先 MOPS／TWSE／TPEx；次級數據標示 `⚠️ 尚待官方來源確認`，保留資料日期與查詢日期。

## 完整盡調的 A–F 流程

[pipeline_contract.md](../brian-vc/skills/vc-investment-evaluator/references/pipeline_contract.md) 是 19 個模組、相依關係、產物與完成閘門的唯一權威；本頁只提供導覽。

```text
A 案件啟動 → B 證據底稿 → C 獨立盡調 → D 市場查驗／估值／財測
                                                   ↓
                              F 組裝與交付 ← E 審查與內容凍結
```

| 操作 | 主要工具或產物 |
|---|---|
| 初始化與續跑 | `evaluator_runner.py init`；`verify --invalidate-stale` 檢查失效證據 |
| 證據與分析 | 文件索引、Factbase、專家分析、CitationTable；由 AI 閱讀、查證與判斷 |
| 計算與模型輸入 | `irr_matrix.py`、`prepare_workbook_input.py` |
| 工作簿 | 11 分頁 evaluator Factbase、7 分頁財測模型；公說流程另有 35 分頁底稿 |
| 凍結與組裝 | `assemble_canonical_package.py` 組裝 canonical package |
| 渲染與驗收 | Executive／Full-critical decks、逐頁視覺 QA、`verify_and_record_delivery.py` |

上述工具位於 [evaluator scripts](../brian-vc/skills/vc-investment-evaluator/scripts/)。它們協助計算與驗證，來源閱讀、衝突處理、專家分析、估值判斷、RedTeam 與 ContentFreeze 仍需 AI 執行。只有 `F_GATE=complete` 才可宣告該流程交付完成。

樣式預設為 `neutral`；明確指定才使用 BrianStyle。樣式不得改動計算、來源、缺件標籤或 Executive／Full 的內容邊界。

## 目錄地圖

```text
README.md                         使用者首頁與 AI 導覽
INSTALL.md                        安裝、驗證與排錯
docs/PROJECT.md                   架構與開發入口
.agents/plugins/marketplace.json  marketplace 入口
brian-vc/                         可安裝的完整 plugin
  .codex-plugin/plugin.json       套件名稱、版本與 Skills 路徑
  requirements.txt                獨立 Python 依賴
  scripts/                        共用 preflight、router、樣式解析
  skills/                         三個 SKILL.md 及各自工具、references
  assets/styles/                  報告樣式
  tests/                          合約、回歸測試與必要的合成測試資料
.github/workflows/test.yml        CI
tools/                           專案維護工具
_local/                          Git 忽略的本機案例、封存與日誌
```

## 開發驗證

以下從 repository root 執行，使用已備妥依賴的 Python 環境：

```sh
python -X utf8 brian-vc/scripts/preflight.py --json
python -X utf8 brian-vc/tests/run_all.py
```

完整測試包含來源／安裝副本檢查、prompt routing、三個 Skill 合約、公說處理、evaluator 架構與續跑、workbook／deck 合約及 F1 gate 整合。[CI](../.github/workflows/test.yml) 在 Windows 的 Python 3.12、3.13、3.14 執行同一套回歸入口。

測試通過代表對應程式與合約檢查通過；實際安裝載入、平台 runtime 可用性、真實 XLSX／PPTX 產出及視覺 QA 需另行驗證。歷史 QA 紀錄已移至本機 `_local/archive/`，不代表目前環境已完成同樣實測。

## 本機資料與封存

案例統一放在 `_local/cases/`，新日誌與臨時產物放在 `_local/logs/`、`_local/tmp/`；整個 `_local/` 已由 `.gitignore` 排除。執行案件工具時，明確提供這裡的案件路徑。案件內的歷史 manifest 可能記錄搬移前的絕對路徑，續跑前應重新確認來源定位。

2026-09-06 整理的舊版來源、原始 ZIP、遷移筆記、歷史測試報告及真實案件回歸資料集中在 `_local/archive/`，其中的清單記錄原始相對路徑。必要的合成 Markdown fixtures 仍留在測試目錄；真實案件回歸屬選配，封存後不納入預設測試。需要還原時，依封存清單取回指定檔案，避免覆蓋現有修改。

Git ignore 不會移除既有提交的歷史；本次搬走的已追蹤檔案會在工作樹顯示為刪除，提交這次整理後才會從新版 Git 樹移除。本機封存不會隨 clone 傳送。
