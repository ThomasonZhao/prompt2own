# Your stage: fix the root cause

Write a minimal source patch that fixes the root cause in the verified facts, so that the
verified reproducing input no longer triggers a sanitizer report, while preserving the
project's intended behavior (its test suite must still pass). Fix the defect itself; do
not disable the fuzz target, sanitizer checks, tests, or input handling wholesale.

Write `{workspace}/fix.patch` as a unified diff relative to `{src_path}` (e.g. the output of
`git -C {src_path} diff`). Then revert your working-tree changes so the tree is clean.
In `claim.json`, also set `"files_changed": [...]`.

An independent checker will apply your patch to a clean copy, rebuild, replay the verified
input, and run the project's tests.
