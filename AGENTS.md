## Work Procedure
Always follow this procedure when performing tasks:
1. **Plan the changes**: Before making any code modifications, create a detailed plan outlining what will be changed and why
2. **Get user confirmation**: Present the plan to the user and wait for explicit confirmation before proceeding
3. **Modify code**: Make the necessary code changes according to the confirmed plan
4. **Git Commit**: Commit changes with a Korean commit message that reflects the user's intent, at least **3 lines** long.
5. **Run and Verify**: Execute the code and perform MD5 checksum comparison between new outputs and reference files if pipelines or logic were changed.
6. **Finalize**:
   - Record **issues/problems** in `.codex\issue.md` (issue only).
   - Record **solutions/workarounds** in the global skill: `$troubleshooting`.
   - Clearly specify which skills were used in the final response.
   - Remove unnecessary files and folders.

----
# Environment rules
- Use the existing conda env: `module`
- Always run Python/pip as: `conda run -n module python` / `conda run -n module pip`.

----
# Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform imperative tasks into verifiable goals:

| Instead of... | Transform to... |
|--------------|-----------------|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug" | "Write a test that reproduces it, then make it pass" |
| "Refactor X" | "Ensure tests pass before and after" |

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let the LLM loop independently. Weak criteria ("make it work") require constant clarification.

----
# Codebase Rule: Configuration Management
- Do not restore or roll back files/code that you did not modify yourself. Never attempt to "fix" or revert changes in files unrelated to your current task, including using `git checkout`.
- Use `polars` then `pandas` library.
- Leverage Parallel Agent Execution: you can use multiple agents to handle different parts of the task concurrently. Proactively launch multiple independent tasks (search, read, validation) simultaneously to reduce turnaround time.
- When exporting CSV files that may include Korean text, use UTF-8 with BOM (`utf-8-sig`) by default.
- Unless the user instructs otherwise: **Bug fixes / corrections** to existing logic must **replace** the old logic and its outputs entirely (do not keep both). For **new logic additions**, ask the user whether the existing logic should be kept or removed before proceeding.




- User interest in web automation. 
- use playwright mcp when run the script. If it does not working, capture the screenshot and fix the problem. you can also read 'progress/' folder's file for finding a solution. 
- "Archive\work_flow.md" file is the reference of the web automation flow.



