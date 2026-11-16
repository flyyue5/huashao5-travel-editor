#!/usr/bin/env python3
"""Closing must decorate the existing final shot without adding duration or media."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1];S=ROOT/'skills/huashao5-travel-editor/scripts'
sys.path.insert(0,str(S))
import travel_edit as edit
import ending


def cli(*args,ok=True):
    r=subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True)
    assert (r.returncode==0)==ok,(args,r.stdout,r.stderr)
    return r


with tempfile.TemporaryDirectory(prefix='closing-test-') as d:
    p=Path(d);source=p/'source';source.mkdir();export=p/'different output';export.mkdir();ff=edit.tool('ffmpeg')
    edit.run([ff,'-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=30:d=6','-f','lavfi','-i','sine=frequency=440:duration=6:sample_rate=48000','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',source/'clip.mp4'])
    dialogue={'kind':'dialogue','start':.2,'end':1.5,'text':'已确认测试文案','text_verified':True}
    base={'schema_version':1,'width':320,'height':180,'fps':30,'caption_theme':'huashao_v2',
          'branding':{'mode':'text','text':'旅行频道'},
          'clips':[{'source':'clip.mp4','in':0,'out':2},{'source':'clip.mp4','in':2,'out':6}],
          'events':[dialogue,{'kind':'ending','start':5,'end':5.9,'text':'旧收尾'}],
          'speakers':{},'music':[],'sfx':[],'stickers':[]}
    edit.write(source/'base.json',base)
    plan={'seconds':3,'title':'下次见','finish':{'video_fade_out':1,'audio_fade_out':1.2}}
    edit.write(source/'plan.json',plan)
    result=ending.build(source/'plan.json',export/'closed.json',source/'base.json')
    closed=edit.read(export/'closed.json')
    assert result['added_seconds']==0 and result['total_seconds']==6
    assert closed['branding']==base['branding'] and len(closed['clips'])==2
    assert closed['events'][0]==dialogue and closed['events'][-1]['start']==3
    assert all(x['text']!='旧收尾' for x in closed['events'])
    assert [(c['in'],c['out']) for c in closed['clips']]==[(0,2),(2,6)]
    assert all(Path(c['source']).is_absolute() for c in closed['clips'])
    for key in ('music','sfx','stickers'):assert closed[key]==base[key]
    ending.build(source/'plan.json',export/'again.json',export/'closed.json')
    assert edit.read(export/'again.json')==closed
    cli(S/'travel_edit.py','render',export/'closed.json',export/'closed.mp4')
    assert abs(edit.duration(edit.probe(export/'closed.mp4'))-6)<.15
    r=subprocess.run([ff,'-v','error','-ss',str(6-1/30),'-i',str(export/'closed.mp4'),'-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'],capture_output=True,check=True)
    assert len(r.stdout)==320*180 and sum(r.stdout)/len(r.stdout)<3
    for kind in ('extra_media','too_long','fade','old_recap'):
        bad=copy.deepcopy(plan);episode=source/'base.json'
        if kind=='extra_media':bad['clips']=[{'source':'clip.mp4','in':0,'out':2}]
        if kind=='too_long':bad['seconds']=15
        if kind=='fade':bad['finish']['audio_fade_out']=4
        if kind=='old_recap':
            old=copy.deepcopy(base);old['ending']={'start':2,'duration':4}
            edit.write(source/'recap.json',old);episode=source/'recap.json'
        edit.write(source/'bad.json',bad)
        cli(S/'ending.py',source/'bad.json',export/f'{kind}.json','--episode',episode,ok=False)
        assert not (export/f'{kind}.json').exists()
    cli(S/'ending.py',source/'plan.json',export/'closed.json','--episode',source/'base.json',ok=False)
    assert edit.read(source/'base.json')==base
    print(json.dumps({'status':'passed','cases':['zero added footage/duration','unchanged dialogue and audio cues','inherited branding','replace previous closing title','idempotent reapplication','path rebasing','final frame black including logo','reject recap and extra media','preserve original EDL'],'actual_listening':False},indent=2))
