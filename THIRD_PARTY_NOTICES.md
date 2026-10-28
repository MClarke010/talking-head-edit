# Third-party notices

## cut-video

The cutting stage of this skill is **cut-video** by Louise de Sadeleer
(https://github.com/louisedesadeleer/cut-video), used under the MIT License.

It is included unchanged in `talking-head-edit/third_party/cut-video/`:

- `CUTTING.md` is the original `SKILL.md` from cut-video, renamed so it loads as
  instructions inside this skill instead of as a separate skill.
- `make_review.py` is the original optional timeline editor.
- `LICENSE` is the original MIT license, which applies to those files.

Copyright (c) 2026 Louise de Sadeleer. All credit for the cutting approach
(Whisper + Montreal Forced Aligner, ground-truth windows, trim+concat render)
goes to her.

## Tools the skill installs or calls (not bundled)

- ffmpeg (LGPL/GPL), https://ffmpeg.org
- OpenAI Whisper (MIT), https://github.com/openai/whisper
- Montreal Forced Aligner (MIT), https://montreal-forced-aligner.readthedocs.io

## Fonts

No fonts are bundled. The skill uses fonts already installed on your computer.

## Sound

`talking-head-edit/assets/pop.wav` is an original sound generated for this
project (a synthesized tone, no samples). It is covered by this project's MIT
license.
