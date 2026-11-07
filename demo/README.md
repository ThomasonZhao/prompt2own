# Prompt2Own midway demo video

A 3-minute video (under the 3:00 limit) built reproducibly with Manim, from the real result files.

## Rebuild

```bash
bash demo/build.sh            # 1080p30, about 15-25 min on CPU
bash demo/build.sh --preview  # 480p15, a few minutes, for checking layout
```

The first run creates `demo/.venv` (Python 3.11) from `demo/requirements.txt`. Torch is the CPU
build, so the install uses the PyTorch CPU index. System packages it needs (Ubuntu 22.04):

```bash
apt-get install -y ffmpeg fonts-inter fonts-jetbrains-mono libpango1.0-dev libcairo2-dev pkg-config espeak-ng
```

## Outputs (`demo/out/`, gitignored)

| File | What |
| --- | --- |
| `prompt2own_demo.mp4` | Voiced cut: 1920x1080, 30 fps, H.264 + AAC, voice normalized to -16 LUFS |
| `prompt2own_demo_silent.mp4` | The same picture with no audio, for presenting live over it |
| `prompt2own_demo.srt` | Subtitles matching the narration |
| `stills/*.png` | 6 representative frames; `stills/all/` has one per narration beat |

`demo/script.md` is the presenter script. Every line has its measured start time, which is the
same in both cuts, so you can read along with the silent version.

## How it fits together

- `data.py` loads every number and event from the result files into one dict `D`, and fails
  loudly if a file or field is missing. Sources: `results/figs/*.csv`, `results/figs/false_accepts.md`,
  `results/summary.csv`, `tasks/*.txt` and `docs/EVAL.md` (paper reference numbers) from this
  checkout. The per-run event logs, ledgers and grades come from the `results` git branch through
  `git show` (override the ref with `P2O_RESULTS_REF`). `python demo/data.py` prints the dict and
  the provenance of each source.
- The run scene shows real output of the project's own `scripts/trace.py`. `data.py` copies each
  run's files into `demo/cache/` and runs the tool there. The cache holds no PoC or patch bytes, so
  trace.py's `deliverables:` line would wrongly read "(none)"; that one line is dropped.
- `narration.py` holds the narration as templates filled from `D`, so no number is typed by
  hand. Edit the words there; `script.md` is regenerated on every build.
- `tts.py` picks the voice: OpenAI TTS if `OPENAI_API_KEY` is set, else ElevenLabs if
  `ELEVENLABS_API_KEY` is set, else local Kokoro (`af_heart`, speed 1.1). Audio is cached in
  `demo/cache/voice/`. A pronunciation map changes only the audio (for example "PoC" is spoken
  "P O C"); subtitles keep the written text.
- `scenes/*.py` holds one Manim scene per section, timed to the narration with manim-voiceover.
  `style.py` sets the palette, fonts, footer and the beat timing log.
- `assemble.py` concatenates the scenes, normalizes loudness, writes both cuts, merges the
  subtitles and writes `script.md` with measured times. It also checks that no beat's animations
  end more than 0.5 s after its sentence.

## Safety

The video shows file names, short hashes, crash types and function names only. It never shows
PoC bytes, input contents or patch diffs, and `data.py` never loads them.

## Before submitting

- The author line on the close card is `AUTHOR` in `scenes/s5_next.py` (currently the git user).
  Add the other team members' names there.
