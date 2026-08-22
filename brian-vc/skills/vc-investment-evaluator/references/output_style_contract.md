# Output style adapter contract

Read this file before rendering Stage F deliverables. Stage and artifact rules
come from `pipeline_contract.md`; this file owns presentation rules only.

## Boundary

Keep analysis and visual presentation separate:

- The core workflow owns facts, calculations, citations, conflicts, missing-data labels, expert outputs, and final section order.
- A style owns typography, color, spacing, chart treatment, table appearance, cover treatment, and reusable templates.
- A style must never change calculations, suppress required content, or reinterpret evidence.

Finish and freeze the canonical analytical artifacts before loading a style:

1. Factbase and FactSheet
2. Coverage and conflict logs
3. Expert raw files and `DECK_EXPORT` blocks
4. CitationTable
5. IRR and return-multiple matrices
6. ContentFreeze

## Resolution

Resolve a style with the plugin-level helper:

```powershell
python ../../scripts/resolve_style.py neutral
python ../../scripts/resolve_style.py C:\path\to\my-style
```

Accept a built-in style id, a `style.json` path, or a directory containing
`style.json`. The optional `VC_REPORT_STYLE` environment variable may provide a
default. If no style is requested, use `neutral`.

Third-party styles should copy the shape of
`assets/styles/neutral/` and validate against
`assets/styles/style.schema.json`.

## Required report variants

- **Executive version**: concise investment thesis, terms, key evidence,
  financials, valuation, return analysis, conditions, and decision framework.
- **Full-critical version**: all executive content plus conflicts, missing data,
  red flags, RedTeam findings, failure paths, and management questions.

The style may add presentation-only pages but must not remove required content.

## Fallback

If the requested style cannot be resolved or rendered:

1. Preserve the canonical analytical artifacts.
2. Report the style failure clearly.
3. Render with the neutral style when possible.
4. Do not mark the overall analytical workflow failed solely because an
   optional custom style is unavailable.
