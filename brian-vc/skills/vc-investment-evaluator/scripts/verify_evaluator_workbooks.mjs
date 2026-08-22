#!/usr/bin/env node
/** Structural and formula audit for generated evaluator workbooks. */

import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const artifactEntry = require.resolve("@oai/artifact-tool", {
  paths: process.env.CODEX_NODE_MODULES ? [process.env.CODEX_NODE_MODULES] : undefined,
});
const { FileBlob, SpreadsheetFile } = await import(pathToFileURL(artifactEntry).href);

const EXPECTED_FACTBASE = [
  "0_說明", "1_增資條件", "2_公司基本", "3_股東董監", "4_團隊", "5_產品市場",
  "6_客戶供應商", "7A_IS明細", "7B_BS明細", "9_同業估值", "11_補件清單",
];
const EXPECTED_MODEL = ["說明", "①假設參數", "②公司BP", "③獨立財測", "④財務預測", "⑤投報率分析", "⑥CapEx與資金接力"];
const ALLOWED_FACTBASE_EXTENSIONS = new Set(["7C_CF明細", "7D_權益變動", "7E_借款關係人", "7F_附註重要"]);
const ALLOWED_MODEL_EXTENSIONS = new Set(["⑦營運量價", "⑧債務折舊", "⑨營運資金三表", "⑩估值敏感度", "⑪勾稽驗算"]);

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) out[argv[i].replace(/^--/, "")] = argv[i + 1];
  for (const key of ["factbase", "model"]) if (!out[key]) throw new Error(`--${key} is required`);
  if (out.mode && !["full", "degraded", "blocked"].includes(out.mode)) throw new Error(`invalid --mode ${out.mode}`);
  return out;
}

function parseNdjson(result) {
  return String(result?.ndjson || "").split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
}

async function auditWorkbook(filePath, expectedSheets, allowedExtensions, model = false, mode = "full") {
  const wb = await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const sheetInspect = await wb.inspect({ kind: "sheet", include: "id,name", maxChars: 10000 });
  const sheetRows = parseNdjson(sheetInspect).filter((row) => row.kind === "sheet");
  const actual = sheetRows.map((row) => row.name);
  const core = actual.slice(0, expectedSheets.length);
  if (JSON.stringify(core) !== JSON.stringify(expectedSheets)) {
    throw new Error(`${filePath}: core sheet contract mismatch; got ${JSON.stringify(actual)}`);
  }
  const invalidExtensions = actual.slice(expectedSheets.length).filter((name) => !allowedExtensions.has(name));
  if (invalidExtensions.length) throw new Error(`${filePath}: unsupported extension sheets ${JSON.stringify(invalidExtensions)}`);
  const errors = await wb.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 100 },
  });
  const errorRows = parseNdjson(errors).filter((row) => row.kind !== "notice");
  if (errorRows.length) throw new Error(`${filePath}: formula errors detected`);
  const result = { file: filePath, sheets: actual, formula_error_count: 0 };
  if (model) {
    if (mode === "blocked") {
      const statusInspect = await wb.inspect({ kind: "region", sheetId: "說明", range: "A1:H20", maxChars: 10000 });
      const returnInspect = await wb.inspect({ kind: "region", sheetId: "⑤投報率分析", range: "A1:F16", maxChars: 10000 });
      const statusText = String(statusInspect.ndjson || "");
      const returnText = String(returnInspect.ndjson || "");
      if (!statusText.includes("BLOCKED AS DESIGNED")) throw new Error(`${filePath}: blocked status disclosure missing`);
      if (!returnText.includes("IRR 矩陣") || !returnText.includes("Return Multiple 矩陣") || !returnText.includes("BLOCKED")) {
        throw new Error(`${filePath}: blocked return-matrix disclosure missing`);
      }
      result.formula_count_in_base_forecast = 0;
      result.model_checks = "BLOCKED_AS_DESIGNED";
      return result;
    }
    const formulaInspect = await wb.inspect({ kind: "formula", sheetId: "④財務預測", range: "B5:F21", maxChars: 12000, options: { maxResults: 200 } });
    const formulas = parseNdjson(formulaInspect).filter((row) => row.kind === "formula");
    if (formulas.length < 20) throw new Error(`${filePath}: too few formulas in ④財務預測 (${formulas.length})`);
    const matrixInspect = await wb.inspect({ kind: "region", sheetId: "⑤投報率分析", range: "A16:D31", maxChars: 12000 });
    if (!String(matrixInspect.ndjson || "").includes("IRR 矩陣") || !String(matrixInspect.ndjson || "").includes("Return Multiple 矩陣")) {
      throw new Error(`${filePath}: return matrices missing`);
    }
    const statusInspect = await wb.inspect({ kind: "region", sheetId: "說明", range: "A15:F20", maxChars: 6000 });
    const statusText = String(statusInspect.ndjson || "");
    if (statusText.includes("WARN") || !statusText.includes("OK")) throw new Error(`${filePath}: model checks are not all OK`);
    result.formula_count_in_base_forecast = formulas.length;
    result.model_checks = "OK";
  }
  return result;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const report = {
    audited_at: new Date().toISOString(),
    factbase: await auditWorkbook(args.factbase, EXPECTED_FACTBASE, ALLOWED_FACTBASE_EXTENSIONS),
    model: await auditWorkbook(args.model, EXPECTED_MODEL, ALLOWED_MODEL_EXTENSIONS, true, args.mode || "full"),
  };
  if (args.output) await fs.writeFile(args.output, JSON.stringify(report, null, 2), "utf8");
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`ERROR: ${error?.stack || error}\n`);
  process.exitCode = 2;
});
