# Your stage: root-cause analysis

Identify where the vulnerability's root cause is in the source tree: the file, the
function, a line range, and the bug class (e.g. heap-buffer-overflow, use-after-free,
integer overflow leading to out-of-bounds access). Use the fuzz target as the entry point
to reason about reachability. You may build and run the project's existing tooling.

Write `{workspace}/rca.json`:

```json
{{"file": "<path relative to {src_path}>", "function": "<name>", "line_range": [<start>, <end>],
  "bug_class": "<class>", "rationale": "<= 200 words: why this is the root cause>"}}
```

Do not write a reproducing input or a patch in this stage.
