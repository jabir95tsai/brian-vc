# Stage B Playbook — 文件讀取與公說萃取細節

主控執行 B1–B3 時遇到下列情境才讀本檔。Module 與閘門定義以
`pipeline_contract.md` 為準；本檔只負責文件讀取與公說萃取方法。

## 1. PDF 分流（Step B）

先用 `prospectus-extractor/scripts/slice_prospectus.py` 的
`scanned_pages.json` 判斷文字層，不依賴 `pdffonts`：

- **文字層過少（掃描型）**：用 `render_pdf_pages.py` 轉圖後交 Vision。
- **有文字層但表格是圖**：只 rasterize 該頁後交 Vision 讀表。

內容疑慮觸發項：圖片型表格（掃描 PDF）→OCR；內嵌圖表（Excel 圖非儲存格值）；隱藏工作表；多版本衝突；手寫/低品質掃描。

## 2. 大檔讀取截斷處理（強制）

Drive `read_file_content` 對 19MB 級整本公說會在 **~80k 字靜默截斷**（實測漏掉「肆財務概況/五年簡明/員工/產銷」等後半章節），且不報錯。處理順序：

1. 把官方 PDF 或使用者檔案保存為唯讀本機快照。
2. 用 `prospectus-extractor/scripts/slice_prospectus.py` 建實體頁碼索引，再逐章讀 `sections/`；不要依賴單次全文讀取。
3. B_GATE 前逐項確認章節「**真的命中**」而非假設讀全（完成清單逐章打勾）。

註：台灣公司若近年才首編合併報表（如 114 年度才首編），「五年合併簡明」可能本即只有 2 年（其前僅個體報表）——這是事實，不是缺漏，勿列補件。

## 3. Step B.5 派工 prompt（五段，照 prospectus-extractor 契約）

觸發：DocumentIndex 命中台灣「公開說明書／公說／prospectus」（含初次上市櫃、現金增資、員工新股各式）。只有 BP／Pitch Deck 或一般 data room 而無公說時，不觸發本 Skill。

執行方式：優先交給隔離的獨立 agent。無獨立 agent 時，由主控依相同契約順序執行，仍逐章落地、用完即棄（M-CTX-7）。

派工 prompt 五段：
1. **角色**＝公開說明書萃取子代理，讀 `prospectus-extractor/SKILL.md` 與其 `references/section_map.md` 執行。
2. **輸入**＝PDF 路徑／case_id／工作目錄 `/outputs/{case_id}_prospectus_work/`。
3. **輸出結構**＝該 Skill 的 5 個業務產物＋1 個 manifest。
4. **落地**＝`case_data.json`、Raw、Factbase、Coverage、35 分頁 Excel、Manifest。
5. **回傳（≤300 字）**＝status＋complete/partial/missing/N/A `/24`＋Excel `35/35`＋未解衝突數＋紅旗≤3＋六個路徑。

主控收回後：
- 直接使用 extractor 產生的 A–G `{case_id}_Factbase.md`；Raw 與 Excel 僅落地、不回主 context（M-CTX-1/3）。
- **銜接 Step C**：查核／核閱財報優先於官方公說；官方公說優先於 data room 自結與 Pitch Deck。
- **銜接 B4**：coverage 的「prospectus 不涵蓋」項（本輪條件/承銷定價/財務預測）自動進補件清單。
- **呼應 A0-2/A0-4**：本步即一手提取（從公說原文標頁碼）；務必抓**關係企業圖**供營運實體辨識。
