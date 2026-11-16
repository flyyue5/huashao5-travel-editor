#!/usr/bin/env python3
"""Add a short closing caption and fade to the existing last shot; add no footage."""
import argparse
import copy
import json
from pathlib import Path
import sys
from travel_edit import number, read, source_path, validate, write


def relocate(edl,base):
    result=copy.deepcopy(edl)
    for kind in ('clips','music','sfx'):
        for item in result.get(kind,[]):
            if item.get('source') and not item['source'].startswith('asset:'):
                item['source']=str(source_path(base,item['source']))
    if result.get('branding',{}).get('mode')=='image':
        result['branding']['source']=str(source_path(base,result['branding']['source']))
    if result.get('fonts_dir'):
        result['fonts_dir']=str((base/result['fonts_dir']).resolve())
    return result


def build(plan_path,output,episode_path):
    plan_path=Path(plan_path).resolve();output=Path(output).resolve()
    if output.exists():raise ValueError('Output exists; choose a new versioned EDL.')
    plan=read(plan_path)
    for key in ('clips','music','sfx','stickers','events','branding'):
        if plan.get(key):raise ValueError('Closing only accepts text/timing/fades. Do not add footage, audio, stickers or branding here.')
    episode_path=Path(episode_path).resolve()
    result=relocate(read(episode_path),episode_path.parent)
    old=result.get('ending',{})
    if old and old.get('mode')!='in_place':
        raise ValueError('This is an old appended recap ending. Use the original episode EDL without that recap.')
    total,timeline,_=validate(result,output.parent,media=True)
    requested=number(plan.get('seconds',3),'closing seconds',.75)
    if requested>5:raise ValueError('Closing should be at most 5 seconds within the last shot.')
    duration=min(requested,timeline[-1]['duration'])
    if duration<.75:raise ValueError('The last shot is too short for readable closing text. Review its cut; do not append repeated footage.')
    start=total-duration
    title=plan.get('title','下次见')
    if not isinstance(title,str) or not 1<=len(title)<=20 or len(title.splitlines())>2:
        raise ValueError('Closing title needs 1..20 characters and at most two lines.')
    result['events']=[e for e in result.get('events',[]) if not (e.get('_role')=='closing_title' or (e.get('kind')=='ending' and e.get('end',0)>start))]
    result['events'].append({'kind':'ending','start':start,'end':total,'text':title,
        'x':plan.get('title_x',.5),'y':plan.get('title_y',.72),'size':plan.get('title_size',58),'_role':'closing_title'})
    finish=plan.get('finish',{'video_fade_out':min(1,duration/2),'audio_fade_out':min(1.2,duration/2)})
    for key in ('video_fade_out','audio_fade_out'):
        if number(finish.get(key,0),key)>duration:raise ValueError('Closing fades must stay inside the closing window.')
    result['finish']=finish
    result['ending']={'mode':'in_place','start':start,'duration':duration,'title':title,'added_seconds':0,'branding':'inherited'}
    actual=validate(result,output.parent,media=True)[0]
    if abs(actual-total)>.001:raise ValueError('Closing unexpectedly changed the episode duration.')
    write(output,result)
    return {'output':str(output),'closing_start':start,'closing_seconds':duration,'added_seconds':0,'total_seconds':total}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('plan');p.add_argument('output');p.add_argument('--episode',required=True)
    a=p.parse_args()
    try:print(json.dumps(build(a.plan,a.output,a.episode),ensure_ascii=False))
    except (ValueError,OSError,KeyError,TypeError) as e:print(f'ERROR: {e}',file=sys.stderr);return 2
    return 0


if __name__=='__main__':sys.exit(main())
