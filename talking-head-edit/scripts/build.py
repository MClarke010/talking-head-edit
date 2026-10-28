#!/usr/bin/env python3
"""Add captions, a title card, an optional on-screen list, and pop sound effects
to an already-cut talking-head video, in one ffmpeg pass.

Originally built by Marshay Bradley for her own videos, generalized for anyone.
MIT License (see LICENSE at the repo root).

Usage:
  build.py config.json                    # full render
  build.py config.json --preview 1,4.5    # still frames at those times -> preview.png

The look comes from references/style.json (edit it once to make it yours).
Anything under "style" in config.json overrides it for a single video.

Config (JSON, paths relative to the config file):
{
  "video": "cut.mp4",                      # the already-cut video (no captions yet)
  "words": "words.json",                   # whisper JSON of the CUT video (word_timestamps)
  "output": "~/Downloads/edited/My-video_final.mp4",
  "title": "3 things I wish\\\\NI knew sooner",   # optional; \\\\N = line break
  "replacements": [["clawed", "Claude"]],  # fix misheard words
  "card": {                                # optional on-screen list that builds line by line
    "lines": [["Step 1: Plan", 12.4], ["Step 2: Film", 18.9], ["= Done", 25.1]],
    "end": 32.0
  },
  "pops": [12.4, 18.9, 25.1],              # optional sound-effect times (seconds)
  "denoise": true,
  "style": {"highlight_color": "#FF5C8A"}  # optional per-video style overrides
}
"""
import json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)


def find_tool(name):
    """Prefer whatever is on PATH; fall back to the conda env the setup guide creates."""
    found = shutil.which(name)
    if found:
        return found
    for env in ('~/miniforge3/envs/mfa/bin', '~/miniconda3/envs/mfa/bin', '~/anaconda3/envs/mfa/bin'):
        p = os.path.join(os.path.expanduser(env), name)
        if os.path.exists(p):
            return p
    sys.exit(f"Couldn't find {name}. Install ffmpeg first (see the setup guide).")


FFMPEG, FFPROBE = find_tool('ffmpeg'), find_tool('ffprobe')

# ------------------------------------------------------------------ style
# Neutral defaults. Fonts were picked because they ship with both macOS and Windows.
DEFAULT_STYLE = {
    "caption_font": "Arial Black",
    "caption_size": 54,
    "caption_color": "#FFFFFF",
    "highlight_color": "#3EE6FF",     # the word being spoken right now
    "caption_outline": 3.8,
    "caption_shadow": 2.5,
    "caption_position": 0.74,          # 0 = top of frame, 1 = bottom. 0.74 is about chest height
    "all_caps": True,
    "max_words_per_caption": 3,
    "title_font": "Georgia",
    "title_size": 96,
    "title_color": "#FFFFFF",
    "title_position": 0.11,            # from the top
    "title_hold": 3.6,                 # seconds before the title fades
    "typewriter": True,                # title types in letter by letter
    "card_font": "Arial",
    "card_size": 37,
    "card_color": "#FFFFFF",
    "card_top": 0.125,                 # keep clear of TikTok's top nav (top ~11%)
    "sound_effects": True,
    "sound_file": "assets/pop.wav",    # relative to the skill folder, or an absolute path
    "sound_volume": 0.35,              # ~7 dB under the voice
}
REF_H = 1280                            # sizes above are tuned on a 720x1280 frame, scaled by height


def load_style(cfg):
    style = dict(DEFAULT_STYLE)
    path = os.path.join(SKILL_DIR, 'references', 'style.json')
    if os.path.exists(path):
        style.update({k: v for k, v in json.load(open(path)).items() if not k.startswith('_')})
    style.update(cfg.get('style', {}))
    return style


def ass_color(hex_color, alpha='00'):
    """'#RRGGBB' -> ASS '&HAABBGGRR' (ASS stores colours backwards)."""
    h = hex_color.lstrip('#')
    r, g, b = h[0:2], h[2:4], h[4:6]
    return '&H' + f'{alpha}{b}{g}{r}'.upper()


def norm(t):
    return re.sub(r"[^a-z0-9']", '', t.lower())


def load_words(path):
    d = json.load(open(path))
    ws = [[w['start'], w['end'], w['word'].strip()] for s in d['segments'] for w in s.get('words', [])]
    return [w for w in ws if w[2]]


def apply_replacements(words, reps):
    for src, dst in reps:
        pat = [norm(x) for x in src.split()]
        out_words = dst.split()
        i = 0
        while i <= len(words) - len(pat):
            if [norm(w[2]) for w in words[i:i + len(pat)]] == pat:
                span = words[i:i + len(pat)]
                trail = re.search(r'[.,?!]+$', span[-1][2])
                trail = trail.group(0) if trail and not re.search(r'[.,?!]$', dst) else ''
                if len(out_words) == len(span):          # 1:1, keep each word's timing
                    for k, w in enumerate(span):
                        w[2] = out_words[k] + (trail if k == len(span) - 1 else '')
                    i += len(span)
                else:                                     # merge into one caption word
                    words[i:i + len(pat)] = [[span[0][0], span[-1][1], dst + trail]]
                    i += 1
            else:
                i += 1
    return words


def auto_money(words):
    """'432 dollars' -> '$432', '$2' ',000' -> '$2,000', '1301 dollars' -> '$1,301'."""
    out, i = [], 0
    while i < len(words):
        s, e, t = words[i]
        n = norm(t)
        if n.isdigit():
            num, j = n, i
            while j + 1 < len(words) and words[j + 1][2].startswith(',') and norm(words[j + 1][2]).isdigit():
                j += 1; num += norm(words[j][2])
            has_dollar = t.startswith('$')
            if j + 1 < len(words) and norm(words[j + 1][2]) in ('dollars', 'dollar'):
                j += 1; has_dollar = True
            if has_dollar:
                trail = re.search(r'[.,?!]+$', words[j][2])
                out.append([s, words[j][1], f"${int(num):,}" + (trail.group(0) if trail else '')])
                i = j + 1
                continue
        out.append([s, e, t]); i += 1
    glued = []                                            # glue "y" + "'all" style splits
    for w in out:
        if glued and w[2].startswith("'") and w[2][1:2].isalpha():
            glued[-1] = [glued[-1][0], w[1], glued[-1][2] + w[2]]
        else:
            glued.append(w)
    return glued


def chunk(words, max_words):
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1][0] - w[1] if i + 1 < len(words) else 9
        if (len(cur) >= max_words or re.search(r'[.,?!]$', w[2]) or gap > 0.35
                or len(' '.join(x[2] for x in cur)) > 18):
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    return chunks


def ts(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def build_ass(cfg, base, W, H, st):
    k = H / REF_H
    sx = lambda v: round(v * k, 1)
    hi, lo = '{\\c' + ass_color(st['highlight_color']) + '&}', '{\\c' + ass_color(st['caption_color']) + '&}'
    clean = (lambda t: re.sub(r'(?<!\d)[.,?!]+|[.,?!]+$', '', t.upper() if st['all_caps'] else t))
    ev = []

    # captions: the current word lights up
    words = load_words(os.path.join(base, cfg['words']))
    words = auto_money(apply_replacements(words, cfg.get('replacements', [])))
    chunks = chunk(words, st['max_words_per_caption'])
    cap_y = H * st['caption_position']
    for ci, ch in enumerate(chunks):
        nxt = chunks[ci + 1][0][0] if ci + 1 < len(chunks) else ch[-1][1] + 0.5
        chunk_end = min(nxt, ch[-1][1] + 0.6)
        texts = [clean(w[2]) for w in ch]
        br = None
        if len(' '.join(texts)) > 14 and len(texts) > 1:
            br = 1 if len(texts) == 2 else (1 if len(texts[0]) >= len(texts[-1]) else 2)
        for wi, w in enumerate(ch):
            start = w[0]
            end = ch[wi + 1][0] if wi + 1 < len(ch) else chunk_end
            parts = []
            for j, t in enumerate(texts):
                parts.append((hi if j == wi else lo) + t)
                if j < len(texts) - 1:
                    parts.append(r'\N' if br == j + 1 else ' ')
            ev.append(f"Dialogue: 1,{ts(start)},{ts(end)},Cap,,0,0,0,,{{\\an2\\pos({W / 2:.0f},{cap_y:.0f})}}" + ''.join(parts))

    # title card
    title = cfg.get('title')
    if title:
        ty = H * st['title_position']
        if st['typewriter']:
            seq = []
            for part in [p for p in re.split(r'(\\N)', title) if p]:
                seq += [part] if part == '\\N' else list(part)
            vis = [i for i, c in enumerate(seq) if c not in (' ', '\\N')]
            for n, idx in enumerate(vis):
                start = 0.15 + n * 0.06
                last = n + 1 == len(vis)
                end = st['title_hold'] if last else start + 0.06
                shown, hidden = ''.join(seq[:idx + 1]), ''.join(seq[idx + 1:])
                fade = '\\fad(0,300)' if last else ''
                ev.append(f"Dialogue: 2,{ts(start)},{ts(end)},Title,,0,0,0,,{{\\an8\\pos({W / 2:.0f},{ty:.0f}){fade}}}"
                          + shown + ('{\\alpha&HFF&}' + hidden if hidden else ''))
        else:
            ev.append(f"Dialogue: 2,{ts(0.1)},{ts(st['title_hold'])},Title,,0,0,0,,{{\\an8\\pos({W / 2:.0f},{ty:.0f})\\fad(200,300)}}{title}")

    # on-screen list that builds one line at a time; a line starting with "=" gets an underline above it
    card = cfg.get('card') or cfg.get('report_card')
    if card and card.get('lines'):
        lines, end = card['lines'], card['end']
        size = st['card_size'] * k
        width = max(len(t) for t, _ in lines) * 0.5 * size
        x = (W - width) / 2
        top, gap = H * st['card_top'], sx(42)
        for n, (txt, t) in enumerate(lines):
            y = top + n * gap
            ev.append(f"Dialogue: 2,{ts(t - 0.03)},{ts(end)},Card,,0,0,0,,{{\\an7\\pos({x:.0f},{y:.0f})\\fad(120,250)}}{txt}")
            if txt.lstrip().startswith('=') and n > 0:
                uy = y - sx(3)
                ev.append(f"Dialogue: 2,{ts(t - 0.05)},{ts(end)},Card,,0,0,0,,{{\\an7\\pos({x:.0f},{uy:.0f})\\bord0\\shad1\\fad(120,250)\\p1}}"
                          f"m 0 0 l {width:.0f} 0 {width:.0f} {sx(3)} 0 {sx(3)}{{\\p0}}")

    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{st['caption_font']},{sx(st['caption_size'])},{ass_color(st['caption_color'])},{ass_color(st['caption_color'])},&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,{sx(st['caption_outline'])},{sx(st['caption_shadow'])},2,20,20,0,1
Style: Title,{st['title_font']},{sx(st['title_size'])},{ass_color(st['title_color'])},{ass_color(st['title_color'])},&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,{sx(1.5)},8,20,20,0,1
Style: Card,{st['card_font']},{sx(st['card_size'])},{ass_color(st['card_color'])},{ass_color(st['card_color'])},&H50000000,&H78000000,0,0,0,0,100,100,0,0,1,{sx(1.2)},{sx(1.5)},8,20,20,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return head + '\n'.join(ev) + '\n', words


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cfg_path = os.path.abspath(sys.argv[1])
    base = os.path.dirname(cfg_path)
    cfg = json.load(open(cfg_path))
    st = load_style(cfg)
    video = os.path.join(base, cfg['video'])
    W, H = map(int, subprocess.check_output(
        [FFPROBE, '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height',
         '-of', 'csv=p=0:s=x', video]).decode().strip().split('x'))
    ass, words = build_ass(cfg, base, W, H, st)
    ass_path = os.path.join(base, 'overlays.ass')
    open(ass_path, 'w').write(ass)
    open(os.path.join(base, 'captions_final.txt'), 'w').write(' '.join(w[2] for w in words))
    vf = 'ass=' + ass_path.replace('\\', '/').replace(':', '\\:')

    if '--preview' in sys.argv:
        times = [float(t) for t in sys.argv[sys.argv.index('--preview') + 1].split(',')]
        pngs = []
        for t in times:
            p = os.path.join(base, f'_prev_{t}.png')
            subprocess.run([FFMPEG, '-y', '-loglevel', 'error', '-copyts', '-ss', str(t), '-i', video,
                            '-vf', vf, '-frames:v', '1', p], check=True)
            pngs.append(p)
        ins = sum([['-i', p] for p in pngs], [])
        stack = (''.join(f'[{i}]' for i in range(len(pngs))) + f'hstack={len(pngs)},scale={min(1800, 360 * len(pngs))}:-1'
                 if len(pngs) > 1 else 'scale=360:-1')
        out = os.path.join(base, 'preview.png')
        subprocess.run([FFMPEG, '-y', '-loglevel', 'error', *ins, '-filter_complex', stack, out], check=True)
        print(out)
        return

    pops = cfg.get('pops', []) if st['sound_effects'] else []
    sound = os.path.expanduser(st['sound_file'])
    if not os.path.isabs(sound):
        sound = os.path.join(SKILL_DIR, sound)
    if pops and not os.path.exists(sound):
        print(f"Sound file not found ({sound}), rendering without sound effects.")
        pops = []
    voice = 'highpass=f=85,afftdn=nr=14:nf=-48:tn=1,lowpass=f=15000' if cfg.get('denoise', True) else 'anull'
    fc = [f"[0:v]{vf}[v]", f"[0:a]{voice}[voice]"]
    if pops:
        n = len(pops)
        fc.append(f"[1:a]afade=t=out:st=0.35:d=0.2,volume={st['sound_volume']},asplit={n}" + ''.join(f'[p{i}]' for i in range(n)))
        for i, t in enumerate(pops):
            ms = max(0, int(round((t - 0.03) * 1000)))
            fc.append(f"[p{i}]adelay={ms}|{ms}[d{i}]")
        fc.append('[voice]' + ''.join(f'[d{i}]' for i in range(n)) + f"amix=inputs={n + 1}:normalize=0:duration=first[a]")
    else:
        fc.append('[voice]anull[a]')
    out = os.path.expanduser(cfg.get('output', '~/Downloads/edited/video_final.mp4'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cmd = [FFMPEG, '-y', '-loglevel', 'error', '-i', video]
    if pops:
        cmd += ['-i', sound]
    cmd += ['-filter_complex', ';'.join(fc), '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'fast',
            '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', out]
    subprocess.run(cmd, check=True)
    print(out)


if __name__ == '__main__':
    main()
