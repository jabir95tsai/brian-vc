# 安裝 Brian VC

本文件是人與 AI 共用的安裝入口。專案用途與使用範例見 [README](README.md)。

## 給 AI：收到「幫我安裝這個 repo」時

目標是將完整 `brian-vc` plugin 安裝至使用者的 Codex，確認安裝狀態，並說明新對話如何使用。不要只複製三份 `SKILL.md`：它們依賴共用 scripts、references 與 assets。

1. **檢查環境與既有安裝。** 確認有 Codex plugin 管理能力；CLI 可先執行 `codex plugin --help`、`codex plugin list` 與 `codex plugin marketplace list`。已安裝且來源相符時先驗證，避免重複安裝。同名來源指向不同 repo 時先釐清，不要覆蓋。
2. **新增來源，再安裝。** 使用下節指令；每一步成功才執行下一步。已有相符來源可略過新增。只有 UI 時使用其 plugin 管理介面；缺少自訂 marketplace 能力時回報限制與具體下一步。
3. **確認實際安裝位置與狀態。** 從安裝結果或 plugin 管理器取得套件路徑與版本，不要猜測快取位置。核對來源、套件名稱與三個 Skills，從安裝位置執行 preflight。
4. **解讀依賴檢查。** `pass` 是已通過的檢查，`managed` 表示留待平台受管環境提供或確認。整體 `pass` 不代表所有文件工具已可執行，也不代表完整盡調已通過實測。
5. **回報並結束安裝。** 說明名稱、版本、來源、安裝狀態、preflight 結果及待確認依賴。請使用者開新對話，貼上 README 的使用範例；新對話才能確認 Skills 是否已載入。安裝驗證不需要執行真實案件。

## 安裝指令

適用於支援 `codex plugin` 的 CLI，以下兩行不需要先 clone：

```sh
codex plugin marketplace add https://github.com/jabir95tsai/brian-vc
codex plugin add brian-vc@brian-vc-local
```

| 項目 | 由 repo manifest 定義的值 |
|---|---|
| Repository | `https://github.com/jabir95tsai/brian-vc` |
| Marketplace manifest | `.agents/plugins/marketplace.json` |
| Marketplace name | `brian-vc-local` |
| Plugin name | `brian-vc` |
| Plugin source | `./brian-vc`，相對於 repository root |
| Plugin manifest | `brian-vc/.codex-plugin/plugin.json` |
| Bundled Skills | `vc-quick-screen`、`prospectus-extractor`、`vc-investment-evaluator` |

若已有本機 clone，可在 repository root 執行 `codex plugin marketplace add .`，再執行相同的 plugin add 指令。Clone 本身不等於安裝，也不要把 repository root 當成 plugin root。

CLI 語法於 2026-09-06 以本機 `--help` 核對；不同版本請先讀其 help。Codex CLI 也可使用 `/plugins` 開啟 plugin browser。安裝後須開新對話／session，參見 [OpenAI Plugins 官方文件](https://learn.chatgpt.com/docs/plugins)。

## 驗證與執行依賴

使用 Python 3.12+。先切換到實際安裝的 plugin root（包含 `.codex-plugin/`、`scripts/`、`skills/` 的目錄），再執行：

```sh
python -X utf8 scripts/preflight.py --json
```

若只在檢查開發用 checkout，從 repository root 執行：

```sh
python -X utf8 brian-vc/scripts/preflight.py --json
```

兩者檢查的副本不同。來源 checkout 通過，不足以證明 Codex 已安裝或載入套件。

Codex 有受管 Documents、PDF、Spreadsheets、Presentations runtime 時優先使用；開始文件工作前載入並確認對應能力。新版 evaluator 的 XLSX／PPTX 使用受管 `@oai/artifact-tool`，單獨安裝 Python 套件不能取代它。

需要獨立 Python 執行環境時，在自有虛擬環境中，從 plugin root 執行：

```sh
python -m pip install -r requirements.txt
python -X utf8 scripts/preflight.py --strict-python-deps --json
```

`python` 應指向要使用的解譯器；部分 macOS／Linux 環境需改成 `python3`。嚴格檢查可確認 Python 模組可載入，仍需另行確認受管文件工具。CI 的 Python 3.12／3.13／3.14 測試平台為 Windows，其他平台須在目標環境驗證。

## 排錯

| 狀況 | 下一步 |
|---|---|
| 找不到 `codex` 或沒有 `plugin` 子命令 | 使用具 plugin 管理能力的 Codex；若已有圖形介面，確認其可新增自訂來源。不要改用其他 agent 的 plugin 格式。 |
| GitHub 來源讀不到 | 回報網路／存取錯誤；有可用 clone 時可改用本機 marketplace。 |
| Marketplace 名稱衝突 | 檢查既有來源是否為本 repo；保留使用者設定，釐清後再處理。 |
| 已安裝，但找不到 Skills | 開新對話，檢查 plugin 是否啟用，再確認三個 Skills 是否出現在可用清單。 |
| preflight 顯示 `fail` | 依該項目檢查套件完整性或依賴，修正後重跑。 |
| preflight 顯示 `managed` | 到平台受管 runtime 確認；採獨立 Python 時安裝 requirements 後跑嚴格檢查。 |
| Python 檢查通過，但不能產生 Excel／PPTX | 確認受管 `@oai/artifact-tool` 與對應文件 Skills；回報缺少的能力。 |

## 安裝完成的回報格式

```text
Plugin：brian-vc，版本 <實際版本>
來源：<實際 marketplace／repo>
安裝：<已確認／失敗與原因>
Preflight：<結果；尚未確認的 managed 項目>
Skills 載入：<新對話已確認／待新對話確認>
下一步：開新對話，附上簡報並說「幫我初篩這份簡報」。
```
