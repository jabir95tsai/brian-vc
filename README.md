# Brian VC Codex Plugin

Brian VC is a Codex plugin containing three complete, cooperating Skills for
venture-capital screening and due diligence:

| Skill | Use it for | Main deliverable |
|---|---|---|
| `vc-quick-screen` | L0/L1 thin evidence such as one BP or pitch deck | 2–3 page screening memo and upgrade checklist |
| `prospectus-extractor` | Taiwan prospectus extraction | sourced case data, Factbase, 24-item coverage, fixed 35-sheet workbook and manifest |
| `vc-investment-evaluator` | L2 data rooms with audited/reviewed financials, cap table, term sheet and detailed statements | full A–F diligence package, 11/35-sheet Factbase, seven-sheet model, Executive and Full-critical decks |

The plugin separates facts and calculations from rendering. Neutral styling is
the default; BrianStyle is used only when explicitly requested. It does not
make the GP's investment decision.

## Install and inspect

The repository includes a marketplace at
`.agents/plugins/marketplace.json` whose local plugin source is
`./brian-vc`. Open the repository root in Codex and use the plugin manager to
inspect or install `brian-vc`. When publishing this repository to GitHub, add
that repository as a personal marketplace; no internal absolute path is stored
in the manifest.

Run packaging preflight from the plugin directory:

```powershell
python -X utf8 scripts/preflight.py
```

Standalone Python execution can install the declared dependencies once:

```powershell
python -m pip install -r requirements.txt
```

Codex should use its managed Documents, PDF, Spreadsheets and Presentations
runtimes when available. New evaluator XLSX/PPTX authoring uses
`@oai/artifact-tool`; `openpyxl` remains only for the legacy prospectus
workbook path.

## Use

Examples:

```text
Use $vc-quick-screen to screen this pitch deck and tell me whether to enter full DD.
Use $prospectus-extractor to turn this Taiwan prospectus into a sourced Factbase and 35-sheet Excel.
Use $vc-investment-evaluator to run full due diligence on this data room and produce the IC package.
```

For a folder of mixed documents, all three Skills call the same router:

```powershell
python -X utf8 scripts/route_case.py C:\path\to\case
```

The router is only a preflight signal. Each Skill must still read the documents
and prove its data gate. A prospectus is a conditional extraction workflow; it
does not by itself authorize a full valuation or IRR.

## Evaluator execution contract

`pipeline_contract.md` is the single A–F / 19-module authority. The practical
handoff is:

1. Initialize one case manifest with `evaluator_runner.py init`.
2. Record each module's evidence and artifacts; resume with
   `verify --invalidate-stale`.
3. Prepare the frozen workbook/deck JSON with
   `prepare_workbook_input.py`; IRR matrices come from `irr_matrix.py`.
4. Build and audit the 11-sheet Factbase and seven-sheet financial model with
   the managed spreadsheet runtime.
5. Freeze F1 using `assemble_canonical_package.py`.
6. Render both decks from the frozen ContextPackage, inspect every preview,
   then call `verify_and_record_delivery.py`.
7. Report complete only when `F_GATE=complete`.

Semantic judgment from B1 through E3 remains agent work: source reading,
conflict resolution, expert analysis, official comparable-company research,
valuation judgment, RedTeam and ContentFreeze cannot be replaced by a filename
classifier or deterministic renderer.

## Verification

Run the complete deterministic suite:

```powershell
python -X utf8 tests/run_all.py
```

It covers repo and installed-copy preflight, prompt-routing fixtures, all three
Skill contracts, the prospectus pipeline, evaluator architecture and resume,
workbook/deck contracts, and F1 gate integration. Managed-runtime live QA also
generates and inspects real XLSX/PPTX artifacts; the latest evidence is in
`brian-vc/tests/vc-investment-evaluator/test-report-2026-08-15.md`.

## Test data

Every company in this repository is fictional. The pitch decks, memos,
prospectus fixtures and data-room samples under `brian-vc/tests/` and
`brian-vc/skills/*/scripts/example_*` are synthetic fixtures built to exercise
the contracts. No real deal material, and no analysis of any real company, is
included here.

## Safety and evidence policy

- Official Taiwan market data order: MOPS, TWSE, then TPEx.
- Secondary values must be labeled `⚠️ 尚待官方來源確認` with data and query dates.
- Missing investment inputs stay missing; thin evidence never gets fabricated IRR.
- Original inputs remain read-only; generated artifacts live in the case output directory.
- All deliverables are internal research drafts, not investment advice.
