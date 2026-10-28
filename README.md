# Talking Head Edit: a Claude skill that edits your talking videos for you

Drop in a raw video of yourself talking. Get back a post-ready vertical video:

- **Tight cuts.** Ums, long pauses, false starts and retakes gone, while keeping your laughs and punchline pauses.
- **Captions in your style.** Word-by-word highlight, your fonts, your colors, at chest height.
- **A title card** that types itself in.
- **An on-screen list** that builds line by line as you talk (great for numbers, steps, or money breakdowns).
- **Pop sound effects** on the moments that matter.
- **Light background-noise cleanup.**

No timeline. No dragging clips with your finger. You set your style once, then every video comes out looking like you.

## What you need

- A Mac (Windows and Linux can work, but this was built and tested on Mac)
- A paid Claude plan with **Claude Code** (the Code tab in the Claude desktop app, or the `claude` command in Terminal)
- About 10 minutes for the one-time setup. Claude does the installing; you just say yes.

## Install

Follow the one-page guide: **[SETUP-GUIDE.pdf](SETUP-GUIDE.pdf)** (also in [SETUP-GUIDE.md](SETUP-GUIDE.md)).

Short version: click **Code → Download ZIP** on this page, unzip it, open Claude Code, and say:

> Install the talking-head-edit skill from the talking-head-edit-main folder in my Downloads into my personal skills (~/.claude/skills), then check and set up the tools it needs.

Or if you're comfortable in Terminal:

```bash
git clone https://github.com/MClarke010/talking-head-edit.git
cp -r talking-head-edit/talking-head-edit ~/.claude/skills/
```

Start a new Claude Code session afterward so it picks up the skill.

## Use it

1. Drag in 3 to 5 reference photos or videos of the look you love and say **"set up my video style using these references."** Claude suggests a look from them and saves it once you approve.
2. Drag in a raw video and say **"edit this video."**
3. Review the cut, ask for tweaks ("keep the part about my dog", "move the captions up a little"), and you're done.

Your look lives in `talking-head-edit/references/style.json` if you ever want to edit it by hand.

## Credits

- **Cutting engine:** [cut-video](https://github.com/louisedesadeleer/cut-video) by Louise de Sadeleer (MIT). It's included unchanged in `talking-head-edit/third_party/cut-video/`. All credit for the cutting approach goes to her.
- **Everything else** (captions, title, on-screen list, sound effects, style system): Marshay Bradley.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for details.

## License

MIT. Use it, change it, share it. Keep the license and credits with it.
