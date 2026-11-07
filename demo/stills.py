"""Extract one still per narration beat (just before the next beat starts) from a rendered scene.

Usage: python demo/stills.py <scene_id> <video.mp4> <out_dir> [--at 0.5,3.2 ...]
"""
import json
import subprocess
import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parent


def main():
    sid, video, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    t = json.loads((DEMO / "cache" / "timings" / f"{sid}.json").read_text())
    starts = [b["start"] for b in t["beats"]] + [t["duration"]]
    times = [max(starts[i + 1] - 0.4, starts[i]) for i in range(len(starts) - 1)]
    if "--at" in sys.argv:
        times = [float(x) for x in sys.argv[sys.argv.index("--at") + 1].split(",")]
    for i, ts in enumerate(times, 1):
        dst = out / f"{sid}_{i}.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{ts:.2f}", "-i", str(video),
                        "-frames:v", "1", str(dst)], check=True)
        print(dst, f"t={ts:.2f}")
    print("duration", round(t["duration"], 2))


if __name__ == "__main__":
    main()
