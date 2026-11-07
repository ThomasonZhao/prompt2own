"""Shared look and scene base class: warm paper palette, Inter + JetBrains Mono, footer, beats."""
from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path

from manim import (DL, DOWN, LEFT, RIGHT, UP, UR, MovingCameraScene, Rectangle, RoundedRectangle,
                   Text, VGroup, config, smooth)
from manim_voiceover import VoiceoverScene

DEMO = Path(__file__).resolve().parent
sys.path.insert(0, str(DEMO))
from narration import NARRATION  # noqa: E402
from tts import make_service  # noqa: E402

BG = "#FBF7F0"
INK = "#2B2A28"
MUTED = "#8A847A"
TERRA = "#C8553D"
AMBER = "#E0A458"
SAGE = "#5B8E7D"
SLATE = "#4F6D8C"
SAND = "#EFE6D8"

SANS = "Inter"
MONO = "JetBrains Mono"

STROKE = 2.5          # px-ish stroke for outlines
T_MOVE = 0.9          # default transition length (0.6-1.2 s rule)

config.background_color = BG


def T(s: str, size: float = 32, color: str = INK, weight: str = "NORMAL", **kw) -> Text:
    return Text(s, font=SANS, font_size=size, color=color, weight=weight, **kw)


def M(s: str, size: float = 24, color: str = INK, **kw) -> Text:
    return Text(s, font=MONO, font_size=size, color=color, **kw)


def card(w: float, h: float, fill: str = "#FFFFFF", stroke: str = INK, r: float = 0.18,
         opacity: float = 1.0, sw: float = STROKE) -> RoundedRectangle:
    return RoundedRectangle(width=w, height=h, corner_radius=r, fill_color=fill,
                            fill_opacity=opacity, stroke_color=stroke, stroke_width=sw)


def labeled_card(title: str, sub: str = "", w: float = 3.0, h: float = 1.3, stroke: str = INK,
                 fill: str = "#FFFFFF", tsize: float = 30, ssize: float = 22,
                 sub_mono: bool = False) -> VGroup:
    box = card(w, h, fill=fill, stroke=stroke)
    t = T(title, tsize, weight="SEMIBOLD")
    g = VGroup(t)
    if sub:
        s = (M(sub, ssize, MUTED) if sub_mono else T(sub, ssize, MUTED))
        g.add(s)
        g.arrange(DOWN, buff=0.14)
    if g.width > w - 0.35:
        g.scale_to_fit_width(w - 0.35)
    g.move_to(box)
    return VGroup(box, g)


class PaperScene(VoiceoverScene, MovingCameraScene):
    """Base for every scene: background, footer, TTS, and beats driven by narration.py."""

    SCENE_ID = ""

    def setup(self):
        super().setup()
        self.camera.background_color = BG
        self.set_speech_service(make_service())
        self._beats: list[dict] = []
        frame = self.camera.frame
        ft = T("Prompt2Own · CS329Z midway", 20, MUTED)
        fbg = Rectangle(width=ft.width + 0.3, height=ft.height + 0.2, fill_color=BG,
                        fill_opacity=1, stroke_width=0).move_to(ft)
        self.footer = VGroup(fbg, ft).set_z_index(50)
        w0, h0 = frame.width, self.footer.width

        def follow(m):
            k = frame.width / w0
            m.set_width(h0 * k)
            m.move_to(frame.get_corner(DL) + (RIGHT * 0.35 + UP * 0.25) * k, aligned_edge=DL)
        self.footer.add_updater(follow)
        follow(self.footer)
        self.add(self.footer)

    @contextmanager
    def beat(self, i: int):
        text = NARRATION[self.SCENE_ID][i]
        rec = {"beat": i + 1, "start": float(self.renderer.time), "text": text}
        self._beats.append(rec)
        with self.voiceover(text=text) as tr:
            yield tr
            rec["audio"] = float(tr.duration)
            rec["anim_end"] = float(self.renderer.time)   # last animation/wait inside the beat

    def tear_down(self):
        out = DEMO / "cache" / "timings"
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{self.SCENE_ID}.json").write_text(json.dumps(
            {"scene": self.SCENE_ID, "duration": float(self.renderer.time), "beats": self._beats},
            indent=1))
        super().tear_down()


def ease():
    return smooth
