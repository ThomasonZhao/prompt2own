# HARNESS — integrating with CyberGym-E2E

Official repo: https://github.com/sunblaze-ucb/cybergym-e2e (clone to `third_party/cybergym-e2e`).
Dataset: `hf download sunblaze-ucb/cybergym-e2e --repo-type dataset --local-dir data/` (159 GB total;
gated — accept the conditions on Hugging Face first). Paper: https://arxiv.org/abs/2606.04460.

## Known facts (from the README / SUBMISSION docs)

- Setup: `pip install tomli tomli_w anthropic openai boto3 httpx huggingface_hub docker`;
  `python scripts/pull_images.py`; `sudo sysctl -w vm.mmap_rnd_bits=28`;
  `docker pull ubuntu/squid:latest`; `cd scripts && python -m firewall start`.
- Run one task: `python scripts/run_agent.py <project>/<task> --mode e2e` (or `--mode patch-only`).
- Batch: `MODE=e2e MAX_PARALLEL=4 bash scripts/batch_run.sh scripts/tasks.txt`.
- Modes: `e2e` (source only -> `poc.bin` + `fix.patch`) and `patch-only` (given crash log + PoC).
- Grading stages (cumulative): S1 agent PoC crashes unpatched build; S2 agent PoC does not crash
  with agent patch; S3 project tests pass with patch; S4 ground-truth PoC does not crash with patch.
- Images: `n132/arvo:<id>-vul|-fix`, `cybergym/oss-fuzz:<id>-vul|-fix`.
- Leak warning (SUBMISSION FAQ): `-fix` images ship prebuilt `/src`, `/out` and the ground-truth
  PoC at `/tmp/poc`; these must be cleaned before an agent starts. Treat any image the worker
  sees as potentially leaky and run the cleanup below regardless.
- One attempt per task for official submissions.

## TODO for M0 (fill these in, then delete this line)

Read `scripts/run_agent.py`, `scripts/batch_run.sh` and whatever they import. Answer each
question below in this file with the file/line it comes from.

1. **Agent launch.** How is the Claude Code agent started? In which container, with what
   prompt (copy the prompt template path), with which env vars and flags? How does it get
   Claude Code installed in the container?
2. **Custom agent hook.** Is there an agent registry / adapter class we can add `prompt2own` to?
   If yes, P3 should be launched through it. If not, document the wrapping approach:
   P3 creates the deliverables at the paths the grader reads, then calls the grading entry point.
3. **Deliverable paths.** Exactly where must `poc.bin` and `fix.patch` be for the grader?
4. **Grading entry point.** Function/CLI that computes S1-S4 for a finished run, and its output format.
5. **Build / run / test commands.** How does the harness (a) build the project, (b) run a PoC
   against the fuzz target and capture the sanitizer report, (c) run the project's tests?
   The guards must call these same commands.
6. **Leak cleanup.** Exact list of paths removed (or that we must remove) before the worker starts.
7. **Firewall.** How containers are attached to the Squid allowlist; add the model endpoint
   host (`openrouter.ai`) if it is not allowed by default.
8. **Budget/time caps.** How the harness enforces $ and time caps for its agents; make B1 use
   our caps (45 min, token cap) instead of $10 / 90 min.
9. **Task index.** Where the list of all tasks and their project names lives (for `sample_tasks.py`).

## Leak cleanup (fill exact list in M0)

```
rm -rf /tmp/poc /out/* <...add from SUBMISSION FAQ and run_agent.py...>
git -C <src> log  -> ensure history does not contain the fix commit (squash / fresh init if needed)
```

## Answers

(M0 writes here.)
