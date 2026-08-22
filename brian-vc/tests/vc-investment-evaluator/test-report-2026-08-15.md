# vc-investment-evaluator test report — 2026-08-15

Environment: Windows, Codex managed Node/Python runtimes, neutral style.

## Deterministic regression

- Unified suite: 12/12 commands passed.
- Plugin preflight: pass in source repository and clean installed-copy layout.
- Prompt routing fixtures: all three Skills covered; thin-data IRR boundary covered.
- `vc-quick-screen`: 28/28 static checks and all positive/negative semantic fixtures passed.
- `prospectus-extractor`: 19/19 tests passed.
- Evaluator architecture: 18/18 checks passed for the canonical 19-module DAG.
- Evaluator runner: 3/3 tests passed for initialization, dependency/hash checks and stale invalidation.
- Workbook source contract: 3/3 tests passed.
- Deck source contract: 3/3 tests passed.
- F1 canonical package: end-to-end manifest/gate test passed.

## Managed spreadsheet live QA

Generated from `fixture_evaluator_case.json` with `@oai/artifact-tool`:

- Compact Factbase: exactly 11 required sheets.
- Financial model: exactly 7 required sheets.
- Formula-error scan: 0 in both workbooks.
- Base forecast formula audit: 70 formulas in `④財務預測`.
- Visible model Checks: `OK`.
- IRR and Return Multiple matrices present and sourced from `scripts/irr_matrix.py`.
- Rendered and visually inspected: Factbase cover/terms/history/missing-items plus all seven model sheets; no material clipping or unreadable output found.

## Managed presentation live QA

Generated from the same frozen fixture with the neutral renderer:

- Executive: 16 slides; `qa_deck.py` 8/8 passed.
- Full-critical: 21 slides; `qa_deck.py --full` 11/11 passed.
- Five comparable companies, eight-row historical IS, eight-row forecast, team table, technical/market quantitative tables and IRR/Multiple double matrices passed structural checks.
- Full-critical conflict, risk matrix, RedTeam, failure paths, missing-items and management-question slides present.
- All Executive slides and all Full-critical-only slides were visually inspected from PNG previews; layout JSON search found no overflow, clipping, overlap or out-of-bounds flags.

## Boundary retained

These tests prove packaging, deterministic transformations and rendering. They
do not replace forward evaluation of the agent's B1–E3 semantic judgments on a
new real data room. Model forward-testing with independent tasks remains a
separate release exercise when fresh-task delegation is authorized.
