# Legacy feature parity

The new evaluator keeps the original artifact families while using one frozen
payload and reusable builders.

| Legacy function | New canonical output |
|---|---|
| Structured financial factbase | 11-sheet Factbase plus optional CF, equity, debt/related-party, and notes extensions |
| Assumptions, drivers, IS/BS/CF, debt/depreciation, valuation, checks | Seven-sheet core model plus `financial_extensions` sheets |
| Investment memo | `legacy-parity/*_Investment_Memo.md` and `.docx` |
| DD request list | `legacy-parity/*_DD_Request_Tracker.xlsx` |
| Management questions | `legacy-parity/*_Management_QA.docx` |
| Interview record | `legacy-parity/*_Interview_Notes.docx` |
| Meeting record | `legacy-parity/*_Meeting_Minutes.docx` |
| Financial-statement notes | `legacy-parity/*_Financial_Statement_Notes.docx` |
| Investment committee decks | Executive and Full-critical PPTX |

All outputs are generated from the same prepared case JSON. Missing interview,
meeting, or financial-note content produces a clearly marked template, not
fabricated records. `replay_evaluator_case.py` regenerates the complete set and
records every QA step in `evaluator_replay_report.json`.

When legacy outputs are supplied for comparison, preserve their useful depth
without importing their claims into the new evidence base. Compare at least:

- evidence boundary and source freshness;
- formula correctness and model depth as separate dimensions;
- cap-table and deal-term version control;
- risk, DD tracker, interview, and meeting workflow coverage;
- structural QA, visual QA, and actual delivery readiness.

Do not score the new evaluator higher merely because it emits more files or
passes structural tests. A legacy driver schedule may be analytically deeper
even when its formulas are broken; migrate the reusable logic into the common
schema and tests instead of copying case-specific assumptions.
