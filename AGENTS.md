## Work Procedure
Always follow this procedure when performing tasks:
1. **Plan the changes**: Before making any code modifications, create a detailed plan outlining what will be changed and why
2. **Get user confirmation**: Present the plan to the user and wait for explicit confirmation before proceeding
3. **Modify code**: Make the necessary code changes according to the confirmed plan
4. **Git commit in Korean**: Commit your changes with a Korean commit message
5. **Run the modified code**: Execute the modified code to verify your work


---
## Environment rules
- Use the existing conda env: `playwright`.
- Always run Python/pip as: `conda run -n playwright python` / `conda run -n playwright pip`.
- **Do not** create or activate any `venv` or `.venv` or run `uv venv`.
- If a package is missing, prefer: `conda run -n playwright pip install <pkg>`
- Before running Python, verify the interpreter path with:
  `conda run -n playwright python -c "import sys; print(sys.executable)"`

---
## **Codebase Rule: Configuration Management**
- when refactoring existing pipelines or logic, perform MD5 checksum comparison between new outputs and reference files as a validation step. 
- Use "polars" then "pandas" library. 

### **Core Principle: Centralized Control**
The primary goal is to centralize shared values across multiple scripts. This ensures consistency and minimizes code modifications when parameters change.

----
- User interest in web automation. 
- For web-related tasks, always use Playwright CLI and the Playwright CLI skill.
- if it does not working, capture the screenshot and fix the problem. you can also read 'progress/' folder's file for finding a solution. 
- You can change the automation script to a different language if you prefer. The only reason it is currently written in Python is because it needs to interact with Excel files for web automation purpose. 
- "Archive\work_flow.md" file is the reference of the web automation flow.
