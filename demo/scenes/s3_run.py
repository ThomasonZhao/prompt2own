"""A real run: the project's own scripts/trace.py output for real event logs, replayed.

Everything shown comes from data.D: trace lines (captured by running trace.py), attempt
timings/costs, guard evidence (crash type and function names only) and the official grade.
No PoC bytes, input contents or patch diffs appear.
"""
import re

from manim import (DOWN, LEFT, RIGHT, UP, AddTextLetterByLetter, Arrow, Create, FadeIn, FadeOut,
                   Indicate, LaggedStart, Line, ReplacementTransform, SurroundingRectangle,
                   Transform, VGroup, Write)

from style import (AMBER, BG, INK, MUTED, SAGE, SAND, SLATE, TERRA, PaperScene, T, M, card)
from data import D

R = D["run"]
TR = D["trace"]
RJ = D["reject"]
FONT = 19
LINE_H = 0.315
TOP = 2.55          # y of first console line
LEFT_X = -6.55


def find_row(lines, stage, attempt):
    pat = re.compile(rf"^\d\d:\d\d:\d\d\s+{stage}\s+{attempt}\s")
    for i, l in enumerate(lines):
        if pat.match(l):
            return i
    raise KeyError((stage, attempt))


def find(lines, prefix):
    for i, l in enumerate(lines):
        if l.lstrip().startswith(prefix):
            return i
    raise KeyError(prefix)


MAXC = 82   # display cut so lines fit the console card; trace.py's own --width is 80


def mline(s, color=INK, maxc=MAXC):
    s = s if len(s) <= maxc else s[: maxc - 1] + "…"
    return M(s if s.strip() else " ", FONT, color)


class Console:
    """Lines placed top-down inside the sand card; keeps a list so rows can be highlighted."""

    def __init__(self):
        self.rows: list = []

    def place(self, mob, k):
        mob.move_to([LEFT_X, TOP - k * LINE_H, 0], aligned_edge=LEFT)
        return mob


class S3Run(PaperScene):
    SCENE_ID = "s3_run"

    def stage_graph(self):
        names = ["RCA", "PoC", "Patch"]
        nodes = VGroup(*[VGroup(card(1.7, 0.55, fill="#FFFFFF", stroke=SLATE, r=0.27),
                                T(n, 22, SLATE, weight="SEMIBOLD")) for n in names])
        for n in nodes:
            n[1].move_to(n[0])
        nodes.arrange(RIGHT, buff=0.55)
        arrows = VGroup(*[Arrow(nodes[i].get_right(), nodes[i + 1].get_left(), buff=0.06,
                                color=MUTED, stroke_width=2.5, max_tip_length_to_length_ratio=0.3)
                          for i in range(2)])
        grader = VGroup(card(1.9, 0.55, fill="#EDEAE4", stroke=MUTED, r=0.27),
                        T("grader", 22, MUTED, weight="SEMIBOLD"))
        grader[1].move_to(grader[0])
        grader.next_to(nodes, RIGHT, buff=0.9)
        sep = Line(UP * 0.3, DOWN * 0.3, color=MUTED, stroke_width=2).move_to(
            (nodes.get_right() + grader.get_left()) / 2)
        g = VGroup(nodes, arrows, sep, grader).move_to([-2.25, 3.4, 0])
        return g, nodes, grader

    def counters(self, minutes, usd):
        c = M(f"{minutes:4.1f} min  ${usd:.3f}", 22, INK)
        return c.move_to([6.85, 3.4, 0], aligned_edge=RIGHT)

    def activate(self, nodes, i, color=AMBER):
        anims = []
        for k, n in enumerate(nodes):
            on = k == i
            anims.append(n[0].animate.set_stroke(color if on else SLATE, width=5 if on else 2.5)
                         .set_fill(SAND if on else "#FFFFFF", opacity=1))
        return anims

    def show_lines(self, con, lines, start_k, idxs, colors=None, rt=0.35):
        mobs = []
        for j, i in enumerate(idxs):
            m = con.place(mline(lines[i], (colors or {}).get(i, INK)), start_k + j)
            mobs.append(m)
        self.play(LaggedStart(*[FadeIn(m, shift=RIGHT * 0.1) for m in mobs], lag_ratio=0.5),
                  run_time=max(rt * len(mobs), 0.6))
        return VGroup(*mobs)

    def hl(self, mob, color):
        r = SurroundingRectangle(mob, color=color, buff=0.06, corner_radius=0.06, stroke_width=2.5,
                                 fill_color=color, fill_opacity=0.12)
        self.play(Create(r), run_time=0.6)
        return r

    def chip(self, text, color=SAGE, size=18):
        t = M(text, size, color)
        return VGroup(card(t.width + 0.4, 0.5, fill=color, stroke=color, opacity=0.13, r=0.14), t)

    def construct(self):
        L = TR["libspng"]
        att = {(a["stage"], a["attempt"]): a for a in R["attempts"]}
        cum = []
        tot = 0.0
        for a in R["attempts"]:
            tot += a["usd"]
            cum.append(tot)
        cum = {(a["stage"], a["attempt"]): c for a, c in zip(R["attempts"], cum)}

        graph, nodes, grader = self.stage_graph()
        cnt = self.counters(0.0, 0.0)
        panel = card(13.6, 5.55, fill=SAND, stroke=SAND, r=0.2).move_to([0, TOP - 2.45, 0])
        con = Console()
        prompt = con.place(mline("$ python scripts/trace.py results/runs/p3/libspng__arvo_14935",
                                 SLATE), 0)
        ledger_lab = T("ledger", 20, SAGE, weight="SEMIBOLD").move_to([-6.2, -3.05, 0])

        # beat 0: the tool and the header
        with self.beat(0) as tr:
            self.play(FadeIn(graph), FadeIn(cnt), FadeIn(panel), run_time=0.9)
            self.play(AddTextLetterByLetter(prompt), run_time=1.6)
            head = self.show_lines(con, L, 1, [0, 1, 2, 3], {0: MUTED, 1: MUTED, 2: MUTED, 3: MUTED})
            self.play(FadeIn(ledger_lab), run_time=0.4)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        k = 5
        r1 = find_row(L, "rca", 1)
        r2 = find_row(L, "rca", 2)
        with self.beat(1) as tr:
            self.play(*self.activate(nodes, 0), run_time=0.6)
            rows1 = self.show_lines(con, L, k, [r1, r1 + 1])
            h1 = self.hl(rows1[0], TERRA)
            a = att[("rca", 1)]
            self.play(Transform(cnt, self.counters(a["t_end"] / 60, cum[("rca", 1)])), run_time=0.6)
            rows2 = self.show_lines(con, L, k + 2, [r2, r2 + 1])
            h2 = self.hl(rows2[0], SAGE)
            a = att[("rca", 2)]
            self.play(Transform(cnt, self.counters(a["t_end"] / 60, cum[("rca", 2)])), run_time=0.6)
            f = next(x for x in R["facts"] if x["stage"] == "rca")
            c1 = self.chip(f"rca {f['function']} (unchecked)").next_to(ledger_lab, RIGHT, buff=0.3)
            self.play(FadeIn(c1, shift=UP * 0.15), run_time=0.6)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        p1 = find_row(L, "poc", 1)
        poc = att[("poc", 1)]
        with self.beat(2) as tr:
            self.play(*self.activate(nodes, 1), FadeOut(h1), FadeOut(h2), run_time=0.6)
            rows3 = self.show_lines(con, L, k + 4, [p1, p1 + 1])
            h3 = self.hl(rows3[0], SAGE)
            fr = poc["frames_fn"]
            rca_fn = next(x for x in R["facts"] if x["stage"] == "rca")["function"]
            ev = VGroup(T("exec_poc evidence", 22, AMBER, weight="SEMIBOLD"),
                        M(poc["crash_type"], 20, INK),
                        M(f"#0 {fr[0]}", 20, INK),
                        M(f"#1 {fr[1]}  ✓ RCA", 20, SAGE),
                        ).arrange(DOWN, aligned_edge=LEFT, buff=0.14)
            evc = VGroup(card(ev.width + 0.5, ev.height + 0.45, fill="#FFFFFF", stroke=AMBER), ev)
            ev.move_to(evc[0])
            evc.move_to([4.55, 0.55, 0])
            self.play(FadeIn(evc, shift=LEFT * 0.2), run_time=0.8)
            assert fr[1] == rca_fn and poc["matches_rca"]
            self.play(Transform(cnt, self.counters(poc["t_end"] / 60, cum[("poc", 1)])), run_time=0.6)
            f = next(x for x in R["facts"] if x["stage"] == "poc")
            c2 = self.chip(f"{f['file']} {f['sha']}").next_to(c1, RIGHT, buff=0.2)
            self.play(FadeIn(c2, shift=UP * 0.15), run_time=0.6)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        q1 = find_row(L, "patch", 1)
        pat = att[("patch", 1)]
        with self.beat(3) as tr:
            self.play(*self.activate(nodes, 2), FadeOut(h3), FadeOut(evc), run_time=0.6)
            rows4 = self.show_lines(con, L, k + 6, [q1, q1 + 1])
            checks = [("applies", pat["build_ok"]), ("rebuilds", pat["build_ok"]),
                      ("PoC no longer crashes", pat["verified_poc_fixed"]),
                      ("tests pass", pat["tests_passed"])]
            items = VGroup(*[T(("✓  " if ok else "✗  ") + name, 22, SAGE if ok else TERRA)
                             for name, ok in checks]).arrange(DOWN, aligned_edge=LEFT, buff=0.16)
            title = T("exec_patch checks", 22, AMBER, weight="SEMIBOLD")
            box = VGroup(title, items).arrange(DOWN, aligned_edge=LEFT, buff=0.22)
            pc = VGroup(card(box.width + 0.6, box.height + 0.45, fill="#FFFFFF", stroke=AMBER), box)
            box.move_to(pc[0])
            pc.move_to([4.6, 0.45, 0])
            self.play(FadeIn(pc[0]), FadeIn(title), run_time=0.5)
            self.play(LaggedStart(*[FadeIn(i, shift=RIGHT * 0.1) for i in items], lag_ratio=0.6),
                      run_time=1.8)
            f = next(x for x in R["facts"] if x["stage"] == "patch")
            c3 = self.chip(f"{f['file']} {f['sha']}").next_to(c2, RIGHT, buff=0.2)
            end_i = next(i for i, l in enumerate(L) if "run_end:" in l)
            tail = self.show_lines(con, L, k + 8, [end_i - 1, end_i], {end_i - 1: MUTED})
            self.play(FadeIn(c3, shift=UP * 0.15),
                      Transform(cnt, self.counters(R["seconds"] / 60, R["usd"])), run_time=0.7)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        g = R["grade"]
        gi = find(L, "official grade:")
        with self.beat(4) as tr:
            self.play(*self.activate(nodes, -1), FadeOut(pc), run_time=0.5)
            self.play(grader[0].animate.set_fill("#FFFFFF").set_stroke(SAGE, width=5),
                      grader[1].animate.set_color(SAGE), run_time=0.8)
            gl = self.show_lines(con, L, k + 10, [gi], {gi: SAGE})
            marks = VGroup(*[T(f"S{i} {'✓' if g[f's{i}'] else '✗'}", 24,
                               SAGE if g[f's{i}'] else TERRA, weight="SEMIBOLD") for i in (1, 2, 3, 4)])
            marks.arrange(RIGHT, buff=0.35)
            mk = VGroup(card(marks.width + 0.4, marks.height + 0.3, fill="#FFFFFF", stroke=SAGE), marks)
            marks.move_to(mk[0])
            mk.move_to([6.85, 3.4, 0], aligned_edge=RIGHT)
            self.play(FadeOut(cnt), run_time=0.4)
            self.play(LaggedStart(*[FadeIn(x, scale=1.2) for x in [mk[0], *marks]], lag_ratio=0.25),
                      run_time=1.2)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        # beat 5: a correct rejection (htslib), and B1's false claim on the same task
        H = TR["htslib_p3"]
        B = TR["htslib_b1"]
        with self.beat(5) as tr:
            old = VGroup(prompt, head, rows1, rows2, rows3, rows4, tail, gl, c1, c2, c3, ledger_lab, mk)
            short = card(13.6, 4.4, fill=SAND, stroke=SAND, r=0.2).move_to([0, TOP + 0.3 - 4.4 / 2, 0])
            self.play(FadeOut(old), *self.activate(nodes, 1, TERRA),
                      grader[0].animate.set_fill("#EDEAE4").set_stroke(MUTED, width=2.5),
                      grader[1].animate.set_color(MUTED),
                      Transform(panel, short), run_time=0.8)
            pr2 = con.place(mline(f"$ python scripts/trace.py results/runs/p3/"
                                  f"{RJ['task_id'].replace('/', '__')}", SLATE), 0)
            self.play(AddTextLetterByLetter(pr2), run_time=1.0)
            idx = [0, 3]
            pocs = [find_row(H, "poc", n) for n in (1, 2, 3)]
            for p in pocs:
                idx += [p, p + 1]
            ei = next(i for i, l in enumerate(H) if "run_end:" in l)
            gi2 = find(H, "official grade:")
            idx += [ei, gi2]
            cols = {i: MUTED for i in (0, 3)}
            cols[gi2] = INK
            hl_lines = self.show_lines(con, H, 1, idx, cols, rt=0.22)
            rr = VGroup(*[SurroundingRectangle(hl_lines[2 + 2 * j], color=TERRA, buff=0.05,
                                               corner_radius=0.05, stroke_width=2.5,
                                               fill_color=TERRA, fill_opacity=0.12)
                          for j in range(3)])
            self.play(LaggedStart(*[Create(r) for r in rr], lag_ratio=0.4), run_time=1.2)
            agree = self.chip("grader agrees: no crash (S1 fail)", SAGE, 18)
            agree.move_to([6.5, hl_lines[-1].get_y() - 0.42, 0], aligned_edge=RIGHT)
            self.play(FadeIn(agree), run_time=0.6)
            self.wait(1.2)
            # B1 on the same task
            bi = next(i for i, l in enumerate(B) if re.match(r"^\d\d:\d\d:\d\d\s+single", l))
            be = next(i for i, l in enumerate(B) if "run_end:" in l)
            bg = find(B, "official grade:")
            bl = VGroup(T("Claude Code alone (B1), same task", 22, INK, weight="SEMIBOLD"),
                        *[mline(B[i], TERRA if i == bg else INK, 80) for i in (be, bg)]
                        ).arrange(DOWN, aligned_edge=LEFT, buff=0.14)
            bc = VGroup(card(bl.width + 0.5, bl.height + 0.4, fill="#FFFFFF", stroke=TERRA), bl)
            bl.move_to(bc[0])
            bc.move_to([0, -2.5, 0])
            self.play(FadeIn(bc, shift=UP * 0.2), run_time=0.8)
            self.play(Indicate(bl[-1], color=TERRA, scale_factor=1.04), run_time=1.0)
            self.wait(max(tr.get_remaining_duration(), 0))
        self.wait(0.4)  # end-of-scene hold, outside the beat
