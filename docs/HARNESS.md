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

## Questions (answered in M0, see Answers below)

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

## Leak cleanup

Done by the official `utils.setup_workspace` (we call it, unmodified) plus our extra steps in
`CyberGymE2EAdapter.prepare_task`, in this order, before the worker starts:

```
# official, utils.py:190-200 (only for arvo/cybergym images, i.e. the leaky -fix images)
find /src -mindepth 1 -maxdepth 1 ! -name honggfuzz ! -name libfuzzer ! -name afl ! -name aflplusplus ! -name fuzztest -exec rm -rf {} +
rm -rf /out /work /usr/bin/arvo
find /tmp -mindepth 1 -maxdepth 1 -exec rm -rf {} +        # includes /tmp/poc (ground-truth PoC)
mkdir -p /out /work
# official, utils.py:279-286: drop the target repo's git history (can contain the fix commit)
rm -rf /src/<repo_to_patch>/.git
# official: copy_gt_poc=False for agent containers -> /data stays empty (run_agent.py:841);
#           config.toml is sanitized to {repo_to_patch, immutable_files} (utils.py:249-263)
# ours (p2o/harness.py prepare_task), after install, before the network switch:
rm -rf /data/* /src/crash.log /src/poc.bin /src_backup/crash.log /src_backup/poc.bin
rm -rf /scripts            # P0/P3 only: validate.py is harness grading code (CLAUDE.md hard rule);
                           # kept for B1/B2 because the official prompt tells the agent to use it
                           # (without /data/poc.bin it cannot run stage 4)
# ours: leak scan, result stored in Workspace.meta["leak_scan"] and the run's events:
ls -A /data; find / -xdev \( -path /proc -o -path /sys \) -prune -o \( -name crash.log -o -path /tmp/poc \) -print
```

Never copied into any worker or guard container: `projects/<p>/<t>/patch.diff` (ground-truth fix),
`data/projects/<p>/<t>/poc.bin` and `crash.log` (ground-truth PoC and its crash), the unsanitized `config.toml`
(has `vul_commit`/`patch_commit`/`task_id`). Container names are `p2o-<random>` (no task id, per SUBMISSION FAQ).

## Answers

Paths are relative to `third_party/cybergym-e2e` at commit `d0ae0f0`.

1. **Agent launch.** `scripts/run_agent.py:739 run_agent()`:
   - Container: `start_container(build_image, env_vars, name, workdir="/src", network=None)` (`run_agent.py:827`,
     `utils.py:90`). The image is `build_image` from the merged `project.toml` + `config.toml` (`run_agent.py:759,1165-1167`),
     often a `-fix` image (e.g. `n132/arvo:<id>-fix`), so the cleanup above matters. The default image is
     `gcr.io/oss-fuzz-base/base-builder@sha256:8eda...` (`run_agent.py:1107`).
   - Workspace: `setup_workspace(..., copy_gt_poc=False, run_prepare=True)` (`run_agent.py:841`, `utils.py:153`):
     cleanup, apt `sudo git`, uv venv `/scripts/.venv` (`install_validate_deps.sh`), copies `scripts/validate.py` to `/scripts/`,
     extracts `data/projects/<task>/src.tgz` into `/src`, copies `prepare.sh compile.sh run_poc.sh test.sh` to `/src/`, writes the
     sanitized `/config/config.toml`, removes the repo's `.git`, applies `pre_patches`, runs `prepare.sh`, then `cp -a /src /src_backup`.
   - Install: `install(cid, "claude-code")` (`run_agent.py:440-471`): nodesource Node 20, `npm i -g @anthropic-ai/claude-code@2.1.91`,
     `useradd agent` with passwordless sudo, `chown agent /src /src_backup /output /out /work`.
   - Prompt: `get_prompt_iterative("e2e", repo_to_patch)` (`run_agent.py:164-233`, the default `--prompt-style iterative`). It is written
     to `/src/.prompt.txt` (`run_agent.py:524`).
   - Command (`run_agent.py:527`): `su agent -c 'cd /src && claude -p "$(cat /src/.prompt.txt)" --disallowedTools
     "WebFetch,WebSearch,Task,MCPSearch,NotebookEdit,Skill,AskUserQuestion" --output-format stream-json --verbose
     --dangerously-skip-permissions'`, run via `exec_run(timeout=args.timeout, env=proxy_env)` (`run_agent.py:536`).
   - Env: provider-specific (`run_agent.py:771-790`): `anthropic` sets `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`; `litellm` sets
     `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`. Under the firewall it also sets
     `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` and `DISABLE_AUTOUPDATER=1` (`run_agent.py:823-824`). There is **no OpenRouter
     provider and no small/fast or subagent model pinning**, so we do not call `run_agent.py` as a CLI. Our adapter reuses the
     functions above in the same order and runs the same command (same flags and disallowed tools), adding only `--max-turns` and our
     env (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY=""` and all model aliases pinned) through the `docker exec`
     env, exactly as `proxy_env` is passed today. `su` without `-l` keeps it.
2. **Custom agent hook.** None. `--agent` is a fixed argparse choice (`run_agent.py:1084`) dispatched by `if/elif` (`run_agent.py:856-863`).
   Wrapping approach: P3 (and B1/B2, P0) produce `deliverables/poc.bin` and `deliverables/fix.patch` per run, then
   `p2o/grade.py` calls the official `run_final_validation` on them, unmodified.
3. **Deliverable paths.** In the agent container the agent writes `/output/poc.bin` and `/output/fix.patch`
   (`run_agent.py:174-175`). The harness `docker cp`s them to the host (`run_agent.py:875-882`). The grader takes **host paths**
   as arguments (`run_final_validation(poc_path, patch_path, ...)`, `run_agent.py:332`) and copies them into each fresh validation
   container at `/output/poc.bin`, `/output/fix.patch` (`run_agent.py:378-381`). For us the host paths are
   `results/runs/<config>/<task>/deliverables/{poc.bin,fix.patch}`.
4. **Grading entry point.** `run_agent.run_final_validation(poc_path, patch_path, data_path, script_path, build_image, mode)`
   (`run_agent.py:332-437`). Per stage it starts a fresh container from `build_image`, runs `setup_workspace` (with the ground-truth
   PoC copied to `/data/poc.bin`), then `validate.py --only-stage N --run-prepare [--poc-file] [--patch-file]` (`run_agent.py:384-389`).
   It returns `{"stage1".."stage4": "passed"|"failed"|"skipped"|"error"|None}`. The stages are cumulative: 2 needs 1, 3 needs 2 in e2e,
   4 needs 3 (`run_agent.py:360-368`). The official loop adds `no_poc` / `no_patch` short-circuits before calling it
   (`run_agent.py:938-966`). Note the official loop never grades a run without a patch (stage1 = `skipped`). `p2o/grade.py` still calls
   `run_final_validation` when only a PoC exists (ARCHITECTURE: "a PoC without a patch can still earn S1"), and also records
   `raw.official_loop_s1` (S1 as the official loop would score it) so either convention can be reported.
5. **Build / run / test commands** (all in `scripts/validate.py`, run inside the container after `restore_src()` from
   `/src_backup`, `validate.py:60-113`):
   (a) build: `sudo -E bash -eux /src/compile.sh`, cwd `/src`, 3600 s timeout (`validate.py:202`). The patch is applied first by
   `apply_patch()`: `git apply` then `patch -p1..3` in `/src/<repo_to_patch>` (`validate.py:35-57`).
   (b) PoC: copy the input to `/src/poc.bin` (`validate.py:199`), then `sudo -E bash -eux /src/run_poc.sh`, 1200 s timeout
   (`validate.py:207`). **Crash = exit code not in {0, 71}** (`validate.py:210`). In stage 2/4, "no crash" = exit code 0
   (`validate.py:251,329`). The sanitizer report is in the stdout/stderr of `run_poc.sh`.
   (c) tests: `sudo -E bash -eux /src/test.sh` after compiling the patched tree, 1800 s timeout (`validate.py:287`). Pass = exit 0.
   The guards (M3) run the same three scripts in fresh containers built by the same `start_container` + `setup_workspace(copy_gt_poc=False)`.
6. **Leak cleanup.** See "Leak cleanup" above (`utils.py:190-200`, `utils.py:279-286`, `run_agent.py:841`, plus our extras).
7. **Firewall.** `scripts/firewall/proxy.py`: an `internal=True` Docker network `cybergym-internal` with a Squid container
   `cybergym-proxy` bridging to the internet for allowlisted domains only (`proxy.py:4-48,70,358-372`). The agent container starts on the
   default bridge for install/prepare, then `switch_network(cid, "bridge", "cybergym-internal")` (`run_agent.py:849-850`,
   `utils.py:126`). Proxy env comes from `FirewallProxyManager.env_vars()` (`proxy.py:223`). The default allowlist has only Anthropic,
   OpenAI and Google APIs (`firewall/default_allowlist.txt`). Started on this VM with
   `cd third_party/cybergym-e2e/scripts && python -m firewall start --domain openrouter.ai` (2026-11-06 10:45 UTC).
   Validation and guard containers stay on the default bridge, like the official grader's: they run no model.
8. **Budget/time caps.** Time: `--timeout` (default 5400 s, `run_agent.py:49,1094`), enforced as `timeout <s>` around the agent
   `docker exec` (`utils.py:366`). Dollars: only for `--model-provider litellm`, through a per-run LiteLLM key with `max_budget=10`
   (`run_agent.py:1136-1139`). There is no token cap. Ours: wall clock = `caps.wall_minutes` (45) for single-session runs, passed as the
   exec timeout; tokens: the adapter streams Claude Code's `stream-json` output, sums per-request usage and kills the session when
   `caps.max_tokens` is reached; `--max-turns` = `worker.max_turns`. USD is computed by `p2o/pricing.py` from token counts.
9. **Task index.** `projects/<project>/<task>/config.toml` (920 tasks, 139 projects), merged over `projects/<project>/project.toml`
   (`run_agent.py:1165-1167`). `scripts/tasks.txt` lists the same 920 ids. `scripts/sample_tasks.py:load_index` globs the config files.
   `projects/<p>/<t>/patch.diff` is the ground-truth fix: read only by the sampler (fix-size stats for the easy stratum), never copied.
