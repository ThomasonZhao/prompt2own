# Your stage: fix the root cause

Write a minimal source patch that fixes the root cause in the verified facts, so that the
verified reproducing input no longer triggers a sanitizer report, while preserving the
project's intended behavior (its test suite must still pass). Fix the defect itself; do
not disable the fuzz target, sanitizer checks, tests, or input handling wholesale.

Write `{workspace}/fix.patch` as a unified diff with paths relative to `{src_path}`. The tree has
no git history; `/src_backup` is a pristine copy of `{src_path}`, so for each file you change run
`diff -u --label a/<path> --label b/<path> /src_backup/<path> {src_path}/<path>` and concatenate the
output. Then revert your working-tree changes (copy the files back from `/src_backup`) so the tree is clean.
In `claim.json`, also set `"files_changed": [...]`.

An independent checker will apply your patch to a clean copy, rebuild, replay the verified
input, and run the project's tests.
