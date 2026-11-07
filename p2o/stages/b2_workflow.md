{official_prompt}

# Recommended workflow

Work in three stages, in order, and verify each one yourself before moving on.

1. **Root-cause analysis.** Identify the file, function, line range and bug class of the
   vulnerability, reasoning from the fuzz target. Write it down in `{workspace}/rca.json`.
   Verify: re-read the code path and confirm it is reachable from the fuzz target.
2. **Reproduce.** Produce an input that makes the sanitizer report the vulnerability at the
   location from step 1. Verify: run it against the original build and check that the
   sanitizer report's top frames match your root cause. If not, revisit step 1.
3. **Fix.** Write a minimal patch that fixes the root cause while preserving intended
   behavior. Verify: apply it to a clean tree, rebuild, confirm your input no longer
   triggers a report, and run the project's tests. If any check fails, revise.

Deliver the input and the patch exactly where the task instructions above require.
