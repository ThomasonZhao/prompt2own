"""Narration for every scene, as templates filled from data.D.

Scenes import `NARRATION[scene_id]` (a list of sentences/beats; each beat becomes one
`self.voiceover(...)` block). `python demo/narration.py` regenerates demo/script.md.
No number in here is typed by hand: each one is a field of D.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import D, f2  # noqa: E402

P, M, G, R = D["paper"], D["main"], D["guards"], D["run"]
A = {(a["stage"], a["attempt"]): a for a in R["attempts"]}
poc = A[("poc", 1)]
rca2 = A[("rca", 2)]
rca_fact = next(f for f in R["facts"] if f["stage"] == "rca")
b1, b2, p3 = M["b1"]["all"], M["b2"]["all"], M["p3"]["all"]
gp, gx = G["exec_poc"], G["exec_patch"]
FA = D["false_accepts"]
RJ = D["reject"]
# the htslib beat states these facts in words; fail if the data stops supporting them
assert len(RJ["pocs"]) == 3 and not any(p["accept"] for p in RJ["pocs"])
assert not RJ["p3"]["s1"] and RJ["b1"]["claimed_success"] and not RJ["b1"]["s4"]
assert FA["different_location"] == FA["n"] == gx["false_accepts"]


def _pct_spoken(x: float) -> str:
    v = x if x > 1 else 100 * x
    return f"{v:.1f}".rstrip("0").rstrip(".") + " percent"


def _cents(usd: float) -> str:
    return f"{round(usd * 100)} cents"


def _minutes(s: float) -> str:
    return f"{round(s / 60)} minutes"


_NUM = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
        17: "seventeen", 18: "eighteen", 30: "thirty", 90: "ninety"}


def _w(n: int) -> str:
    return _NUM.get(n, str(n))


# (scene id, title, target window) -> list of beats
SCENES: list[tuple[str, str, str, list[str]]] = [
    ("s1_problem", "The problem", "0:00-0:20", [
        f"Hand a coding agent the crash, and {P['setup'].replace(' + ', ' with ')} patches "
        f"{_pct_spoken(P['patch_only'])} of memory-safety bugs.",
        f"Ask for the whole job, find, reproduce and fix, and only {_pct_spoken(P['s4'])} are truly "
        "fixed. Agents also claim success they didn't earn.",
        "Our question: if every step must show executable evidence, do agents become more correct, "
        "and more honest?",
    ]),
    ("s2_system", "The system", "0:20-0:50", [
        "Prompt2Own runs each task as a fixed chain: root cause, proof of concept, patch. "
        "Every attempt is a fresh Claude Code harness session, driving a GLM model.",
        "Guards gate every step. The PoC guard needs a sanitizer crash where the root cause pointed. "
        "The patch guard rebuilds, replays the PoC, and runs the tests.",
        "A rejection goes back with its reason, for a retry. Accepted facts go into a ledger.",
        "Guards never see ground truth. The official grader runs only after the run, and only its "
        "last check, S4, the benchmark's own crash fixed, counts as a real fix.",
    ]),
    ("s3_run", "A real run", "0:50-1:40", [
        "This is our trace tool, replaying the event log of a real run on the libspng dev task.",
        "The first root-cause attempt ends without its report, so the orchestrator rejects it. "
        f"The retry suspects {rca_fact['function']}, unchecked for now.",
        f"The PoC crashes with an AddressSanitizer {poc['crash_type'].split(':')[1]}, and "
        f"{rca_fact['function']} is in the stack, so the guard accepts.",
        "The patch guard rebuilds, the crash is gone, the tests pass. "
        f"{_cents(R['usd']).capitalize()}, {_minutes(R['seconds'])}.",
        "Only then does the hidden grader run: all four checks pass.",
        f"Guards also say no. On htslib, the agent claimed a crash three times, once at "
        f"{_pct_spoken(RJ['pocs'][0]['claim_conf'])} confidence. No sanitizer report, so all three "
        "were rejected. The grader agrees. Claude Code alone, on the same task, claimed success, and failed.",
    ]),
    ("s4_findings", "What we found", "1:40-2:37", [
        f"We ran three setups on {_w(D['graded']['n_tasks'])} pre-registered tasks: Claude Code as "
        "shipped, Claude Code given our workflow as a prompt, and the full system.",
        f"The full system doesn't win yet: {f2(p3['s4'])} true success, versus {f2(b1['s4'])} and "
        f"{f2(b2['s4'])}. At this size, no gap is significant.",
        "The guards show where verification works. The PoC guard never accepted a bad PoC: "
        f"precision {f2(gp['precision'])}. The patch guard: {f2(gx['precision'])}. "
        f"{_w(gx['false_accepts']).capitalize()} of {_w(gx['accepts'])} accepted patches failed the real check.",
        f"In all {_w(FA['different_location'])}, the agent fixed a real but different bug. The patch "
        "fixes my PoC, not the target. False success moved to the edge with the weakest check.",
    ]),
    ("s5_next", "What's next", "2:37-2:52", [
        "Next: a patch guard that knows something the worker doesn't, like fuzzing the patched build; "
        "a stages-without-guards ablation; and more tasks and seeds.",
        f"Every number here comes from {_w(D['graded']['total'])} graded runs on CyberGym-E2E.",
    ]),
]

NARRATION = {sid: beats for sid, _, _, beats in SCENES}
WPM_ESTIMATE = 155


def script_md() -> str:
    lines = ["# Prompt2Own midway demo: narration", "",
             "Generated by `python demo/narration.py` from `demo/data.py`; do not edit by hand.",
             f"Estimated at {WPM_ESTIMATE} wpm before TTS; per-scene times are replaced with measured "
             "audio durations after the voice is generated.", ""]
    total_w, t = 0, 0.0
    for sid, title, window, beats in SCENES:
        w = sum(len(b.split()) for b in beats)
        dur = w / WPM_ESTIMATE * 60 + 0.4 * len(beats)  # small pause per beat
        lines += [f"## {sid}: {title} (target {window}; est. {t:5.1f}s to {t + dur:5.1f}s, {w} words)", ""]
        lines += [f"{i}. {b}" for i, b in enumerate(beats, 1)] + [""]
        total_w += w
        t += dur
    lines += [f"**Total: {total_w} words, est. {int(t // 60)}:{t % 60:04.1f}.**", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "script.md"
    out.write_text(script_md())
    print(script_md())
