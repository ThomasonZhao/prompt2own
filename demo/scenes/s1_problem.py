from manim import (DOWN, LEFT, RIGHT, UP, Arrow, Create, FadeIn, FadeOut, GrowFromEdge,
                   LaggedStart, Line, Rectangle, ReplacementTransform, VGroup, Write, AnimationGroup)

from style import (AMBER, INK, MUTED, SAGE, SLATE, TERRA, PaperScene, T, card, labeled_card)
from data import D, pct

P = D["paper"]
BASE_Y, TOP_Y, X0 = -2.35, 1.15, -5.2       # chart: y of 0% and of 100%, left x
H = TOP_Y - BASE_Y


def bar(x, v, color, w=0.9):
    r = Rectangle(width=w, height=max(H * v / 100, 0.001), fill_color=color, fill_opacity=1,
                  stroke_width=0)
    r.move_to([x, BASE_Y, 0], aligned_edge=DOWN)
    return r


class S1Problem(PaperScene):
    SCENE_ID = "s1_problem"

    def construct(self):
        # stage chain
        names = ["Find the root cause", "Reproduce (PoC)", "Patch"]
        cards = VGroup(*[labeled_card(n, w=3.3, h=0.9, stroke=SLATE, tsize=26) for n in names])
        cards.arrange(RIGHT, buff=0.9).to_edge(UP, buff=0.45)
        arrows = VGroup(*[Arrow(cards[i].get_right(), cards[i + 1].get_left(), buff=0.1,
                                color=INK, stroke_width=3, max_tip_length_to_length_ratio=0.25)
                          for i in range(2)])

        # axes
        yax = Line([X0, BASE_Y, 0], [X0, TOP_Y + 0.15, 0], color=MUTED, stroke_width=2)
        xax = Line([X0, BASE_Y, 0], [5.6, BASE_Y, 0], color=MUTED, stroke_width=2)
        ticks = VGroup()
        for v in (0, 50, 100):
            y = BASE_Y + H * v / 100
            ticks.add(T(f"{v}%", 20, MUTED).next_to([X0, y, 0], LEFT, buff=0.15))
            if v:
                ticks.add(Line([X0, y, 0], [5.6, y, 0], color=MUTED, stroke_width=1,
                               stroke_opacity=0.35))
        ylab = T("tasks fixed", 22, MUTED).rotate(1.5708).next_to(ticks, LEFT, buff=0.2)
        src = T(f"{P['setup']} · CyberGym-E2E paper, {P['n_tasks']} tasks", 20, MUTED)
        src.move_to([2.1, TOP_Y + 0.35, 0])

        with self.beat(0) as tr:
            self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.2) for c in cards], lag_ratio=0.3),
                      run_time=1.4)
            self.play(LaggedStart(*[Create(a) for a in arrows], lag_ratio=0.4), run_time=0.8)
            self.play(Create(yax), Create(xax), FadeIn(ticks), FadeIn(ylab), run_time=0.8)
            b0 = bar(-3.0, P["patch_only"], SAGE, w=1.4)
            l0 = T(pct(P["patch_only"]), 30, INK, weight="SEMIBOLD").next_to(b0, UP, buff=0.12)
            n0 = T("patch only\n(given the crash)", 22, INK).next_to(b0, DOWN, buff=0.15)
            self.play(GrowFromEdge(b0, DOWN), run_time=1.2)
            self.play(FadeIn(l0), FadeIn(n0), FadeIn(src), run_time=0.6)
            self.wait(max(tr.get_remaining_duration() - 0.2, 0))

        with self.beat(1) as tr:
            xs = [0.0, 1.4, 2.8, 4.2]
            vals = [P["s1"], P["s2"], P["s3"], P["s4"]]
            cols = [AMBER, AMBER, AMBER, TERRA]
            bars = VGroup(*[bar(x, v, c) for x, v, c in zip(xs, vals, cols)])
            labs = VGroup(*[T(pct(v), 26, INK, weight="SEMIBOLD").next_to(b, UP, buff=0.1)
                            for v, b in zip(vals, bars)])
            ns = VGroup(*[T(s, 22, INK).next_to([x, BASE_Y, 0], DOWN, buff=0.2)
                          for s, x in zip(["S1", "S2", "S3", "S4"], xs)])
            e2e = T("end to end: find, reproduce, fix", 22, MUTED).next_to(bars, UP, buff=0.75)
            e2e.set_x(2.1).set_y(BASE_Y + 2.45)
            ghost = b0.copy()
            self.play(ReplacementTransform(ghost, bars), run_time=1.2)
            self.play(FadeIn(labs), FadeIn(ns), FadeIn(e2e), run_time=0.7)
            real = T("S4 = really fixed", 22, TERRA).move_to([4.6, BASE_Y + 1.75, 0])
            real_ptr = Line(real.get_bottom() + DOWN * 0.05, labs[3].get_top() + UP * 0.05,
                            color=TERRA, stroke_width=2)
            real = VGroup(real, real_ptr)
            self.play(FadeIn(real), run_time=0.6)
            # false claim: the agent stamps "done ✓", the hidden grader says ✗
            stamp = VGroup(card(1.9, 0.62, fill="#FFFFFF", stroke=TERRA),
                           T("done ✓", 26, TERRA, weight="SEMIBOLD"))
            stamp[1].move_to(stamp[0])
            stamp.next_to(cards[2], DOWN, buff=0.25).shift(LEFT * 1.2)
            gx = VGroup(card(2.2, 0.62, fill="#FFFFFF", stroke=MUTED),
                        T("grader: ✗", 26, TERRA))
            gx[1].move_to(gx[0])
            gx.next_to(stamp, RIGHT, buff=0.2)
            self.play(FadeIn(stamp, scale=1.15), run_time=0.6)
            self.play(FadeIn(gx), run_time=0.6)
            self.wait(max(tr.get_remaining_duration() - 0.2, 0))

        with self.beat(2) as tr:
            everything = VGroup(cards, arrows, yax, xax, ticks, ylab, src, b0, l0, n0, bars, labs,
                                ns, e2e, real, stamp, gx)
            self.play(FadeOut(everything, shift=UP * 0.3), run_time=0.8)
            title = T("Prompt2Own", 84, INK, weight="BOLD")
            sub = T("evidence-gated agents for vulnerability research", 36, MUTED)
            VGroup(title, sub).arrange(DOWN, buff=0.35).shift(UP * 0.9)
            q = T("Must every step show executable evidence?\n"
                  "Do agents become more correct, and more honest?", 30, SLATE,
                  line_spacing=1.2).next_to(sub, DOWN, buff=0.9)
            self.play(Write(title), run_time=1.0)
            self.play(FadeIn(sub, shift=UP * 0.15), run_time=0.7)
            self.play(FadeIn(q, shift=UP * 0.15), run_time=0.8)
            self.wait(max(tr.get_remaining_duration(), 0))
        self.wait(0.6)  # end-of-scene hold, outside the beat
