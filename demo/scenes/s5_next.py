from manim import DOWN, LEFT, RIGHT, UP, FadeIn, FadeOut, LaggedStart, VGroup, Write

from style import (AMBER, INK, MUTED, SAGE, SLATE, TERRA, PaperScene, T, M, card)
from data import D

AUTHOR = "Thomason Zhao"
REPO = "github.com/ThomasonZhao/prompt2own"

NEXT = [
    (TERRA, "A smarter patch guard", "independent tester agent,\nor fuzz the patched build"),
    (SLATE, "Ablation P0", "stages without guards: cost of\nsplitting vs. value of checking"),
    (SAGE, "Scale up", "60-100 tasks · 3 seeds\nguard-noise study"),
]


class S5Next(PaperScene):
    SCENE_ID = "s5_next"

    def construct(self):
        title = T("What's next", 40, INK, weight="SEMIBOLD").move_to([0, 2.7, 0])
        cards = VGroup()
        for col, head, body in NEXT:
            box = card(4.3, 2.6, fill="#FFFFFF", stroke=col)
            txt = VGroup(T(head, 26, col, weight="SEMIBOLD"), T(body, 22, INK, line_spacing=1.15))
            txt.arrange(DOWN, buff=0.3)
            if txt.width > 3.9:
                txt.scale_to_fit_width(3.9)
            cards.add(VGroup(box, txt.move_to(box)))
        cards.arrange(RIGHT, buff=0.25).move_to([0, 0.1, 0])

        with self.beat(0) as tr:
            self.play(FadeIn(title, shift=DOWN * 0.15), run_time=0.7)
            self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.25) for c in cards], lag_ratio=0.5),
                      run_time=2.2)
            self.wait(max(tr.get_remaining_duration() - 0.1, 0))

        g = D["graded"]
        name = T("Prompt2Own", 72, INK, weight="BOLD")
        sub = T("evidence-gated agents for vulnerability research", 30, MUTED)
        who = T(AUTHOR, 28, INK)
        repo = M(REPO, 24, SLATE)
        src = VGroup(T(f"All numbers from {g['total']} graded runs on CyberGym-E2E", 24, MUTED),
                     T(f"{g['n_tasks']} tasks × 3 configs · model {g['model']} in the Claude Code harness",
                       20, MUTED)).arrange(DOWN, buff=0.12)
        close = VGroup(name, sub, who, repo, src).arrange(DOWN, buff=0.32).move_to([0, 0.2, 0])
        if src.width > 13:
            src.scale_to_fit_width(13)
        with self.beat(1) as tr:
            self.play(FadeOut(VGroup(title, cards), shift=UP * 0.3), run_time=0.7)
            self.play(Write(name), run_time=0.9)
            self.play(LaggedStart(*[FadeIn(m, shift=UP * 0.1) for m in (sub, who, repo, src)],
                                  lag_ratio=0.3), run_time=1.4)
            self.wait(max(tr.get_remaining_duration(), 0))
        self.wait(1.6)  # end-of-scene hold, outside the beat
