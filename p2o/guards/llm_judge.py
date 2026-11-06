"""LLM-judge guard (P2). # STATUS: stub — final report only, do not implement for midway."""
from __future__ import annotations

from ..types import GuardInput, Verdict
from .base import register


class LLMJudgeGuard:
    name = "llm_judge@0"

    def __init__(self, harness, cfg: dict):
        self.cfg = cfg

    def check(self, inp: GuardInput) -> Verdict:
        raise NotImplementedError("P2 is out of scope for the midway build (docs/SPEC.md §2)")


register("llm_judge")(lambda harness, cfg: LLMJudgeGuard(harness, cfg))
