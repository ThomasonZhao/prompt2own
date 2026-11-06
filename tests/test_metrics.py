import importlib.util
import pandas as pd

spec = importlib.util.spec_from_file_location("analyze", "scripts/analyze.py")


def load():
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_fsr_and_gap(monkeypatch):
    import os
    monkeypatch.chdir(os.path.dirname(os.path.dirname(__file__)))
    a = load()
    df = pd.DataFrame({"config": ["b1"] * 4, "status": ["failed"] * 4,
                       "claimed_success": [1, 1, 1, 0], "s1": [1, 1, 0, 0], "s2": [1, 1, 0, 0],
                       "s3": [1, 1, 0, 0], "s4": [1, 0, 0, 0], "usd": [0.5] * 4, "minutes": [10] * 4})
    row = a.main_table(df).iloc[0]
    assert abs(row["fsr"] - 2 / 3) < 1e-9
    assert abs(row["check_pass_gap"] - 0.5) < 1e-9
    assert abs(row["usd_per_s4"] - 2.0) < 1e-9
