# 接回 vc-investment-evaluator Phase 0

## 觸發位置

DocumentIndex 命中台灣公開說明書後，在一般 Factbase 彙整與 ConflictResolver
之前呼叫 `$prospectus-extractor`。主控不得略讀整本 PDF。

## 派工輸入

```text
role: prospectus extractor
prospectus_pdf: 絕對路徑或已保存的官方 PDF 快照
case_id: ...
output_dir: ...
optional_sources: 查核財報、年報、data room 補件
```

執行端必讀本 Skill 的 `SKILL.md`、`section_map.md` 與
`case_data.schema.json`，並產生正式 5 個業務產物＋1 個 manifest。

## 驗收 payload

```text
status: success|failed|not_applicable
coverage: complete n / partial n / missing n / N/A n / 24
excel: 35/35, order=ok|failed
conflicts_unresolved: n
red_flags: 最多 3 項
missing_required: 項目清單
outputs: 六個絕對路徑
```

主控只接收此 payload 與 Factbase 路徑；Raw 全文留在輸出目錄。manifest
`validation_status` 不是 `success` 時，不得進入估值或 IRR。

## 衝突與 FactSheet

- 查核／核閱財報優先於官方公說；官方公說優先於 data room 自結與 Pitch Deck。
- extractor 把所有候選值與未解衝突留在 `case_data.conflicts`。
- evaluator 執行 ConflictResolver 後才產生 `FactSheet.json`。
- 公說通常沒有本輪 Term Sheet／估值／IRR；G 區保留並標缺，不補猜。

