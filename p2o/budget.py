"""Global API spend tracking across all runs and processes. # STATUS: implemented"""
from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path

DEFAULT_PATH = "results/budget.json"
TOTAL_USD = 150.0
# Env overrides (P2O_BUDGET_FILE, P2O_BUDGET_USD) are read in Budget(), not at import time:
# cli.py imports this module before load_dotenv() runs, so import-time reads would ignore .env.


@contextmanager
def _locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


class Budget:
    def __init__(self, path: Path | None = None, total_usd: float | None = None):
        self.path = Path(path) if path is not None else Path(os.environ.get("P2O_BUDGET_FILE", DEFAULT_PATH))
        self.total = total_usd if total_usd is not None else float(os.environ.get("P2O_BUDGET_USD", TOTAL_USD))

    def _read(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {"spent": 0.0, "by_config": {}}

    def spent(self) -> float:
        return self._read()["spent"]

    def remaining(self) -> float:
        return self.total - self.spent()

    def can_start(self, worst_case_usd: float) -> bool:
        return self.remaining() >= worst_case_usd

    def record(self, config_id: str, usd: float) -> None:
        with _locked(self.path):
            d = self._read()
            d["spent"] += usd
            d["by_config"][config_id] = d["by_config"].get(config_id, 0.0) + usd
            self.path.write_text(json.dumps(d, indent=2))

    def report(self) -> str:
        d = self._read()
        rows = "\n".join(f"  {k}: ${v:.2f}" for k, v in sorted(d["by_config"].items()))
        return f"spent ${d['spent']:.2f} of ${self.total:.2f} (remaining ${self.remaining():.2f})\n{rows}"
