# vc-investment-evaluator 架構重構紀錄

日期：2026-07-31

## 目標

先整理歷次迭代造成的前後不一，再建立可擴充的大管線。保留既有投資方法、專家深度、舊 Phase 輸出檔名與原始來源資料；不在本輪實作新的 PPTX／Excel renderer。

## 稽核發現

1. `Phase 6` 同時表示投組經理 subagent 與主控 IC 整合，Owner 不清楚。
2. `Phase 5A/5B`、`Phase 0.5` 與歷次小數編號讓新增功能只能繼續插號。
3. SKILL 主文寫 `pdffonts→OCR/Vision`，但現行 Phase 0 playbook 已明訂不依賴 `pdffonts`。
4. 公說段落曾把公說中的財報寫成最高優先，與「查核／核閱財報優先」衝突。
5. Factbase Excel 同時出現公說 35 分頁母版與 11 分頁清單，沒有清楚說明是兩條條件式路徑。
6. 現行契約仍殘留 `subagent_type=claude`、`Claude 財測`、`.claude` tool-result 路徑與 `web_search` 工具名稱。
7. `qa_deck.py` 原稱取代目視 checklist，實際只驗 PPTX 結構，不能證明視覺版面。
8. v4.0 主標、v4.2 changelog 與 OpenAI port v0.1 同時存在，版本語意不一致。
9. 工作流程、角色方法、style、財測與歷史 changelog 有重複規則，容易再次漂移。
10. 初版 Stage DAG 把 C1/C2 畫成 C4/D1 前置、漏畫 C1/C2→E1，並誤畫 D3→E1，與 registry 不一致。
11. `qa_deck.py` 的 `python-pptx` 未宣告，缺套件訊息使用不適合 Windows 的 `--break-system-packages`。
12. 重構時遺失製造業 P/E 折價、ARR 倍數與五組案件類型關鍵追問。
13. `irr_matrix.py` 只列 Hurdle 圖例，沒有標記實際儲存格。

## 新架構

以 Stage A–F 作唯一上層流程：

| Stage | 大管線 | Module |
|---|---|---|
| A | 案件啟動與分流 | A1–A2 |
| B | 證據底座 | B1–B4 |
| C | 獨立盡調 | C1–C4 |
| D | 市場查驗與報酬 | D1–D3 |
| E | 決策挑戰與凍結 | E1–E3 |
| F | 交付與 QA | F1–F3 |

`references/pipeline_contract.md` 現為 Module 相依、Owner、輸入、產物、完成證據、阻斷範圍與 Stage gate 的唯一權威。舊 Phase 1–6 檔名保留作 resume 與既有引用相容；新增功能一律使用 Module ID。

## 已統一的規則

- 財務證據：查核／核閱財報 > 官方公說及申報 > 最新自結 > BP／Pitch Deck。
- 市場資料：MOPS > TWSE > TPEx；二手來源僅交叉驗證。
- 公說案件：固定 35 分頁母版加 evaluator 延伸分頁。
- 無公說案件：才可使用 11 分頁精簡版，且必須明確標示。
- 主控 Owner：A、B、D1、E3、F；獨立專家／reviewer：C1–C4、D2、E1、E2；D3 可由主控或獨立模型 agent 執行。
- RedTeam 優先使用未參與主分析的獨立 reviewer，不綁特定供應商。
- Style 只處理呈現；分析、證據、計算與必要內容先完成並凍結。
- `qa_deck.py` 明確定位為結構 QA，視覺 QA 仍是獨立閘門。
- DAG 改成 19 個 Module 的可機械解析直接前置依賴，並逐邊比對 canonical dependency manifest。
- C1/C2/C3 可平行；只有 C3 餵 C4/D1；C1/C2 直接進 E1；D3 不阻斷 E1，而是在 E3 收斂。
- plugin 根層 `requirements.txt` 宣告 `python-pptx>=1.0,<2`；缺套件 guard 指向該檔，不使用平台限定 pip 旗標。
- Fund Profile 還原製造業 P/E `0.75/0.85/1.0`、新創 ARR `5x/8x/12x` 與案件類型關鍵追問。
- `irr_matrix.py --hurdle` 會在每個 IRR 儲存格實際加上 `✅/⚠️/❌`。

## 擴充方式

新增功能時：

1. 選 Stage 並新增唯一 Module ID。
2. 在 registry 宣告 Owner、輸入、輸出、完成證據、阻斷範圍。
3. 領域方法只寫在一個 reference；確定性邏輯放 script。
4. 更新對應 Stage gate 與 F1 artifact mapping。
5. 新增正向、缺輸入、舊產物與內容損壞測試。

不再新增 `Phase 5C`、`Phase 6.5` 或把同一規則複製到多個檔案。

## 實作邊界

本輪沒有把契約能力誤稱為已自動化。現有程式化能力仍是：

- IRR／Return Multiple 計算。
- 長文字／DECK_EXPORT 切片。
- PPTX 結構 QA。
- 透過 `prospectus-extractor` 執行公說萃取與 manifest 驗證。

仍待後續實作：Stage artifact manifest、無公說 Factbase Excel builder、七分頁財測模型 builder、style-agnostic PPTX renderer、視覺 QA 與端到端 runner。

## 驗證

執行：

```powershell
python -X utf8 brian-vc/tests/vc-investment-evaluator/check_architecture.py
python -X utf8 C:\Users\jabir\.codex\skills\.system\skill-creator\scripts\quick_validate.py brian-vc\skills\vc-investment-evaluator
```

結果：

- 架構一致性：18/18 checks passed。
- Skill validator：`Skill is valid!`
- `git diff --check`：通過。
- Miniconda 隔離環境缺套件 guard：exit 2、無 traceback、安裝路徑正確。
- Codex Presentations runtime：`qa_deck.py --help` exit 0，可載入 `python-pptx`。
- IRR CLI smoke：負報酬、未達 Hurdle、達標三類儲存格分別輸出 `❌/⚠️/✅`。
- Miniconda Python 若未加 `-X utf8`，官方 validator 會受 Windows CP950 影響；這是 validator 的讀檔環境問題，不是 Skill UTF-8 內容錯誤。

## 主要異動檔

- `brian-vc/skills/vc-investment-evaluator/SKILL.md`
- `brian-vc/skills/vc-investment-evaluator/references/pipeline_contract.md`
- `brian-vc/skills/vc-investment-evaluator/references/experts/*.md`
- `brian-vc/skills/vc-investment-evaluator/references/phase0_playbook.md`
- `brian-vc/skills/vc-investment-evaluator/references/output_style_contract.md`
- `brian-vc/skills/vc-investment-evaluator/references/financial_model_contract.md`
- `brian-vc/skills/vc-investment-evaluator/scripts/*.py`
- `brian-vc/tests/vc-investment-evaluator/check_architecture.py`
