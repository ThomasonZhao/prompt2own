import os
import pytest

from p2o.budget import Budget
from p2o.config import load_config
from p2o.fakes import FakeHarness, FakeWorker
from p2o.orchestrator import Orchestrator


@pytest.fixture
def make(tmp_path, monkeypatch):
    monkeypatch.chdir(os.path.dirname(os.path.dirname(__file__)))
    def _make(config="configs/p3.yaml", worker=None, harness=None, budget_usd=150.0, **overrides):
        cfg = load_config(config)
        for k, v in overrides.items():
            setattr(cfg, k, v)
        h, w = harness or FakeHarness(), worker or FakeWorker()
        b = Budget(tmp_path / "budget.json", budget_usd)
        return Orchestrator(cfg, h, w, tmp_path / "results", b), h, w
    return _make
