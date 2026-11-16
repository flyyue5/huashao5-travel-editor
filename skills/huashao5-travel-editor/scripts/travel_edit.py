#!/usr/bin/env python3
"""Portable travel edit utilities. Python 3.9+, FFmpeg with libass, ffprobe.

The agent supplies a reviewed edit decision list; all times are seconds.
Optional ASR and preview retrieval live in separate, explicit commands.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

MEDIA = {'.mp4', '.mov', '.m4v', '.mkv', '.avi', '.webm', '.mts', '.wav', '.m4a', '.mp3'}
ROOT = Path(__file__).resolve().parents[1]
GRADES = {
    'none': '',
    'natural_warm': 'eq=contrast=1.025:brightness=0.005:saturation=1.035,colorbalance=rh=0.015:bh=-0.012',
    'cool_travel': 'eq=contrast=1.025:saturation=0.98,colorbalance=bs=0.012',
    'night_neutral': 'eq=contrast=1.01:brightness=0.012:saturation=0.97',
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    os.replace(f.name, path)


def tool(name):
    value = os.environ.get(name.upper()) or shutil.which(name)
    if not value:
        raise ValueError(f'Missing {name}; install it or set {name.upper()} to its executable path.')
    return value


def run(args, cwd=None, timeout=1800):
    p = subprocess.run([str(a) for a in args], cwd=cwd, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if p.returncode:
        raise ValueError(f'{Path(str(args[0])).name} failed ({p.returncode}): {p.stderr[-3500:]}')
    return p


def probe(path):
    return json.loads(run([tool('ffprobe'), '-v', 'error', '-show_format', '-show_streams',
                           '-of', 'json', str(path)], timeout=120).stdout)


def duration(meta):
    candidates = [meta.get('format', {}).get('duration')]
    candidates += [s.get('duration') for s in meta.get('streams', [])]
    for n in candidates:
        try:
            n = float(n)
            if math.isfinite(n) and n > 0:
                return n
        except (ValueError, TypeError):
            pass
    raise ValueError('Cannot determine finite media duration.')


def stream(meta, kind):
    return next((s for s in meta.get('streams', []) if s.get('codec_type') == kind), None)


def number(n, label, minimum=0):
    if isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) or n < minimum:
        raise ValueError(f'{label} must be a finite number >= {minimum}.')
    return n


def source_path(base, value):
    if value.startswith('asset:'):
        p = (ROOT / 'assets' / value[6:]).resolve()
        if ROOT / 'assets' not in p.parents:
            raise ValueError('Bundled asset path escapes assets/.')
        if not p.is_file():
            raise ValueError(f'Missing bundled asset: {value}')
        return p
    p = Path(value)
    p = (base / p).resolve() if not p.is_absolute() else p.resolve()
    if not p.is_file():
        raise ValueError(f'Missing local source: {p}')
    return p


def doctor(_):
    result = {}
    for name in ('ffmpeg', 'ffprobe'):
        try:
            result[name] = run([tool(name), '-version']).stdout.splitlines()[0]
        except ValueError as e:
            result[name] = str(e)
    if shutil.which('ffmpeg') or os.environ.get('FFMPEG'):
        filters = run([tool('ffmpeg'), '-hide_banner', '-filters']).stdout
        for name in ('subtitles', 'loudnorm', 'sidechaincompress'):
            result[name] = bool(re.search(r'\b' + name + r'\b', filters))
    result['python'] = sys.version.split()[0]
    result['chinese_font_files_found'] = [str(p) for p in (
        Path('/System/Library/Fonts/PingFang.ttc'),
        Path('/System/Library/Fonts/STHeiti Medium.ttc'),
        Path('/System/Library/Fonts/Hiragino Sans GB.ttc')) if p.is_file()]
    result['font_check'] = 'Render and inspect Chinese glyphs; filter presence is not a font check.'
    if shutil.which('fc-list'):
        result['fontconfig_chinese'] = run(['fc-list', ':lang=zh', 'family']).stdout.splitlines()[:20]
    result['asr'] = 'Optional transcribe.py adapter, or import a reviewed transcript'
    result['ready'] = all(result.get(k) is True for k in ('subtitles','loudnorm','sidechaincompress')) and not result['ffprobe'].startswith('Missing')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result['ready']:
        raise ValueError('Install FFmpeg/ffprobe with libass before rendering.')


def init_project(args):
    out = Path(args.output).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Project directory must be empty; do not overwrite a season.')
    for folder in ('private/music', 'private/branding', 'raw', 'review', 'exports'):
        (out / folder).mkdir(parents=True, exist_ok=True)
    for file in ('cast.example.json', 'episode-brief.example.json', 'edit-decision.example.json', 'ending-plan.example.json'):
        shutil.copy2(ROOT / 'assets' / file, out / file.replace('.example', ''))
    shutil.copy2(ROOT / 'assets' / 'workflow.json', out / 'workflow.json')
    if getattr(args, 'opening_source', None):
        from music_assets import import_opening
        import_opening(args.opening_source, out, 0, 50)
    write(out / 'season-memory.json', {'version': 1, 'episodes': [], 'running_jokes': [],
                                     'open_storylines': [], 'edit_preferences': []})
    (out / '.gitignore').write_text('private/\nraw/\nreview/\nexports/\ncast.json\nseason-memory.json\n.env*\n', encoding='utf-8')
    print(out)


def ingest(args):
    source = Path(args.source).resolve()
    if not source.is_dir():
        raise ValueError('Source must be a media directory.')
    records, seen, errors = [], {}, []
    for p in sorted(source.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in MEDIA:
            continue
        digest = hashlib.sha256()
        with p.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                digest.update(block)
        sha = digest.hexdigest()
        rec = {'asset_id': 'm_' + sha[:16], 'relative_path': p.relative_to(source).as_posix(),
               'sha256': sha, 'bytes': p.stat().st_size}
        if sha in seen:
            rec['duplicate_of'] = seen[sha]
        else:
            try:
                meta = probe(p)
                rec.update(duration=duration(meta), streams=meta.get('streams', []),
                           tags=meta.get('format', {}).get('tags', {}))
                rec['review_status'] = 'unreviewed'
            except (ValueError, subprocess.TimeoutExpired) as e:
                rec['error'] = str(e)
                errors.append(rec['relative_path'])
            seen[sha] = rec['relative_path']
        records.append(rec)
    write(args.output, {'schema_version': 1, 'source_root': str(source), 'assets': records,
                        'errors': errors, 'note': 'Creation tags are not guaranteed capture times. No content analysis performed.'})
    print(json.dumps({'assets': len(records), 'duplicates': sum('duplicate_of' in r for r in records), 'errors': errors}))


def prepare(args):
    manifest = read(args.manifest)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report = []
    for asset in manifest['assets']:
        if 'duplicate_of' in asset or 'error' in asset:
            continue
        p = Path(manifest['source_root']) / asset['relative_path']
        aid = asset['asset_id']
        v, a = stream(asset, 'video'), stream(asset, 'audio')
        item = {'asset_id': aid, 'frames': []}
        if v:
            for i, fraction in enumerate((0.1, 0.35, 0.65, 0.9)):
                target = out / f'{aid}_{i}.jpg'
                t = max(0, asset['duration'] * fraction - 0.05)
                run([tool('ffmpeg'), '-v', 'error', '-nostdin', '-n', '-ss', t, '-i', p,
                     '-frames:v', 1, '-vf', 'scale=480:-2', '-q:v', 3, target])
                item['frames'].append({'time': t, 'path': target.name})
        if a:
            target = out / f'{aid}.wav'
            run([tool('ffmpeg'), '-v', 'error', '-nostdin', '-n', '-i', p, '-vn',
                 '-ac', 1, '-ar', 16000, '-c:a', 'pcm_s16le', target])
            item['audio'] = target.name
        report.append(item)
    write(out / 'derivatives.json', report)
    print(json.dumps({'prepared': len(report), 'output': str(out)}, ensure_ascii=False))


def validate(edl, base, media=True):
    if edl.get('schema_version') != 1:
        raise ValueError('schema_version must be 1.')
    if edl.get('caption_theme') != 'huashao_v2':
        raise ValueError('This skill requires caption_theme=huashao_v2.')
    for key in ('width', 'height', 'fps'):
        n = edl.get(key)
        if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
            raise ValueError(f'{key} must be a positive integer.')
    w, h, fps = edl['width'], edl['height'], edl['fps']
    if w % 2 or h % 2 or max(w, h) > 4096 or fps > 60:
        raise ValueError('Use even dimensions <= 4096 and fps <= 60.')
    if not edl.get('clips'):
        raise ValueError('clips cannot be empty.')
    cache, total, timeline = {}, 0., []
    for i, c in enumerate(edl['clips']):
        start = number(c.get('in', 0), f'clip {i} in')
        end = number(c.get('out'), f'clip {i} out')
        if end <= start or (end - start) < 1 / fps:
            raise ValueError(f'clip {i}: out must exceed in by at least a frame.')
        # Frame quantization makes source-to-timeline mapping deterministic.
        d = round((end - start) * fps) / fps
        number(c.get('gain_db', 0), 'gain_db', -60)
        if c.get('fit', 'contain') not in ('contain', 'cover'):
            raise ValueError('fit must be contain or cover.')
        if c.get('grade', 'none') not in GRADES:
            raise ValueError('Unknown grade preset.')
        for field in ('focal_x', 'focal_y'):
            if not 0 <= number(c.get(field, .5), field) <= 1:
                raise ValueError('Focal points must be normalized to 0..1.')
        if c.get('kind') == 'card':
            if start != 0 or not re.fullmatch(r'#[0-9a-fA-F]{6}', c.get('color', '#FFF4DE')):
                raise ValueError('Cards require in=0 and a #RRGGBB color.')
        else:
            p = source_path(base, c['source'])
            if media:
                meta = cache.setdefault(str(p), probe(p)) if str(p) not in cache else cache[str(p)]
                v = stream(meta, 'video')
                if not v:
                    raise ValueError(f'clip {i} needs a video stream.')
                if v.get('color_transfer') in ('smpte2084', 'arib-std-b67'):
                    raise ValueError(f'clip {i} is HDR. Make and inspect an SDR proxy first; do not silently recolor it.')
                if end > duration(meta) + 1 / fps:
                    raise ValueError(f'clip {i} ends past source duration.')
        timeline.append({'clip_index': i, 'source': c.get('source'), 'source_in': start,
                         'source_out_requested': end, 'timeline_in': total, 'timeline_out': total + d,
                         'duration': d})
        total += d
    speakers = edl.get('speakers', {})
    for sid, person in speakers.items():
        if not person.get('display_name') or not re.fullmatch(r'#[0-9a-fA-F]{6}', person.get('color', '')):
            raise ValueError(f'Invalid speaker {sid}: display_name and #RRGGBB color required.')
    for i, e in enumerate(edl.get('events', [])):
        start = number(e.get('start'), f'event {i} start')
        end = number(e.get('end'), f'event {i} end')
        if not start < end <= total + .001:
            raise ValueError(f'event {i} must be inside the output timeline.')
        if not isinstance(e.get('text'), str) or not e['text'].strip():
            raise ValueError(f'event {i} needs text.')
        if e.get('kind') not in ('dialogue', 'flower', 'location', 'title', 'ending', 'lyric'):
            raise ValueError(f'event {i}: unsupported kind.')
        for key in ('x', 'y'):
            if key in e and not .03 <= number(e[key], key) <= .97:
                raise ValueError('Caption positions must be within 0.03..0.97.')
        if e.get('kind') == 'flower' and len(e['text']) > 20:
            raise ValueError('Flower text must be short (20 characters max).')
        sid = e.get('speaker_id')
        if sid and (sid not in speakers or not e.get('speaker_verified') or speakers[sid].get('identity_source') != 'user_provided'):
            raise ValueError(f'event {i}: names require an explicit user-provided segment/name mapping.')
        if e['kind'] in ('dialogue','lyric') and e.get('text_verified') is not True:
            raise ValueError(f'event {i}: verify dialogue/lyrics against source before burning in.')
        if 'size' in e and not 12 <= number(e['size'],'caption size') <= 120:
            raise ValueError('Caption size must be 12..120.')
        for key in ('color', 'outline'):
            if key in e and not re.fullmatch(r'#[0-9A-Fa-f]{6}', e[key]):
                raise ValueError(f'Invalid event {key}.')
        if e['kind']=='lyric':
            chars=re.sub(r'[，。！？、；：\s]','',e['text'])
            if not chars or len(chars)>14 or end-start < len(chars)*.035+.1:
                raise ValueError('Split lyrics into readable 1..14 character phrases with enough time.')
            for beat in e.get('pulse_times',[]):
                number(beat,'lyric pulse time')
    for kind in ('music', 'sfx'):
        for i, a in enumerate(edl.get(kind, [])):
            p = source_path(base, a['source'])
            t = number(a.get('timeline_in', 0), 'audio timeline_in')
            d = number(a.get('duration'), 'audio duration', .01)
            s = number(a.get('source_in', 0), 'audio source_in')
            number(a.get('gain_db', -20 if kind == 'music' else -8), 'audio gain_db', -80)
            for k in ('fade_in','fade_out'):
                if k in a and not 0 <= number(a[k], k) <= d:
                    raise ValueError('Audio fades must fit the cue.')
            if t + d > total + .001:
                raise ValueError(f'{kind} {i} extends past output.')
            if a.get('rights') not in ('user_owned', 'licensed', 'public_domain', 'user_provided_reference', 'official_preview'):
                raise ValueError(f'{kind} {i}: record audio provenance in rights.')
            if a.get('rights')=='official_preview' and d > 30.1:
                raise ValueError('A preview cue cannot exceed the available 30-second excerpt.')
            if media:
                m = probe(p)
                if not stream(m, 'audio') or s + d > duration(m) + .02:
                    raise ValueError(f'{kind} {i}: invalid audio range.')
    brand=edl.get('branding', {'mode':'none'})
    if brand.get('mode','none') not in ('none','text','image'):
        raise ValueError('branding.mode must be none, text or image.')
    if brand.get('mode')=='text' and (not isinstance(brand.get('text'),str) or not 1<=len(brand['text'])<=16 or '\n' in brand['text']):
        raise ValueError('Text logo needs 1..16 characters on one line.')
    if brand.get('mode')=='text' and brand.get('style','blue') not in ('blue','gold'):
        raise ValueError('Text logo style must be blue or gold.')
    if brand.get('mode')=='image':
        source_path(base,brand['source'])
        if not .04 <= number(brand.get('width',.14),'logo width') <= .3:
            raise ValueError('Logo width must be 0.04..0.30 of frame width.')
    for k in ('x','y'):
        if not 0<=number(brand.get(k,.03), 'logo '+k)<=.85:
            raise ValueError('Logo position must be 0..0.85.')
    if 'fonts_dir' in edl and not (base / edl['fonts_dir']).resolve().is_dir():
        raise ValueError('fonts_dir must be an existing font directory.')
    for st in edl.get('stickers',[]):
        if not isinstance(st.get('cell'),int) or isinstance(st['cell'],bool) or not 0<=st['cell']<=5:
            raise ValueError('Sticker cell must be 0..5.')
        a=number(st.get('start'),'sticker start'); b=number(st.get('end'),'sticker end')
        if not a<b<=total: raise ValueError('Sticker must fit the output timeline.')
        size=number(st.get('width',.12),'sticker width')
        x=number(st.get('x',.7),'sticker x'); y=number(st.get('y',.65),'sticker y')
        if not .03<=size<=.35 or x+size>1 or y+size*w/h>.98:
            raise ValueError('Sticker must fit inside frame.')
    for key in ('video_fade_out','audio_fade_out'):
        fade=number(edl.get('finish',{}).get(key,0),'finish '+key)
        if fade>min(5,total): raise ValueError('End fades must fit the timeline and be at most 5 seconds.')
    return total, timeline, cache


def stamp(t, srt=False):
    # Quantize first so 59.999 does not become an invalid seconds=60 field.
    units = int(round(t * (1000 if srt else 100)))
    rate = 1000 if srt else 100
    hours, units = divmod(units, 3600 * rate)
    minutes, units = divmod(units, 60 * rate)
    seconds, fraction = divmod(units, rate)
    return (f'{hours:02}:{minutes:02}:{seconds:02},{fraction:03}' if srt
            else f'{hours}:{minutes:02}:{seconds:02}.{fraction:02}')


def clean_text(s):
    return s.replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\r', '').replace('\n', '\\N')


def ass_color(value):
    return '&H00' + value[5:7] + value[3:5] + value[1:3]


def captions(edl, out):
    if edl.get('caption_theme') == 'huashao_v2':
        import importlib.util
        spec = importlib.util.spec_from_file_location('variety_captions', Path(__file__).with_name('variety_captions.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.write_captions(edl, out)
    out.mkdir(parents=True, exist_ok=True)
    w, h = edl['width'], edl['height']
    scale = min(w / 1080, h / 720)
    font = edl.get('font') or ('Heiti SC' if sys.platform == 'darwin' else 'Noto Sans CJK SC')
    if any(c in font for c in ',\r\n'):
        raise ValueError('Invalid font family.')
    # Conservative shared UI area; actual app preview remains required.
    margin_l, margin_r = round(w * .07), round(w * (.18 if h>w else .07))
    bottom = round(h * (.20 if h>w else .10))
    styles = []
    def style(name, size, primary, align, vertical, bold=-1, back='&H8C173A2C'):
        outline=0 if name in ('Title','Ending','Location') else max(1,round(2*scale))
        shadow=0 if name in ('Title','Ending','Location') else 1
        styles.append(f'Style: {name},{font},{round(size * scale)},{primary},&H000000FF,&H0023392E,{back},{bold},0,0,0,100,100,0,0,1,{outline},{shadow},{align},{margin_l},{margin_r},{vertical},1')
    style('Dialogue', 45, '&H00FFFFFF', 2, bottom)
    style('Flower', 68, '&H0092EFFF', 5, 0)
    style('Location', 32, '&H00FFFFFF', 7, round(h * .12))
    style('Title', 86, '&H002C3A17', 5, 0)
    style('Ending', 48, '&H002C3A17', 5, 0)
    style('Lyric', 40, '&H0099DFFF', 1, round(h*.09), bold=0)
    for sid, person in edl.get('speakers', {}).items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+', sid):
            raise ValueError('Speaker IDs use ASCII letters, numbers, _ or -.')
        style('Speaker_' + sid, 45, '&H00FFFFFF', 2, bottom)
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
'''
    lines, srts = [], []
    for e in sorted(edl.get('events', []), key=lambda e: (e['start'], e['end'])):
        kind = e['kind']
        name = kind.title()
        text = clean_text(e['text'])
        prefix = ''
        if kind == 'dialogue' and e.get('speaker_id'):
            sid = e['speaker_id']
            p = edl['speakers'][sid]
            name = 'Speaker_' + sid
            color = ass_color(p['color'])
            prefix = '{\\c' + color + '}' + clean_text(p['display_name']) + '  {\\c&HFFFFFF&}'
        animation = ''
        if kind == 'flower':
            animation = '{\\an5\\pos(' + str(round(w*e.get('x',.45))) + ',' + str(round(h*e.get('y',.60))) + ')\\fad(80,120)\\fscx92\\fscy92\\t(0,160,\\fscx100\\fscy100)}'
        elif kind in ('title', 'ending'):
            animation = '{\\fad(150,150)}'
        if kind == 'lyric':
            animation += '{\\fnSongti SC\\i1\\fax-0.10\\bord1\\shad1}'
        if kind != 'flower' and ('x' in e or 'y' in e):
            animation += '{\\an5\\pos(' + str(round(w*e.get('x',.5))) + ',' + str(round(h*e.get('y',.5))) + ')}'
        if e.get('color'):
            if not re.fullmatch(r'#[0-9a-fA-F]{6}', e['color']):
                raise ValueError('Event color must be #RRGGBB.')
            animation += '{\\c' + ass_color(e['color']) + '&}'
        if e.get('size'):
            size=number(e['size'],'caption size',12)
            if size>120: raise ValueError('Caption size must be <=120.')
            animation += '{\\fs' + str(round(size*scale)) + '}'
        layer = 1 if kind == 'flower' else 0
        if kind == 'dialogue' and edl.get('caption_theme') == 'variety_blue':
            cy=round(h*e['y']) if 'y' in e else round(h-bottom-22*scale)
            bw=round(w*.72); bh=round(50*scale); bx=round((w-bw)/2)
            vector='{\\an7\\pos('+str(bx)+','+str(cy-bh//2)+')\\p1\\bord0\\shad0\\c&HBE8656&\\alpha&H35&}m 0 0 l '+str(bw)+' 0 l '+str(bw)+' '+str(bh)+' l 0 '+str(bh)+'{\\p0}'
            lines.append(f"Dialogue: 0,{stamp(e['start'])},{stamp(e['end'])},Dialogue,,0,0,0,,{vector}")
            animation += '{\\fnSongti SC\\fs'+str(round(35*scale))+'\\bord0\\shad0}'
            layer=1
        lines.append(f"Dialogue: {layer},{stamp(e['start'])},{stamp(e['end'])},{name},,0,0,0,,{animation}{prefix}{text}")
        if kind == 'dialogue':
            label = edl['speakers'][e['speaker_id']]['display_name'] + '：' if e.get('speaker_id') else ''
            srts.append(f"{len(srts)+1}\n{stamp(e['start'],True)} --> {stamp(e['end'],True)}\n{label}{e['text']}\n")
    (out / 'captions.ass').write_text(header + '\n'.join(styles) + '\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n' + '\n'.join(lines) + '\n', encoding='utf-8')
    (out / 'captions.srt').write_text('\n'.join(srts), encoding='utf-8')


def render(args):
    edl_path = Path(args.edl).resolve()
    edl = read(edl_path)
    total, timeline, cache = validate(edl, edl_path.parent, media=True)
    dest = Path(args.output).resolve()
    outputs = [dest, dest.with_suffix('.ass'), dest.with_suffix('.srt'), dest.with_suffix('.timeline.json')]
    if any(p.exists() for p in outputs):
        raise ValueError('An output or sidecar already exists; choose a new versioned filename.')
    dest.parent.mkdir(parents=True, exist_ok=True)
    ff = tool('ffmpeg')
    w, h, fps = edl['width'], edl['height'], edl['fps']
    with tempfile.TemporaryDirectory(prefix='travel-render-', dir=dest.parent) as folder:
        tmp = Path(folder)
        captions(edl, tmp)
        for i, (c, t) in enumerate(zip(edl['clips'], timeline)):
            d, start = t['duration'], t['source_in']
            cmd = [ff, '-v', 'error', '-nostdin', '-n']
            if c.get('kind') == 'card':
                cmd += ['-f', 'lavfi', '-i', f"color=c={c.get('color','#FFF4DE')}:s={w}x{h}:r={fps}:d={d}"]
                has_audio = False
            else:
                p = source_path(edl_path.parent, c['source'])
                has_audio = bool(stream(cache[str(p)], 'audio')) and not c.get('mute', False)
                cmd += ['-ss', start, '-i', p]
            if not has_audio:
                cmd += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
            if c.get('fit', 'contain') == 'cover':
                fit = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}:(iw-ow)*{c.get('focal_x',.5)}:(ih-oh)*{c.get('focal_y',.5)}"
            else:
                bg=edl.get('background','#173A2C')
                if not re.fullmatch(r'#[0-9a-fA-F]{6}',bg): raise ValueError('Invalid background color.')
                fit = f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={bg}'
            vf = fit + f',setsar=1,fps={fps},format=yuv420p,setpts=PTS-STARTPTS'
            if c.get('kind')!='card' and GRADES[c.get('grade','none')]:
                vf += ',' + GRADES[c.get('grade','none')]
            cmd += ['-map', '0:v:0', '-map', '0:a:0' if has_audio else '1:a:0', '-t', d,
                    '-vf', vf, '-af', f"aresample=48000,aformat=channel_layouts=stereo,volume={c.get('gain_db',0)}dB,apad,atrim=duration={d},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={max(0,d-.012)}:d=0.012",
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', 18, '-c:a', 'pcm_s16le',
                    '-map_metadata', '-1', tmp / f'part_{i:04}.mkv']
            run(cmd)
        (tmp / 'concat.txt').write_text(''.join(f"file 'part_{i:04}.mkv'\n" for i in range(len(timeline))), encoding='utf-8')
        run([ff, '-v', 'error', '-nostdin', '-n', '-f', 'concat', '-safe', 1, '-i', 'concat.txt', '-c', 'copy', 'base.mkv'], cwd=tmp)
        cmd = [ff, '-v', 'error', '-nostdin', '-n', '-i', 'base.mkv']
        filters, music_labels, sfx_labels = [], [], []
        inputs = 1
        for kind, labels in (('music', music_labels), ('sfx', sfx_labels)):
            for a in edl.get(kind, []):
                cmd += ['-i', source_path(edl_path.parent, a['source'])]
                d, si, ti = a['duration'], a.get('source_in', 0), a.get('timeline_in', 0)
                fade_in = a.get('fade_in', min(.5, d / 3))
                fade_out = a.get('fade_out', min(.8, d / 3))
                label = f'{kind}{inputs}'
                gain = a.get('gain_db', -20 if kind == 'music' else -8)
                filters.append(f'[{inputs}:a:0]atrim=start={si}:duration={d},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume={gain}dB,afade=t=in:d={fade_in},afade=t=out:st={d-fade_out}:d={fade_out},adelay={round(ti*1000)}|{round(ti*1000)},apad,atrim=duration={total}[{label}]')
                labels.append(f'[{label}]')
                inputs += 1
        if music_labels:
            filters += ['[0:a]asplit=2[dialogue][side]', ''.join(music_labels) + f'amix=inputs={len(music_labels)}:normalize=0[music]',
                        '[music][side]sidechaincompress=threshold=0.035:ratio=6:attack=15:release=350[ducked]']
            audio_labels = ['[dialogue]', '[ducked]'] + sfx_labels
        else:
            audio_labels = ['[0:a]'] + sfx_labels
        audio_finish=''
        fade=edl.get('finish',{}).get('audio_fade_out',0)
        if fade: audio_finish=f',afade=t=out:st={total-fade}:d={fade}'
        filters.append(''.join(audio_labels) + f'amix=inputs={len(audio_labels)}:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo,loudnorm=I=-16:TP=-1.5:LRA=9,aformat=sample_rates=48000:channel_layouts=stereo'+audio_finish+'[aout]')
        font_option=''
        if edl.get('fonts_dir'):
            # Copy into a fixed relative path so filter quoting never exposes user paths.
            shutil.copytree((edl_path.parent / edl['fonts_dir']).resolve(), tmp/'fonts')
            font_option=':fontsdir=fonts'
        filters.append('[0:v]subtitles=captions.ass'+font_option+'[captioned]')
        previous='captioned'
        brand=edl.get('branding',{})
        if brand.get('mode')=='image':
            cmd += ['-loop','1','-framerate',str(fps),'-i',source_path(edl_path.parent,brand['source'])]
            lw=max(2,round(w*brand.get('width',.14)/2)*2)
            filters += [f'[{inputs}:v]format=rgba,scale={lw}:-2[bug]',
                        f'[{previous}][bug]overlay={round(w*brand.get("x",.03))}:{round(h*brand.get("y",.03))}:format=auto[branded]']
            previous='branded'; inputs+=1
        for i,st in enumerate(edl.get('stickers',[])):
            cmd += ['-loop','1','-framerate',str(fps),'-i',ROOT/'assets/travel-stickers.png']
            cell=st['cell']; a=st['start']; b=st['end']; size=max(2,round(w*st.get('width',.12)/2)*2)
            fade=min(.15,(b-a)/3); x=round(w*st.get('x',.7)); y=round(h*st.get('y',.65))
            filters.append(f'[{inputs}:v]format=rgba,crop=512:512:{cell%3*512}:{cell//3*512},lut=a=if(lt(val\\,210)\\,0\\,255),scale={size}:{size},fade=t=in:st={a}:d={fade}:alpha=1,fade=t=out:st={b-fade}:d={fade}:alpha=1[st{i}]')
            yy=f'{y}+{h*.016}*exp(-7*(t-{a}))*cos(18*(t-{a}))'
            filters.append(f"[{previous}][st{i}]overlay=x={x}:y='{yy}':enable='between(t,{a},{b})':format=auto[decor{i}]")
            previous=f'decor{i}'; inputs+=1
        video_finish=''
        fade=edl.get('finish',{}).get('video_fade_out',0)
        if fade: video_finish=f',fade=t=out:st={max(0,total-fade-1/fps)}:d={fade}'
        filters.append(f'[{previous}]format=yuv420p'+video_finish+'[vout]')
        (tmp / 'filters.txt').write_text(';\n'.join(filters), encoding='utf-8')
        cmd += ['-filter_complex_script', 'filters.txt', '-filter_complex_threads','2', '-map', '[vout]', '-map', '[aout]', '-t', total,
                '-c:v', 'libx264', '-preset', 'medium', '-crf', 19, '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '192k', '-ar', 48000, '-movflags', '+faststart', '-map_metadata', '-1', 'final.mp4']
        run(cmd, cwd=tmp)
        # Verify the encoded mix, then apply one constant gain correction.
        # One-pass dynamic loudnorm can miss integrated loudness on short cuts.
        meter=run([ff,'-hide_banner','-i','final.mp4','-vn','-af','loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json','-f','null','-'],cwd=tmp).stderr
        found=re.search(r'\{\s*"input_i".*?\}',meter,re.S)
        if found:
            levels=json.loads(found.group(0)); loud=float(levels['input_i']); peak=float(levels['input_tp'])
            if math.isfinite(loud) and math.isfinite(peak):
                gain=min(-16-loud,-2.0-peak)
                if abs(gain)>.15:
                    run([ff,'-v','error','-nostdin','-n','-i','final.mp4','-c:v','copy','-af',f'volume={gain}dB','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart','leveled.mp4'],cwd=tmp)
                    os.replace(tmp/'leveled.mp4',tmp/'final.mp4')
        actual = probe(tmp / 'final.mp4')
        if abs(duration(actual) - total) > max(.15, 2/fps):
            raise ValueError('Rendered duration differs from EDL; output withheld.')
        run([ff, '-v', 'error', '-i', tmp / 'final.mp4', '-f', 'null', '-'])
        # All work succeeded. Publish only the completed file and its sidecars.
        shutil.copy2(tmp / 'captions.ass', dest.with_suffix('.ass'))
        shutil.copy2(tmp / 'captions.srt', dest.with_suffix('.srt'))
        write(dest.with_suffix('.timeline.json'), {'duration': total, 'clips': timeline, 'edl': edl})
        os.replace(tmp / 'final.mp4', dest)
    print(json.dumps({'output': str(dest), 'duration': total, 'status': 'rendered; visual and listening review still required'}, ensure_ascii=False))


def qa(args):
    p = Path(args.source).resolve()
    meta = probe(p)
    decoded = run([tool('ffmpeg'), '-v', 'error', '-i', p, '-f', 'null', '-'])
    audio = run([tool('ffmpeg'), '-hide_banner', '-i', p, '-vn', '-af',
                 'loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json', '-f', 'null', '-']).stderr if stream(meta, 'audio') else ''
    match = re.search(r'\{\s*"input_i".*?\}', audio, re.S)
    result = {'duration': duration(meta), 'video': stream(meta, 'video'), 'audio': stream(meta, 'audio'),
              'decode_errors': decoded.stderr.strip(), 'loudness': json.loads(match.group(0)) if match else None,
              'human_checks_pending': ['Chinese glyphs', 'speaker names', 'subtitle timing', 'UI-safe framing', 'music/dialogue balance', 'story authenticity']}
    write(args.output, result)
    print(json.dumps({'qa': str(args.output), 'decode_ok': not decoded.stderr.strip()}, ensure_ascii=False))


def scan(args):
    """Find review candidates. Quiet audio is not a speech-recognition result."""
    p=Path(args.source).resolve(); meta=probe(p); dur=duration(meta)
    vf='blackdetect=d=0.35:pix_th=0.08,freezedetect=n=-50dB:d=1.5'
    cmd=[tool('ffmpeg'),'-hide_banner','-nostdin','-i',p]
    if stream(meta,'video'): cmd += ['-vf',vf]
    if stream(meta,'audio'): cmd += ['-af','silencedetect=noise=-38dB:d=1.5']
    result=run(cmd+['-f','null','-']).stderr
    silence=[]; pending=None
    for line in result.splitlines():
        m=re.search(r'silence_start: ([0-9.]+)',line)
        if m: pending=float(m.group(1))
        m=re.search(r'silence_end: ([0-9.]+)',line)
        if m and pending is not None:
            silence.append({'start':pending,'end':min(dur,float(m.group(1)))}); pending=None
    if pending is not None: silence.append({'start':pending,'end':dur})
    black=[{'start':float(a),'end':float(b)} for a,b in re.findall(r'black_start:([0-9.]+) black_end:([0-9.]+)',result)]
    freezes=[]; pending=None
    for line in result.splitlines():
        m=re.search(r'freeze_start: ([0-9.]+)',line)
        if m: pending=float(m.group(1))
        m=re.search(r'freeze_end: ([0-9.]+)',line)
        if m and pending is not None:
            freezes.append({'start':pending,'end':min(dur,float(m.group(1)))});pending=None
    if pending is not None: freezes.append({'start':pending,'end':dur})
    write(args.output,{'source':str(p),'duration':dur,'quiet_candidates':silence,
        'black_candidates':black,'static_candidates':freezes,
        'decision':'review_required','deleted':False,
        'limitations':'Quiet is not no-speech; wind/noise can mask silence. Stillness, darkness and lack of dialogue are not automatically bad. Review actions, reactions and scenery before EDL cuts.'})
    print(json.dumps({'quiet':len(silence),'black':len(black),'static':len(freezes),'output':str(args.output)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('doctor'); p.set_defaults(fn=doctor)
    p = subs.add_parser('init-project'); p.add_argument('output'); p.add_argument('--opening-source'); p.set_defaults(fn=init_project)
    p = subs.add_parser('ingest'); p.add_argument('source'); p.add_argument('output'); p.set_defaults(fn=ingest)
    p = subs.add_parser('prepare'); p.add_argument('manifest'); p.add_argument('output'); p.set_defaults(fn=prepare)
    p = subs.add_parser('validate'); p.add_argument('edl'); p.add_argument('--structure-only', action='store_true')
    p.set_defaults(fn=lambda a: print(json.dumps({'duration': validate(read(a.edl), Path(a.edl).resolve().parent, not a.structure_only)[0], 'valid': True})))
    p = subs.add_parser('captions'); p.add_argument('edl'); p.add_argument('output')
    def caption_command(a):
        edl = read(a.edl); validate(edl, Path(a.edl).resolve().parent, False); captions(edl, Path(a.output))
    p.set_defaults(fn=caption_command)
    p = subs.add_parser('render'); p.add_argument('edl'); p.add_argument('output'); p.set_defaults(fn=render)
    p = subs.add_parser('qa'); p.add_argument('source'); p.add_argument('output'); p.set_defaults(fn=qa)
    p = subs.add_parser('scan'); p.add_argument('source'); p.add_argument('output'); p.set_defaults(fn=scan)
    args = parser.parse_args()
    try:
        args.fn(args)
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as e:
        print(f'ERROR: {e}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
