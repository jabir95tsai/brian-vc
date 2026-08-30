# Brian VC Codex Plugin

[![plugin-regression](https://github.com/jabir95tsai/brian-vc/actions/workflows/test.yml/badge.svg)](https://github.com/jabir95tsai/brian-vc/actions/workflows/test.yml)

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

## Requirements

- **Codex.** This is a plugin for the OpenAI Codex CLI, not for Claude Code or
  any other agent host. `.agents/plugins/marketplace.json` and
  `brian-vc/.codex-plugin/plugin.json` are Codex manifests.
- **Python 3.12 or newer.** CI runs 3.12, 3.13 and 3.14 on Windows; 3.12 is the
  supported floor. Nothing in the plugin is Windows-only — the shell snippets
  below are PowerShell because that is the development environment.
- **Traditional Chinese.** The three `SKILL.md` prompts, and every deliverable
  they produce, are written in Traditional Chinese, and the evaluator's
  official-source rules are Taiwan-specific (MOPS, TWSE, TPEx). Only this
  README and the Python/JS tooling are in English.

## Install and inspect

`.agents/plugins/marketplace.json` at the repository root declares one plugin,
`brian-vc`, whose source is the local path `./brian-vc`; no absolute path is
stored in the manifest. Clone this repository, open its root in Codex, and use
the plugin manager to inspect or install `brian-vc`. To install it from outside
the checkout, add your clone — or this repository on GitHub — as a personal
marketplace first.

Every command below runs from the repository root, which is where `git clone`
leaves you. Confirm the installed package is complete:

```powershell
python -X utf8 brian-vc/scripts/preflight.py
```

Preflight validates the marketplace entry, the plugin manifest, all three
Skills and the Python dependencies. The Skills run it themselves before doing
any work, so a failure here is the first thing to fix.

Standalone Python execution can install the declared dependencies once:

```powershell
python -m pip install -r brian-vc/requirements.txt
```

Codex should use its managed Documents, PDF, Spreadsheets and Presentations
runtimes when available. New evaluator XLSX/PPTX authoring uses
`@oai/artifact-tool`; `openpyxl` remains only for the legacy prospectus
workbook path.

## Use

Ask Codex for a Skill by name. Examples:

```text
Use $vc-quick-screen to screen this pitch deck and tell me whether to enter full DD.
Use $prospectus-extractor to turn this Taiwan prospectus into a sourced Factbase and 35-sheet Excel.
Use $vc-investment-evaluator to run full due diligence on this data room and produce the IC package.
```

For a folder of mixed documents, all three Skills call the same router:

```powershell
python -X utf8 brian-vc/scripts/route_case.py C:\path\to\case
```

The router is only a preflight signal. Each Skill must still read the documents
and prove its data gate. A prospectus is a conditional extraction workflow; it
does not by itself authorize a full valuation or IRR.

## Evaluator execution contract

`brian-vc/skills/vc-investment-evaluator/references/pipeline_contract.md` is the
single A–F / 19-module authority. The practical handoff is:

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

Those scripts live in `brian-vc/skills/vc-investment-evaluator/scripts/`; the
Skill invokes them itself, so the list above is a map of the pipeline rather
than a sequence to type by hand.

Semantic judgment from B1 through E3 remains agent work: source reading,
conflict resolution, expert analysis, official comparable-company research,
valuation judgment, RedTeam and ContentFreeze cannot be replaced by a filename
classifier or deterministic renderer.

## Verification

Run the complete deterministic suite:

```powershell
python -X utf8 brian-vc/tests/run_all.py
```

It covers repo and installed-copy preflight, prompt-routing fixtures, all three
Skill contracts, the prospectus pipeline, evaluator architecture and resume,
workbook/deck contracts, and F1 gate integration. This is the same command CI
runs on every push. Managed-runtime live QA also generates and inspects real
XLSX/PPTX artifacts; the latest evidence is in
`brian-vc/tests/vc-investment-evaluator/test-report-2026-08-15.md`.

## Repository layout

| Path | What it is |
|---|---|
| `brian-vc/` | the plugin package: manifest, shared `scripts/`, the three `skills/`, `tests/` |
| `.agents/plugins/marketplace.json` | the marketplace entry Codex reads to find the plugin |
| `migration-notes/` | dated design records from the port to Codex, kept for provenance; not needed to use the plugin |

## Test data

Every company named in this repository is fictional. The pitch decks, memos,
prospectus fixtures and data-room samples under `brian-vc/tests/` and
`brian-vc/skills/*/scripts/example_*` are synthetic fixtures built to exercise
the contracts.

## License

None. All rights reserved — this is published for inspection, not for reuse.
Absent a license file, the default of copyright law applies: you may read the
repository, but you may not copy, modify or redistribute it. Ask if you want to
use any of it.

## Safety and evidence policy

- Official Taiwan market data order: MOPS, TWSE, then TPEx.
- Secondary values must be labeled `⚠️ 尚待官方來源確認` with data and query dates.
- Missing investment inputs stay missing; thin evidence never gets fabricated IRR.
- Original inputs remain read-only; generated artifacts live in the case output directory.
- All deliverables are internal research drafts, not investment advice.
