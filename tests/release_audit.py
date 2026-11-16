#!/usr/bin/env python3
"""Audit the public source tree; never include private cache or media in release."""
import json
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[1]
skip={'.git','.local','projects','__pycache__','.venv'}
files=[p for p in root.rglob('*') if p.is_file() and not any(x in skip or x.startswith('.venv-') for x in p.relative_to(root).parts)]
errors=[]
private_patterns={
    'personal home directory': re.compile(r'/(?:Users|home)/[^/\s\"\']+/'),
    'Windows user directory': re.compile(r'[A-Za-z]:\\Users\\[^\\\s]+', re.I),
    'Library identifier': re.compile(r'(?:libfile[_-]|file-inline-)[A-Za-z0-9_-]{8,}'),
    'access credential': re.compile(r'(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16})'),
    'private key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}
tracked=subprocess.run(['git','-C',str(root),'ls-files','-z'],capture_output=True,text=True)
if tracked.returncode==0:
    for name in tracked.stdout.split('\0'):
        if not name:continue
        parts=Path(name).parts
        if any(part in {'.local','projects','private','raw','review','exports','models','.venv'} for part in parts):
            errors.append(f'Private path was force-added to Git: {name}')
for p in files:
    rel=p.relative_to(root).as_posix()
    if p.is_symlink():errors.append(f'Symbolic link in public tree: {rel}')
    if p.suffix.lower() in ('.pem','.key','.p12','.pfx'):errors.append(f'Credential file: {rel}')
    if p.stat().st_size>20*1024*1024:errors.append(f'Unexpected large file: {rel}')
    if p.suffix.lower() in ('.mp4','.mov','.mkv','.m4a','.mp3','.safetensors','.onnx','.pt','.zip','.bundle'):
        errors.append(f'External/private binary in public tree: {rel}')
    if p.suffix.lower()=='.wav' and not rel.startswith('skills/huashao5-travel-editor/assets/sfx/'):
        errors.append(f'Audio outside the original SFX directory: {rel}')
    if p.name.startswith('.env'):errors.append(f'Environment file: {rel}')
    if p.suffix in ('.md','.py','.json','.yaml','.yml','.txt'):
        text=p.read_text(encoding='utf-8')
        for label,pattern in private_patterns.items():
            if pattern.search(text):errors.append(f'Potential {label} in {rel}')
    if p.suffix.lower() in ('.png','.jpg','.jpeg','.webp') and rel!='skills/huashao5-travel-editor/assets/travel-stickers.png':
        errors.append(f'Image not in the public asset allowlist: {rel}')
skill=root/'skills/huashao5-travel-editor';doc=(skill/'SKILL.md').read_text()
assert doc.startswith('---\nname: huashao5-travel-editor\n')
assert '\ndescription:' in doc and len(doc.splitlines())<500
for target in re.findall(r'\]\(([^)]+)\)',doc):
    if not target.startswith('http') and not (skill/target).is_file():errors.append(f'Missing skill reference: {target}')
cat=json.loads((skill/'assets/music-catalog.json').read_text())
assert len(cat['tracks'])==14 and len({x['track_id'] for x in cat['tracks']})==14
assert all(x['source_type']=='official_public_preview' for x in cat['tracks'])
assert not (skill/'README.md').exists()
if errors:raise SystemExit('\n'.join(errors))
print(json.dumps({'status':'passed','public_files':len(files),'private_media_included':False,'tracks':14},indent=2))
