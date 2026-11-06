"""All data models. Single source of truth for schemas (see docs/INTERFACES.md).

# STATUS: implemented
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Stage(str, Enum):
    RCA = "rca"
    POC = "poc"
    PATCH = "patch"
    SINGLE = "single"  # B1 / B2 single-session runs


STAGE_ORDER = [Stage.RCA, Stage.POC, Stage.PATCH]


class Task(BaseModel):
    task_id: str            # harness id, e.g. "curl/arvo_66012"
    project: str = ""


# ---------- worker-written files ----------

class RCAResult(BaseModel):
    file: str
    function: str
    line_range: tuple[int, int]
    bug_class: str
    rationale: str = Field(max_length=2000)


class Claim(BaseModel):
    done: bool
    confidence: float = Field(ge=0.0, le=1.0)
    expected_crash_location: str | None = None
    files_changed: list[str] = []
    notes: str = ""


# ---------- worker I/O ----------

class Usage(BaseModel):
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached: int = 0

    def __add__(self, o: "Usage") -> "Usage":
        return Usage(tokens_in=self.tokens_in + o.tokens_in,
                     tokens_out=self.tokens_out + o.tokens_out,
                     tokens_cached=self.tokens_cached + o.tokens_cached)

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out + self.tokens_cached


class Fact(BaseModel):
    ts: str = Field(default_factory=now)
    stage: Stage
    attempt: int
    guard: str
    data: dict[str, Any]
    artifact_sha256: str | None = None


class StageRequest(BaseModel):
    stage: Stage
    attempt: int
    facts: list[Fact]
    last_reason: str | None = None


class StageOutput(BaseModel):
    stage: Stage
    attempt: int
    artifact_dir: Path
    claim: Claim | None = None
    rca: RCAResult | None = None
    schema_error: str | None = None
    worker_error: str | None = None
    usage: Usage = Usage()
    seconds: float = 0.0
    exit_code: int = 0
    prompt_hash: str = ""


# ---------- guards ----------

class GuardInput(BaseModel):
    task: Task
    stage: Stage
    attempt: int
    artifact_dir: Path
    claim: Claim
    facts: list[Fact]


class Verdict(BaseModel):
    accept: bool
    reason: str
    evidence: dict[str, Any] = {}
    guard: str
    seconds: float = 0.0


# ---------- harness results ----------

class Workspace(BaseModel):
    task: Task
    run_dir: Path
    container_id: str = ""
    src_path: str = "/src"          # path of the source tree inside the container
    meta: dict[str, Any] = {}


class WorkerExec(BaseModel):
    exit_code: int
    stdout: str
    seconds: float
    timed_out: bool = False


class PoCRun(BaseModel):
    crashed: bool
    sanitizer_report: str | None = None
    top_frames: list[str] = []
    exit_code: int | None = None
    timed_out: bool = False
    seconds: float = 0.0


class BuildResult(BaseModel):
    ok: bool
    log_tail: str = ""
    image_or_container: str = ""
    seconds: float = 0.0
    stage_failed: Literal["apply", "build", None] = None


class TestResult(BaseModel):
    ok: bool
    failed: int = 0
    log_tail: str = ""
    seconds: float = 0.0


# ---------- run records ----------

RunStatus = Literal["success_claimed", "failed", "infra_error", "cap_hit"]


class RunRecord(BaseModel):
    run_id: str
    config: str
    task: Task
    seed: int
    status: RunStatus
    stop_reason: str = ""
    failed_at: Stage | None = None
    claimed_success: bool = False
    attempts: dict[str, int] = {}
    guard_counts: dict[str, dict[str, int]] = {}   # guard -> {"accept": n, "reject": n}
    final_guard_accept: dict[str, bool] = {}       # stage -> last verdict accepted?
    usage: Usage = Usage()
    usd: float = 0.0
    seconds: float = 0.0
    model: str = ""
    provider: str = ""
    prompt_hash: str = ""
    config_hash: str = ""
    started: str = ""
    ended: str = ""


class GradeRecord(BaseModel):
    config: str
    task_id: str
    s1: bool
    s2: bool
    s3: bool
    s4: bool
    raw: dict[str, Any] = {}
