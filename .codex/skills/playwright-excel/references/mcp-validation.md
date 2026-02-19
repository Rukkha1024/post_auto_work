# Playwright CLI Validation (Required)

## Ensure Playwright CLI + skill are ready
- Verify CLI access: `playwright-cli --help` (or `npx playwright-cli --help`).
- Install local editor-assistant skills when needed: `playwright-cli install --skills`.
- Use one named session for the entire validation run (for example, `excel-validation`).

## Preflight
- Load Excel data and print keys (mask secrets).
- Open the target URL in one session and confirm the page loads:
  - `playwright-cli -s=excel-validation open <url> --headed`
  - `playwright-cli -s=excel-validation snapshot`

## Validate each step
Use the same pattern for every action (fill/click):
1. Take a snapshot before the action.
2. Perform the action with CLI commands.
3. For `.fill()`, read back the field value and compare with the Excel value.
4. Take a screenshot after the action.
5. Capture a final visual summary with `vision` at key checkpoints.

```text
playwright-cli -s=excel-validation snapshot
playwright-cli -s=excel-validation click "<locator>"
playwright-cli -s=excel-validation type "<locator>" "<value>"
playwright-cli -s=excel-validation fill "<locator>" "<value>"
playwright-cli -s=excel-validation wait-for "<locator-or-text>"
playwright-cli -s=excel-validation execute "return document.querySelector('<selector>')?.value"
playwright-cli -s=excel-validation screenshot
playwright-cli -s=excel-validation vision
```

## Error handling
On any exception:
- Capture `snapshot`, `screenshot`, and `vision`.
- Report the mismatch and re-raise the error.

## Report
Write a markdown report that includes:
- Script path, Excel path, target subject, timestamp
- Excel keys loaded (mask secrets)
- Step-by-step status + screenshots
- Visual summary notes from CLI checkpoints
