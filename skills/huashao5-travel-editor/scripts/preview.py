#!/usr/bin/env python3
"""Write a local video viewing page beside a completed MP4."""
import argparse
import html
from pathlib import Path
import urllib.parse

p=argparse.ArgumentParser(description=__doc__);p.add_argument('video');a=p.parse_args()
video=Path(a.video).resolve()
if not video.is_file():p.error('Video not found.')
dest=video.with_suffix('.html')
if dest.exists():p.error('Preview exists; choose a new version.')
name=html.escape(video.stem);src=html.escape(urllib.parse.quote(video.name))
dest.write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title><style>body{{margin:0;background:#101a25;color:#f8f5ed;font:16px system-ui}}main{{max-width:1100px;margin:5vh auto;padding:24px}}h1{{font-weight:500;font-size:24px}}video{{width:100%;max-height:75vh;background:#000;border-radius:12px}}a{{color:#b9d9e9}}p{{line-height:1.7}}</style>
<main><h1>{name}</h1><video controls playsinline preload="metadata" src="{src}"></video><p><a href="{src}" download>下载视频</a></p></main></html>''',encoding='utf-8')
print(dest)
