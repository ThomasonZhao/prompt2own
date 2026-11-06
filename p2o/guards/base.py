"""Guard interface, registry and NullGuard. # STATUS: implemented

Guards run outside the worker's container and never read ground truth.
"""
from __future__ import annotations

import time
from typing import Callable, Protocol

from ..types import GuardInput, Verdict


class Guard(Protocol):
    name: str
    def check(self, inp: GuardInput) -> Verdict: ...


class NullGuard:
    name = "null@1"

    def check(self, inp: GuardInput) -> Verdict:
        return Verdict(accept=True, reason="ok", evidence={"unchecked": True}, guard=self.name)


def reject(guard: str, reason: str, t0: float, **evidence) -> Verdict:
    return Verdict(accept=False, reason=reason, evidence=evidence, guard=guard, seconds=time.time() - t0)


def accept(guard: str, t0: float, **evidence) -> Verdict:
    return Verdict(accept=True, reason="ok", evidence=evidence, guard=guard, seconds=time.time() - t0)


# name -> factory(harness, guard_cfg_dict) -> Guard
REGISTRY: dict[str, Callable[..., Guard]] = {"null": lambda harness, cfg: NullGuard()}


def register(name: str):
    def deco(factory):
        REGISTRY[name] = factory
        return factory
    return deco


def build_guard(name: str, harness, cfg: dict) -> Guard:
    from . import exec_patch, exec_poc, llm_judge  # noqa: F401  (populate registry)
    if name not in REGISTRY:
        raise KeyError(f"unknown guard {name!r}; known: {sorted(REGISTRY)}")
    return REGISTRY[name](harness, cfg)
