#!/usr/bin/env python3
"""Fetch the fixed official previews, or import the original opening from a local MP3/MV.

Audio caches belong to the user's project. Never write downloaded audio into the skill.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.parse
import urllib.request
from travel_edit import ROOT, duration, probe, read, run, stream, tool, write


def catalogue():
    return read(ROOT/'assets/music-catalog.json')['tracks']


def official_url(url):
    u=urllib.parse.urlparse(url)
    return u.scheme=='https' and u.hostname and (u.hostname.endswith('.itunes.apple.com') or u.hostname=='itunes.apple.com')


def request(url):
    if not official_url(url):
        raise ValueError('Only official HTTPS Apple preview/catalogue hosts are accepted.')
    response=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'TravelPreviewEditor/0.1'}),timeout=45)
    if not official_url(response.url):
        response.close()
        raise ValueError('Unexpected preview redirect host.')
    return response


def download(url,path):
    with request(url) as response, path.open('wb') as out:
        total=0
        while True:
            block=response.read(65536)
            if not block: break
            total+=len(block)
            if total>12*1024*1024: raise ValueError('Preview exceeds 12 MiB limit.')
            out.write(block)


def refresh(track):
    for country in ('us','hk','cn'):
        try:
            with request(f'https://itunes.apple.com/lookup?id={track["track_id"]}&country={country}') as response:
                records=json.loads(response.read(1024*1024)).get('results',[])
            for r in records:
                if r.get('trackId')==track['track_id'] and official_url(r.get('previewUrl','')):
                    return r['previewUrl']
        except (ValueError,OSError):
            pass
    raise ValueError('Official preview unavailable; leave cue empty or ask for a local source. Do not substitute a different recording.')


def check_preview(path):
    meta=probe(path); seconds=duration(meta)
    if not stream(meta,'audio') or not 1<=seconds<=31:
        raise ValueError('Expected a short official audio preview, not a full song.')
    return seconds


def fetch(project,ids,offline=False):
    project=Path(project).resolve()
    if not (project/'workflow.json').is_file(): raise ValueError('Run init-project first.')
    all_tracks=catalogue(); byid={str(t['track_id']):t for t in all_tracks}
    wanted=list(byid) if ids==['all'] else ids
    if not wanted or any(i not in byid for i in wanted): raise ValueError('Choose all or IDs from the fixed 14-song catalogue.')
    folder=project/'private/music/previews';folder.mkdir(parents=True,exist_ok=True)
    index_path=folder/'index.json'
    previous=read(index_path) if index_path.exists() else {'tracks':[]}
    records={str(t['track_id']):t for t in previous['tracks']}; failures=[]
    for tid in wanted:
        track=byid[tid]; dest=folder/f'{tid}.m4a'; url=track['preview_url']
        try:
            if dest.exists():
                seconds=check_preview(dest)
                url=records.get(tid,{}).get('preview_url',url)
            else:
                if offline: raise ValueError('Preview is not cached and --offline forbids download.')
                handle=tempfile.NamedTemporaryFile(suffix='.m4a',dir=folder,delete=False);tmp=Path(handle.name);handle.close()
                try:
                    try: download(url,tmp);seconds=check_preview(tmp)
                    except (ValueError,OSError):
                        url=refresh(track);download(url,tmp);seconds=check_preview(tmp)
                    os.replace(tmp,dest)
                finally:
                    if tmp.exists():tmp.unlink()
            records[tid]={**track,'preview_url':url,'duration':seconds,'source':dest.relative_to(project).as_posix(),
                'rights':'official_preview','full_song':False,'redistribution_license_verified':False}
            print(json.dumps({'track_id':tid,'status':'ready','seconds':seconds},ensure_ascii=False),flush=True)
        except (ValueError,OSError) as e:
            records.pop(tid,None);failures.append({'track_id':tid,'error':str(e)})
    write(index_path,{'tracks':list(records.values()),'failures':failures})
    if failures: raise ValueError(json.dumps(failures,ensure_ascii=False))


def import_opening(source,project,start=0,seconds=50):
    project=Path(project).resolve();source=Path(source).expanduser().resolve()
    if not (project/'workflow.json').is_file():raise ValueError('Run init-project first.')
    meta=probe(source)
    if not stream(meta,'audio') or start<0 or seconds<=0 or start+seconds>duration(meta)+.02:
        raise ValueError('Opening source must contain the requested audio range; never loop or stretch it silently.')
    dest=project/'private/music/opening-original.m4a';dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise ValueError('Opening already exists; use a new project or explicitly replace the local file.')
    run([tool('ffmpeg'),'-v','error','-nostdin','-n','-ss',start,'-i',source,'-t',seconds,'-vn','-ar',48000,'-ac',2,'-c:a','aac','-b:a','256k','-map_metadata','-1',dest])
    write(project/'private/music/opening.json',{'source':dest.relative_to(project).as_posix(),'source_filename':source.name,
        'source_in':start,'duration':duration(probe(dest)),'route':'original_recording_no_voice_conversion',
        'rights':'user_provided_reference','public_audio_included':False})
    print(json.dumps({'opening':dest.relative_to(project).as_posix(),'seconds':seconds,'pitch_or_speed_changed':False},ensure_ascii=False))


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('list');a.set_defaults(fn=lambda a:print(json.dumps(catalogue(),ensure_ascii=False,indent=2)))
    a=s.add_parser('fetch');a.add_argument('project');a.add_argument('--ids',nargs='+',default=['all']);a.add_argument('--offline',action='store_true');a.set_defaults(fn=lambda a:fetch(a.project,a.ids,a.offline))
    a=s.add_parser('import-opening');a.add_argument('source');a.add_argument('project');a.add_argument('--start',type=float,default=0);a.add_argument('--seconds',type=float,default=50);a.set_defaults(fn=lambda a:import_opening(a.source,a.project,a.start,a.seconds))
    a=p.parse_args()
    try:a.fn(a)
    except (ValueError,OSError) as e:print(f'ERROR: {e}',file=sys.stderr);return 2
    return 0


if __name__=='__main__':sys.exit(main())
