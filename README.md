# Brian VC

[![plugin-regression](https://github.com/jabir95tsai/brian-vc/actions/workflows/test.yml/badge.svg)](https://github.com/jabir95tsai/brian-vc/actions/workflows/test.yml)

**讓 Codex 協助你看投資案：從簡報初篩、公開說明書萃取，到完整投資盡調。**

Brian VC 是三個互相協作的 Codex Skills。提供公司文件與需求，AI 依資料完整度選擇流程，產出有來源的繁體中文研究底稿、報告與簡報。

## 安裝：貼這一句給 Codex

```text
幫我安裝 https://github.com/jabir95tsai/brian-vc
```

**給收到這個要求的 AI：** 請先讀 [INSTALL.md](INSTALL.md)，依目前環境完成安裝與驗證，再回報結果。

需要支援 Plugins 的 Codex 環境；完整文件產出另需 Python 3.12+ 與對應文件工具。安裝後請開新對話載入 Skills。

<details>
<summary>手動安裝（Codex CLI）</summary>

```sh
codex plugin marketplace add https://github.com/jabir95tsai/brian-vc
codex plugin add brian-vc@brian-vc-local
```

`brian-vc-local` 是本專案宣告的 marketplace 名稱。版本不支援上述指令時，請參閱 [安裝與排錯](INSTALL.md)。

</details>

## 安裝後，直接說你要做什麼

附上文件，或提供 Codex 可讀取的資料夾路徑：

| 你手上有什麼 | 可以這樣說 | 對應 Skill／主要產出 |
|---|---|---|
| 一份 BP、Pitch Deck 或公司介紹 | 幫我初篩這份簡報，判斷是否值得進一步 DD。 | `vc-quick-screen`：2–3 頁初篩備忘、疑慮與補件清單 |
| 台灣公開說明書 | 幫我把這份公說整理成有來源的事實底稿與 Excel。 | `prospectus-extractor`：來源定位、24 項 coverage、固定 35 分頁 Excel |
| 完整 data room | 幫我評估這個資料夾的投資案，產出投審會資料。 | `vc-investment-evaluator`：盡調、財測與估值、Executive／Full 簡報 |

想指定流程，也可以說：

```text
使用 $vc-quick-screen 分析這份簡報，列出亮點、疑慮與必取資料。
```

完整盡調需要財報、股權資料、詳細三表及本輪交易條件等證據。資料不足時會分流或列出缺口；缺少交易條件時，不會把 IRR 當成已可計算。

## 整個專案如何運作

```text
公司文件 → 盤點與資料分流 → 初篩／公說萃取／完整盡調 → 驗證與交付
                              公說萃取也可供完整盡調使用
```

Skills 引導 AI 閱讀來源、分析與判斷；Python／JavaScript 工具負責檢查、計算、組裝與驗證。分析內容先凍結，再製作 Excel／簡報；預設採中性樣式，可明確指定 BrianStyle。

| 想了解什麼 | 從這裡開始 |
|---|---|
| 安裝、依賴與排錯；AI 安裝步驟 | [INSTALL.md](INSTALL.md) |
| 三個工作流程的完整指令 | [初篩](brian-vc/skills/vc-quick-screen/SKILL.md) · [公說萃取](brian-vc/skills/prospectus-extractor/SKILL.md) · [投資盡調](brian-vc/skills/vc-investment-evaluator/SKILL.md) |
| 架構、資料流程、測試與開發入口 | [專案指南](docs/PROJECT.md) |
| GPT-6 Astra 使用、契約調整與新對話測試 | [遷移紀錄](docs/ASTRA6_MIGRATION.md) |
| Plugin 包裝與安裝來源 | [Plugin manifest](brian-vc/.codex-plugin/plugin.json) · [Marketplace manifest](.agents/plugins/marketplace.json) |

## 資料與使用邊界

- 事實與數字保留來源；台灣市場資料優先查驗 MOPS、TWSE、TPEx，未確認資料明確標示。
- 原始輸入保持唯讀，產出放在案件輸出目錄；範例與測試資料不應當成投資依據。
- 交付內容是內部研究草稿，投資決策由使用者負責。
- 本專案目前未提供開源授權，保留所有權利；安裝說明不代表另行授予使用、修改或散布授權，使用授權請洽作者。
