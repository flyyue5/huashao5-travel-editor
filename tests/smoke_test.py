#!/usr/bin/env python3
"""Offline end-to-end tests with synthetic media and no personal assets."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/huashao5-travel-editor'
SCRIPT=SKILL/'scripts/travel_edit.py'
sys.path.insert(0,str(SCRIPT.parent))
import travel_edit as edit
import music_assets as music


def cli(script,*args,ok=True):
    r=subprocess.run([sys.executable,str(script),*map(str,args)],capture_output=True,text=True)
    assert (r.returncode==0)==ok,(args,r.stdout,r.stderr)
    return r


def main():
    cases=[]
    with tempfile.TemporaryDirectory(prefix='travel-skill-test-') as folder:
        p=Path(folder);raw=p/'原片 with space';raw.mkdir();ff=edit.tool('ffmpeg')
        voiced=raw/"片段 ' A.mp4";silent=raw/'竖屏静音.mp4';tone=p/'music.wav'
        edit.run([ff,'-v','error','-f','lavfi','-i','testsrc2=s=480x270:r=30:d=4','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=4','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',voiced])
        edit.run([ff,'-v','error','-f','lavfi','-i','color=c=0x345D72:s=270x480:r=30:d=2','-c:v','libx264',silent])
        edit.run([ff,'-v','error','-f','lavfi','-i','sine=frequency=220:sample_rate=48000:duration=6',tone])
        old_hash=hashlib.sha256(voiced.read_bytes()).hexdigest()
        (raw/'重复.mp4').write_bytes(voiced.read_bytes());(raw/'损坏.mp4').write_bytes(b'not a movie')
        project=p/'project';cli(SCRIPT,'init-project',project);cli(SCRIPT,'init-project',project,ok=False)
        cli(SCRIPT,'ingest',raw,p/'inventory.json');inv=edit.read(p/'inventory.json')
        assert len(inv['assets'])==4 and inv['errors']==['损坏.mp4']
        assert sum('duplicate_of' in a for a in inv['assets'])==1
        cli(SCRIPT,'prepare',p/'inventory.json',p/'review')
        assert len(list((p/'review').glob('*.jpg')))==8
        cli(SCRIPT,'scan',silent,p/'scan.json');assert edit.read(p/'scan.json')['deleted'] is False
        cases+=['duplicate/corrupt inventory','quoted and Chinese paths','derivatives','scan does not delete','init refuses overwrite']
        edl={'schema_version':1,'width':480,'height':270,'fps':30,'caption_theme':'huashao_v2','branding':{'mode':'none'},
            'speakers':{},'clips':[{'source':str(voiced),'in':.5,'out':3.5},{'source':str(silent),'in':0,'out':2,'fit':'cover'},
            {'kind':'card','in':0,'out':1,'color':'#C7B6A5'}],
            'events':[{'kind':'lyric','start':.1,'end':1.9,'text':'这是原创测试文字','text_verified':True,'animation':'bounce','pulse_times':[.5,1,1.5]},
            {'kind':'dialogue','start':2,'end':3.6,'text':'一起出发吧','text_verified':True},
            {'kind':'flower','start':4,'end':5.5,'text':'好，出发！','y':.4}],
            'music':[{'source':str(tone),'timeline_in':0,'source_in':0,'duration':2,'gain_db':-23,'fade_in':.3,'fade_out':.5,'rights':'user_owned'}],
            'sfx':[{'source':'asset:sfx/soft-pop.wav','timeline_in':4,'duration':.12,'gain_db':-8,'rights':'licensed'}],
            'stickers':[{'cell':2,'start':3.8,'end':5.2,'x':.72,'y':.35,'width':.12}]}
        logo=p/'logo.png';edit.run([ff,'-v','error','-f','lavfi','-i','color=c=0x00AACC:s=60x20:d=1','-frames:v','1',logo])
        for mode in ('none','text','image'):
            edl['branding']={'mode':mode}
            if mode=='text':edl['branding'].update(text='旅行频道',style='gold')
            if mode=='image':edl['branding'].update(source=str(logo),width=.15)
            ep=p/f'{mode}.json';out=p/f'{mode}.mp4';edit.write(ep,edl)
            cli(SCRIPT,'validate',ep);cli(SCRIPT,'render',ep,out);cli(SCRIPT,'qa',out,p/f'{mode}.qa.json')
            qa=edit.read(p/f'{mode}.qa.json')
            assert abs(qa['duration']-6)<.15 and not qa['decode_errors']
            assert qa['audio']['channels']==2
            assert -17.5<float(qa['loudness']['input_i'])<-14.5
            assert float(qa['loudness']['input_tp'])<=-1.5
            ass=out.with_suffix('.ass').read_text();srt=out.with_suffix('.srt').read_text()
            assert '人物1' not in ass
            assert '一起出发吧' in srt and '好，出发！' not in srt
            assert ('旅行频道' in ass)==(mode=='text')
            cli(SCRIPT,'render',ep,out,ok=False)
        cases+=['all three branding modes','mixed orientation and silent source','animated lyric and stickers','SFX and intermittent BGM','no implicit identity','full decode and loudness','output protection']
        cli(SKILL/'scripts/preview.py',p/'none.mp4');assert (p/'none.html').is_file()
        # A real explicit user mapping renders a name; an unverified identity is rejected.
        edl['branding']={'mode':'none'}
        edl['speakers']={'p1':{'display_name':'测试昵称','color':'#86B8D4','identity_source':'user_provided'}}
        edl['events'][1].update(speaker_id='p1',speaker_verified=True)
        edit.write(p/'named.json',edl);cli(SCRIPT,'captions',p/'named.json',p/'named')
        assert '测试昵称' in (p/'named/captions.srt').read_text()
        for mutation in ('identity','transcript','bounds','preview_length','asset_escape','sticker','theme'):
            bad=json.loads(json.dumps(edl))
            if mutation=='identity':bad['speakers']['p1']['identity_source']='voice_guess'
            if mutation=='transcript':bad['events'][1]['text_verified']=False
            if mutation=='bounds':bad['clips'][0]['out']=50
            if mutation=='preview_length':bad['music'][0].update(rights='official_preview',duration=45)
            if mutation=='asset_escape':bad['sfx'][0]['source']='asset:../SKILL.md'
            if mutation=='sticker':bad['stickers'][0]['cell']=7
            if mutation=='theme':bad['caption_theme']='unknown_theme'
            edit.write(p/'invalid.json',bad);cli(SCRIPT,'validate',p/'invalid.json',ok=False)
        assert hashlib.sha256(voiced.read_bytes()).hexdigest()==old_hash
        cases+=['explicit name only','unverified transcript rejected','invalid source/cue/sticker rejected','asset traversal rejected','source preserved']
        music.import_opening(tone,project,0,3)
        assert 2.9<edit.read(project/'private/music/opening.json')['duration']<3.1
        cli(SKILL/'scripts/music_assets.py','import-opening',tone,project,'--seconds','3',ok=False)
        # Offline cache validation without accessing the Internet.
        cache=project/'private/music/previews';cache.mkdir()
        tid=str(music.catalogue()[0]['track_id']);shutil.copy2(project/'private/music/opening-original.m4a',cache/f'{tid}.m4a')
        music.fetch(project,[tid],offline=True)
        assert len(edit.read(cache/'index.json')['tracks'])==1
        cli(SKILL/'scripts/music_assets.py','fetch',project,'--ids',str(music.catalogue()[1]['track_id']),'--offline',ok=False)
        cli(SKILL/'scripts/transcribe.py','--help')
        cases+=['original opening import','offline preview cache and missing-source failure','ASR CLI help']
        # Portrait template and no-audio project must render too.
        cards=edit.read(SKILL/'assets/edit-decision.example.json');cards.update(width=270,height=480)
        edit.write(p/'cards.json',cards);cli(SCRIPT,'render',p/'cards.json',p/'cards.mp4')
        assert abs(edit.duration(edit.probe(p/'cards.mp4'))-6)<.15
        cases+=['portrait all-silent template']
    print(json.dumps({'status':'passed','cases':cases,'actual_listening_performed':False,'model_inference_tested':False},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
