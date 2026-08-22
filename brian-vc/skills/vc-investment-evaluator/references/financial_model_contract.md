# D3 financial model content contract

Use this contract for the required standalone financial model. Keep workbook
content and formulas independent from the selected report style.

Create `{company}_financial_model_vN.xlsx` with these seven core sheets in this order:

1. `說明`
2. `①假設參數`
3. `②公司BP`
4. `③獨立財測`
5. `④財務預測`
6. `⑤投報率分析`
7. `⑥CapEx與資金接力`

Requirements:

- Separate source inputs, editable assumptions, formulas, and outputs.
- Include conservative, base, and upside scenarios.
- Build revenue bottom-up with a model appropriate to the business.
- Express explicit bottom-up inputs under each scenario's
  `forecast_rows[].drivers` (for example product volume × price). Direct yearly
  revenue is also permitted when its source and owner are retained.
  `ratio_proxy_fallback` is allowed only when the data room cannot support a
  driver model and must be labeled as a limitation.
- Record the method separately for every scenario under
  `independent_forecast.scenario_methods`. A missing driver schedule in one
  scenario must not downgrade another scenario that has valid `forecast_rows`.
- If `financial_extensions.operating_drivers` is populated while a scenario
  still uses `ratio_proxy_fallback`, disclose a driver-integration gap. An
  extension sheet is evidence storage, not proof that the core forecast is
  driver-linked.
- Generate IRR and return-multiple matrices with `scripts/irr_matrix.py`.
- State units, periods, source files, and assumption owners.
- Label AI-generated forecasts as estimates rather than company guidance.
- Preserve formulas for auditability and verify that the workbook opens without
  formula errors.
- Apply the selected style only after calculations and validation pass.

Optional legacy-depth extensions follow the seven core sheets and are emitted
only from `financial_extensions`: `⑦營運量價`, `⑧債務折舊`,
`⑨營運資金三表`, `⑩估值敏感度`, and `⑪勾稽驗算`. Factbase extensions
use `7C_CF明細`, `7D_權益變動`, `7E_借款關係人`, and `7F_附註重要`.
The verifier checks the exact core prefix and allows schema-driven extensions;
company-specific builder forks are not allowed.
