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
    ("s1_hook", "Hook", "0:00-0:15", [
        f"Hand a coding agent the crash, and {P['setup'].replace(' + ', ' with ')} patches "
        f"{_pct_spoken(P['patch_only'])} of memory-safety bugs.",
        f"Ask it to find, reproduce and fix the bug on its own, and only {_pct_spoken(P['s4'])} are truly fixed.",
        "This is Prompt2Own: evidence-gated agents for vulnerability research.",
    ]),
    ("s2_why", "Why it breaks", "0:15-0:35", [
        "Two things break. Context is lost at every hand-off,",
        "and agents say done when they aren't.",
        "The grader has four cumulative checks: the agent's input crashes the program, its patch stops "
        "that crash, the tests still pass, and finally, the benchmark's own hidden crash is gone. "
        "Only that last check, S4, is a real fix.",
    ]),
    ("s3_system", "The system", "0:35-1:05", [
        "Prompt2Own runs each task as a fixed chain: root cause, proof of concept, patch. "
        "Every attempt is a fresh Claude Code harness session, driving a GLM model.",
        "Guards gate each step. The PoC guard needs a sanitizer crash where the root cause pointed. "
        "The patch guard rebuilds, replays the PoC, and runs the tests.",
        "Rejections come back with a reason. Accepted facts go into a ledger.",
        "Guards never see ground truth, and the grader runs only afterwards. "
        "So we can measure false success, and each guard's accuracy.",
    ]),
    ("s4_run", "A real run", "1:05-1:50", [
        f"Here is a real run, on the libspng development task, compressed from {_minutes(R['seconds'])}.",
        "The first root-cause attempt ends without writing its report, and is rejected.",
        f"The retry suspects {rca_fact['function']}, at only {_pct_spoken(rca2['claim_conf'])} confidence.",
        f"The PoC causes an AddressSanitizer {poc['crash_type'].split(':')[1]} in {poc['crash_fn']}, "
        "called from that function. It matches, so the guard accepts.",
        "The patch applies, rebuilds, stops the crash, and passes the tests.",
        f"{_cents(R['usd']).capitalize()} in total. Then the hidden grader runs: S1 to S4, all pass.",
    ]),
    ("s5_findings", "What we found", "1:50-2:35", [
        f"On {_w(D['graded']['n_tasks'])} pre-registered tasks, Claude Code as shipped passes the tests on "
        f"{f2(b1['s3'])} but truly fixes {f2(b1['s4'])}. {_pct_spoken(b1['fsr']).capitalize()} of its "
        "success claims are false.",
        f"Our full system doesn't beat it yet: {f2(p3['s4'])}, p equals {f2(D['paired']['p3_vs_b1']['p'])}. "
        f"Claude Code given our workflow as a prompt reached {f2(b2['s4'])}. None of these gaps is significant.",
        f"Verification works unevenly. The PoC guard never accepted a bad PoC: precision {f2(gp['precision'])}. "
        f"The patch guard: {f2(gx['precision'])}. {_w(gx['false_accepts']).capitalize()} of its "
        f"{_w(gx['accepts'])} accepts failed S4.",
        f"In all {_w(FA['different_location'])}, the agent fixed a real but different bug: the patch fixes "
        "my PoC, not the target. False success moves to the weakest check.",
        f"Splitting also costs: from S1 to S2, P3 falls from {f2(p3['s1'])} to {f2(p3['s2'])}; "
        f"Claude Code from {f2(b1['s1'])} to {f2(b1['s2'])}.",
    ]),
    ("s6_next", "What's next", "2:35-2:55", [
        "Next: a patch guard that knows something the worker doesn't, such as an independent tester agent, "
        "or fuzzing the patched build.",
        "A stages-without-guards ablation, to separate the cost of splitting from the value of checking.",
        "And sixty to a hundred tasks, three seeds, and a guard-noise study.",
    ]),
    ("s7_close", "Close", "2:55-3:00", [
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
