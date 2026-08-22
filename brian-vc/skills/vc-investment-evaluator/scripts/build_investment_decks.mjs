#!/usr/bin/env node
/** Render Executive and Full-critical investment committee decks. */

import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const artifactEntry = require.resolve("@oai/artifact-tool", {
  paths: process.env.CODEX_NODE_MODULES ? [process.env.CODEX_NODE_MODULES] : undefined,
});
const { Presentation, PresentationFile } = await import(pathToFileURL(artifactEntry).href);

const W = 1280;
const H = 720;
const P = { navy: "#17324D", blue: "#244A68", teal: "#1E6F74", ink: "#15212B", gray: "#5F6B76", pale: "#EDF2F5", white: "#FFFFFF", amber: "#C77C16", red: "#A23B3B", green: "#2F7D5A", line: "#CFD8DE" };

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) out[argv[i].replace(/^--/, "")] = argv[i + 1];
  for (const key of ["input", "output-dir"]) if (!out[key]) throw new Error(`--${key} is required`);
  return out;
}

function safeName(value) { return String(value || "case").replace(/[\\/:*?"<>|]/g, "_").replace(/\s+/g, "_"); }
function fmt(value, decimals = 0) { return isFiniteEvidence(value) ? Number(value).toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) : "UNKNOWN"; }
function pct(value, decimals = 0) { return isFiniteEvidence(value) ? `${(Number(value) * 100).toFixed(decimals)}%` : "UNKNOWN"; }
function bullet(items) {
  return items
    .map((item) => String(item ?? "").replace(/\s+/g, " ").trim())
    .map((item) => item.replace(/^[•·●▪*-]\s*/, ""))
    .filter(Boolean)
    .map((item, index) => `${index + 1}｜${item}`)
    .join("\n");
}
function copy(data, key, fallback) { return data.deck?.copy?.[key] || fallback; }
function compact(value, maxChars = 96) {
  const text = String(value || "");
  return text.length <= maxChars ? text : `${text.slice(0, maxChars - 1)}…`;
}
function rowsOrGap(rows, columns, message) {
  return rows?.length ? rows : [[message, ...Array(Math.max(0, columns - 1)).fill("尚待補件")]];
}
function isFiniteEvidence(value) { return value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)); }
function isVerifiedComparable(row) {
  if (!row || typeof row !== "object") return false;
  if (!String(row.company || "").trim() || !String(row.as_of || "").trim() || !String(row.source_url || "").trim()) return false;
  if (row.verification_status && row.verification_status !== "verified") return false;
  return ["revenue", "market_cap", "pe", "ev_revenue"].some((key) => isFiniteEvidence(row[key]));
}
function verifiedComparables(data) { return (data.comparables || []).filter(isVerifiedComparable); }
function scenarioUsesDriverModel(data, key) {
  const explicit = data.independent_forecast?.scenario_methods?.[key];
  return explicit ? explicit === "driver_model" : data.independent_forecast?.method === "driver_model";
}

function addText(slide, text, position, style = {}, name = undefined) {
  const shape = slide.shapes.add({ geometry: "textbox", name, position, fill: "none", line: { style: "solid", fill: "none", width: 0 } });
  shape.text = String(text ?? "");
  shape.text.style = { fontSize: 18, color: P.ink, fontFamily: "Aptos", verticalAlignment: "middle", ...style };
  return shape;
}

function addRect(slide, position, fill, line = "none", radius = undefined, name = undefined) {
  return slide.shapes.add({ geometry: radius ? "roundRect" : "rect", name, position, fill, line: { style: "solid", fill: line, width: line === "none" ? 0 : 1 }, ...(radius ? { borderRadius: radius } : {}) });
}

function addSlideBase(deck, title, eyebrow, section = "INVESTMENT REVIEW") {
  const slide = deck.slides.add();
  slide.background.fill = P.white;
  addRect(slide, { left: 0, top: 0, width: 18, height: H }, P.teal);
  addText(slide, section, { left: 60, top: 34, width: 260, height: 24 }, { fontSize: 13, bold: true, color: P.teal }, "section-label");
  addText(slide, title, { left: 60, top: 72, width: 1120, height: 58 }, { fontSize: 36, bold: true, color: P.navy }, "slide-title");
  if (eyebrow) addText(slide, eyebrow, { left: 60, top: 132, width: 1120, height: 30 }, { fontSize: 16, color: P.gray }, "slide-subtitle");
  addRect(slide, { left: 60, top: 174, width: 1120, height: 2 }, P.line);
  return slide;
}

function addFooter(slide, data, index, variant) {
  addText(slide, `${data.meta.company}｜${data.meta.as_of}｜${variant}`, { left: 60, top: 680, width: 760, height: 18 }, { fontSize: 11, color: P.gray });
  addText(slide, String(index), { left: 1120, top: 680, width: 60, height: 18 }, { fontSize: 11, color: P.gray, alignment: "right" });
}

function styleTable(table, rows, cols, header = true, fontSize = 16) {
  table.styleOptions = { headerRow: header, bandedRows: true };
  table.borders.assign({ style: "solid", fill: P.line, width: 1 });
  const all = table.cells.block({ row: 0, column: 0, rowCount: rows, columnCount: cols });
  all.textStyle.fontSize = fontSize;
  all.textStyle.color = P.ink;
  if (header) {
    const h = table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: cols });
    h.fill = P.blue;
    h.textStyle.color = P.white;
    h.textStyle.bold = true;
  }
  return table;
}

function addTable(slide, values, position, widths = undefined, fontSize = 16) {
  const rows = values.length;
  const cols = Math.max(...values.map((row) => row.length));
  const table = slide.tables.add({ rows, columns: cols, ...position, values, ...(widths ? { columnWidths: widths } : {}) });
  return styleTable(table, rows, cols, true, fontSize);
}

function cover(deck, data, variant) {
  const slide = deck.slides.add();
  slide.background.fill = P.navy;
  addRect(slide, { left: 0, top: 0, width: 24, height: H }, P.teal);
  addText(slide, variant === "Executive" ? "EXECUTIVE INVESTMENT REVIEW" : "FULL-CRITICAL INVESTMENT REVIEW", { left: 80, top: 72, width: 720, height: 30 }, { fontSize: 15, bold: true, color: "#8FD0D2" });
  addText(slide, data.meta.company, { left: 80, top: 164, width: 960, height: 80 }, { fontSize: 54, bold: true, color: P.white });
  addText(slide, variant === "Executive" ? copy(data, "executive_subtitle", data.deck.communication_job) : copy(data, "full_subtitle", "完整證據、風險、反方與失敗路徑"), { left: 80, top: 268, width: 920, height: 68 }, { fontSize: 28, color: "#DCE8EE" });
  addRect(slide, { left: 80, top: 398, width: 540, height: 2 }, P.teal);
  addText(slide, `Case ${data.meta.case_id}\n資料截至 ${data.meta.as_of}\n${data.meta.currency}／${data.meta.unit}`, { left: 80, top: 430, width: 430, height: 110 }, { fontSize: 18, color: "#DCE8EE" });
  addText(slide, "內部研究草稿｜非投資建議\n進場／金額／最終條件由 GP 決定", { left: 760, top: 500, width: 400, height: 90 }, { fontSize: 18, bold: true, color: "#8FD0D2", alignment: "right" });
  return slide;
}

function narrativeSlide(deck, data) {
  const s = addSlideBase(deck, copy(data, "narrative_title", "投資命題、證據邊界與待確認條件"), data.deck.communication_job);
  addText(s, data.deck.thesis, { left: 60, top: 214, width: 700, height: 120 }, { fontSize: 27, bold: true, color: P.navy });
  addRect(s, { left: 810, top: 214, width: 370, height: 250 }, P.pale, P.line, "rounded-xl");
  addText(s, "目前判斷", { left: 846, top: 246, width: 280, height: 30 }, { fontSize: 20, bold: true, color: P.teal });
  addText(s, data.deck.decision_status, { left: 846, top: 296, width: 285, height: 100 }, { fontSize: 25, bold: true, color: P.navy });
  addText(s, "進場 / 不進場：【GP 填入】\n前置確認條件：【GP 填入】\n建議金額：【GP 填入】", { left: 60, top: 430, width: 700, height: 120 }, { fontSize: 20, color: P.ink });
  return s;
}

function termsSlide(deck, data) {
  if (data.mode === "blocked") {
    const reason = data.deal.blocked_reason || "現行交易條件未揭露";
    const s = addSlideBase(deck, copy(data, "terms_title", "本輪交易條件未揭露，估值與報酬模型 BLOCKED"), copy(data, "terms_subtitle", "空白代表缺乏證據；不得以 0、舊輪次或公司 BP 反推替代"));
    const rows = [
      ["欄位", "狀態", "判讀"], ["輪次", data.deal.round || "未揭露", "僅保留案件描述"],
      ["投資額", "BLOCKED", compact(reason)], ["投前估值", "BLOCKED", compact(reason)], ["投後估值", "BLOCKED", compact(reason)],
      ["證券權利", data.deal.security || "BLOCKED", "取得簽署版 Term Sheet 後驗證"],
    ];
    addTable(s, rows, { left: 60, top: 212, width: 720, height: 350 }, [250, 190, 280]);
    addText(s, "解除 BLOCKED 的前提", { left: 840, top: 218, width: 300, height: 34 }, { fontSize: 24, bold: true, color: P.navy });
    addText(s, bullet(data.deck.conditions), { left: 840, top: 275, width: 320, height: 300 }, { fontSize: 17, color: P.ink });
    return s;
  }
  const stake = data.deal.post_money ? data.deal.investment / data.deal.post_money : 0;
  const defaultTitle = data.mode === "degraded"
    ? "本輪條件尚未完整，先以透明假設建立敏感度"
    : `本輪投資 ${fmt(data.deal.investment, 1)}、投後估值 ${fmt(data.deal.post_money, 1)}，對應持股約 ${pct(stake, 1)}`;
  const s = addSlideBase(deck, copy(data, "terms_title", defaultTitle), copy(data, "terms_subtitle", "條件採簽署版文件為準；任何衝突回到 ConflictLog"));
  const rows = [
    ["條件", "數值", "判讀"], ["輪次", data.deal.round, data.deal.security || "未提供"], ["投資額", fmt(data.deal.investment, 1), data.meta.unit],
    ["投前估值", fmt(data.deal.pre_money, 1), data.meta.unit], ["投後估值", fmt(data.deal.post_money, 1), data.meta.unit],
    ["投資人持股", pct(data.deal.investment / data.deal.post_money, 1), "投資額／投後估值"], ["ESOP 稀釋", pct(data.deal.esop_dilution_pct || 0, 1), "尚須確認 fully diluted 口徑"],
  ];
  addTable(s, rows, { left: 60, top: 212, width: 720, height: 350 }, [250, 190, 280]);
  addText(s, "價格成立的前提", { left: 840, top: 218, width: 300, height: 34 }, { fontSize: 24, bold: true, color: P.navy });
  addText(s, bullet(data.deck.conditions), { left: 840, top: 275, width: 320, height: 300 }, { fontSize: 17, color: P.ink });
  return s;
}

function evidenceTableSlide(deck, title, subtitle, rows, headers, takeaway, keyword = "") {
  const s = addSlideBase(deck, title, subtitle);
  addTable(s, [headers, ...rows], { left: 60, top: 210, width: 760, height: 330 }, undefined, 16);
  addRect(s, { left: 860, top: 210, width: 320, height: 330 }, P.pale, P.line, "rounded-xl");
  addText(s, keyword || "投資含義", { left: 895, top: 245, width: 250, height: 32 }, { fontSize: 22, bold: true, color: P.teal });
  addText(s, takeaway, { left: 895, top: 300, width: 250, height: 190 }, { fontSize: 20, bold: true, color: P.navy });
  return s;
}

function teamSlide(deck, data) {
  const rows = rowsOrGap((data.team || []).map((r) => [r.name, r.title, r.experience, r.source]), 4, "團隊資料未提供");
  return evidenceTableSlide(deck, copy(data, "team_title", "經營團隊與治理資料"), copy(data, "team_subtitle", "職責、學經歷與關係人資訊均須以正式文件驗證"), rows, ["姓名", "職稱", "經歷", "來源"], copy(data, "team_takeaway", data.team?.length ? "團隊能力與治理完整性應分開判讀。" : "團隊資料尚缺，degraded 模式不得推定能力已驗證。"), "團隊判讀");
}

function historySlide(deck, data) {
  const h = [...data.financial_history].sort((a, b) => a.year - b.year);
  const rows = [
    ["營業收入", ...h.map((r) => fmt(r.revenue, 1))], ["銷貨成本", ...h.map((r) => fmt(r.cogs, 1))], ["毛利", ...h.map((r) => fmt(r.revenue - r.cogs, 1))],
    ["毛利率", ...h.map((r) => pct((r.revenue - r.cogs) / r.revenue, 1))], ["營業費用", ...h.map((r) => fmt(r.opex, 1))],
    ["淨利", ...h.map((r) => fmt(r.net_income, 1))], ["CapEx", ...h.map((r) => fmt(r.capex, 1))], ["期末現金", ...h.map((r) => fmt(r.cash, 1))],
  ];
  const latestSource = h.at(-1)?.source || "尚待補件";
  const s = addSlideBase(deck, copy(data, "history_title", "歷史財務表現與品質"), `歷史 IS／BS｜${data.meta.unit}｜來源：${latestSource}`);
  // Widths must follow the actual number of history years, not a fixed three:
  // a case with two audited years (or four) otherwise fails column-width validation.
  const historyWidths = [270, ...h.map(() => Math.max(90, Math.round(480 / Math.max(h.length, 1))))];
  addTable(s, [["歷史 IS／指標", ...h.map((r) => String(r.year))], ...rows], { left: 60, top: 210, width: 750, height: 390 }, historyWidths, 15);
  s.charts.add("line", { position: { left: 850, top: 245, width: 330, height: 250 }, categories: h.map((r) => String(r.year)), series: [{ name: "營收", values: h.map((r) => r.revenue), fill: P.teal }, { name: "淨利", values: h.map((r) => r.net_income), fill: P.amber }], hasLegend: true, dataLabels: { showValue: false }, yAxis: { majorGridlines: { style: "solid", fill: P.line, width: 1 } } });
  addText(s, copy(data, "history_takeaway", "營收與獲利品質仍須以客戶、產品及現金流明細拆解。"), { left: 850, top: 530, width: 320, height: 62 }, { fontSize: 18, bold: true, color: P.navy });
  return s;
}

function forecastSlide(deck, data) {
  if (data.independent_forecast?.status === "blocked") {
    const reason = data.independent_forecast.reason || data.deal.blocked_reason || "無可用財測假設";
    return evidenceTableSlide(
      deck,
      copy(data, "forecast_title", "獨立財務預測 BLOCKED｜未建立"),
      "無可用財測假設；歷史財務仍完整保留",
      [["BLOCKED", reason, "不得用公司 BP、0 值或任意成長率替代"], ["解除條件", "取得可驗證的量價、毛利、費用與 CapEx 假設", "再建獨立情境"]],
      ["狀態", "原因／條件", "證據邊界"],
      "blocked 是正確輸出：它阻止缺證據的數字進入估值與 IRR。",
      "財測邊界",
    );
  }
  const f = data.independent_forecast.scenarios.base;
  const rows = [
    ["營收", ...f.map((r) => fmt(r.revenue, 1))], ["毛利率", ...f.map((r) => pct(r.gross_margin, 1))], ["營業費用", ...f.map((r) => fmt(r.opex, 1))],
    ["EBIT", ...f.map((r) => fmt(r.ebit, 1))], ["淨利", ...f.map((r) => fmt(r.net_income, 1))], ["CapEx", ...f.map((r) => fmt(r.capex, 1))],
    ["FCF proxy", ...f.map((r) => fmt(r.fcf_proxy, 1))], ["Revenue multiple", ...f.map(() => `${data.assumptions.scenarios.base.exit_revenue_multiple.toFixed(1)}x`)],
  ];
  const end = f.at(-1) || {};
  const defaultTitle = `基準情境至 ${end.year || "退出年"}：營收 ${fmt(end.revenue || 0, 1)}、FCF proxy ${fmt(end.fcf_proxy || 0, 1)}`;
  const s = addSlideBase(deck, copy(data, "forecast_title", defaultTitle), `${data.independent_forecast.label}｜${data.meta.unit}`);
  addTable(s, [["財務預測", ...f.map((r) => String(r.year))], ...rows], { left: 60, top: 210, width: 790, height: 390 }, [240, 110, 110, 110, 110, 110], 14);
  s.charts.add("line", { position: { left: 885, top: 230, width: 295, height: 270 }, categories: f.map((r) => String(r.year)), series: [{ name: "營收", values: f.map((r) => r.revenue), fill: P.teal }, { name: "FCF proxy", values: f.map((r) => r.fcf_proxy), fill: P.amber }], hasLegend: true, yAxis: { majorGridlines: { style: "solid", fill: P.line, width: 1 } } });
  addText(s, copy(data, "forecast_takeaway", scenarioUsesDriverModel(data, "base") ? "基準情境由輸入的營運驅動與明細假設產生；仍須以最新實績滾動更新。" : "限制：基準情境目前為比率 proxy，未含完整營運資金；投審前應以產品量價與月度 CF 更新。"), { left: 885, top: 520, width: 295, height: 80 }, { fontSize: 16, color: P.red });
  return s;
}

function bpCompareSlide(deck, data) {
  const bp = new Map((data.bp_forecast || []).map((r) => [r.year, r]));
  if (data.independent_forecast?.status === "blocked") {
    const rows = [...bp.values()].slice(0, 5).map((r) => [r.year, fmt(r.revenue || 0, 1), r.source || "公司 BP", "公司主張；未與獨立財測比較"]);
    return evidenceTableSlide(
      deck,
      copy(data, "bp_compare_title", "公司 BP 保留作主張；獨立基準 BLOCKED"),
      "BP 可追溯不等於已驗證；不得自動升格為投資模型",
      rowsOrGap(rows, 4, "公司 BP 未提供可比較年度"),
      ["年度", "公司營收預測", "來源", "判讀"],
      "交易條件與獨立假設缺失時，只呈現公司主張，不計算差距或報酬。",
      "比較邊界",
    );
  }
  const f = data.independent_forecast.scenarios.base;
  const rows = f.map((r) => [r.year, fmt(bp.get(r.year)?.revenue || 0, 1), fmt(r.revenue, 1), pct((bp.get(r.year)?.revenue || 0) / r.revenue - 1, 1)]);
  const direction = rows.some((row) => Number.parseFloat(row[3]) > 0) ? "存在高於獨立基準的年度" : "未高於獨立基準";
  return evidenceTableSlide(deck, copy(data, "bp_compare_title", `公司 BP 與獨立基準比較：${direction}`), "BP 是公司預測；獨立財測是估計，兩者不可混用", rows, ["年度", "公司 BP", "獨立基準", "BP 差異"], copy(data, "bp_takeaway", "差距本身不是對錯判斷，而是管理層必須提出量價、訂單與毛利證據的範圍。"), "差距含義");
}

function compsSlide(deck, data) {
  const comps = verifiedComparables(data);
  const rows = rowsOrGap(comps.map((r) => [r.company, r.ticker, isFiniteEvidence(r.revenue) ? fmt(r.revenue) : "N/A", isFiniteEvidence(r.market_cap) ? fmt(r.market_cap) : "N/A", isFiniteEvidence(r.pe) ? `${Number(r.pe).toFixed(1)}x` : "N/A", isFiniteEvidence(r.ev_revenue) ? `${Number(r.ev_revenue).toFixed(1)}x` : "N/A", r.as_of]), 7, "可比公司尚未完成官方驗證");
  const multiples = comps.filter((r) => isFiniteEvidence(r.ev_revenue)).map((r) => Number(r.ev_revenue));
  const range = multiples.length ? `${Math.min(...multiples).toFixed(1)}–${Math.max(...multiples).toFixed(1)}x` : "尚待官方來源確認";
  const s = addSlideBase(deck, copy(data, "comps_title", `${comps.length} 家已驗證同業；EV/Revenue 觀察區間 ${range}`), "同業比較／同業估值｜MOPS → TWSE → TPEx；資料日期與查詢日期需並列");
  addTable(s, [["公司", "代號", "營收", "市值", "P/E", "EV/Rev", "資料日"], ...rows], { left: 60, top: 215, width: 1120, height: 350 }, [190, 110, 150, 150, 130, 140, 190], 15);
  addText(s, "來源 URL 留存於 CitationTable；本頁只顯示已驗證值。", { left: 60, top: 590, width: 900, height: 28 }, { fontSize: 15, color: P.gray });
  return s;
}

function valuationSlide(deck, data) {
  return evidenceTableSlide(deck, copy(data, "valuation_title", "退出估值情境與成立條件"), "退出 Revenue multiple 情境｜估值單位同模型", rowsOrGap(data.deck.valuation_scenarios, 4, "估值情境尚未完成"), ["情境", "退出倍數", "退出估值", "判讀"], copy(data, "valuation_takeaway", "退出倍數必須與成長、毛利、可比公司及資料日期共同驗證。"), "估值判讀");
}

function returnsSlide(deck, data) {
  if (data.return_matrix?.status === "blocked") {
    const reason = data.return_matrix.reason || data.deal.blocked_reason || "現行交易條件未揭露";
    const s = addSlideBase(deck, copy(data, "returns_title", "IRR 與 Return Multiple｜BLOCKED"), "未計算不是 0 報酬；缺少交易條件時不得製造假精確");
    addText(s, "IRR 矩陣", { left: 60, top: 202, width: 520, height: 30 }, { fontSize: 22, bold: true, color: P.navy });
    addTable(s, [["狀態", "原因"], ["BLOCKED", compact(reason, 110)], ["缺口", "投資額／投後估值／持股／證券權利"]], { left: 60, top: 244, width: 530, height: 240 }, [150, 380], 14);
    addText(s, "Return Multiple 矩陣", { left: 650, top: 202, width: 530, height: 30 }, { fontSize: 22, bold: true, color: P.navy });
    addTable(s, [["狀態", "解除條件"], ["BLOCKED", "取得現行 Term Sheet"], ["下一步", "驗證稀釋、退出值與持有期間"]], { left: 650, top: 244, width: 530, height: 240 }, [150, 380], 14);
    addText(s, "事實 DD 可繼續；估值與報酬層停在證據邊界。", { left: 60, top: 540, width: 1120, height: 44 }, { fontSize: 20, bold: true, color: P.red });
    return s;
  }
  const s = addSlideBase(deck, copy(data, "returns_title", `報酬率敏感度相對 Hurdle ${pct(data.assumptions.hurdle_rate, 0)}`), "IRR／Return Multiple 雙矩陣｜由 scripts/irr_matrix.py 產生");
  const irr = data.return_matrix.irr_rows;
  const mult = data.return_matrix.multiple_rows;
  addText(s, "IRR 矩陣", { left: 60, top: 202, width: 520, height: 30 }, { fontSize: 22, bold: true, color: P.navy });
  addTable(s, irr, { left: 60, top: 244, width: 530, height: 300 }, [170, 120, 120, 120], 14);
  addText(s, "Return Multiple 矩陣", { left: 650, top: 202, width: 530, height: 30 }, { fontSize: 22, bold: true, color: P.navy });
  addTable(s, mult, { left: 650, top: 244, width: 530, height: 300 }, [170, 120, 120, 120], 14);
  addText(s, `持股 ${data.return_matrix.stake_pct.toFixed(1)}%｜持有 ${data.assumptions.holding_years} 年｜Hurdle ${pct(data.assumptions.hurdle_rate, 0)}`, { left: 60, top: 574, width: 1120, height: 28 }, { fontSize: 16, color: P.gray });
  return s;
}

function conditionsSlide(deck, data) {
  const rows = data.deck.conditions.map((c, i) => [`C${i + 1}`, c, i < 2 ? "P0" : "P1", i < 2 ? "投審前" : "撥款前"]);
  return evidenceTableSlide(deck, copy(data, "conditions_title", `${rows.length} 項前置條件界定下一步驗證`), "條件未完成時，F_GATE 不代表 GP 已核准投資", rowsOrGap(rows, 4, "前置條件尚未定義"), ["ID", "前置條件", "優先級", "期限"], copy(data, "conditions_takeaway", "P0 若失敗，應重估價格、調整條件或停止。"), "決策設計");
}

function scoreSlide(deck, data) {
  const s = addSlideBase(deck, copy(data, "score_title", "多維度研究評分與驗證優先級"), "評分是研究摘要，不是自動投資決策");
  s.charts.add("bar", { position: { left: 70, top: 220, width: 700, height: 350 }, categories: data.deck.scores.map((r) => r[0]), series: [{ name: "Score", values: data.deck.scores.map((r) => r[1]), fill: P.teal }], hasLegend: false, dataLabels: { showValue: true, position: "outEnd" }, xAxis: { maximumScale: 100, minimumScale: 0, majorUnit: 20 }, yAxis: { majorGridlines: { style: "solid", fill: P.line, width: 1 } } });
  const ranked = [...data.deck.scores].sort((a, b) => Number(b[1]) - Number(a[1]));
  addText(s, copy(data, "score_takeaway", `最高：${ranked[0]?.[0] || "N/A"} ${ranked[0]?.[1] ?? "N/A"}\n最低：${ranked.at(-1)?.[0] || "N/A"} ${ranked.at(-1)?.[1] ?? "N/A"}\n\n分數用於定位驗證工作，不代表自動投資決策。`), { left: 850, top: 250, width: 290, height: 240 }, { fontSize: 24, bold: true, color: P.navy });
  return s;
}

function closeSlide(deck, data) {
  const s = addSlideBase(deck, copy(data, "close_title", "下一步：補證、重算、反方檢驗與決策留白"), "決策框架：補證 → 重算 → RedTeam → GP 決策", "DECISION");
  addText(s, "1", { left: 85, top: 235, width: 65, height: 65 }, { fontSize: 42, bold: true, color: P.teal, alignment: "center" });
  addText(s, copy(data, "close_step_1", "補齊 P0\n取得直接證據與來源定位"), { left: 170, top: 224, width: 265, height: 95 }, { fontSize: 22, bold: true, color: P.navy });
  addText(s, "2", { left: 475, top: 235, width: 65, height: 65 }, { fontSize: 42, bold: true, color: P.teal, alignment: "center" });
  addText(s, copy(data, "close_step_2", "重算\n營運驅動、資金需求與估值"), { left: 560, top: 224, width: 260, height: 95 }, { fontSize: 22, bold: true, color: P.navy });
  addText(s, "3", { left: 865, top: 235, width: 65, height: 65 }, { fontSize: 42, bold: true, color: P.teal, alignment: "center" });
  addText(s, "提交 GP\n進場／金額／條件保持留白", { left: 950, top: 224, width: 230, height: 95 }, { fontSize: 22, bold: true, color: P.navy });
  addRect(s, { left: 80, top: 410, width: 1100, height: 2 }, P.line);
  addText(s, "進場 / 不進場：【GP 填入】     前置確認條件：【GP 填入】     建議金額：【GP 填入】", { left: 90, top: 455, width: 1080, height: 70 }, { fontSize: 24, bold: true, color: P.navy, alignment: "center" });
  return s;
}

function fullOnlySlides(deck, data) {
  const conflict = evidenceTableSlide(deck, copy(data, "conflict_title", "資料衝突、來源優先序與處理狀態"), "衝突解析｜高優先欄位未解時 D2、D3、E3、F2 不得通過", rowsOrGap(data.deck.conflicts, 4, "目前未列出衝突"), ["欄位", "來源一", "來源二", "狀態／處理"], copy(data, "conflict_takeaway", "影響估值或報酬的未解衝突，必須使交付狀態降為 partial／blocked。"), "資料品質");
  const p0Count = (data.deck.risks || []).filter((row) => row[3] === "P0").length;
  const risk = evidenceTableSlide(deck, copy(data, "risk_title", `風險矩陣：${p0Count} 項 P0 待關閉`), "風險矩陣｜Impact × Likelihood × Owner action", rowsOrGap(data.deck.risks, 5, "風險尚未整理"), ["風險", "影響", "機率", "優先級", "緩解／驗證"], copy(data, "risk_takeaway", "不同風險必須各自對應證據、Owner、觸發點與停止條件。"), "風險含義");
  const red = addSlideBase(deck, copy(data, "redteam_title", "RedTeam：最可能推翻目前結論的假設"), "獨立反方審查｜結論反轉條件必須保留", "REDTEAM");
  addText(red, bullet(data.deck.redteam), { left: 70, top: 220, width: 720, height: 330 }, { fontSize: 23, color: P.ink });
  addRect(red, { left: 850, top: 220, width: 320, height: 300 }, "#F8EEEE", "#E2BABA", "rounded-xl");
  addText(red, "反對投資的充分條件", { left: 880, top: 255, width: 260, height: 58 }, { fontSize: 22, bold: true, color: P.red });
  addText(red, copy(data, "redteam_reversal", "若關鍵收入、成本或資金假設無法驗證，基準估值與報酬情境不得視為成立。"), { left: 880, top: 340, width: 250, height: 130 }, { fontSize: 22, bold: true, color: P.navy });
  const fail = evidenceTableSlide(deck, copy(data, "failure_title", `${(data.deck.failure_paths || []).length} 條失敗路徑與決策動作`), "Failure paths｜不是一般風險清單，而是結論反轉機制", rowsOrGap(data.deck.failure_paths, 3, "失敗路徑尚未整理"), ["失敗路徑", "一階影響", "決策動作"], "每條路徑都要有可觀察觸發點；若命中，停止沿用原模型。", "反事實測試");
  const missingRows = (data.missing_items || []).map((r) => [r.priority, r.item, r.reason, r.owner, r.status]);
  const missing = evidenceTableSlide(deck, copy(data, "missing_title", `資料缺失／補件：${missingRows.length} 項影響目前判讀`), "補件清單｜P0 優先於更多敘事分析", rowsOrGap(missingRows, 5, "目前未列出缺件"), ["優先級", "補件", "理由", "Owner", "狀態"], copy(data, "missing_takeaway", "未取得直接證據的主張，必須維持未驗證狀態。"), "缺件影響");
  const q = addSlideBase(deck, copy(data, "questions_title", `${data.deck.management_questions.length} 項管理層問題測試關鍵假設`), "管理層問答｜迴避財務誠信核心問題時，案件標 blocked", "MANAGEMENT QUESTIONS");
  addText(q, data.deck.management_questions.map((x, i) => `Q${i + 1}｜${x}`).join("\n\n"), { left: 80, top: 210, width: 1040, height: 400 }, { fontSize: 22, color: P.ink });
  return [conflict, risk, red, fail, missing, q];
}

function buildDeck(data, variant) {
  const deck = Presentation.create({ slideSize: { width: W, height: H } });
  const slides = [cover(deck, data, variant), narrativeSlide(deck, data), termsSlide(deck, data)];
  slides.push(evidenceTableSlide(deck, copy(data, "business_title", "商業模式、收入組合與集中度"), "商業模式｜收入流與集中度是估值的共同驅動", rowsOrGap(data.deck.business_metrics, 3, "商業指標尚未整理"), ["指標", "數值", "證據／判讀"], copy(data, "business_takeaway", "收入品質、集中度與單位經濟應共同驗證。"), "商業含義"));
  slides.push(evidenceTableSlide(deck, copy(data, "technology_title", "技術成熟度、品質與供應韌性"), "技術／競品｜量產狀態不等於供應與品質風險已解除", rowsOrGap(data.deck.technology_metrics, 3, "技術指標尚未整理"), ["技術指標", "數值", "證據／停止題"], copy(data, "technology_takeaway", "技術可行性、可量產性與供應韌性必須分別驗證。"), "技術含義"));
  slides.push(evidenceTableSlide(deck, copy(data, "market_title", "產業、競爭與市場證據"), "產業／市場規模｜官方同業定錨，不能直接代替公司驗證", rowsOrGap(data.deck.market_metrics, 3, "市場指標尚未整理"), ["市場指標", "數值", "來源／假設"], copy(data, "market_takeaway", "市場資料提供邊界，公司特定成長仍需訂單、價格與滲透率證據。"), "市場含義"));
  slides.push(teamSlide(deck, data), historySlide(deck, data), forecastSlide(deck, data), bpCompareSlide(deck, data), compsSlide(deck, data), valuationSlide(deck, data), returnsSlide(deck, data), scoreSlide(deck, data));
  if (variant === "Full-critical") slides.push(...fullOnlySlides(deck, data));
  else slides.push(conditionsSlide(deck, data));
  slides.push(closeSlide(deck, data));
  slides.forEach((slide, i) => addFooter(slide, data, i + 1, variant));
  return deck;
}

async function writeBlob(filePath, blob) { await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer())); }

async function exportDeck(deck, outputPath, previewDir) {
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.mkdir(previewDir, { recursive: true });
  for (const [index, slide] of deck.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(path.join(previewDir, `${stem}.png`), await deck.export({ slide, format: "png", scale: 1 }));
    await fs.writeFile(path.join(previewDir, `${stem}.layout.json`), await (await slide.export({ format: "layout" })).text(), "utf8");
  }
  await writeBlob(path.join(previewDir, "montage.webp"), await deck.export({ format: "webp", montage: true, scale: 1 }));
  const inspect = await deck.inspect({ kind: "slide,textbox,table,chart", maxChars: 12000 });
  await fs.writeFile(path.join(previewDir, "deck-inspect.ndjson"), inspect.ndjson || "", "utf8");
  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(outputPath);
  return { output: outputPath, slides: deck.slides.items.length, preview_dir: previewDir };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const data = JSON.parse(await fs.readFile(args.input, "utf8"));
  if (!data.return_matrix || !data.independent_forecast || !data.deck) throw new Error("input is not a prepared, content-frozen evaluator case");
  data.deck.communication_job ||= "研究摘要、證據邊界與待確認事項";
  data.deck.thesis ||= "投資命題尚待補件與驗證。";
  data.deck.decision_status ||= "研究中；GP 決策留白";
  for (const key of ["conditions", "business_metrics", "technology_metrics", "market_metrics", "valuation_scenarios", "risks", "conflicts", "redteam", "failure_paths", "management_questions"]) data.deck[key] ||= [];
  data.deck.scores ||= [["資料完整度", 0]];
  const mode = data.mode || data.meta.mode || "full";
  if (mode === "full" && verifiedComparables(data).length < 5) throw new Error("F2 blocked in full mode: at least five verified comparables are required");
  const out = path.resolve(args["output-dir"]);
  const preview = path.resolve(args["preview-dir"] || path.join(out, "deck-preview"));
  const base = safeName(data.meta.company);
  const executive = await exportDeck(buildDeck(data, "Executive"), path.join(out, `${base}_Executive_${safeName(data.meta.version || "v1")}.pptx`), path.join(preview, "executive"));
  const full = await exportDeck(buildDeck(data, "Full-critical"), path.join(out, `${base}_Full-critical_${safeName(data.meta.version || "v1")}.pptx`), path.join(preview, "full-critical"));
  const report = { generated_at: new Date().toISOString(), style: "neutral", mode, executive, full };
  const reportPath = path.join(out, `${base}_deck_build.json`);
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2), "utf8");
  process.stdout.write(`${JSON.stringify({ ...report, report: reportPath }, null, 2)}\n`);
}

main().catch((error) => { process.stderr.write(`ERROR: ${error?.stack || error}\n`); process.exitCode = 2; });
