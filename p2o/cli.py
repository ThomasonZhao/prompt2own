"""CLI. # STATUS: implemented (wiring). `python -m p2o.cli --help`"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import typer
from dotenv import load_dotenv

from .budget import Budget
from .config import load_config
from .types import Task

app = typer.Typer(add_completion=False)
RESULTS = Path("results")
FAKE_RESULTS = RESULTS / "fake"   # --fake output never mixes with real runs, grades or spend

ResultsOpt = typer.Option(None, help="results root (default: results/, or results/fake/ with --fake)")


def _root(results: Path | None, fake: bool = False) -> Path:
    root = results if results is not None else (FAKE_RESULTS if fake else RESULTS)
    if fake and root.resolve() == RESULTS.resolve():
        raise typer.BadParameter("--fake output must not go under the real results/ root")
    return root


def _budget(root: Path) -> Budget:
    # real runs: P2O_BUDGET_FILE or results/budget.json; any other root keeps its own file
    return Budget() if root == RESULTS else Budget(root / "budget.json")


def _tasks(path: Path) -> list[Task]:
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tid, _, project = line.partition(",")
            out.append(Task(task_id=tid.strip(), project=project.strip() or tid.split("/")[0]))
    return out


def _make(config: Path, fake: bool, root: Path, vary: bool = False):
    from .orchestrator import Orchestrator
    cfg = load_config(config)
    if fake:
        from .fakes import FakeHarness, FakeWorker
        # run: the fixed demo script (reject -> retry -> accept); batch: varied per (config, task)
        h, w = FakeHarness(), FakeWorker(vary=cfg.id if vary else None)
    else:
        from .harness import CyberGymE2EAdapter
        from .worker import ClaudeCodeWorker
        h = CyberGymE2EAdapter()
        w = ClaudeCodeWorker(h, cfg)
    return Orchestrator(cfg, h, w, root, _budget(root))


@app.command()
def run(config: Path = typer.Option(...), task: str = typer.Option(...), fake: bool = False,
        results: Path = ResultsOpt):
    """Run one task."""
    orch = _make(config, fake, _root(results, fake))
    rec = orch.run(Task(task_id=task, project=task.split("/")[0]))
    typer.echo(f"{rec.task.task_id}: {rec.status} ({rec.stop_reason}) ${rec.usd:.3f} {rec.seconds/60:.1f} min")


@app.command()
def batch(config: Path = typer.Option(...), tasks: Path = typer.Option(...),
          parallel: int = 4, fake: bool = False, results: Path = ResultsOpt):
    """Run many tasks; resumable (skips tasks with run.json)."""
    orch = _make(config, fake, _root(results, fake), vary=True)
    todo = [t for t in _tasks(tasks) if not orch.is_done(t)]
    typer.echo(f"{len(todo)} tasks to run; {orch.budget.report()}")
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        futs = {ex.submit(orch.run, t): t for t in todo}
        for f in as_completed(futs):
            t = futs[f]
            try:
                r = f.result()
                typer.echo(f"[done] {t.task_id}: {r.status} ${r.usd:.3f}")
            except Exception as e:
                typer.echo(f"[fail] {t.task_id}: {type(e).__name__}: {e}")


@app.command()
def grade(config: Path = typer.Option(...), tasks: Path = typer.Option(...), fake: bool = False,
          results: Path = ResultsOpt):
    """Grade finished runs with the official grader."""
    from .grade import grade as do_grade
    cfg = load_config(config)
    root = _root(results, fake)
    for t in _tasks(tasks):
        try:
            g = do_grade(root, cfg.id, t, fake=fake)
            typer.echo(f"{t.task_id}: S1={g.s1} S2={g.s2} S3={g.s3} S4={g.s4}")
        except FileNotFoundError as e:
            typer.echo(f"skip {t.task_id}: {e}")


@app.command()
def summarize(results: Path = typer.Option(RESULTS, help="results root, e.g. results/fake"),
              manifest: Path = typer.Option(Path("tasks/sample_manifest.json"),
                                            help="sample manifest with the task_id -> stratum map")):
    """Write <results>/summary.csv from run.json + grade files."""
    from .summary import summarize as do
    typer.echo(str(do(results, manifest)))


@app.command()
def budget(results: Path = typer.Option(RESULTS, help="results root, e.g. results/fake")):
    """Show spend vs. budget."""
    typer.echo(_budget(results).report())


def main():
    load_dotenv()
    app()


if __name__ == "__main__":
    main()
