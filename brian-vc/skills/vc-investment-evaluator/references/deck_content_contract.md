# F2 deck content contract

The deck renderer reads the frozen JSON produced by
`scripts/prepare_workbook_input.py`. It must contain the case facts, canonical
`return_matrix`, `independent_forecast`, and a `deck` object assembled from the
Stage C–E `DECK_EXPORT` blocks.

Required `deck` fields:

- `communication_job`, `thesis`, `decision_status`
- `conditions`, `business_metrics`, `technology_metrics`, `market_metrics`
- `scores`, `valuation_scenarios`, `risks`, `conflicts`
- `redteam` and `redteam_handoff` (the E2→F1 handoff sentence from `experts/redteam.md`, authored by E2 and quoted verbatim — not written by the assembler), `failure_paths`, `management_questions`
- optional `copy`: case-specific titles and takeaways. Company facts, fixed
  transaction numbers, industry claims, and score conclusions belong here,
  never in the generic renderer source.

In `full` mode, Executive is at least a 15-slide decision deck and requires at
least five verified comparables plus the complete evidence sections.
Full-critical includes all Executive
evidence plus conflicts, risk matrix, RedTeam, failure paths, missing items,
and management questions. The renderer may shorten display copy but must not
change calculations, facts, risk levels, sources, or GP decision blanks.

In `degraded` mode, the renderer may show an explicit evidence-gap row for
missing comparables, team, or other unavailable content. The gap must state
that evidence is unverified or pending and never counts as a verified row.
Do not invent content to satisfy layout.

Run `qa_deck.py --mode full|degraded|quick-screen`; add `--full` for the
Full-critical variant. Structural QA does not replace inspection of rendered
PNGs and layout JSON.
