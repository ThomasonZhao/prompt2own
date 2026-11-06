# INTERFACES

Code is authoritative: `p2o/types.py`, `p2o/harness.py`, `p2o/worker.py`,
`p2o/guards/base.py`. This file explains them. Keep both in sync.

## 1. Directory layout of results

```
results/
  budget.json                          # global spend (p2o/budget.py)
  runs/<config_id>/<task_id>/
    run.json                           # RunRecord (written at run_end)
    events.jsonl                       # every event
    ledger.jsonl                       # guard-confirmed facts only
    work/<stage>/<attempt>/            # copied out of the container after each attempt
      prompt.md  worker_stdout.json  claim.json  rca.json | poc.bin | fix.patch
    deliverables/poc.bin  deliverables/fix.patch
  grades/<config_id>/<task_id>.json    # GradeRecord (grader only)
  summary.csv                          # one row per (config, task, seed)
  figs/                                # analyze.py outputs
  fake/                                # same layout, for --fake runs only (own budget.json)
```

Every CLI command takes `--results <root>` (default `results/`). `--fake` defaults to
`results/fake/` and refuses the real root, so synthetic runs, grades and spend never mix
with real ones. `run --fake` uses the fixed demo script (reject -> retry -> accept);
`batch --fake` draws a deterministic random script per (config, task) (`p2o.fakes.varied_script`).

`events.jsonl` `run_start` carries `config_hash` and `templates_hash` (hash of every file in
the prompt dir); each `stage_attempt` carries the rendered prompt's `prompt_hash`.
`RunRecord.claimed_success` is the PATCH stage's own last claim (`done`), never an earlier
stage's; `final_guard_accept[stage]` is the stage guard's last verdict, ignoring
orchestrator rejections (schema / worker errors) where no guard ran.

## 2. Stage outputs (what a worker must write in its workspace)

| Stage | Files | Schema |
| --- | --- | --- |
| rca | `rca.json`, `claim.json` | `RCAResult`, `Claim` |
| poc | `poc.bin`, `poc_notes.md` (<=100 words), `claim.json` | `Claim` with `expected_crash_location` |
| patch | `fix.patch` (unified diff vs. original tree), `claim.json` | `Claim` with `files_changed` |
| single (B1/B2) | `poc.bin`, `fix.patch` where the harness expects them, `claim.json` | `Claim` |

```json
// rca.json
{"file": "src/foo.c", "function": "parse_header", "line_range": [120, 160],
 "bug_class": "heap-buffer-overflow", "rationale": "<= 200 words"}
// claim.json
{"done": true, "confidence": 0.7, "expected_crash_location": "parse_header",
 "files_changed": ["src/foo.c"], "notes": "optional, <= 50 words"}
```

Schema failure = rejected attempt with reason `schema_error: <pydantic message, truncated 200 chars>`; the guard is not called.

## 3. Guard I/O

```python
class GuardInput(BaseModel):
    task: Task; stage: Stage; attempt: int
    artifact_dir: Path          # host path to work/<stage>/<attempt>/
    claim: Claim
    facts: list[Fact]           # verified facts so far (e.g. the RCA, the verified PoC)

class Verdict(BaseModel):
    accept: bool
    reason: str                 # short, mechanical, NO ground truth; shown to next attempt
    evidence: dict              # structured; becomes Fact.data on accept
    guard: str                  # "<name>@<version>"
    seconds: float
```

Reason vocabulary (extend, don't paraphrase): `ok`, `schema_error:*`, `no_sanitizer_report`,
`crash_location_mismatch: got <frame>, claimed <fn>`, `run_timeout`, `patch_apply_failed`,
`build_failed`, `poc_still_crashes`, `tests_failed: <n>`, `guard_timeout`, `guard_error`.

## 4. HarnessAdapter (p2o/harness.py)

```python
class HarnessAdapter(Protocol):
    def prepare_task(self, task: Task, run_dir: Path) -> Workspace: ...
    def exec_worker(self, ws: Workspace, prompt: str, work_subdir: str,
                    env: dict[str, str], timeout_s: int) -> WorkerExec: ...
    def copy_out(self, ws: Workspace, container_path: str, host_dir: Path) -> None: ...
    def official_prompt(self, task: Task) -> str: ...      # harness's own e2e prompt (B1, B2)
    def run_poc(self, task: Task, poc_path: Path, build: BuildResult | None,
                timeout_s: int) -> PoCRun: ...           # fresh container each call
    def apply_patch_and_build(self, task: Task, patch_path: Path,
                              timeout_s: int) -> BuildResult: ...  # fresh container
    def run_tests(self, task: Task, build: BuildResult, timeout_s: int) -> TestResult: ...
    def write_deliverables(self, ws: Workspace, poc: Path | None, patch: Path | None) -> None: ...
    def teardown(self, ws: Workspace) -> None: ...
```

`PoCRun` = `{crashed: bool, sanitizer_report: str | None, top_frames: list[str], exit_code, timed_out, seconds}`.
`run_poc` with `build=None` uses the original vulnerable build; with a `BuildResult` from `apply_patch_and_build` it uses the patched build (used by `exec_patch`).

## 5. Worker (p2o/worker.py)

```python
class Worker(Protocol):
    def run(self, ws: Workspace, stage: Stage, attempt: int, prompt: str,
            artifact_dir: Path, prompt_hash: str) -> StageOutput: ...   # stage=SINGLE for B1/B2
```

`StageOutput` carries: `artifact_dir`, parsed `claim`/`rca` (or `schema_error`), `worker_error`, `usage`
(`tokens_in`, `tokens_out`, `tokens_cached`), `seconds`, `exit_code`, `prompt_hash`. The orchestrator renders the prompt; the worker only runs it.

`ClaudeCodeWorker` runs, inside the task container:
`claude -p "$(cat prompt.md)" --output-format json --max-turns <cfg> --dangerously-skip-permissions`
with `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` (= `$OPENROUTER_API_KEY`), `ANTHROPIC_API_KEY=""`
and every model alias (`ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`, `ANTHROPIC_DEFAULT_{HAIKU,SONNET,OPUS}_MODEL`,
`CLAUDE_CODE_SUBAGENT_MODEL`) set to the config's `model`, cwd = source tree,
and the stage workspace path given in the prompt. Usage is read from the JSON's `usage`
field; **USD is computed by `p2o/pricing.py`**, never from `total_cost_usd`. Check the
installed Claude Code's `--help` for the exact flag names before relying on them.

## 6. Config (configs/*.yaml -> RunConfig)

```yaml
id: p3
mode: stage_graph            # stage_graph | single_session
seed: 0
model: ${P2O_MODEL:-z-ai/glm-5.3-flash}           # OpenRouter slug
provider: ${P2O_PROVIDER:-openrouter}
base_url: ${ANTHROPIC_BASE_URL:-https://openrouter.ai/api}
prices_per_mtok:                                  # USD / 1M tokens, keyed by model slug;
  z-ai/glm-5.3-flash:           {input: 0.15,  cached_input: 0.03,  output: 0.50}
  deepseek/deepseek-v4.1-flash: {input: 0.051, cached_input: 0.018, output: 0.567}
caps: {wall_minutes: 45, max_tokens: ${P2O_TOKEN_CAP}, max_usd: 0.75}
worker: {max_turns: 60, stage_timeout_minutes: 15}
stages:
  rca:   {guard: null,       max_attempts: 1}
  poc:   {guard: exec_poc,   max_attempts: 3}
  patch: {guard: exec_patch, max_attempts: 3}
guards:
  exec_poc:   {timeout_s: 300, require_location_match: true, top_k_frames: 5}
  exec_patch: {timeout_s: 900, run_tests: true}
prompts: {dir: p2o/stages, single: null, suffix: claim_suffix.md}
```

`model` must be a key of `prices_per_mtok` (load fails otherwise); runtime code uses
`RunConfig.prices`, the entry for `model`. The table is identical across configs.

For `single_session`, `stages` is omitted and `prompts.single` names the template
(`null` = official harness prompt for B1, `b2_workflow.md` for B2).

## 7. summary.csv columns

`config, task_id, project, seed, status, stop_reason, failed_at, claimed_success,
s1, s2, s3, s4, usd, tokens_in, tokens_out, tokens_cached, minutes,
attempts_rca, attempts_poc, attempts_patch, poc_guard_accepts, poc_guard_rejects,
patch_guard_accepts, patch_guard_rejects, final_poc_guard_accept, final_patch_guard_accept,
model, provider, prompt_hash, config_hash`
