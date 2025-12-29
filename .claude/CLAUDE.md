## Work Procedure
Always follow this procedure when performing tasks:
1. **Plan the changes**: Before making any code modifications, create a detailed plan outlining what will be changed and why
2. **Get user confirmation**: Present the plan to the user and wait for explicit confirmation before proceeding
3. **Modify code**: Make the necessary code changes according to the confirmed plan
4. **Git commit in Korean**: Commit your changes with a Korean commit message
5. **Run the modified code**: Execute the modified code to verify your work


---
## Environment rules
- Use the existing conda env: `playwright` (WSL2).
- Always run Python/pip as: `conda run -n playwright python` / `conda run -n playwright pip`.
- **Do not** create or activate any `venv` or `.venv` or run `uv venv`.
- If a package is missing, prefer:
  1) `mamba/conda install -n playwright <pkg>` (if available)
  2) otherwise `conda run -n playwright pip install <pkg>`
- Before running Python, verify the interpreter path with:
  `conda run -n playwright python -c "import sys; print(sys.executable)"`

---
## **Codebase Rule: Configuration Management**
- when refactoring existing pipelines or logic, perform MD5 checksum comparison between new outputs and reference files as a validation step. 
- Use "polars" then "pandas" library. 

### **Core Principle: Centralized Control**
The primary goal is to centralize shared values across multiple scripts. This ensures consistency and minimizes code modifications when parameters change.

### **Items to Include in Config Files:**
1.  **Paths and Directories:** Define paths to data, logs, and outputs (e.g., `RAW_DATA_DIR`, `OUTPUT_DIR`).
2.  **File Identification Patterns:** Store regex or fixed strings for parsing filenames (e.g., `VELOCITY_PATTERN`, `TRIAL_PATTERNS`).
3.  **Data Structure Definitions:** List column names for data extraction or processing (e.g., `FORCEPLATE_COLUMNS`, `METADATA_COLS`).
4.  **Fixed Processing Constants:** Define constants derived from the experimental setup (e.g., `FRAME_RATIO`, `FORCEPLATE_DATA_START`).
5.  **Tunable Analysis Parameters:** Specify parameters that researchers might adjust (e.g., filter cutoffs, normalization methods).
6.  **Shared Texts:** Centralize common log messages or report headers (e.g., `STAGE03_SUMMARY_HEADER`).

