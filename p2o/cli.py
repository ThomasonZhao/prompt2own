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


def _tasks(path: Path) -> list[Task]:
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tid, _, project = line.partition(",")
            out.append(Task(task_id=tid.strip(), project=project.strip() or tid.split("/")[0]))
    return out


def _make(config: Path, fake: bool):
    from .orchestrator import Orchestrator
    cfg = load_config(config)
    if fake:
        from .fakes import FakeHarness, FakeWorker
        h, w = FakeHarness(), FakeWorker()
    else:
        from .harness import CyberGymE2EAdapter
        from .worker import ClaudeCodeWorker
        h = CyberGymE2EAdapter()
        w = ClaudeCodeWorker(h, cfg)
    return Orchestrator(cfg, h, w, RESULTS)


@app.command()
def run(config: Path = typer.Option(...), task: str = typer.Option(...), fake: bool = False):
    """Run one task."""
    orch = _make(config, fake)
    rec = orch.run(Task(task_id=task, project=task.split("/")[0]))
    typer.echo(f"{rec.task.task_id}: {rec.status} ({rec.stop_reason}) ${rec.usd:.3f} {rec.seconds/60:.1f} min")


@app.command()
def batch(config: Path = typer.Option(...), tasks: Path = typer.Option(...),
          parallel: int = 4, fake: bool = False):
    """Run many tasks; resumable (skips tasks with run.json)."""
    orch = _make(config, fake)
    todo = [t for t in _tasks(tasks) if not orch.is_done(t)]
    typer.echo(f"{len(todo)} tasks to run; {Budget().report()}")
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
def grade(config: Path = typer.Option(...), tasks: Path = typer.Option(...), fake: bool = False):
    """Grade finished runs with the official grader."""
    from .grade import grade as do_grade
    cfg = load_config(config)
    for t in _tasks(tasks):
        try:
            g = do_grade(RESULTS, cfg.id, t, fake=fake)
            typer.echo(f"{t.task_id}: S1={g.s1} S2={g.s2} S3={g.s3} S4={g.s4}")
        except FileNotFoundError as e:
            typer.echo(f"skip {t.task_id}: {e}")


@app.command()
def summarize():
    """Write results/summary.csv."""
    from .summary import summarize as do
    typer.echo(str(do(RESULTS)))


@app.command()
def budget():
    """Show spend vs. budget."""
    typer.echo(Budget().report())


def main():
    load_dotenv()
    app()


if __name__ == "__main__":
    main()
