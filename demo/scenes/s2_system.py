from manim import (DOWN, LEFT, RIGHT, UP, Arrow, Create, CurvedArrow, DashedLine, DashedVMobject,
                   DashedVMobject, FadeIn, FadeOut, GrowFromEdge, LaggedStart, Rectangle,
                   RoundedRectangle, VGroup, Write, AnimationGroup, Indicate)

from style import (AMBER, BG, INK, MUTED, SAGE, SAND, SLATE, TERRA, PaperScene, T, M, card,
                   labeled_card)
from data import D

XS = [-5.05, -2.15, 0.75]          # stage columns
WY, GY = 1.45, -0.62             # worker / guard card rows
CW, CH = 2.6, 1.25


def zone(x0, x1, y0, y1, color, label, top=True):
    r = RoundedRectangle(width=x1 - x0, height=y1 - y0, corner_radius=0.2, stroke_color=color,
                         stroke_width=2, fill_color=color, fill_opacity=0.08)
    r.move_to([(x0 + x1) / 2, (y0 + y1) / 2, 0])
    d = DashedVMobject(r.copy().set_fill(opacity=0), num_dashes=90)
    r.set_stroke(width=0)
    lab = T(label, 20, color, weight="SEMIBOLD")
    lab.move_to([x0 + 0.2, (y1 - 0.22) if top else (y0 + 0.22), 0], aligned_edge=LEFT)
    return VGroup(r, d, lab)


class S2System(PaperScene):
    SCENE_ID = "s2_system"

    def construct(self):
        orch = VGroup(card(8.9, 0.85, fill="#FFFFFF", stroke=INK),
                      T("Orchestrator", 26, weight="SEMIBOLD"),
                      T("stage order in code · retries · caps · event log", 20, MUTED))
        orch[1:].arrange(RIGHT, buff=0.4).move_to(orch[0])
        orch.move_to([-2.15, 3.35, 0])

        wz = zone(-6.6, 2.3, 0.6, 2.62, SLATE, "WORKER ZONE · fresh Claude Code session per attempt")
        workers = VGroup(*[labeled_card(t, s, w=CW, h=CH, stroke=SLATE, sub_mono=True, tsize=26,
                                        ssize=21)
                           for t, s in (("RCA agent", "→ rca.json"), ("PoC agent", "→ poc.bin"),
                                        ("Patch agent", "→ fix.patch"))])
        for w_, x in zip(workers, XS):
            w_.move_to([x, WY - 0.08, 0])

        gz = zone(-6.6, 2.3, -2.05, 0.05, AMBER, "GUARD ZONE", top=False)
        guards = VGroup(*[labeled_card(t, s, w=CW, h=CH, stroke=AMBER, tsize=24, ssize=19)
                          for t, s in (("null guard", "checked later\nby exec_poc"),
                                       ("exec_poc", "sanitizer crash +\nframes match RCA"),
                                       ("exec_patch", "applies · rebuilds\nPoC fixed · tests pass"))])
        for g_, x in zip(guards, XS):
            g_.move_to([x, GY, 0])
        # guard names are code identifiers: render them in mono
        for g_, nm in zip(guards, ("null guard", "exec_poc", "exec_patch")):
            name = g_[1][0]
            mono = M(nm, 23, INK).move_to(name)
            g_[1].remove(name)
            g_[1].add(mono)

        ledger = VGroup(card(8.9, 0.8, fill=SAGE, stroke=SAGE, opacity=0.15),
                        T("Evidence ledger (append-only): written only on guard accept", 22, SAGE,
                          weight="SEMIBOLD"))
        if ledger[1].width > 8.5:
            ledger[1].scale_to_fit_width(8.5)
        ledger[1].move_to(ledger[0])
        ledger.move_to([-2.15, -2.8, 0])

        with self.beat(0) as tr:
            self.play(FadeIn(orch, shift=DOWN * 0.2), run_time=0.8)
            self.play(FadeIn(wz), run_time=0.6)
            self.play(LaggedStart(*[GrowFromEdge(w_, UP) for w_ in workers], lag_ratio=0.35),
                      run_time=1.5)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        submits = VGroup(*[Arrow(w_.get_bottom() + LEFT * 0.35, g_.get_top() + LEFT * 0.35,
                                 buff=0.05, color=INK, stroke_width=3)
                           for w_, g_ in zip(workers, guards)])
        accepts = VGroup(*[CurvedArrow(guards[i].get_right() + UP * 0.15,
                                       workers[i + 1].get_left() + DOWN * 0.15,
                                       angle=1.0, color=SAGE, stroke_width=3.5)
                           for i in range(2)])
        with self.beat(1) as tr:
            self.play(FadeIn(gz), run_time=0.6)
            self.play(LaggedStart(*[FadeIn(g_, shift=UP * 0.2) for g_ in guards], lag_ratio=0.3),
                      run_time=1.2)
            self.play(LaggedStart(*[Create(a) for a in submits], lag_ratio=0.3), run_time=0.9)
            self.play(Indicate(guards[1], color=AMBER, scale_factor=1.05), run_time=1.0)
            self.play(Indicate(guards[2], color=AMBER, scale_factor=1.05), run_time=1.0)
            self.play(LaggedStart(*[Create(a) for a in accepts], lag_ratio=0.4), run_time=1.0)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        rejects = VGroup()
        for i in (1, 2):
            a = DashedLine(guards[i].get_top() + RIGHT * 0.45 + UP * 0.05,
                           workers[i].get_bottom() + RIGHT * 0.45 + DOWN * 0.05,
                           color=TERRA, stroke_width=3, dash_length=0.09)
            a.add_tip(tip_length=0.2, tip_width=0.2)
            rejects.add(a)
        rlab = VGroup(*[T("reject +\nreason", 18, TERRA).next_to(r, RIGHT, buff=0.08) for r in rejects])
        drops = VGroup(*[Arrow(g_.get_bottom() + RIGHT * 0.9, [g_.get_x() + 0.9, ledger.get_top()[1], 0], buff=0.05,
                               color=SAGE, stroke_width=3) for g_ in guards])
        with self.beat(2) as tr:
            self.play(LaggedStart(*[Create(r) for r in rejects], lag_ratio=0.3), FadeIn(rlab),
                      run_time=1.0)
            self.play(LaggedStart(*[Create(d) for d in drops], lag_ratio=0.2), run_time=0.8)
            self.play(GrowFromEdge(ledger, DOWN), run_time=0.9)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        # grader, after the run, behind a frosted panel
        div = DashedLine([2.72, 3.8, 0], [2.72, -3.4, 0], color=MUTED, stroke_width=2,
                         dash_length=0.08)
        after = T("after the run ends", 22, MUTED).move_to([4.95, 3.35, 0])
        gbox = card(4.0, 3.9, fill="#EDEAE4", stroke=INK)
        gtitle = T("Official grader", 30, weight="SEMIBOLD")
        ghold = T("holds the ground-truth PoC", 22, MUTED)
        ladder = VGroup(*[T(s, 23, INK if i < 3 else TERRA, weight="NORMAL" if i < 3 else "BOLD")
                          for i, s in enumerate(["S1  agent PoC crashes the build",
                                                 "S2  agent patch stops it",
                                                 "S3  project tests pass",
                                                 "S4  benchmark's own crash fixed"])])
        ladder.arrange(DOWN, buff=0.22, aligned_edge=LEFT)
        ginner = VGroup(gtitle, ghold, ladder).arrange(DOWN, buff=0.3)
        if ginner.width > 3.7:
            ginner.scale_to_fit_width(3.7)
        grader = VGroup(gbox, ginner.move_to(gbox)).move_to([4.95, 0.55, 0])
        frost = VGroup(card(4.0, 3.9, fill=BG, stroke=MUTED, opacity=0.95),
                       VGroup(T("hidden from", 26, MUTED, weight="SEMIBOLD"),
                              T("workers and guards", 26, MUTED, weight="SEMIBOLD")).arrange(DOWN, buff=0.12))
        frost[1].move_to(frost[0])
        frost.move_to(grader)
        cap_t = T("Guards never see ground truth. The grader runs after the run.", 26, INK)
        cap = VGroup(card(cap_t.width + 0.6, cap_t.height + 0.4, fill=SAND, stroke=SAND), cap_t)
        with self.beat(3) as tr:
            self.play(Create(div), FadeIn(after), run_time=0.7)
            self.play(FadeIn(grader), FadeIn(frost), run_time=0.9)
            frame = self.camera.frame
            self.play(frame.animate.scale(0.75).move_to([2.0, 0.4, 0]), run_time=1.2)
            cap.scale(0.75).move_to([2.0, 0.4 - 3.0 * 0.75 + 0.45, 0])
            self.play(FadeIn(cap, shift=UP * 0.1), run_time=0.7)
            self.wait(1.6)
            self.play(FadeOut(frost), run_time=0.8)
            self.play(Indicate(ladder[3], color=TERRA, scale_factor=1.06), run_time=1.0)
            self.wait(max(tr.get_remaining_duration() - 1.0, 0))
            self.play(frame.animate.scale(1 / 0.75).move_to([0, 0, 0]), FadeOut(cap), run_time=1.0)
        self.wait(0.5)
