from manim import (DOWN, LEFT, RIGHT, UP, Arrow, Create, Dot, FadeIn, FadeOut, GrowFromEdge,
                   Indicate, LaggedStart, Line, MoveAlongPath, Rectangle, ReplacementTransform,
                   VGroup, VMobject, Write, CubicBezier, SurroundingRectangle, linear)

from style import (AMBER, INK, MUTED, SAGE, SAND, SLATE, TERRA, PaperScene, T, M, card)
from data import D, f2

MN = D["main"]
G = D["guards"]
PR = D["paired"]
FA = D["false_accepts"]
N = D["graded"]["n_tasks"]

CFG = [("b1", "B1  Claude Code as shipped", MUTED),
       ("b2", "B2  + our workflow as a prompt", SLATE),
       ("p3", "P3  Prompt2Own: stages + guards", AMBER)]
GX = [-4.0, -1.2, 1.6, 4.4]
OFF = [-0.68, 0.0, 0.68]
BW = 0.6
BASE, TOPV = -2.35, 1.55
H = TOPV - BASE


def y(v):
    return BASE + H * v


class S4Findings(PaperScene):
    SCENE_ID = "s4_findings"

    def construct(self):
        # axes
        x0, x1 = -5.6, 5.9
        yax = Line([x0, BASE, 0], [x0, TOPV + 0.1, 0], color=MUTED, stroke_width=2)
        xax = Line([x0, BASE, 0], [x1, BASE, 0], color=MUTED, stroke_width=2)
        grid = VGroup()
        for v in (0.0, 0.25, 0.5, 0.75, 1.0):
            grid.add(T(f"{v:.2f}", 20, MUTED).next_to([x0, y(v), 0], LEFT, buff=0.12))
            if v:
                grid.add(Line([x0, y(v), 0], [x1, y(v), 0], color=MUTED, stroke_width=1,
                              stroke_opacity=0.3))
        ylab = T(f"fraction of {N} tasks", 22, MUTED).rotate(1.5708).next_to(grid, LEFT, buff=0.15)
        xl = VGroup(*[T(s, 22, INK if i < 3 else TERRA, weight="NORMAL" if i < 3 else "SEMIBOLD")
                      .next_to([gx, BASE, 0], DOWN, buff=0.18)
                      for i, (s, gx) in enumerate(zip(["S1  PoC crashes", "S2  own fix", "S3  tests pass",
                                                       "S4  real fix"], GX))])
        xcap = T("official grader stage (cumulative)", 20, MUTED).next_to(xl, DOWN, buff=0.15)
        legend = VGroup()
        for _, name, col in CFG:
            sw = Rectangle(width=0.32, height=0.32, fill_color=col, fill_opacity=1, stroke_width=0)
            legend.add(VGroup(sw, T(name, 22, INK)).arrange(RIGHT, buff=0.15))
        legend.arrange(RIGHT, buff=0.55).move_to([0.15, 3.35, 0])
        if legend.width > 13.2:
            legend.scale_to_fit_width(13.2)

        bars, whisk = VGroup(), VGroup()
        for j, (c, _, col) in enumerate(CFG):
            for i, s in enumerate(("s1", "s2", "s3", "s4")):
                d = MN[c]["all"]
                x = GX[i] + OFF[j]
                b = Rectangle(width=BW, height=max(H * d[s], 0.001), fill_color=col,
                              fill_opacity=1, stroke_width=0).move_to([x, BASE, 0], aligned_edge=DOWN)
                bars.add(b)
                lo, hi = d[s + "_lo"], d[s + "_hi"]
                w = VGroup(Line([x, y(lo), 0], [x, y(hi), 0], color=INK, stroke_width=2),
                           Line([x - 0.1, y(lo), 0], [x + 0.1, y(lo), 0], color=INK, stroke_width=2),
                           Line([x - 0.1, y(hi), 0], [x + 0.1, y(hi), 0], color=INK, stroke_width=2))
                whisk.add(w)
        ci_note = T("whiskers: Wilson 95% CI · one seed per task", 18, MUTED).move_to([3.9, TOPV + 0.32, 0])

        with self.beat(0) as tr:
            self.play(LaggedStart(*[FadeIn(l, shift=DOWN * 0.15) for l in legend], lag_ratio=0.4),
                      run_time=1.6)
            self.play(Create(yax), Create(xax), FadeIn(grid), FadeIn(ylab), FadeIn(xl), FadeIn(xcap),
                      run_time=0.9)
            self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in bars], lag_ratio=0.06),
                      run_time=2.0)
            self.play(FadeIn(whisk), FadeIn(ci_note), run_time=0.6)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        s4 = [bars[j * 4 + 3] for j in range(3)]
        vals = VGroup(*[T(f2(MN[c]["all"]["s4"]), 24, INK, weight="BOLD").next_to(
            [s4[j].get_x(), y(MN[c]["all"]["s4_hi"]), 0], UP, buff=0.08) for j, (c, _, _) in enumerate(CFG)])
        box = SurroundingRectangle(VGroup(*s4, vals), color=TERRA, buff=0.15, corner_radius=0.1,
                                   stroke_width=2.5)
        pnote = T(f"paired McNemar, n = {N}:  P3 vs B1 p = {f2(PR['p3_vs_b1']['p'])}  ·  "
                  f"P3 vs B2 p = {f2(PR['p3_vs_b2']['p'])}  ·  B2 vs B1 p = {f2(PR['b2_vs_b1']['p'])}",
                  20, INK)
        pnote.move_to([0.15, 2.72, 0])
        ho = MN
        hand = T(f"hand-off cost, S1 → S2:  P3 {f2(ho['p3']['all']['s1'])} → {f2(ho['p3']['all']['s2'])}"
                 f"   vs   B1 {f2(ho['b1']['all']['s1'])} → {f2(ho['b1']['all']['s2'])}", 20, MUTED)
        hand.move_to([-1.6, TOPV + 0.32, 0])
        with self.beat(1) as tr:
            others = VGroup(*[b for k, b in enumerate(bars) if k % 4 != 3])
            self.play(others.animate.set_opacity(0.35), Create(box), FadeIn(vals), run_time=1.0)
            self.play(FadeIn(pnote, shift=DOWN * 0.1), run_time=0.7)
            self.play(FadeOut(ci_note), FadeIn(hand), run_time=0.6)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        # guard precision
        chart = VGroup(yax, xax, grid, ylab, xl, xcap, bars, whisk, box, vals, pnote, hand, legend)
        gx0, gx1 = -3.2, 5.0
        L = gx1 - gx0
        rows = []
        for k, (g, nm, col, truth) in enumerate((("exec_poc", "PoC guard", SAGE, "S1"),
                                                  ("exec_patch", "patch guard", TERRA, "S4"))):
            yy = 0.95 - k * 1.7
            d = G[g]
            b = Rectangle(width=L * d["precision"], height=0.75, fill_color=col, fill_opacity=1,
                          stroke_width=0).move_to([gx0, yy, 0], aligned_edge=LEFT)
            name = VGroup(M(g, 24, INK), T(nm, 20, MUTED)).arrange(DOWN, aligned_edge=RIGHT, buff=0.08)
            name.next_to([gx0, yy, 0], LEFT, buff=0.3)
            val = T(f2(d["precision"]), 30, INK, weight="BOLD").next_to(b, RIGHT, buff=0.15)
            cnt = T(f"{d['false_accepts']} of {d['accepts']} accepts false (vs official {truth})", 21,
                    col).next_to(b, DOWN, buff=0.12).align_to(b, LEFT)
            rows.append(VGroup(b, name, val, cnt))
        gax = Line([gx0, -2.2, 0], [gx1, -2.2, 0], color=MUTED, stroke_width=2)
        gt = VGroup(*[T(f"{v:.2f}", 20, MUTED).next_to([gx0 + L * v, -2.2, 0], DOWN, buff=0.12)
                      for v in (0.0, 0.5, 1.0)])
        gl = T("guard precision: accepted and truly correct / accepted", 22, MUTED).next_to(gt, DOWN, buff=0.12)
        gtitle = T("Where verification works", 34, INK, weight="SEMIBOLD").move_to([0, 2.9, 0])
        with self.beat(2) as tr:
            self.play(FadeOut(chart, shift=LEFT * 0.4), run_time=0.8)
            self.play(FadeIn(gtitle), Create(gax), FadeIn(gt), FadeIn(gl), run_time=0.7)
            for r in rows:
                self.play(GrowFromEdge(r[0], LEFT), FadeIn(r[1]), run_time=1.0)
                self.play(FadeIn(r[2]), FadeIn(r[3]), run_time=0.6)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        # fixes my PoC, not the bug
        prog = card(11.4, 4.3, fill="#FFFFFF", stroke=MUTED, r=0.25).move_to([0.1, -0.15, 0])
        plab = T("the program", 20, MUTED).next_to(prog, UP, buff=0.1).align_to(prog, LEFT)
        entry = VGroup(card(1.9, 0.75, fill=SAND, stroke=INK), T("fuzz input", 22))
        entry[1].move_to(entry[0])
        entry.move_to([-4.4, -0.15, 0])
        bugA = VGroup(card(3.7, 0.85, fill="#FFFFFF", stroke=SLATE), T("bug the agent found", 22, SLATE))
        bugA[1].move_to(bugA[0])
        bugA.move_to([4.1, 1.05, 0])
        bugB = VGroup(card(3.7, 0.85, fill="#FFFFFF", stroke=TERRA),
                      T("benchmark's target bug", 22, TERRA, weight="SEMIBOLD"))
        bugB[1].move_to(bugB[0])
        bugB.move_to([4.1, -1.35, 0])
        pa = CubicBezier(entry.get_right(), entry.get_right() + RIGHT * 2.5,
                         bugA.get_left() + LEFT * 2.5, bugA.get_left()).set_stroke(SLATE, 3)
        pb = CubicBezier(entry.get_right(), entry.get_right() + RIGHT * 2.5,
                         bugB.get_left() + LEFT * 2.5, bugB.get_left() + LEFT * 0.2).set_stroke(TERRA, 3)
        la = VGroup()
        lb = VGroup()
        gate_pt = pa.point_from_proportion(0.72)
        gate = VGroup(Line(gate_pt + UP * 0.38, gate_pt + DOWN * 0.38, color=SAGE, stroke_width=9),
                      T("agent's patch", 20, SAGE, weight="SEMIBOLD").next_to(gate_pt, DOWN, buff=0.45))
        cap = T("False success moves to the edge with the weakest check.", 28, INK, weight="SEMIBOLD")
        cap.move_to([0.1, -2.85, 0])
        note = T(f"{FA['different_location']} of {FA['n']} patch-guard false accepts fixed a real "
                 "but different bug", 20, MUTED)
        note.move_to([2.2, -3.45, 0])
        with self.beat(3) as tr:
            self.play(FadeOut(VGroup(gtitle, gax, gt, gl, *rows)), run_time=0.7)
            self.play(FadeIn(prog), FadeIn(plab), FadeIn(entry), FadeIn(bugA), FadeIn(bugB),
                      run_time=0.8)
            self.play(Create(pa), Create(pb), FadeIn(la), FadeIn(lb), run_time=1.0)
            self.play(FadeIn(gate, scale=1.2), run_time=0.6)
            mine = Dot(entry.get_right(), radius=0.13, color=SLATE)
            mlab = T("agent's PoC", 20, SLATE).next_to(mine, UP, buff=0.12).shift(LEFT * 0.8)
            mlab.add_updater(lambda m: m.next_to(mine, UP, buff=0.12).shift(LEFT * 0.8))
            self.add(mine, mlab)
            stop = VMobject().set_points(pa.get_subcurve(0, 0.66).points)
            self.play(MoveAlongPath(mine, stop), run_time=1.4, rate_func=linear)
            ok = T("blocked ✓  exec_patch accepts", 22, SAGE, weight="SEMIBOLD").next_to(gate, RIGHT, buff=0.1).shift(UP * 0.35)
            ok.move_to([-2.0, 1.55, 0])
            self.play(FadeIn(ok), run_time=0.5)
            gt_dot = Dot(entry.get_right(), radius=0.13, color=TERRA)
            glab = T("ground-truth PoC", 20, TERRA).next_to(gt_dot, DOWN, buff=0.14).shift(LEFT * 1.0)
            glab.add_updater(lambda m: m.next_to(gt_dot, DOWN, buff=0.14).shift(LEFT * 1.0))
            self.add(gt_dot, glab)
            self.play(MoveAlongPath(gt_dot, pb), run_time=1.6, rate_func=linear)
            bad = T("still crashes ✗  S4 fails", 22, TERRA, weight="SEMIBOLD").move_to([3.75, -2.02, 0])
            self.play(FadeIn(bad), Indicate(bugB, color=TERRA, scale_factor=1.05), run_time=0.9)
            self.play(FadeIn(note), run_time=0.5)
            self.play(Write(cap), run_time=1.0)
            mlab.clear_updaters()
            glab.clear_updaters()
            self.wait(max(tr.get_remaining_duration(), 0))
        self.wait(0.8)  # end-of-scene hold, outside the beat
