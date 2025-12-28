@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
conda run -n playwright npx -y playwright-mcp %*
