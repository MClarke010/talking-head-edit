---
name: talking-head-edit
description: Turn a raw talking-head recording (phone video, selfie video, to-camera TikTok, Reel or Short) into a post-ready vertical video in the user's own style. Cuts the ums, dead air and false starts, then adds word-by-word highlighted captions, a typewriter title card, an optional on-screen list that builds line by line, pop sound effects on key moments, and light background-noise cleanup. Use this whenever the user drops a raw .mov or .mp4 of themselves talking and says anything like "edit this", "cut this", "add captions", "make this post-ready", "clean up my video", "do my usual edit", or "set up my video style", even if they don't mention captions or this skill by name.
---

# Talking Head Edit

Takes a raw recording of someone talking to camera and returns a finished vertical video: tightly cut, captioned in their style, with an optional title, on-screen list, and sound effects. Built by Marshay Bradley from the workflow she uses on her own videos. The cutting stage is the open-source **cut-video** skill by Louise de Sadeleer (MIT), bundled in `third_party/cut-video/`.

Most people using this are creators, not developers. Talk to them in plain language, keep technical detail out of the way, and show them the result rather than describing the pipeline.

## 0. Check the tools (first run only)

The skill needs `ffmpeg`, `ffprobe`, `whisper` (openai-whisper) and, for the most accurate cuts, Montreal Forced Aligner (`mfa`). Check what's on `PATH` and in `~/miniforge3/envs/mfa/bin/`.

If something is missing, tell the user in one or two sentences what you need to install and roughly how long it takes (about 10 minutes, one time), and **ask before downloading anything**. The cleanest setup on a Mac:

1. Install Miniforge into `~/miniforge3` (from the conda-forge GitHub release, or `brew install miniforge` if Homebrew works).
2. `conda create -n mfa -c conda-forge montreal-forced-aligner ffmpeg -y`
3. `~/miniforge3/envs/mfa/bin/pip install openai-whisper`
4. `conda run -n mfa mfa model download acoustic english_mfa` and the same for `dictionary english_mfa`.

Put `~/miniforge3/envs/mfa/bin` on `PATH` for the session and set `KMP_DUPLICATE_LIB_OK=TRUE` before calling whisper (PyTorch and MFA ship clashing OpenMP libraries, and whisper crashes without it). On Windows or Linux, drop any `-hwaccel videotoolbox` flags from the cutting instructions.

## 1. Make it theirs (first run, or when they ask)

Read `references/style.json`. If it still has the default values (`highlight_color` is `#3EE6FF`), offer a quick style setup before the first edit.

**Best path: reference photos or videos.** Ask for 3 to 5 examples of the look they want: their own past posts, or screenshots and clips of captions they love. Study them before asking anything else:

- For videos, pull a few frames and look at them: `ffmpeg -i ref.mp4 -vf fps=1/3 ref_%02d.png`
- Note the caption font feel (heavy sans, rounded, serif, handwritten), caption color and highlight color (estimate hex values), caption size and how high it sits on screen, words per caption, all caps or not, title style, and whether sound effects or on-screen lists fit the vibe.
- Pick fonts that are actually installed on their computer and closest to the references (check with `fc-list` on Linux, or `/System/Library/Fonts` and `~/Library/Fonts` on a Mac). Say which font you chose and why if it's a stand-in.

Then describe the proposed look in plain words with the values ("bold white captions, the spoken word in coral #FF6F61, sitting at chest height, 2 to 3 words at a time"), let them adjust, and only then write it to `references/style.json`. Match the *feel* of the references. If they're all one creator's signature look, use them as inspiration rather than a copy, and mention that gently.

**No references?** Ask just these, in one short message: highlight color, favorite fonts (if any), sound effects on or off (and whether they have their own sound file), and a title they want on every video in a series. Or use the defaults and go.

Every future video uses whatever is saved in `references/style.json`. Never use a sound file they haven't given you, and don't rip audio from YouTube or TikTok: it breaks those platforms' terms even for "no copyright" uploads. Free libraries like Pixabay or Mixkit are fine, after the user confirms the download.

## 2. Cut the raw recording

Read `third_party/cut-video/CUTTING.md` and follow it (proxy, whisper, MFA alignment, ground-truth windows, trim+concat render). Work in `/tmp/talking-head-edit/<name>/`. Adjust it for to-camera talking videos:

- **Scripted, clean deliveries compress less.** Expect roughly 20 to 25% cut, not 40 to 60%. Forcing more means cutting real content. Tighten gaps instead (0.18 to 0.25s gaps down to about 0.08s, longer pauses down to 0.1 to 0.2s). Rambly, unscripted takes can go more aggressive.
- **Don't cut a filler word sandwiched between two other words** ("I *literally* edited"). It clips the neighbors and reads as a jump. Cut fillers only at phrase edges (an opening "okay", a sentence-opening "so").
- **Keep short beats before punch words** ("and the total was… nothing"): 0.25 to 0.45s.
- **Offer tangents and sign-off lines as cut candidates** and let the user pick, rather than deciding for them.
- Phone mics often noise-gate, so pauses can be true digital silence. MFA gaps are reliable there.

Render the cut **without captions** (`cut.mp4`) and show it. Save each revision under a **new filename** (`_v2`, `_v3`). Overwriting a file the user has open can corrupt playback.

## 3. Transcribe the cut and fix the words

```bash
ffmpeg -i cut.mp4 -vn -ac 1 -ar 16000 cut.wav
whisper cut.wav --model small.en --word_timestamps True --output_format json --output_dir . --language en
```

Read the transcript and build a `replacements` list for anything misheard. `build.py` already uppercases captions (if `all_caps` is on) and formats money ("432 dollars" → $432). You only need to fix:

- Spelled-out amounts: "ten thousand dollars" → "$10,000"; rates: "50 dollars an hour" → "$50/hr"
- Names and brands: whisper hears "Claude" as "clawed", and mangles most company and people names
- Slang whisper flattens, and letters ("an a" → "an A")

If a name or number is still unclear after re-listening to a short window, ask the user. A wrong dollar amount on screen is worse than a question.

## 4. Pick the extras

All optional. Suggest what fits the video instead of adding everything.

- **Title:** short, 2 lines max, about 14 characters per line (use `\N` for the line break). Types in letter by letter and fades after `title_hold` seconds.
- **On-screen list (`card`):** for videos that walk through numbers or steps. Each line appears when they say it. A line starting with `=` gets an underline above it, so a list of amounts reads like math being worked out live.
- **Pops:** on punchline moments only (the payoff number, the reveal), not every number. Too many pops and none of them land.

**Get exact timing** for every list line and pop: re-transcribe a 3-second window around each moment from `cut.wav` with `small.en` and use that word's start time. Full-pass times can be 0.2 to 1s off, and a late pop feels wrong.

## 5. Render

Write `config.json` next to `cut.mp4`, using `references/example-config.json` as the template. Preview stills first:

```bash
python <skill-dir>/scripts/build.py config.json --preview 0.6,2.5,<a list time>,<a caption time>
```

Look at `preview.png` and check: captions sit around chest height and don't cover the mouth, the title doesn't cover the eyes, and nothing that stays on screen sits in TikTok's or Instagram's UI zones (top ~11% for the nav, right edge for buttons, bottom ~20% for the caption). Move positions in `style` if the framing is different (someone sitting farther back, say). Then render:

```bash
python <skill-dir>/scripts/build.py config.json
```

Voice cleanup (85 Hz low-cut plus gentle denoise) is on by default. Set `"denoise": false` if the user hears artifacts.

## 6. Deliver

Save to `~/Downloads/edited/<Name>_final.mp4` (new filename per revision) and open it. Summarize in a short list: the title, each list line and pop with its timestamp, how much was cut, and any words you weren't sure about. Offer quick tweaks, since a re-render takes seconds.

## Credits

- Cutting engine: [cut-video](https://github.com/louisedesadeleer/cut-video) by Louise de Sadeleer, MIT License. Included unchanged in `third_party/cut-video/` with its license.
- Captions, title, list, sound and style system: Marshay Bradley, MIT License.
- `assets/pop.wav` is an original sound generated for this project. Free to use.
