# Playwright Environment Setup (Blank WSL + Conda Only)

Assumptions:
- Only conda is installed in WSL.
- You have sudo privileges for installing system dependencies.
- For headful (GUI) browsers, you have WSLg (Win11) or an X server; otherwise use headless.

This repo uses a dedicated conda env named `playwright` for browser automation.

## Create the environment

```bash
conda create -n playwright python=3.11 -y
conda install -n playwright -c conda-forge playwright nodejs -y
```

## Install Python packages

Install required Python packages for the project:

```bash
conda run -n playwright pip install playwright>=1.40.0 polars>=0.20.0 PyYAML>=6.0
```

Or install from `requirements.txt`:

```bash
conda run -n playwright pip install -r requirements.txt
```

Packages installed:
- `playwright>=1.40.0`: Browser automation
- `polars>=0.20.0`: Data processing (Excel reading)
- `PyYAML>=6.0`: Configuration file management

## Install browsers and system deps

This step installs Chromium and required Linux libraries.

```bash
sudo -E $(conda info --base)/bin/conda run -n playwright \
  playwright install --with-deps chromium
```

## Open epost.go.kr (headful)

Requires WSLg or an X server. If you do not have a GUI, use the headless example below.

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

## Open epost.go.kr (headless)

```bash
conda run -n playwright python - <<'PY'
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://epost.go.kr", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    browser.close()
PY
```

## Playwright codegen (record actions)

Codegen requires a GUI (headful).

### Basic usage

```bash
conda run -n playwright playwright codegen https://epost.go.kr
```

### Generate Python code with output file

Use flags to specify target language and output file:

```bash
npx playwright codegen --target=python --output tests/naver_test https://www.naver.com/
```

Or with conda:

```bash
conda run -n playwright npx playwright codegen --target=python --output tests/naver_test https://www.naver.com/
```

Flags:
- `--target=python`: Generate Python code (default is JavaScript)
- `--output <file>`: Save generated code to specified file
- Last argument: URL to navigate to

### Run generated test

After generating a test file, run it with:

```bash
conda run -n playwright python tests/파일이름.py
```

Example:

```bash
conda run -n playwright python tests/naver_test.py
```

## Playwright MCP (local install in .codex)

If you want the MCP server installed locally (not just via npx), run this in the repo root:

```bash
rm -rf .codex/node_modules .codex/node_modules.bak .codex/node_modules.partial
conda run -n playwright npm install --no-audit --no-fund
```

Then start the MCP server:

```bash
conda run -n playwright npx playwright-mcp
```

