#!/usr/bin/env node
/** Build the evaluator Factbase and finance model from a frozen case payload. */

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const artifactEntry = require.resolve("@oai/artifact-tool", {
  paths: process.env.CODEX_NODE_MODULES ? [process.env.CODEX_NODE_MODULES] : undefined,
});
const { SpreadsheetFile, Workbook } = await import(pathToFileURL(artifactEntry).href);

const FACTBASE_SHEETS = [
  "0_說明", "1_增資條件", "2_公司基本", "3_股東董監", "4_團隊", "5_產品市場",
  "6_客戶供應商", "7A_IS明細", "7B_BS明細", "9_同業估值", "11_補件清單",
];
const MODEL_SHEETS = [
  "說明", "①假設參數", "②公司BP", "③獨立財測", "④財務預測", "⑤投報率分析", "⑥CapEx與資金接力",
];
const FACTBASE_EXTENSION_SHEETS = {
  cash_flow_history: "7C_CF明細",
  equity_changes: "7D_權益變動",
  debt_and_related_parties: "7E_借款關係人",
  significant_notes: "7F_附註重要",
};
const MODEL_EXTENSION_SHEETS = {
  operating_drivers: "⑦營運量價",
  debt_and_depreciation: "⑧債務折舊",
  working_capital_and_statements: "⑨營運資金三表",
  valuation_sensitivity: "⑩估值敏感度",
  model_checks: "⑪勾稽驗算",
};
const SCENARIOS = [
  ["conservative", "保守"],
  ["base", "基準"],
  ["upside", "積極"],
];

const C = {
  navy: "#17324D", navy2: "#244A68", blue: "#0000FF", green: "#008000",
  white: "#FFFFFF", black: "#000000", gray: "#5B6573", pale: "#EAF0F5",
  light: "#F6F8FA", yellow: "#FFF2CC", red: "#C00000", ok: "#E2F0D9",
};
const NUM = "#,##0.0;[Red](#,##0.0);-";
const COUNT = "#,##0;[Red](#,##0);-";
const PCT = "0.0%;[Red](0.0%);-";
const MULT = "0.0x;[Red](0.0x);-";

function argsFrom(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    if (!key?.startsWith("--") || argv[i + 1] === undefined) throw new Error(`invalid argument near ${key}`);
    out[key.slice(2)] = argv[i + 1];
  }
  for (const required of ["input", "output-dir"]) if (!out[required]) throw new Error(`--${required} is required`);
  return out;
}

function safeName(value) {
  return String(value || "case").replace(/[\\/:*?"<>|]/g, "_").replace(/\s+/g, "_");
}

function values2d(rows) {
  return rows.map((row) => row.map((v) => v ?? ""));
}

function isFiniteEvidence(value) {
  return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
}

function isVerifiedComparable(row) {
  if (!row || typeof row !== "object") return false;
  if (!String(row.company || "").trim() || !String(row.as_of || "").trim() || !String(row.source_url || "").trim()) return false;
  if (row.verification_status && row.verification_status !== "verified") return false;
  return ["revenue", "market_cap", "pe", "ev_revenue"].some((key) => isFiniteEvidence(row[key]));
}

function verifiedComparables(data) {
  return (data.comparables || []).filter(isVerifiedComparable);
}

function scenarioUsesDriverModel(data, key) {
  const explicit = data.independent_forecast?.scenario_methods?.[key];
  return explicit ? explicit === "driver_model" : data.independent_forecast?.method === "driver_model";
}

function writeRecordsSheet(sh, heading, subtitle, records) {
  title(sh, heading, subtitle, "J");
  const rows = Array.isArray(records) ? records : [];
  const keys = [...new Set(rows.flatMap((row) => Object.keys(row || {})))].slice(0, 10);
  const columns = keys.length ? keys : ["status"];
  const lastCol = String.fromCharCode(64 + columns.length);
  sh.getRange(`A4:${lastCol}4`).values = [columns];
  tableHeader(sh.getRange(`A4:${lastCol}4`));
  const values = rows.length ? rows.map((row) => columns.map((key) => row?.[key])) : [["尚待補件"]];
  sh.getRange(`A5:${lastCol}${4 + values.length}`).values = values2d(values);
  sh.getRange(`A4:${lastCol}${4 + values.length}`).format.wrapText = true;
  setWidths(sh, [[`A:${lastCol}`, 20]]);
}

function title(sheet, text, subtitle, lastCol = "H") {
  const t = sheet.getRange(`A1:${lastCol}1`);
  t.merge();
  t.values = [[text]];
  t.format = { fill: C.navy, font: { color: C.white, bold: true, size: 18 }, rowHeight: 30, verticalAlignment: "center" };
  const s = sheet.getRange(`A2:${lastCol}2`);
  s.merge();
  s.values = [[subtitle]];
  s.format = { fill: C.pale, font: { color: C.gray, italic: true, size: 10 }, wrapText: true, rowHeight: 28 };
}

function tableHeader(range) {
  range.format = {
    fill: C.navy2,
    font: { color: C.white, bold: true },
    wrapText: true,
    verticalAlignment: "center",
    rowHeight: 24,
    borders: { bottom: { color: C.navy, style: "thin" } },
  };
}

function section(sheet, row, text, lastCol = "H") {
  const r = sheet.getRange(`A${row}:${lastCol}${row}`);
  r.merge();
  r.values = [[text]];
  r.format = { fill: C.navy, font: { color: C.white, bold: true }, rowHeight: 22 };
}

function standardSheet(sheet, freezeRow = 3) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(freezeRow);
  sheet.getRange("A1:Z250").format.font = { name: "Aptos", size: 10, color: C.black };
}

function setWidths(sheet, widths) {
  for (const [range, width] of widths) sheet.getRange(range).format.columnWidth = width;
}

function sourceId(source, sourceMap) {
  if (!source) return "未提供";
  const match = [...sourceMap.entries()].find(([, src]) => src.name === source || src.url === source);
  return match ? match[0] : String(source);
}

function sourceMapFor(data) {
  const map = new Map();
  for (const [i, src] of (data.sources || []).entries()) map.set(src.id || `S${i + 1}`, src);
  return map;
}

function addSources(sheet, startRow, map, lastCol = "H") {
  section(sheet, startRow, "來源與稽核軌跡", lastCol);
  const headerRow = startRow + 1;
  const headers = [["Source ID", "項目", "資料日", "來源名稱", "URL／檔案", "備註"]];
  sheet.getRange(`A${headerRow}:F${headerRow}`).values = headers;
  tableHeader(sheet.getRange(`A${headerRow}:F${headerRow}`));
  const rows = [...map.entries()].map(([id, src]) => [id, src.item, src.as_of, src.name, src.url, src.notes]);
  if (rows.length) {
    sheet.getRange(`A${headerRow + 1}:F${headerRow + rows.length}`).values = values2d(rows);
    sheet.getRange(`A${headerRow + 1}:F${headerRow + rows.length}`).format.wrapText = true;
  }
}

async function exportAndPreview(wb, outputPath, previewDir, ranges) {
  const summary = await wb.inspect({ kind: "workbook,sheet", maxChars: 8000, tableMaxRows: 8, tableMaxCols: 10 });
  const formulaErrors = await wb.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 100 },
    summary: "formula error scan",
  });
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  if (previewDir) {
    await fs.mkdir(previewDir, { recursive: true });
    for (const [sheetName, range] of Object.entries(ranges)) {
      const preview = await wb.render({ sheetName, range, scale: 1, format: "png" });
      await fs.writeFile(path.join(previewDir, `${safeName(sheetName)}.png`), new Uint8Array(await preview.arrayBuffer()));
    }
  }
  const xlsx = await SpreadsheetFile.exportXlsx(wb);
  await xlsx.save(outputPath);
  return { output: outputPath, sheet_summary: summary, formula_errors: formulaErrors };
}

function buildFactbase(data) {
  const wb = Workbook.create();
  const extensionData = data.financial_extensions || {};
  const extensionNames = Object.entries(FACTBASE_EXTENSION_SHEETS)
    .filter(([key]) => Object.hasOwn(extensionData, key)).map(([, name]) => name);
  const sheets = Object.fromEntries([...FACTBASE_SHEETS, ...extensionNames].map((name) => [name, wb.worksheets.add(name)]));
  const src = sourceMapFor(data);
  for (const sheet of Object.values(sheets)) standardSheet(sheet);

  {
    const sh = sheets["0_說明"];
    title(sh, `${data.meta.company}｜精簡 Factbase`, `Case ${data.meta.case_id}｜資料截至 ${data.meta.as_of}｜${data.meta.currency}／${data.meta.unit}`, "H");
    sh.getRange("A4:B10").values = values2d([
      ["版本", data.meta.version || "v1"], ["分析人員", data.meta.analyst || "未提供"], ["模式", `${data.mode || "full"}｜無公開說明書之精簡版（11 分頁）`],
      ["資料狀態", "Data room 來源；不存在公說 35 分頁母版"], ["內容邊界", "事實底稿，不含投資結論"],
      ["公式色彩", "藍字＝可編輯假設；綠字＝跨表連結；黑字＝公式"], ["缺件處理", "見 11_補件清單；未提供欄位不得推測補值"],
    ]);
    sh.getRange("A4:A10").format = { fill: C.pale, font: { bold: true } };
    sh.getRange("B4:B10").format.wrapText = true;
    addSources(sh, 12, src, "H");
    setWidths(sh, [["A:A", 18], ["B:B", 42], ["C:C", 14], ["D:D", 25], ["E:E", 45], ["F:F", 36]]);
  }
  {
    const sh = sheets["1_增資條件"];
    title(sh, "增資條件", "所有金額單位依 0_說明；條件衝突須回到 ConflictLog", "F");
    const rows = [
      ["狀態", data.mode === "blocked" ? "BLOCKED｜不得以假設補交易條件" : data.mode || "full"],
      ["Blocked reason", data.deal.blocked_reason],
      ["輪次", data.deal.round], ["證券", data.deal.security], ["投資額", data.deal.investment], ["投前估值", data.deal.pre_money],
      ["投後估值", data.deal.post_money], ["每股價格", data.deal.price_per_share], ["投前股數", data.deal.shares_pre],
      ["新股數", data.deal.new_shares], ["ESOP 稀釋", data.deal.esop_dilution_pct], ["備註", data.deal.notes], ["來源", sourceId(data.deal.source, src)],
    ];
    sh.getRange(`A4:B${3 + rows.length}`).values = values2d(rows);
    sh.getRange(`A4:A${3 + rows.length}`).format = { fill: C.pale, font: { bold: true } };
    sh.getRange("B6:B11").format.numberFormat = NUM;
    sh.getRange("B12:B12").format.numberFormat = PCT;
    setWidths(sh, [["A:A", 22], ["B:B", 42]]);
  }
  {
    const sh = sheets["2_公司基本"];
    title(sh, "公司基本資料", "法律實體與營運實體需明確區分", "F");
    const c = data.company || {};
    const rows = [["公司名稱", data.meta.company], ["統一編號", c.tax_id], ["成立日", c.founded], ["地址", c.address], ["網站", c.website], ["業務描述", c.description]];
    sh.getRange(`A4:B${3 + rows.length}`).values = values2d(rows);
    sh.getRange(`A4:A${3 + rows.length}`).format = { fill: C.pale, font: { bold: true } };
    sh.getRange("B4:B12").format.wrapText = true;
    setWidths(sh, [["A:A", 20], ["B:B", 65]]);
  }
  {
    const sh = sheets["3_股東董監"];
    title(sh, "股東與董監", "持股比例以最新 cap table 為準；來源不一致時列入 ConflictLog", "F");
    sh.getRange("A4:D4").values = [["股東", "股數", "持股比例", "來源"]];
    tableHeader(sh.getRange("A4:D4"));
    const holders = (data.shareholders || []).map((r) => [r.name, r.shares, r.ownership_pct, sourceId(r.source, src)]);
    if (holders.length) sh.getRange(`A5:D${4 + holders.length}`).values = values2d(holders);
    sh.getRange(`B5:B${Math.max(5, 4 + holders.length)}`).format.numberFormat = COUNT;
    sh.getRange(`C5:C${Math.max(5, 4 + holders.length)}`).format.numberFormat = PCT;
    const dr = 7 + holders.length;
    section(sh, dr, "董監事", "F");
    sh.getRange(`A${dr + 1}:D${dr + 1}`).values = [["姓名", "職稱", "代表法人", "來源"]];
    tableHeader(sh.getRange(`A${dr + 1}:D${dr + 1}`));
    const directors = (data.directors || []).map((r) => [r.name, r.title, r.representative, sourceId(r.source, src)]);
    if (directors.length) sh.getRange(`A${dr + 2}:D${dr + 1 + directors.length}`).values = values2d(directors);
    setWidths(sh, [["A:A", 24], ["B:B", 18], ["C:C", 20], ["D:D", 28]]);
  }
  {
    const sh = sheets["4_團隊"];
    title(sh, "管理團隊", "學經歷須保留文件來源，不以口頭資訊代替", "F");
    sh.getRange("A4:D4").values = [["姓名", "職稱", "經歷", "來源"]];
    tableHeader(sh.getRange("A4:D4"));
    const rows = (data.team || []).map((r) => [r.name, r.title, r.experience, sourceId(r.source, src)]);
    if (rows.length) sh.getRange(`A5:D${4 + rows.length}`).values = values2d(rows);
    sh.getRange(`A5:D${Math.max(5, 4 + rows.length)}`).format.wrapText = true;
    setWidths(sh, [["A:A", 20], ["B:B", 16], ["C:C", 55], ["D:D", 28]]);
  }
  {
    const sh = sheets["5_產品市場"];
    title(sh, "產品與收益流", "收入占比需與財務明細可勾稽", "F");
    sh.getRange("A4:E4").values = [["產品／服務", "商業模式", "狀態", "收入占比", "來源"]];
    tableHeader(sh.getRange("A4:E4"));
    const rows = (data.products || []).map((r) => [r.name, r.model, r.status, r.revenue_share_pct, sourceId(r.source, src)]);
    if (rows.length) sh.getRange(`A5:E${4 + rows.length}`).values = values2d(rows);
    sh.getRange(`D5:D${Math.max(5, 4 + rows.length)}`).format.numberFormat = PCT;
    setWidths(sh, [["A:A", 28], ["B:B", 24], ["C:C", 16], ["D:D", 15], ["E:E", 28]]);
  }
  {
    const sh = sheets["6_客戶供應商"];
    title(sh, "客戶與供應商", "集中度與合約期間為核心風險欄位", "F");
    sh.getRange("A4:D4").values = [["客戶", "集中度", "合約到期", "來源"]];
    tableHeader(sh.getRange("A4:D4"));
    const customers = (data.customers || []).map((r) => [r.name, r.concentration_pct, r.contract_end, sourceId(r.source, src)]);
    if (customers.length) sh.getRange(`A5:D${4 + customers.length}`).values = values2d(customers);
    sh.getRange(`B5:B${Math.max(5, 4 + customers.length)}`).format.numberFormat = PCT;
    const sr = 7 + customers.length;
    section(sh, sr, "供應商", "F");
    sh.getRange(`A${sr + 1}:D${sr + 1}`).values = [["供應商", "集中度", "品項", "來源"]];
    tableHeader(sh.getRange(`A${sr + 1}:D${sr + 1}`));
    const suppliers = (data.suppliers || []).map((r) => [r.name, r.concentration_pct, r.item, sourceId(r.source, src)]);
    if (suppliers.length) sh.getRange(`A${sr + 2}:D${sr + 1 + suppliers.length}`).values = values2d(suppliers);
    sh.getRange(`B${sr + 2}:B${Math.max(sr + 2, sr + 1 + suppliers.length)}`).format.numberFormat = PCT;
    setWidths(sh, [["A:A", 24], ["B:B", 16], ["C:C", 25], ["D:D", 28]]);
  }
  {
    const sh = sheets["7A_IS明細"];
    title(sh, "損益表歷史明細", "歷史實績；獨立估計另見財務模型", "H");
    sh.getRange("A4:G4").values = [["年度", "營收", "銷貨成本", "營業費用", "淨利", "CapEx", "來源"]];
    tableHeader(sh.getRange("A4:G4"));
    const rows = data.financial_history.map((r) => [r.year, r.revenue, r.cogs, r.opex, r.net_income, r.capex, sourceId(r.source, src)]);
    sh.getRange(`A5:G${4 + rows.length}`).values = values2d(rows);
    sh.getRange(`B5:F${4 + rows.length}`).format.numberFormat = NUM;
    setWidths(sh, [["A:A", 12], ["B:F", 16], ["G:G", 30]]);
  }
  {
    const sh = sheets["7B_BS明細"];
    title(sh, "資產負債表歷史明細", "資產＝負債＋權益之差異需進 ConflictLog", "H");
    sh.getRange("A4:G4").values = [["年度", "現金", "負債借款", "總資產", "總負債", "權益", "來源"]];
    tableHeader(sh.getRange("A4:G4"));
    const rows = data.financial_history.map((r) => [r.year, r.cash, r.debt, r.total_assets, r.total_liabilities, r.equity, sourceId(r.source, src)]);
    sh.getRange(`A5:G${4 + rows.length}`).values = values2d(rows);
    sh.getRange(`B5:F${4 + rows.length}`).format.numberFormat = NUM;
    setWidths(sh, [["A:A", 12], ["B:F", 16], ["G:G", 30]]);
  }
  {
    const sh = sheets["9_同業估值"];
    title(sh, "同業估值", "官方來源優先；非官方值須在來源欄明確標記", "I");
    sh.getRange("A4:H4").values = [["公司", "代號", "營收", "市值", "P/E", "EV/Revenue", "資料日", "來源 URL"]];
    tableHeader(sh.getRange("A4:H4"));
    const rows = verifiedComparables(data).map((r) => [r.company, r.ticker, r.revenue, r.market_cap, r.pe, r.ev_revenue, r.as_of, r.source_url]);
    if (rows.length) sh.getRange(`A5:H${4 + rows.length}`).values = values2d(rows);
    sh.getRange(`C5:D${Math.max(5, 4 + rows.length)}`).format.numberFormat = NUM;
    sh.getRange(`E5:F${Math.max(5, 4 + rows.length)}`).format.numberFormat = MULT;
    sh.getRange(`A5:H${Math.max(5, 4 + rows.length)}`).format.wrapText = true;
    setWidths(sh, [["A:A", 22], ["B:B", 12], ["C:D", 16], ["E:F", 14], ["G:G", 14], ["H:H", 45]]);
  }
  {
    const sh = sheets["11_補件清單"];
    title(sh, "補件清單", "P0 未解且影響估值或財務誠信時，案件不得宣稱完整", "G");
    sh.getRange("A4:F4").values = [["優先級", "缺件", "理由", "負責人", "期限", "狀態"]];
    tableHeader(sh.getRange("A4:F4"));
    const rows = (data.missing_items || []).map((r) => [r.priority, r.item, r.reason, r.owner, r.due, r.status]);
    if (rows.length) sh.getRange(`A5:F${4 + rows.length}`).values = values2d(rows);
    sh.getRange(`A5:F${Math.max(5, 4 + rows.length)}`).format.wrapText = true;
    setWidths(sh, [["A:A", 12], ["B:B", 34], ["C:C", 45], ["D:D", 16], ["E:E", 15], ["F:F", 14]]);
  }
  for (const [key, sheetName] of Object.entries(FACTBASE_EXTENSION_SHEETS)) {
    if (!sheets[sheetName]) continue;
    writeRecordsSheet(sheets[sheetName], sheetName, "案例提供的財務延伸明細；欄位由 frozen payload 決定", extensionData[key]);
  }
  return wb;
}

function buildBlockedFinancialModel(data) {
  const wb = Workbook.create();
  const extensionData = data.financial_extensions || {};
  const extensionNames = Object.entries(MODEL_EXTENSION_SHEETS)
    .filter(([key]) => Object.hasOwn(extensionData, key)).map(([, name]) => name);
  const sheets = Object.fromEntries([...MODEL_SHEETS, ...extensionNames].map((name) => [name, wb.worksheets.add(name)]));
  for (const sheet of Object.values(sheets)) standardSheet(sheet, 4);
  const reason = data.deal.blocked_reason || "現行交易條件未揭露";

  {
    const sh = sheets["說明"];
    title(sh, `${data.meta.company}｜財務模型 BLOCKED`, `Case ${data.meta.case_id}｜事實資料保留；不得以假設補本輪條件`, "H");
    sh.getRange("A4:B11").values = values2d([
      ["模型狀態", "BLOCKED AS DESIGNED"], ["原因", reason], ["事實底稿", "已產出，歷史財務與缺件仍可查閱"],
      ["獨立財測", "BLOCKED｜未建立"], ["估值", "BLOCKED｜未計算"], ["IRR／Return Multiple", "BLOCKED｜未計算"],
      ["解除條件", "取得現行 Term Sheet，或由使用者明示可計算的假設交易條件"], ["證據邊界", "公司 BP 可保留作主張，不升格為獨立估計"],
    ]);
    sh.getRange("A4:A11").format = { fill: C.pale, font: { bold: true } };
    sh.getRange("B4:B11").format.wrapText = true;
    section(sh, 14, "Checks", "H");
    sh.getRange("A15:F16").values = values2d([
      ["檢查", "Actual", "Expected", "Difference", "Tolerance", "Status"],
      ["未揭露交易條件時拒絕建立報酬模型", "blocked", "blocked", "—", "—", "BLOCKED AS DESIGNED"],
    ]);
    tableHeader(sh.getRange("A15:F15"));
    sh.getRange("F16").format = { font: { bold: true }, fill: C.yellow };
    setWidths(sh, [["A:A", 34], ["B:E", 22], ["F:F", 26]]);
  }
  {
    const sh = sheets["①假設參數"];
    title(sh, "① 假設參數｜BLOCKED", "交易條件不存在時保留空白，不以 0 或代理值替代", "E");
    sh.getRange("A4:D10").values = values2d([
      ["欄位", "值", "狀態", "來源／下一步"], ["輪次", data.deal.round, "已知描述", data.deal.source],
      ["投資額", "", "BLOCKED", reason], ["投前估值", "", "BLOCKED", reason], ["投後估值", "", "BLOCKED", reason],
      ["獨立財測假設", "", "BLOCKED", "不得從公司 BP 反推"], ["Hurdle", data.assumptions.hurdle_rate, "Fund profile only", "不代表可計算 IRR"],
    ]);
    tableHeader(sh.getRange("A4:D4"));
    sh.getRange("A5:D10").format.wrapText = true;
    setWidths(sh, [["A:A", 24], ["B:B", 22], ["C:C", 22], ["D:D", 56]]);
  }
  {
    const sh = sheets["②公司BP"];
    title(sh, "② 公司 BP｜只保留公司主張", "本頁不等於獨立財測；來源、口徑與年份需逐列保留", "G");
    const rows = (data.bp_forecast || []).map((r) => [r.year, r.revenue, r.gross_margin, r.opex, r.capex, r.source]);
    sh.getRange("A4:F4").values = [["年度", "營收", "毛利率", "營業費用", "CapEx", "來源"]];
    tableHeader(sh.getRange("A4:F4"));
    if (rows.length) sh.getRange(`A5:F${4 + rows.length}`).values = values2d(rows);
    else sh.getRange("A5:F5").values = [["尚未提供", "", "", "", "", ""]];
    sh.getRange(`B5:B${Math.max(5, 4 + rows.length)}`).format.numberFormat = NUM;
    sh.getRange(`C5:C${Math.max(5, 4 + rows.length)}`).format.numberFormat = PCT;
    sh.getRange(`D5:E${Math.max(5, 4 + rows.length)}`).format.numberFormat = NUM;
    setWidths(sh, [["A:A", 14], ["B:E", 18], ["F:F", 42]]);
  }
  for (const name of ["③獨立財測", "④財務預測", "⑥CapEx與資金接力"]) {
    const sh = sheets[name];
    title(sh, `${name}｜BLOCKED`, "無可用獨立財測假設；歷史財務仍在 Factbase 完整呈現", "G");
    sh.getRange("A4:D5").values = values2d([
      ["狀態", "原因", "不得替代", "解除條件"],
      ["BLOCKED", reason, "公司 BP／0 值／任意成長率", "取得現行 Term Sheet 與可驗證量價假設"],
    ]);
    tableHeader(sh.getRange("A4:D4"));
    sh.getRange("A5:D5").format.wrapText = true;
    setWidths(sh, [["A:A", 18], ["B:B", 48], ["C:C", 38], ["D:D", 48]]);
  }
  {
    const sh = sheets["⑤投報率分析"];
    title(sh, "⑤ 投報率分析｜BLOCKED", "IRR 與 Return Multiple 均未計算；空白是證據狀態，不是 0", "F");
    section(sh, 4, "IRR 矩陣｜BLOCKED", "F");
    sh.getRange("A5:D6").values = values2d([["狀態", "原因", "輸入缺口", "解除條件"], ["BLOCKED", reason, "投資額／投後估值／證券權利", "取得現行 Term Sheet"]]);
    tableHeader(sh.getRange("A5:D5"));
    section(sh, 9, "Return Multiple 矩陣｜BLOCKED", "F");
    sh.getRange("A10:D11").values = values2d([["狀態", "原因", "輸入缺口", "解除條件"], ["BLOCKED", reason, "持股／退出估值／稀釋", "取得現行 Term Sheet"]]);
    tableHeader(sh.getRange("A10:D10"));
    sh.getRange("A5:D11").format.wrapText = true;
    setWidths(sh, [["A:A", 18], ["B:B", 52], ["C:C", 40], ["D:D", 36]]);
  }
  for (const [key, sheetName] of Object.entries(MODEL_EXTENSION_SHEETS)) {
    if (!sheets[sheetName]) continue;
    writeRecordsSheet(sheets[sheetName], sheetName, "證據延伸表保留；blocked 只停止不可計算的預測與報酬", extensionData[key]);
  }
  return wb;
}

function buildFinancialModel(data) {
  if (data.mode === "blocked") return buildBlockedFinancialModel(data);
  const wb = Workbook.create();
  const extensionData = data.financial_extensions || {};
  const extensionNames = Object.entries(MODEL_EXTENSION_SHEETS)
    .filter(([key]) => Object.hasOwn(extensionData, key)).map(([, name]) => name);
  const sheets = Object.fromEntries([...MODEL_SHEETS, ...extensionNames].map((name) => [name, wb.worksheets.add(name)]));
  for (const sheet of Object.values(sheets)) standardSheet(sheet, 4);
  const years = data.assumptions.forecast_years;
  if (years.length !== 5) throw new Error("financial model currently requires exactly five forecast years");
  const history = [...data.financial_history].sort((a, b) => a.year - b.year);
  const latest = history[history.length - 1];

  {
    const sh = sheets["說明"];
    title(sh, `${data.meta.company}｜獨立財務模型`, `Case ${data.meta.case_id}｜${data.meta.currency}／${data.meta.unit}｜資料截至 ${data.meta.as_of}`, "H");
    sh.getRange("A4:B12").values = values2d([
      ["版本", data.meta.version || "v1"], ["建立者", data.meta.analyst || "Brian VC evaluator"], ["期間", `${years[0]}–${years[4]}E（年度）`],
      ["情境", "保守／基準／積極"], ["預測標籤", "獨立估計，非公司財測"], ["估值法", "退出 Revenue multiple（簡化情境估值）"],
      ["色彩慣例", "藍字＝可編輯假設；綠字＝跨表連結；黑字＝公式"], ["公式邊界", "未建立完整三表；各情境 driver／ratio 方法與 FCF proxy 限制須分開揭露"],
      ["模型狀態", "見下方 Checks；任何 WARN 項須在投審前人工複核"],
    ]);
    sh.getRange("A4:A12").format = { fill: C.pale, font: { bold: true } };
    sh.getRange("B4:B12").format.wrapText = true;
    section(sh, 14, "Checks", "H");
    sh.getRange("A15:F15").values = [["檢查", "Actual", "Expected", "Difference", "Tolerance", "Status"]];
    tableHeader(sh.getRange("A15:F15"));
    sh.getRange("A16:A20").values = [["投後估值＝投前＋投資"], ["持股比例 ≤ 100%"], ["基準毛利率範圍"], ["基準 FCF bridge"], ["模型整體狀態"]];
    sh.getRange("B16:B19").formulas = [["='①假設參數'!B8-'①假設參數'!B7-'①假設參數'!B6"], ["='⑤投報率分析'!B7"], ["='①假設參數'!C14"], ["='④財務預測'!G17-'④財務預測'!G18-'④財務預測'!G19"]];
    sh.getRange("C16:C19").values = [[0], [1], [0.46], [0]];
    sh.getRange("D16:D19").formulas = [["=B16-C16"], ["=B17-C17"], ["=B18-C18"], ["=B19-C19"]];
    sh.getRange("E16:E19").values = [[0.001], [0], [0.15], [0.001]];
    sh.getRange("F16:F19").formulas = [["=IF(ABS(D16)<=E16,\"OK\",\"WARN\")"], ["=IF(B17<=C17,\"OK\",\"WARN\")"], ["=IF(AND(B18>=0.2,B18<=0.8),\"OK\",\"WARN\")"], ["=IF(ABS(D19)<=E19,\"OK\",\"WARN\")"]];
    sh.getRange("F20").formulas = [["=IF(COUNTIF(F16:F19,\"WARN\")=0,\"OK\",\"WARN\")"]];
    sh.getRange("B16:B19").format.font = { color: C.green };
    sh.getRange("B16:E19").format.numberFormat = "0.0";
    sh.getRange("F16:F20").format = { font: { bold: true }, fill: C.ok };
    setWidths(sh, [["A:A", 28], ["B:E", 18], ["F:F", 16], ["G:H", 12]]);
  }
  {
    const sh = sheets["①假設參數"];
    title(sh, "① 假設參數", "所有藍字為可編輯輸入；不得把商業假設硬寫進公式", "E");
    sh.getRange("A4:D4").values = [["交易與共通假設", "值", "單位", "來源／Owner"]];
    tableHeader(sh.getRange("A4:D4"));
    sh.getRange("A5:D11").values = values2d([
      ["最新實績年度", latest.year, "年度", latest.source], ["投資額", data.deal.investment, data.meta.unit, data.deal.source],
      ["投前估值", data.deal.pre_money, data.meta.unit, data.deal.source], ["投後估值", data.deal.post_money, data.meta.unit, data.deal.source],
      ["持有年數", data.assumptions.holding_years, "年", "GP／Fund Profile"], ["Hurdle rate", data.assumptions.hurdle_rate, "%", "Fund Profile"],
      ["最新實績營收", latest.revenue, data.meta.unit, latest.source],
    ]);
    sh.getRange("B5:B11").format = { font: { color: C.blue }, fill: C.yellow };
    sh.getRange("B6:B8").format.numberFormat = NUM;
    sh.getRange("B10:B10").format.numberFormat = PCT;
    sh.getRange("A13:D13").values = [["情境假設", "保守", "基準", "積極"]];
    tableHeader(sh.getRange("A13:D13"));
    const metricRows = [
      ["revenue_growth", "營收年增率", PCT], ["gross_margin", "毛利率", PCT], ["opex_ratio", "營業費用率", PCT],
      ["tax_rate", "稅率", PCT], ["capex_ratio", "CapEx／營收", PCT], ["exit_revenue_multiple", "退出 Revenue multiple", MULT],
    ];
    sh.getRange("A14:A19").values = metricRows.map((r) => [r[1]]);
    for (let c = 0; c < SCENARIOS.length; c++) {
      const col = String.fromCharCode(66 + c);
      sh.getRange(`${col}14:${col}19`).values = metricRows.map((r) => [data.assumptions.scenarios[SCENARIOS[c][0]][r[0]]]);
      sh.getRange(`${col}14:${col}19`).format = { font: { color: C.blue }, fill: C.yellow };
    }
    for (let r = 0; r < metricRows.length; r++) sh.getRange(`B${14 + r}:D${14 + r}`).format.numberFormat = metricRows[r][2];
    sh.getRange("A21:D23").values = values2d([
      ["模型聲明", "所有情境均為獨立估計，非公司財測", "", ""],
      ["收入模型", SCENARIOS.map(([key, label]) => `${label}：${scenarioUsesDriverModel(data, key) ? "driver model" : "ratio proxy"}`).join("；"), "", ""],
      ["退出估值", "退出年營收 × Revenue multiple；投資人持股＝投資額／投後估值", "", ""],
    ]);
    sh.getRange("B21:D23").merge(true);
    sh.getRange("A21:D23").format.wrapText = true;
    setWidths(sh, [["A:A", 30], ["B:D", 20], ["E:E", 18]]);
  }
  {
    const sh = sheets["②公司BP"];
    title(sh, "② 公司 BP", "公司提供之預測；只作比較基準，不視為獨立驗證", "G");
    sh.getRange("A4:F4").values = [["項目", ...years]];
    tableHeader(sh.getRange("A4:F4"));
    const bpByYear = new Map((data.bp_forecast || []).map((r) => [r.year, r]));
    sh.getRange("A5:A9").values = [["營收"], ["毛利率"], ["營業費用"], ["CapEx"], ["來源"]];
    sh.getRange("B5:F8").values = values2d([
      years.map((y) => bpByYear.get(y)?.revenue), years.map((y) => bpByYear.get(y)?.gross_margin),
      years.map((y) => bpByYear.get(y)?.opex), years.map((y) => bpByYear.get(y)?.capex),
    ]);
    const bpSources = [...new Set(years.map((y) => bpByYear.get(y)?.source).filter(Boolean))];
    sh.getRange("B9:F9").merge(true);
    sh.getRange("B9").values = [[bpSources.length ? bpSources.join("；") : "未提供"]];
    sh.getRange("B5:F9").format.font = { color: C.blue };
    sh.getRange("B9:F9").format.wrapText = true;
    sh.getRange("B5:F5").format.numberFormat = NUM;
    sh.getRange("B6:F6").format.numberFormat = PCT;
    sh.getRange("B7:F8").format.numberFormat = NUM;
    setWidths(sh, [["A:A", 24], ["B:F", 16], ["G:G", 14]]);
  }
  {
    const sh = sheets["③獨立財測"];
    title(sh, "③ 獨立財測", `獨立估計，非公司財測；${SCENARIOS.map(([key, label]) => `${label}=${scenarioUsesDriverModel(data, key) ? "driver" : "ratio proxy"}`).join("／")}`, "F");
    const assumptionCols = { conservative: "B", base: "C", upside: "D" };
    for (let s = 0; s < SCENARIOS.length; s++) {
      const [key, label] = SCENARIOS[s];
      const start = 4 + s * 14;
      section(sh, start, `${label}情境｜獨立估計，非公司財測`, "F");
      sh.getRange(`A${start + 1}:F${start + 1}`).values = [["項目", ...years]];
      tableHeader(sh.getRange(`A${start + 1}:F${start + 1}`));
      sh.getRange(`A${start + 2}:A${start + 10}`).values = [["營收"], ["成長率"], ["毛利"], ["毛利率"], ["營業費用"], ["EBIT"], ["稅負"], ["淨利"], ["CapEx"]];
      const ac = assumptionCols[key];
      const rows = [];
      const firstRevenue = `='①假設參數'!$B$11*(1+'①假設參數'!$${ac}$14)`;
      rows.push([firstRevenue, "=B" + (start + 2) + "*(1+'①假設參數'!$" + ac + "$14)", "=C" + (start + 2) + "*(1+'①假設參數'!$" + ac + "$14)", "=D" + (start + 2) + "*(1+'①假設參數'!$" + ac + "$14)", "=E" + (start + 2) + "*(1+'①假設參數'!$" + ac + "$14)"]);
      rows.push(Array(5).fill(`='①假設參數'!$${ac}$14`));
      rows.push(["=B" + (start + 2) + "*'①假設參數'!$" + ac + "$15", "=C" + (start + 2) + "*'①假設參數'!$" + ac + "$15", "=D" + (start + 2) + "*'①假設參數'!$" + ac + "$15", "=E" + (start + 2) + "*'①假設參數'!$" + ac + "$15", "=F" + (start + 2) + "*'①假設參數'!$" + ac + "$15"]);
      rows.push(Array(5).fill(`='①假設參數'!$${ac}$15`));
      rows.push(["=B" + (start + 2) + "*'①假設參數'!$" + ac + "$16", "=C" + (start + 2) + "*'①假設參數'!$" + ac + "$16", "=D" + (start + 2) + "*'①假設參數'!$" + ac + "$16", "=E" + (start + 2) + "*'①假設參數'!$" + ac + "$16", "=F" + (start + 2) + "*'①假設參數'!$" + ac + "$16"]);
      rows.push(["=B" + (start + 4) + "-B" + (start + 6), "=C" + (start + 4) + "-C" + (start + 6), "=D" + (start + 4) + "-D" + (start + 6), "=E" + (start + 4) + "-E" + (start + 6), "=F" + (start + 4) + "-F" + (start + 6)]);
      rows.push(["=MAX(0,B" + (start + 7) + "*'①假設參數'!$" + ac + "$17)", "=MAX(0,C" + (start + 7) + "*'①假設參數'!$" + ac + "$17)", "=MAX(0,D" + (start + 7) + "*'①假設參數'!$" + ac + "$17)", "=MAX(0,E" + (start + 7) + "*'①假設參數'!$" + ac + "$17)", "=MAX(0,F" + (start + 7) + "*'①假設參數'!$" + ac + "$17)"]);
      rows.push(["=B" + (start + 7) + "-B" + (start + 8), "=C" + (start + 7) + "-C" + (start + 8), "=D" + (start + 7) + "-D" + (start + 8), "=E" + (start + 7) + "-E" + (start + 8), "=F" + (start + 7) + "-F" + (start + 8)]);
      rows.push(["=B" + (start + 2) + "*'①假設參數'!$" + ac + "$18", "=C" + (start + 2) + "*'①假設參數'!$" + ac + "$18", "=D" + (start + 2) + "*'①假設參數'!$" + ac + "$18", "=E" + (start + 2) + "*'①假設參數'!$" + ac + "$18", "=F" + (start + 2) + "*'①假設參數'!$" + ac + "$18"]);
      sh.getRange(`B${start + 2}:F${start + 10}`).formulas = rows;
      sh.getRange(`B${start + 2}:F${start + 10}`).format.font = { color: C.green };
      if (scenarioUsesDriverModel(data, key)) {
        const explicit = data.independent_forecast.scenarios[key];
        if (!Array.isArray(explicit) || explicit.length !== years.length) throw new Error(`driver_model ${key} must provide one row per forecast year`);
        const priorRevenue = [latest.revenue, ...explicit.slice(0, -1).map((r) => r.revenue)];
        sh.getRange(`B${start + 2}:F${start + 10}`).values = values2d([
          explicit.map((r) => r.revenue),
          explicit.map((r, i) => priorRevenue[i] ? r.revenue / priorRevenue[i] - 1 : 0),
          explicit.map((r) => r.gross_profit),
          explicit.map((r) => r.gross_margin),
          explicit.map((r) => r.opex),
          explicit.map((r) => r.ebit),
          explicit.map((r) => r.tax),
          explicit.map((r) => r.net_income),
          explicit.map((r) => r.capex),
        ]);
        sh.getRange(`B${start + 2}:F${start + 10}`).format.font = { color: C.blue };
      }
      sh.getRange(`B${start + 2}:F${start + 2}`).format.numberFormat = NUM;
      sh.getRange(`B${start + 3}:F${start + 3}`).format.numberFormat = PCT;
      sh.getRange(`B${start + 4}:F${start + 4}`).format.numberFormat = NUM;
      sh.getRange(`B${start + 5}:F${start + 5}`).format.numberFormat = PCT;
      sh.getRange(`B${start + 6}:F${start + 10}`).format.numberFormat = NUM;
    }
    setWidths(sh, [["A:A", 24], ["B:F", 16]]);
  }
  {
    const sh = sheets["④財務預測"];
    title(sh, "④ 財務預測｜基準情境", "由 ③獨立財測 跨表連結；獨立估計，非公司財測", "G");
    sh.getRange("A4:F4").values = [["項目", ...years]];
    tableHeader(sh.getRange("A4:F4"));
    sh.getRange("A5:A12").values = [["營收"], ["成長率"], ["毛利"], ["毛利率"], ["營業費用"], ["EBIT"], ["淨利"], ["CapEx"]];
    const sourceRows = [20, 21, 22, 23, 24, 25, 27, 28];
    for (let i = 0; i < sourceRows.length; i++) {
      sh.getRange(`B${5 + i}:F${5 + i}`).formulas = [[..."BCDEF"].map((col) => `='③獨立財測'!${col}${sourceRows[i]}`)];
      sh.getRange(`B${5 + i}:F${5 + i}`).format.font = { color: C.green };
    }
    sh.getRange("B5:F5").format.numberFormat = NUM;
    sh.getRange("B6:F6").format.numberFormat = PCT;
    sh.getRange("B7:F7").format.numberFormat = NUM;
    sh.getRange("B8:F8").format.numberFormat = PCT;
    sh.getRange("B9:F12").format.numberFormat = NUM;
    section(sh, 14, "FCF bridge 與 Checks", "G");
    sh.getRange("A15:F15").values = [["項目", ...years]];
    tableHeader(sh.getRange("A15:F15"));
    sh.getRange("A16:A21").values = [["淨利"], ["CapEx"], ["FCF proxy"], ["FCF 重算"], ["Difference"], ["Status"]];
    sh.getRange("B16:F17").formulas = [["=B11", "=C11", "=D11", "=E11", "=F11"], ["=B12", "=C12", "=D12", "=E12", "=F12"]];
    sh.getRange("B18:F18").formulas = [["=B16-B17", "=C16-C17", "=D16-D17", "=E16-E17", "=F16-F17"]];
    sh.getRange("B19:F19").formulas = [["=B11-B12", "=C11-C12", "=D11-D12", "=E11-E12", "=F11-F12"]];
    sh.getRange("B20:F20").formulas = [["=B18-B19", "=C18-C19", "=D18-D19", "=E18-E19", "=F18-F19"]];
    sh.getRange("B21:F21").formulas = [["=IF(ABS(B20)<=0.001,\"OK\",\"WARN\")", "=IF(ABS(C20)<=0.001,\"OK\",\"WARN\")", "=IF(ABS(D20)<=0.001,\"OK\",\"WARN\")", "=IF(ABS(E20)<=0.001,\"OK\",\"WARN\")", "=IF(ABS(F20)<=0.001,\"OK\",\"WARN\")"]];
    sh.getRange("B16:F17").format.font = { color: C.green };
    sh.getRange("B16:F20").format.numberFormat = NUM;
    sh.getRange("B21:F21").format = { fill: C.ok, font: { bold: true } };
    setWidths(sh, [["A:A", 24], ["B:F", 16], ["G:G", 14]]);
  }
  {
    const sh = sheets["⑤投報率分析"];
    title(sh, "⑤ 投報率分析", "IRR／Return Multiple 雙矩陣由 scripts/irr_matrix.py 產生；估值與公式可追溯", "F");
    sh.getRange("A4:C4").values = [["核心輸入／輸出", "值", "說明"]];
    tableHeader(sh.getRange("A4:C4"));
    sh.getRange("A5:A14").values = [["投資額"], ["投後估值"], ["投資人持股"], ["持有年數"], ["Hurdle"], ["退出年營收（基準）"], ["退出倍數（基準）"], ["退出估值"], ["預估回收"], ["Return multiple"]];
    sh.getRange("B5:B11").formulas = [["='①假設參數'!B6"], ["='①假設參數'!B8"], ["=B5/B6"], ["='①假設參數'!B9"], ["='①假設參數'!B10"], ["='④財務預測'!F5"], ["='①假設參數'!C19"]];
    sh.getRange("B12:B14").formulas = [["=B10*B11"], ["=B12*B7"], ["=B13/B5"]];
    sh.getRange("C5:C14").values = values2d([[data.meta.unit], [data.meta.unit], ["投資額／投後估值"], ["年"], ["Fund Profile"], ["獨立估計"], ["Revenue multiple"], [data.meta.unit], [data.meta.unit], ["x"]]);
    sh.getRange("B5:B14").format.font = { color: C.green };
    sh.getRange("B5:B6").format.numberFormat = NUM;
    sh.getRange("B7:B7").format.numberFormat = PCT;
    sh.getRange("B9:B9").format.numberFormat = PCT;
    sh.getRange("B10:B10").format.numberFormat = NUM;
    sh.getRange("B11:B11").format.numberFormat = MULT;
    sh.getRange("B12:B13").format.numberFormat = NUM;
    sh.getRange("B14:B14").format.numberFormat = MULT;
    const matrix = data.return_matrix;
    if (!matrix || matrix.generator !== "scripts/irr_matrix.py") throw new Error("prepared input must include return_matrix from scripts/irr_matrix.py");
    section(sh, 16, "IRR 矩陣", "F");
    const irrRows = matrix.irr_rows;
    sh.getRange(`A17:D${16 + irrRows.length}`).values = values2d(irrRows);
    tableHeader(sh.getRange("A17:D17"));
    section(sh, 25, "Return Multiple 矩陣", "F");
    const multRows = matrix.multiple_rows;
    sh.getRange(`A26:D${25 + multRows.length}`).values = values2d(multRows);
    tableHeader(sh.getRange("A26:D26"));
    sh.getRange("A34:F35").values = [["矩陣口徑", `Stake ${matrix.stake_pct.toFixed(1)}%；退出估值欄為保守／基準／積極 multiples 對投後估值之情境值。`, "", "", "", ""], ["注意", "矩陣是獨立情境測試，不等同投資建議。正式案須由 CitationTable 與 D2 驗證退出倍數。", "", "", "", ""]];
    sh.getRange("B34:F35").merge(true);
    sh.getRange("A34:F35").format.wrapText = true;
    setWidths(sh, [["A:A", 28], ["B:D", 20], ["E:F", 16]]);
  }
  {
    const sh = sheets["⑥CapEx與資金接力"];
    title(sh, "⑥ CapEx 與資金接力", "以基準情境 FCF proxy 推估額外資金需求；不含完整營運資金與融資現金流", "G");
    sh.getRange("A4:F4").values = [["項目", ...years]];
    tableHeader(sh.getRange("A4:F4"));
    sh.getRange("A5:A10").values = [["CapEx"], ["淨利"], ["FCF proxy"], ["當年資金缺口"], ["累積資金缺口"], ["Runway 註記"]];
    sh.getRange("B5:F5").formulas = [["='④財務預測'!B12", "='④財務預測'!C12", "='④財務預測'!D12", "='④財務預測'!E12", "='④財務預測'!F12"]];
    sh.getRange("B6:F6").formulas = [["='④財務預測'!B11", "='④財務預測'!C11", "='④財務預測'!D11", "='④財務預測'!E11", "='④財務預測'!F11"]];
    sh.getRange("B7:F7").formulas = [["=B6-B5", "=C6-C5", "=D6-D5", "=E6-E5", "=F6-F5"]];
    sh.getRange("B8:F8").formulas = [["=MAX(0,-B7)", "=MAX(0,-C7)", "=MAX(0,-D7)", "=MAX(0,-E7)", "=MAX(0,-F7)"]];
    sh.getRange("B9:F9").formulas = [["=B8", "=B9+C8", "=C9+D8", "=D9+E8", "=E9+F8"]];
    sh.getRange("B10:F10").formulas = [["=IF(B8>0,\"需資金接力\",\"自給\")", "=IF(C8>0,\"需資金接力\",\"自給\")", "=IF(D8>0,\"需資金接力\",\"自給\")", "=IF(E8>0,\"需資金接力\",\"自給\")", "=IF(F8>0,\"需資金接力\",\"自給\")"]];
    sh.getRange("B5:F6").format.font = { color: C.green };
    sh.getRange("B5:F9").format.numberFormat = NUM;
    section(sh, 12, "限制與後續", "G");
    sh.getRange("A13:F15").values = values2d([
      ["限制", "尚未納入應收帳款、存貨、應付帳款與融資條件，不能視為完整 cash runway。", "", "", "", ""],
      ["後續", "取得月度現金流與營運資金週轉後，以完整 CF／資金水位取代 FCF proxy。", "", "", "", ""],
      ["判讀", "正數缺口代表需外部融資或降低 CapEx；0 不代表流動性風險已排除。", "", "", "", ""],
    ]);
    sh.getRange("B13:F15").merge(true);
    sh.getRange("A13:F15").format.wrapText = true;
    setWidths(sh, [["A:A", 26], ["B:F", 18], ["G:G", 12]]);
  }
  for (const [key, sheetName] of Object.entries(MODEL_EXTENSION_SHEETS)) {
    if (!sheets[sheetName]) continue;
    writeRecordsSheet(sheets[sheetName], sheetName, "舊版深度功能的 schema-driven 延伸表；未提供資料時不推測", extensionData[key]);
  }
  return wb;
}

async function main() {
  const args = argsFrom(process.argv.slice(2));
  const input = JSON.parse(await fs.readFile(path.resolve(args.input), "utf8"));
  const outputDir = path.resolve(args["output-dir"]);
  const previewRoot = args["preview-dir"] ? path.resolve(args["preview-dir"]) : null;
  const base = safeName(input.meta.company);
  const factbasePath = path.join(outputDir, `${base}_Factbase_${safeName(input.meta.version || "v1")}.xlsx`);
  const modelPath = path.join(outputDir, `${base}_financial_model_${safeName(input.meta.version || "v1")}.xlsx`);
  const factWb = buildFactbase(input);
  const modelWb = buildFinancialModel(input);
  const factQa = await exportAndPreview(factWb, factbasePath, previewRoot ? path.join(previewRoot, "factbase") : null, {
    "0_說明": "A1:H24", "1_增資條件": "A1:F16", "7A_IS明細": "A1:H12", "11_補件清單": "A1:G12",
  });
  const modelQa = await exportAndPreview(modelWb, modelPath, previewRoot ? path.join(previewRoot, "financial-model") : null, {
    "說明": "A1:H22", "①假設參數": "A1:E24", "③獨立財測": "A1:F44", "④財務預測": "A1:G23", "⑤投報率分析": "A1:F36", "⑥CapEx與資金接力": "A1:G17",
  });
  const qa = { generated_at: new Date().toISOString(), factbase: factQa, financial_model: modelQa };
  const qaPath = path.join(outputDir, `${base}_workbook_qa.json`);
  await fs.writeFile(qaPath, JSON.stringify(qa, null, 2), "utf8");
  process.stdout.write(`${JSON.stringify({ factbase: factbasePath, financial_model: modelPath, qa: qaPath }, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`ERROR: ${error?.stack || error}\n`);
  process.exitCode = 2;
});
