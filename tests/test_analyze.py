"""M6: analysis numbers on hand-built rows, and the one-command regeneration of EVAL.md §3."""
import importlib.util
import os
import subprocess
import sys

import pandas as pd
from typer.testing import CliRunner

from p2o.cli import app

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("analyze", os.path.join(REPO, "scripts", "analyze.py"))
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def rows(cfg, s, claimed, status=None, **cols):
    """s: list of (s1,s2,s3,s4) tuples or None (ungraded)."""
    n = len(s)
    out = []
    for i in range(n):
        r = {"config": cfg, "task_id": f"t/{i}", "status": (status or ["failed"] * n)[i],
             "stop_reason": "completed", "failed_at": "", "claimed_success": claimed[i],
             "usd": 0.5, "minutes": 10.0, "model": "m", "provider": "p", "config_hash": "h"}
        for j, k in enumerate(("s1", "s2", "s3", "s4")):
            r[k] = None if s[i] is None else s[i][j]
        for k, v in cols.items():
            r[k] = v[i]
        out.append(r)
    return out


def test_infra_error_and_ungraded_are_excluded_and_counted():
    df = pd.DataFrame(rows("b1", [(1, 1, 1, 1), (0, 0, 0, 0), None, (0, 0, 0, 0)], [1, 1, 1, 0],
                           status=["failed", "failed", "failed", "infra_error"]))
    r = A.main_table(df).iloc[0]
    assert (r["n"], r["n_infra_error"], r["n_ungraded"]) == (2, 1, 1)
    assert r["s4"] == 0.5 and r["fsr"] == 0.5 and r["usd_total"] == 1.0
    assert r["s4_lo"] < 0.5 < r["s4_hi"] and r["fsr_lo"] < 0.5 < r["fsr_hi"]


def test_guard_precision_recall_and_stage_fsr():
    # 5 P3 runs. poc guard: reached in 4 (run 4 never reached poc: rca failed)
    #   final accept: 1,1,0,0  S1: 1,0,1,0  -> tp=1 fp=1 fn=1  precision 1/2, recall 1/2
    #   poc claims (reached): 1,1,1,0 -> stage FSR = claimed & !S1 = run1 -> 1/3
    df = pd.DataFrame(rows(
        "p3", [(1, 1, 1, 1), (0, 0, 0, 0), (1, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0)], [1, 0, 0, 0, 0],
        attempts_poc=[1, 2, 3, 3, 0], poc_guard_accepts=[1, 1, 0, 0, 0], poc_guard_rejects=[0, 1, 3, 2, 0],
        final_poc_guard_accept=[1, 1, 0, 0, None], claimed_poc=[1, 1, 1, 0, None],
        attempts_patch=[1, 0, 0, 0, 0], patch_guard_accepts=[1, 0, 0, 0, 0], patch_guard_rejects=[0] * 5,
        final_patch_guard_accept=[1, None, None, None, None], claimed_patch=[1, None, None, None, None]))
    gt = A.guard_table(df).set_index("guard")
    p = gt.loc["exec_poc"]
    assert (p["reached"], p["accepts"], p["rejects"], p["false_accepts"], p["false_rejects"]) == (4, 2, 2, 1, 1)
    assert p["precision"] == 0.5 and p["recall"] == 0.5 and p["checks"] == 8 and p["check_rejects"] == 6
    assert (p["stage_reached"], p["stage_claimed"]) == (4, 3) and abs(p["stage_fsr"] - 1 / 3) < 1e-9
    q = gt.loc["exec_patch"]
    assert (q["reached"], q["precision"], q["recall"], q["stage_fsr"]) == (1, 1.0, 1.0, 0.0)


def test_guard_table_skips_configs_without_executable_guards():
    df = pd.DataFrame(rows("p0", [(1, 1, 1, 1)], [1], attempts_poc=[1], poc_guard_accepts=[0],
                           poc_guard_rejects=[0], final_poc_guard_accept=[1], claimed_poc=[1],
                           attempts_patch=[1], patch_guard_accepts=[0], patch_guard_rejects=[0],
                           final_patch_guard_accept=[1], claimed_patch=[1]))
    assert A.guard_table(df).empty


def test_paired_table_counts_and_mcnemar():
    s4_p3 = [1, 1, 1, 1, 1, 1, 0, 0]
    s4_b1 = [1, 0, 0, 0, 0, 0, 0, 1]
    mk = lambda v: [(x, x, x, x) for x in v]
    df = pd.DataFrame(rows("p3", mk(s4_p3), [1] * 8) + rows("b1", mk(s4_b1), [1] * 8))
    pt = A.paired_table(df)
    s4 = pt[pt["metric"] == "s4"].iloc[0]
    assert (s4["a"], s4["b"], s4["n"], s4["both"], s4["only_a"], s4["only_b"], s4["neither"]) == \
        ("p3", "b1", 8, 1, 5, 1, 1)
    assert abs(s4["mcnemar_p"] - 0.21875) < 1e-9        # exact binomial, 6 discordant, 5 vs 1
    fs = pt[pt["metric"] == "false_success"].iloc[0]
    assert (fs["only_a"], fs["only_b"]) == (1, 5)        # false success is the complement here
    # no discordant pairs -> p = 1
    df2 = pd.DataFrame(rows("p3", mk([1, 0]), [0, 0]) + rows("b1", mk([1, 0]), [0, 0]))
    assert A.paired_table(df2)["mcnemar_p"].eq(1.0).all()


def test_sanity_warns_on_mixed_config_hash():
    df = pd.DataFrame(rows("p3", [(1, 1, 1, 1), (0, 0, 0, 0)], [1, 0], config_hash=["a", "b"]))
    assert any("config_hash" in w for w in A.sanity(df))


def test_one_command_regenerates_every_eval_output(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO)
    tasks = tmp_path / "tasks.txt"
    tasks.write_text("".join(f"fp{i}/arvo_{i},fp{i}\n" for i in range(12)))
    root = tmp_path / "res"
    for cfg in ("b1", "b2", "p0", "p3"):
        for cmd in ("batch", "grade"):
            r = CliRunner().invoke(app, [cmd, "--config", f"configs/{cfg}.yaml", "--tasks", str(tasks),
                                         "--fake", "--results", str(root)])
            assert r.exit_code == 0, r.output
    assert CliRunner().invoke(app, ["summarize", "--results", str(root)]).exit_code == 0
    summ = pd.read_csv(root / "summary.csv")
    assert len(summ) == 48 and {"claimed_poc", "claimed_patch"} <= set(summ.columns)
    out = tmp_path / "figs"
    p = subprocess.run([sys.executable, "scripts/analyze.py", str(root / "summary.csv"), "--out", str(out),
                        "--all-tasks"], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    for f in A.OUTPUTS:
        assert (out / f).exists() and (out / f).stat().st_size > 0, f
    main = pd.read_csv(out / "table_main.csv")
    assert list(main["config"]) == ["b1", "b2", "p0", "p3"] and (main["n"] == 12).all()
    assert set(pd.read_csv(out / "table_guards.csv")["guard"]) == {"exec_poc", "exec_patch"}
    assert set(pd.read_csv(out / "table_paired.csv")["b"]) == {"b1", "b2", "p0"}


def test_stratum_rows_are_pooled_plus_each_stratum():
    df = pd.DataFrame(rows("p3", [(1, 1, 1, 1), (0, 0, 0, 0), (1, 1, 1, 1)], [1, 1, 0],
                           stratum=["easy", "easy", "uniform"]))
    t = A.main_table(df).set_index("stratum")
    assert list(t.index) == ["all", "easy", "uniform"]
    assert (t.loc["all", "n"], t.loc["easy", "n"], t.loc["uniform", "n"]) == (3, 2, 1)
    assert t.loc["easy", "s4"] == 0.5 and t.loc["uniform", "s4"] == 1.0
    assert abs(t.loc["all", "s4"] - 2 / 3) < 1e-9
    # no stratum column -> pooled rows only
    assert list(A.main_table(pd.DataFrame(rows("p3", [(1, 1, 1, 1)], [1])))["stratum"]) == ["all"]


def test_summary_reads_stratum_from_manifest(tmp_path, monkeypatch):
    import json
    monkeypatch.chdir(REPO)
    tasks = tmp_path / "tasks.txt"
    tasks.write_text("fp1/arvo_1,fp1\nfp2/arvo_2,fp2\nfp3/arvo_3,fp3\n")
    root = tmp_path / "res"
    r = CliRunner().invoke(app, ["batch", "--config", "configs/p3.yaml", "--tasks", str(tasks), "--fake",
                                 "--results", str(root)])
    assert r.exit_code == 0, r.output
    man = tmp_path / "manifest.json"
    man.write_text(json.dumps({"seed": 329, "stratum": {"fp1/arvo_1": "easy", "fp2/arvo_2": "uniform"}}))
    r = CliRunner().invoke(app, ["summarize", "--results", str(root), "--manifest", str(man)])
    assert r.exit_code == 0, r.output
    s = pd.read_csv(root / "summary.csv", keep_default_na=False).set_index("task_id")["stratum"]
    assert (s["fp1/arvo_1"], s["fp2/arvo_2"], s["fp3/arvo_3"]) == ("easy", "uniform", "")


def test_task_filter_drops_dev_tasks(tmp_path):
    df = pd.DataFrame(rows("p3", [(1, 1, 1, 1), (0, 0, 0, 0)], [1, 0]))
    keep = tmp_path / "main.txt"
    keep.write_text("t/1,t\n")
    assert list(A._task_filter(df, keep)["task_id"]) == ["t/1"]
