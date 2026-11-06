"""Load configs/*.yaml with ${ENV} expansion. # STATUS: implemented"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

_ENV = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _expand(text: str) -> str:
    def sub(m: re.Match) -> str:
        val = os.environ.get(m.group(1), m.group(2))
        if val is None:
            raise KeyError(f"env var {m.group(1)} is not set (see .env.example)")
        return val
    return _ENV.sub(sub, text)


class Prices(BaseModel):
    input: float
    cached_input: float
    output: float


class Caps(BaseModel):
    wall_minutes: int = 45
    max_tokens: int = 3_000_000
    max_usd: float = 0.75


class WorkerCfg(BaseModel):
    max_turns: int = 60
    stage_timeout_minutes: int = 15


class StageCfg(BaseModel):
    guard: str = "null"
    max_attempts: int = 1


class PromptCfg(BaseModel):
    dir: str = "p2o/stages"
    single: str | None = None      # None = official harness prompt (B1)
    suffix: str = "claim_suffix.md"


class RunConfig(BaseModel):
    id: str
    mode: Literal["stage_graph", "single_session"]
    seed: int = 0
    model: str
    provider: str
    base_url: str
    prices_per_mtok: dict[str, Prices]     # model slug -> prices; must contain `model`
    caps: Caps = Caps()
    worker: WorkerCfg = WorkerCfg()
    stages: dict[str, StageCfg] = {}
    guards: dict[str, dict] = {}
    prompts: PromptCfg = PromptCfg()

    @model_validator(mode="after")
    def _model_is_priced(self) -> "RunConfig":
        if self.model not in self.prices_per_mtok:
            raise ValueError(f"model {self.model!r} has no entry in prices_per_mtok "
                             f"(known: {sorted(self.prices_per_mtok)})")
        return self

    @property
    def prices(self) -> Prices:
        """Prices of the configured model. The only accessor runtime code should use."""
        return self.prices_per_mtok[self.model]

    @property
    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode()).hexdigest()[:12]


def load_config(path: str | Path) -> RunConfig:
    raw = yaml.safe_load(_expand(Path(path).read_text()))
    if raw.get("stages"):
        raw["stages"] = {k: (v or {}) for k, v in raw["stages"].items()}
        for v in raw["stages"].values():
            if v.get("guard") is None:
                v["guard"] = "null"
    return RunConfig(**raw)
