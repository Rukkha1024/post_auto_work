# Playwright Environment Setup

This repo uses a dedicated conda env named `playwright` for browser automation.

## Create the environment

```bash
conda create -n playwright python=3.11 -y
conda install -n playwright -c conda-forge playwright nodejs -y
```

## Install browsers and system deps

```bash
sudo -E /home/alice/miniconda3/bin/conda run -n playwright \
  playwright install --with-deps chromium
```

## Open epost.go.kr (headful)

```bash
conda run -n playwright python - <<'PY'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://epost.go.kr", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    browser.close()
PY
```

## Playwright codegen (record actions)

```bash
conda run -n playwright playwright codegen https://epost.go.kr
```

## Playwright MCP (local install in .codex)

If you want the MCP server installed locally (not just via npx), run:

```bash
rm -rf .codex/node_modules .codex/node_modules.bak .codex/node_modules.partial
conda run -n playwright npm install --no-audit --no-fund
```

Then start the MCP server:

```bash
conda run -n playwright npx playwright-mcp
```
