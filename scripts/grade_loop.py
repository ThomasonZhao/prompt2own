"""Grade newly finished runs every 5 min until stopped (grade() refuses runs without run.json, so
workers/guards never see grades). Usage: python scripts/grade_loop.py <tasks_file> <config> [...]"""
import subprocess
import sys
import time
from datetime import datetime, timezone

tasks, configs = sys.argv[1], sys.argv[2:]
while True:
    for c in configs:
        r = subprocess.run([sys.executable, "-m", "p2o.cli", "grade", "--config", f"configs/{c}.yaml",
                            "--tasks", tasks, "--parallel", "3", "--only-new"], capture_output=True, text=True)
        ts = datetime.now(timezone.utc).strftime("%H:%M")
        for line in (r.stdout + r.stderr).splitlines():
            if not line.startswith("skip "):
                print(f"[{ts} {c}] {line}", flush=True)
    time.sleep(300)
