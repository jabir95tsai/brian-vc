# CHANGELOG — vc-investment-evaluator

> 歷史紀錄，不能作為執行契約。現行流程以 `SKILL.md` 與
> `pipeline_contract.md` 為準。

## v5.3（2026-08-22）舊版功能補回
- D1 同業清單恢復雙模式：使用者指定的個股或代號優先且不得被覆蓋，否則沿用 C3 Watchlist 並以同產業龍頭補全；清單來源一律標 `user_specified` 或 `auto`，互動情境先請使用者過目。
- 新增錯兩次即停：同一 Module 連續失敗 2 次後 runner 拒絕再重試，manifest 以既有狀態加 `failed_attempts`／`retry_exhausted` 欄位記錄，不新增第七種狀態。
- 新增 E2→F1 RedTeam 交棒語固定格式：payload 直接產出可用句子，F1 組裝 `deck.redteam` 摘要時取用，不必主控重寫。

## v5.2（2026-08-15）可重用 builder、模式 QA 與 replay
- 擴充中文 data-room routing，加入明確的 full／degraded／quick-screen 執行模式。
- 移除通用 deck builder 的固定公司數字、產業敘事與評分結論，改由 frozen payload 的 `deck.copy` 與結構化數據驅動。
- 財測支援 `forecast_rows[].drivers` bottom-up 明細與 `financial_extensions` 舊版深度分頁；核心分頁與公式 QA 保持相容。
- 新增 mode-aware PPTX QA、舊版 Memo／DD／訪談／會議／財報附註相容產物，以及單指令 `replay_evaluator_case.py`。
- fixture 完整 replay 實測通過：11/7 core sheets 加 4/5 個 legacy-depth extensions（70 個基準預測公式、0 formula errors）、16/21 頁 deck 與 7 件 legacy-parity artifacts。

## v5.1（2026-08-15）Codex plugin 1.0 交付層
- 新增三 Skill 共用 preflight 與 L0/L1/L2／公說條件式 router。
- 新增單一 evaluator artifact manifest runner，支援 dependency gate、hash、stale invalidation 與 resume。
- 以平台受管 `@oai/artifact-tool` 實作無公說 11 分頁 Factbase、D3 七分頁財務模型、公式 audit 與逐頁預覽。
- 實作 neutral Executive／Full-critical PPTX renderer，保留 GP 決策留白、IRR／Multiple 雙矩陣與 Full-critical 反方內容。
- 新增 F1 ContextPackage freeze 與 F2/F3 delivery registrar；只有 workbook、PPTX 與視覺 QA 全通過才可得到 `F_GATE=complete`。
- 新增 repository marketplace、install-copy smoke、prompt routing fixtures 與統一 12-command regression suite。

## v5.0（2026-07-31）Stage／Module 架構重構
- 將歷史 Phase 0–7 收斂為 Stage A–F，新增 `pipeline_contract.md` 作為模組相依、產物、狀態與閘門的唯一權威。
- 保留舊 Phase 輸出檔名作續跑相容；新功能改用 Module ID，禁止再新增小數 Phase。
- 統一公說 35 分頁母版與無公說 11 分頁精簡版的雙路徑。
- 移除現行契約中的 Claude 專屬 agent／財測／tool-result 路徑，並統一 PDF 分流與官方來源政策。
- 明確區分 PPTX 結構 QA 與視覺 QA；style adapter 只負責呈現。
- 修正執行 DAG：C1/C2 直接進 E1，C3 才餵 C4/D1，D3 與 E1 平行後在 E3 收斂；圖與 dependency manifest 由測試逐邊比對。
- 還原製造業 P/E 折價、ARR 倍數與案件類型關鍵追問；`--hurdle` 改為實際標記每個 IRR 儲存格。
- 在 plugin 根層 `requirements.txt` 宣告 `python-pptx`，並提供 Windows／Codex 可讀的缺套件指引。

## v4.2（2026-07-09）B.5 驗收閘門（示範科技 0000 教訓）
- 實案失效：示範科技 v1/v2 run 中 DocumentIndex 已命中公說（0000_現增公開說明書_202606），B.5 卻未派工，四件契約落地檔全缺，factbase Excel 被即興做成 11 分頁格式。
- Step B.5 新增驗收閘門：主控 read-back 驗四件落地檔實體存在（Excel 分頁 ≥35），缺任一禁止進 Step D；興櫃登錄公說一律視為公說、「募集條件不適用」不得作為跳過理由。
- Phase 0 完成清單「公說/主文件萃取」改強制舉證：填檔案路徑+分頁數；N/A 須引 DocumentIndex 證明無命中。
- Step D 新增：Factbase Excel 一律走 build_excel.py 35 分頁母版；禁止即興自建母版。

## v4.1（2026-07-08）TechPrimer 銜接
- 新增 `technology-deep-dive` skill 落地檔（TechPrimer）與 Phase 1 技術顧問的銜接：主控派工前掃 `/outputs/TechPrimer_*.md` 與 `{case_id}_TechPrimer_*.md`，主題相符即指定 subagent 必讀；已查證領域數字沿用不重研究，護城河/TRL 投資判斷仍獨立作成（使用規則與邊界見 `references/experts/phase1_tech.md`）。
- 無 TechPrimer 時流程完全不變，不強制先跑 /tech。

## v4.0（2026-07-03）結構定稿
- v3.7–v3.9 三段文末補丁全部合併回本體，消除本體/補丁矛盾（統一契約補入 deck-ready 判斷與 DECK_EXPORT；5A 改為 Chrome→web_fetch→WebSearch 明確 fallback 鏈）。
- 六專家＋RedTeam 人格/輸出結構/DECK_EXPORT 最低要求拆至 `references/experts/`，派工時 subagent 自行讀（省主控 context，呼應 M-CTX-1）。
- Phase 0 大檔處理與 B.5 派工細節移至 `references/phase0_playbook.md`；舊版 Phase 7 BrianStyle 規格現保留於 `references/legacy_brianstyle_deck.md`，OpenAI port 改讀 `references/output_style_contract.md`。
- 新增 `scripts/`：irr_matrix.py（IRR/Multiple 雙矩陣，禁手算）、qa_deck.py（Phase 7 完成閘門程式化 QA）、slice_toolresult.py（超長工具結果錨點切片）。
- 新增 Preflight：依賴檢查（brianstyle-deck 能力檢查取代版本號釘死）、派工能力、**斷點續跑**（掃 /outputs/{case_id}_* 跳過已完成 Phase）、互動/自動模式判定。
- ContentFreeze 增背景/自動模式（主控自答六問落地，標「自動凍結」）。
- 修正：FactSheet hurdle_rate 改依 FUND_PROFILE 帶入（原寫死 0.25）；5A 查詢年份改 {最近完整年度}（原寫死 2025）；BrianStyle 頁數敘述與骨架表對齊。

## v3.9（2026-07）DECK_EXPORT 契約
專家深度直達簡報：每位專家 raw 片尾強制 DECK_EXPORT（NOTE ≤60 字＋ROWS_JSON）；深度底線原文附加；Phase 7 頁面素材強制對照；QA 加驗（一行 note 無量化表＝fail）；需 brianstyle-deck v2.3（10pt 下限、長表分頁）。

## v3.8（2026-07）威世波案四課題
①公說大檔分檔讀＋驗收（80k 字靜默截斷、tool-results 切片、首編合併報表非缺漏）；②同業即時股價只信 Claude-in-Chrome（WebSearch 舊值實測誤差達一倍）；③能派 subagent 就派真六專家；④引擎須含 blocks/save。

## v3.7 多來源觸發放寬 + 專家→deck note 強制對接
Step B.5 觸發加「多來源主文件＋查核財報」組合；專家 payload 加 deck-ready 核心判斷（≤60 字）；highlights 掛〔領域〕標籤；主控不得自寫通用語。

## v3.6 brianstyle-deck v2（範本逆向定稿：#17375B/#1F4E79/斑馬紋/IRR 純斑馬紋雙矩陣；母版可增減頁；科目不刪減）
## v3.5 Phase 7 BrianStyle 改用鎖定版型引擎 brianstyle-deck
## v3.4 Phase 0 Step B.5 公開說明書定點萃取（prospectus-extractor 隔離子代理）
## v3.3 Phase 0 資料充足度閘門（薄資料分流 vc-quick-screen）＋還原六專家完整人格
## v3.2 5A 同業估值強化（擴充 CitationTable）＋兩版簡報定位（BrianStyle 說服版/Full 批判版）＋Factbase 去重＋A0-4 營運實體辨識
