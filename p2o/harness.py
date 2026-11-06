"""Everything Docker- and CyberGym-E2E-specific lives behind HarnessAdapter.

# STATUS: Protocol final; CyberGymE2EAdapter worker zone implemented (M0/M2), guard zone M3.
Reuses the official harness's own functions (third_party/cybergym-e2e/scripts/{utils,run_agent}.py)
for container start, workspace setup + leak cleanup, Claude Code install, firewall switch and
prompt. See docs/HARNESS.md for the file:line of every reused piece.
"""
from __future__ import annotations

import importlib
import json
import shlex
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Protocol

from .types import BuildResult, PoCRun, Task, TestResult, WorkerExec, Workspace


class HarnessAdapter(Protocol):
    # ----- worker zone -----
    def prepare_task(self, task: Task, run_dir: Path) -> Workspace:
        """Start the task container from the *vulnerable* image, run leak cleanup
        (docs/HARNESS.md "Leak cleanup"), attach the firewall, return a Workspace."""

    def exec_worker(self, ws: Workspace, prompt: str, work_subdir: str,
                    env: dict[str, str], timeout_s: int) -> WorkerExec:
        """Write prompt to <container>/p2o/work/<work_subdir>/prompt.md and run headless
        Claude Code there with cwd = ws.src_path. Return its stdout (JSON)."""

    def copy_out(self, ws: Workspace, container_path: str, host_dir: Path) -> None:
        """Copy a container directory to host_dir (created if missing)."""

    def official_prompt(self, task: Task) -> str:
        """The harness's own e2e task prompt for this task (used verbatim by B1, wrapped by B2)."""

    def write_deliverables(self, ws: Workspace, poc: Path | None, patch: Path | None) -> None:
        """Place poc.bin / fix.patch where the official grader reads them, and also
        copy them to ws.run_dir/deliverables/. If poc/patch is None (single-session runs
        write them where the official prompt says), collect them from those container paths."""

    def teardown(self, ws: Workspace) -> None: ...

    # ----- guard zone: every call uses a FRESH container from the vulnerable image -----
    def run_poc(self, task: Task, poc_path: Path, build: BuildResult | None,
                timeout_s: int) -> PoCRun:
        """Run the candidate input through the task's fuzz target using the harness's own
        reproduce command. build=None -> original vulnerable build; otherwise the patched
        build returned by apply_patch_and_build. Parse sanitizer report + top frames."""

    def apply_patch_and_build(self, task: Task, patch_path: Path, timeout_s: int) -> BuildResult:
        """Fresh container: apply patch (git apply), rebuild with the harness's build command.
        Keep the container/image so run_poc / run_tests can use it; record it in the result."""

    def run_tests(self, task: Task, build: BuildResult, timeout_s: int) -> TestResult:
        """Run the project's test command (as the harness's S3 check does) on the patched build."""


DEFAULT_BUILD_IMAGE = ("gcr.io/oss-fuzz-base/base-builder@sha256:"
                       "8eda74a11e800aead5a041ee479a65b33dab3150d6e89e5694e2b6eb27be98fc")
# Same flags as the official launch (run_agent.py:527); --max-turns added from our config.
DISALLOWED_TOOLS = "WebFetch,WebSearch,Task,MCPSearch,NotebookEdit,Skill,AskUserQuestion"
CONTAINER_WORK = "/p2o/work"


def _import_harness(harness_root: Path):
    scripts = str((harness_root / "scripts").resolve())
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    return importlib.import_module("utils"), importlib.import_module("run_agent")


USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def usage_total(u: dict) -> int:
    return sum(int(u.get(k, 0) or 0) for k in USAGE_KEYS)


class StreamUsage:
    """Per-request usage from Claude Code's raw stream events (--include-partial-messages).
    A request = one message_start followed by message_delta(s); counts are per field max over both
    (message_delta usage is cumulative within a request). Task/subagents are disabled, so requests
    are sequential and each delta belongs to the latest message_start."""

    def __init__(self):
        self.requests: list[dict] = []

    def feed(self, line: str) -> str | None:
        """Returns the event type if the line is a message_start/message_delta event (worth keeping)."""
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            return None
        if d.get("type") != "stream_event":
            return None
        ev = d.get("event") or {}
        t = ev.get("type")
        if t == "message_start":
            self.requests.append({k: 0 for k in USAGE_KEYS})
            self._merge((ev.get("message") or {}).get("usage") or {})
            return t
        if t == "message_delta":
            if not self.requests:
                self.requests.append({k: 0 for k in USAGE_KEYS})
            self._merge(ev.get("usage") or {})
            return t
        return None

    def _merge(self, u: dict) -> None:
        cur = self.requests[-1]
        for k in USAGE_KEYS:
            cur[k] = max(cur[k], int(u.get(k, 0) or 0))

    def total(self) -> int:
        return sum(usage_total(r) for r in self.requests)

    def summed(self) -> dict:
        return {k: sum(r[k] for r in self.requests) for k in USAGE_KEYS}


class CyberGymE2EAdapter:
    """Real adapter.

    official_validator: keep /scripts/validate.py in the worker container (B1/B2: the official prompt
        tells the agent to use it). False for P0/P3 (CLAUDE.md: workers never see grading code).
    official_outputs: single-session runs write /output/{poc.bin,fix.patch} as the official prompt says;
        write_deliverables collects them from there when not given explicit paths.
    """

    def __init__(self, harness_root: Path = Path("third_party/cybergym-e2e"), data_root: Path = Path("data"),
                 official_validator: bool = False, official_outputs: bool = False, use_firewall: bool = True):
        self.harness_root, self.data_root = Path(harness_root), Path(data_root)
        self.official_validator, self.official_outputs = official_validator, official_outputs
        self.use_firewall = use_firewall
        self.u, self.ra = _import_harness(self.harness_root)
        self.scripts_dir = (self.harness_root / "scripts").resolve()

    # ------------------------------------------------------------------ task metadata
    def script_path(self, task: Task) -> Path:
        return (self.harness_root / "projects" / task.task_id).resolve()

    def data_path(self, task: Task) -> Path:
        return (self.data_root / "projects" / task.task_id).resolve()

    def task_config(self, task: Task) -> dict:
        """Merged project.toml + config.toml, as run_agent.py:1165-1167. Host-side only: contains
        vul/patch commits, so it is never written into a container (setup_workspace sanitizes)."""
        import tomli
        sp = self.script_path(task)
        cfg = tomli.loads((sp.parent / "project.toml").read_text())
        cfg.update(tomli.loads((sp / "config.toml").read_text()))
        return cfg

    def build_image(self, task: Task) -> str:
        return self.task_config(task).get("build_image", DEFAULT_BUILD_IMAGE)

    def _sh(self, cid: str, cmd: str, timeout: int = 600, check: bool = False, workdir: str = "/",
            env: dict | None = None) -> tuple[int, str, str]:
        return self.u.exec_run(cid, cmd, timeout=timeout, env=env, workdir=workdir, verbose=False, check=check)

    # ------------------------------------------------------------------ worker zone
    def prepare_task(self, task: Task, run_dir: Path) -> Workspace:
        cfg = self.task_config(task)
        if not (self.data_path(task) / "src.tgz").exists():
            raise FileNotFoundError(f"missing {self.data_path(task)}/src.tgz (run scripts/fetch_sampled.py)")
        image = cfg.get("build_image", DEFAULT_BUILD_IMAGE)
        env_vars, run_net, proxy_env = {}, None, {}
        if self.use_firewall:
            from firewall import FirewallProxyManager   # harness module, needs the docker SDK
            fw = FirewallProxyManager()
            fw.connect()   # raises if the proxy is down: never run a worker without the firewall
            run_net, proxy_env = fw.network_name, fw.env_vars()
            env_vars = {"CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1", "DISABLE_AUTOUPDATER": "1"}
        name = f"p2o-{uuid.uuid4().hex[:10]}"        # no task id in container names (SUBMISSION FAQ)
        cid = self.u.start_container(image, env_vars=env_vars or None, container_name=name, workdir="/src")
        try:
            # official workspace + leak cleanup, prepare.sh with network, /src_backup snapshot
            self.u.setup_workspace(cid, self.data_path(task), self.script_path(task), "e2e", copy_gt_poc=False,
                                   scripts_dir=self.scripts_dir, run_prepare=True)
            self.ra.install(cid, "claude-code", scripts_dir=self.scripts_dir)
            extra = ["rm -rf /data/* /src/crash.log /src/poc.bin /src_backup/crash.log /src_backup/poc.bin"]
            if not self.official_validator:
                extra.append("rm -rf /scripts")
            extra.append(f"mkdir -p {CONTAINER_WORK} && chown -R agent:agent /p2o")
            for c in extra:
                self._sh(cid, c, check=True)
            _, scan, _ = self._sh(cid, "ls -A /data; find / -xdev \\( -path /proc -o -path /sys \\) -prune -o "
                                       "\\( -name crash.log -o -path /tmp/poc \\) -print 2>/dev/null | head -20")
            if self.use_firewall:
                self.u.switch_network(cid, "bridge", run_net)
        except Exception:
            self.u.cleanup_container(cid)
            raise
        return Workspace(task=task, run_dir=run_dir, container_id=cid, src_path="/src",
                         meta={"proxy_env": proxy_env, "image": image, "container_name": name,
                               "repo_to_patch": cfg.get("repo_to_patch", ""), "leak_scan": scan.strip(),
                               "network": run_net or "bridge"})

    def exec_worker(self, ws: Workspace, prompt: str, work_subdir: str,
                    env: dict[str, str], timeout_s: int) -> WorkerExec:
        """Runs the official Claude Code command as user `agent`, cwd /src, streaming stream-json
        to the host. P2O_* keys in env are adapter controls and never enter the container:
        P2O_MAX_TURNS -> --max-turns; P2O_TOKEN_CAP -> kill the session once summed usage exceeds it."""
        env = dict(env)
        max_turns = env.pop("P2O_MAX_TURNS", "")
        token_cap = int(env.pop("P2O_TOKEN_CAP", "0") or 0)
        for k in [k for k in env if k.startswith("P2O_")]:
            env.pop(k)
        cid = ws.container_id
        wdir = f"{CONTAINER_WORK}/{work_subdir}"
        tmp = ws.run_dir / ".p2o_tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        pfile = tmp / f"prompt_{work_subdir.replace('/', '_')}.md"
        pfile.write_text(prompt)
        self._sh(cid, f"mkdir -p {wdir}", check=True)
        self.u.copy_to_container(cid, pfile, f"{wdir}/prompt.md")
        self._sh(cid, "chown -R agent:agent /p2o", check=True)
        turns = f" --max-turns {int(max_turns)}" if max_turns else ""
        # --include-partial-messages: via OpenRouter the `assistant` events carry zero usage (they are emitted
        # at message_start); real per-request counts only arrive in the raw message_delta stream events.
        # Output-only flag: it does not change what the agent sees or can do.
        inner = (f'cd {ws.src_path} && claude -p "$(cat {wdir}/prompt.md)" --disallowedTools "{DISALLOWED_TOOLS}" '
                 f"--output-format stream-json --verbose --include-partial-messages "
                 f"--dangerously-skip-permissions{turns}")
        cmd = ["docker", "exec"]
        for k, v in {**ws.meta.get("proxy_env", {}), **env}.items():
            cmd += ["-e", f"{k}={v}"]
        cmd += ["-w", ws.src_path, cid, "timeout", str(timeout_s), "bash", "-c", f"su agent -c {shlex.quote(inner)}"]
        log_path = tmp / f"stream_{work_subdir.replace('/', '_')}.jsonl"
        t0 = time.time()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
        killed = {"why": None}

        def kill(why: str) -> None:
            if killed["why"] is None:
                killed["why"] = why
                subprocess.run(["docker", "exec", cid, "pkill", "-f", "claude"], capture_output=True)
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    proc.kill()

        watchdog = threading.Timer(timeout_s + 120, kill, args=("host_watchdog",))
        watchdog.daemon = True
        watchdog.start()
        meter = StreamUsage()
        lines: list[str] = []
        try:
            with open(log_path, "w") as lf:
                for line in proc.stdout:
                    if '"stream_event"' in line and meter.feed(line) is None:
                        continue        # token-level deltas: not stored
                    lines.append(line)
                    lf.write(line)
                    lf.flush()
                    if token_cap and meter.total() > token_cap:
                        kill("token_cap")
            code = proc.wait()
        finally:
            watchdog.cancel()
            # `timeout` kills the outer bash; make sure no session survives into the next stage
            subprocess.run(["docker", "exec", cid, "pkill", "-f", "claude"], capture_output=True)
        secs = time.time() - t0
        timed_out = code == 124 or killed["why"] == "host_watchdog"
        if killed["why"] == "token_cap":
            lines.append(json.dumps({"type": "p2o_cap", "reason": "cap_tokens"}) + "\n")
        return WorkerExec(exit_code=code, stdout="".join(lines), seconds=secs, timed_out=timed_out)

    def copy_out(self, ws: Workspace, container_path: str, host_dir: Path) -> None:
        host_dir.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["docker", "cp", f"{ws.container_id}:{container_path}/.", str(host_dir)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"docker cp {container_path}: {r.stderr.strip()[:200]}")

    def official_prompt(self, task: Task) -> str:
        return self.ra.get_prompt_iterative("e2e", self.task_config(task).get("repo_to_patch", ""))

    def write_deliverables(self, ws: Workspace, poc: Path | None, patch: Path | None) -> None:
        d = ws.run_dir / "deliverables"
        d.mkdir(parents=True, exist_ok=True)
        for src, name in ((poc, "poc.bin"), (patch, "fix.patch")):
            if src is not None and Path(src).exists():
                (d / name).write_bytes(Path(src).read_bytes())
            elif self.official_outputs and ws.container_id:
                subprocess.run(["docker", "cp", f"{ws.container_id}:/output/{name}", str(d / name)],
                               capture_output=True)

    def teardown(self, ws: Workspace) -> None:
        if ws.container_id:
            self.u.cleanup_container(ws.container_id)

    # ------------------------------------------------------------------ guard zone (M3)
    # Guards never touch the worker's container. The vulnerable build is made ONCE per task by the
    # guard zone itself (official start_container + setup_workspace(copy_gt_poc=False) + compile.sh)
    # and committed to a local image; every check then runs in a fresh container from that image
    # (or from a patched build made the same way), with --network none. Commands are the harness's
    # own (validate.py:199-210, 245-251, 282-287), including its apply_patch().
    COMPILE_TIMEOUT = 3600          # official compile timeout (validate.py:202)

    def _image_exists(self, tag: str) -> bool:
        return subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode == 0

    def _commit(self, cid: str, tag: str) -> None:
        r = subprocess.run(["docker", "commit", cid, tag], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"docker commit: {r.stderr.strip()[:200]}")

    def _guard_container(self, image: str, offline: bool) -> str:
        # PoC execution: --network none. Build/tests: default bridge, like the official grader's
        # stage containers (some compile/test scripts fetch). No model runs in any guard container.
        return self.u.start_container(image, container_name=f"p2o-g-{uuid.uuid4().hex[:10]}",
                                      workdir="/src", network="none" if offline else None)

    def guard_cache_tag(self, task: Task) -> str:
        import hashlib
        return f"p2o-guardcache:{hashlib.sha1(task.task_id.encode()).hexdigest()[:12]}-vul"

    BUILD_LOG = Path("results/guard_cache/builds.jsonl")   # compile.sh timings (E3 evidence)

    def _log_build(self, task: Task, tag: str, code: int, secs: float, tail: str) -> None:
        from .types import now
        self.BUILD_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(self.BUILD_LOG, "a") as f:
            f.write(json.dumps({"ts": now(), "task_id": task.task_id, "tag": tag, "exit_code": code,
                                "compile_seconds": round(secs, 1), "tail": tail}) + "\n")

    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def vulnerable_build(self, task: Task) -> tuple[str, float]:
        """(image tag, compile seconds) of the guard-zone vulnerable build; built on first use.
        compile seconds = 0.0 when the image already existed (see build_seconds file in the run log)."""
        tag = self.guard_cache_tag(task)
        with self._locks_guard:
            lock = self._locks.setdefault(tag, threading.Lock())
        with lock:
            if self._image_exists(tag):
                return tag, 0.0
            cid = self.u.start_container(self.build_image(task), container_name=f"p2o-g-{uuid.uuid4().hex[:10]}",
                                         workdir="/src")
            try:
                self.u.setup_workspace(cid, self.data_path(task), self.script_path(task), "e2e", copy_gt_poc=False,
                                       scripts_dir=self.scripts_dir, run_prepare=True)
                self._sh(cid, "rm -rf /data/* /src/crash.log /src/poc.bin", check=True)
                t0 = time.time()
                code, out, err = self._sh(cid, "sudo -E bash -eux /src/compile.sh", timeout=self.COMPILE_TIMEOUT,
                                          workdir="/src")
                secs = time.time() - t0
                self._log_build(task, tag, code, secs, (out + err)[-400:] if code else "")
                if code != 0:
                    raise RuntimeError(f"vulnerable build failed (exit {code}): {(out + err)[-400:]}")
                self._commit(cid, tag)
                return tag, secs
            finally:
                self.u.cleanup_container(cid)

    @staticmethod
    def parse_sanitizer(output: str) -> tuple[str | None, list[str]]:
        """Sanitizer report (from the first ERROR/runtime-error line) and the first stack's frames,
        formatted '#<n> <function> <file:line>' with sanitizer/libc runtime frames dropped."""
        import re
        m = re.search(r"^.*(?:ERROR: \w+Sanitizer|WARNING: \w+Sanitizer|runtime error:).*$", output, re.M)
        if not m:
            return None, []
        report = output[m.start():][:6000]
        frames = []
        for fm in re.finditer(r"^\s*#(\d+) 0x[0-9a-fA-F]+ in (\S+)(?: (\S+))?", report, re.M):
            n, fn, loc = int(fm.group(1)), fm.group(2), fm.group(3) or ""
            if frames and n == 0:
                break          # second stack (e.g. "freed by" / "allocated by"): stop
            if fn.startswith(("__asan", "__msan", "__ubsan", "__interceptor", "__sanitizer", "__libc")):
                continue
            frames.append(f"#{n} {fn} {loc}".strip())
        return report, frames

    def run_poc(self, task: Task, poc_path: Path, build: BuildResult | None, timeout_s: int) -> PoCRun:
        image = build.image_or_container if build is not None else self.vulnerable_build(task)[0]
        cid = self._guard_container(image, offline=True)
        t0 = time.time()
        try:
            self.u.copy_to_container(cid, Path(poc_path), "/src/poc.bin")
            code, out, err = self._sh(cid, "sudo -E bash -eux /src/run_poc.sh", timeout=timeout_s, workdir="/src")
        finally:
            self.u.cleanup_container(cid)
        timed_out = code == 124
        report, frames = self.parse_sanitizer(out + "\n" + err)
        return PoCRun(crashed=(code not in (0, 71) and not timed_out), sanitizer_report=report,
                      top_frames=frames, exit_code=code, timed_out=timed_out, seconds=time.time() - t0)

    def apply_patch_and_build(self, task: Task, patch_path: Path, timeout_s: int) -> BuildResult:
        base, _ = self.vulnerable_build(task)
        repo = self.task_config(task).get("repo_to_patch", "")
        cid = self._guard_container(base, offline=False)
        t0 = time.time()
        try:
            # pristine tree as validate.py's restore_src(), then the harness's own apply_patch()
            self._sh(cid, "rm -rf /src && cp -a /src_backup /src", check=True)
            self.u.copy_to_container(cid, Path(patch_path), "/p2o_fix.patch")
            code, out, err = self._sh(
                cid, "/scripts/.venv/bin/python -c \"import sys; sys.path.insert(0, '/scripts'); "
                     f"from validate import apply_patch; apply_patch('/src/{repo}', '/p2o_fix.patch')\"")
            if code != 0:
                return BuildResult(ok=False, stage_failed="apply", log_tail=(out + err)[-1500:],
                                   seconds=time.time() - t0)
            self._sh(cid, "rm -f /p2o_fix.patch")
            code, out, err = self._sh(cid, "sudo -E bash -eux /src/compile.sh", timeout=max(timeout_s, self.COMPILE_TIMEOUT),
                                      workdir="/src")
            if code != 0:
                return BuildResult(ok=False, stage_failed="build", log_tail=(out + err)[-1500:],
                                   seconds=time.time() - t0)
            tag = f"p2o-guardbuild:{uuid.uuid4().hex[:12]}"
            self._commit(cid, tag)
            return BuildResult(ok=True, image_or_container=tag, log_tail=(out + err)[-500:], seconds=time.time() - t0)
        finally:
            self.u.cleanup_container(cid)

    def run_tests(self, task: Task, build: BuildResult, timeout_s: int) -> TestResult:
        import re
        cid = self._guard_container(build.image_or_container, offline=False)
        t0 = time.time()
        try:
            code, out, err = self._sh(cid, "sudo -E bash -eux /src/test.sh", timeout=timeout_s, workdir="/src")
        finally:
            self.u.cleanup_container(cid)
        if code == 0:
            return TestResult(ok=True, seconds=time.time() - t0, log_tail=(out + err)[-500:])
        m = re.search(r"(\d+) (?:tests? )?failed", out + err)
        return TestResult(ok=False, failed=int(m.group(1)) if m else 1, log_tail=(out + err)[-1500:],
                          seconds=time.time() - t0)
