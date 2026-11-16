"""Original travel-variety caption templates with configurable branding.

All coordinates in input events are normalized. This renderer does not invent
transcripts or speakers. Dialogue requires text_verified=True.
"""
from pathlib import Path
import re
import sys

def stamp(t):
 n=round(t*100);h,n=divmod(n,360000);m,n=divmod(n,6000);s,n=divmod(n,100)
 return f'{h}:{m:02}:{s:02}.{n:02}'

def clean(s):return s.replace('\\','＼').replace('{','｛').replace('}','｝').replace('\n',r'\N')
def color(s):
 s=s.lstrip('#');return '&H'+s[4:6]+s[2:4]+s[0:2]+'&'

def write_captions(edl,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 w,h=edl['width'],edl['height'];sx=w/1920;sy=h/1080;scale=min(sx,sy)
 font=edl.get('font') or ('Songti SC' if sys.platform=='darwin' else 'Noto Serif CJK SC')
 if any(c in font for c in ',\r\n'):raise ValueError('Invalid font family')
 header=f'''[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Text,{font},{48*scale},&H00FFFFFF,&H000000FF,&H005C3D21,&H80000000,-1,0,0,0,100,100,1,0,1,{1.5*scale},{1*scale},5,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
 events=[];srts=[]
 def add(e,text,layer=2):events.append(f"Dialogue: {layer},{stamp(e['start'])},{stamp(e['end'])},Text,,0,0,0,,{text}")
 def txt(e,text,x,y,size=48,fill='#FFF9EB',align=5,extra='',outline='#476E9E',layer=3):
  add(e,'{'+fr'\an{align}\pos({x:.2f},{y:.2f})\fs{size*scale:.2f}\c{color(fill)}\3c{color(outline)}\bord{1.8*scale:.2f}\shad{1.1*scale:.2f}\fad(110,130)'+extra+'}'+clean(text),layer)
 def path(e,points,fill,border=None,layer=1,alpha='00'):
  coords='m '+' l '.join(f'{x:.2f} {y:.2f}' for x,y in points)
  add(e,'{'+fr'\an7\pos(0,0)\p1\bord{1.3*scale if border else 0:.2f}\shad0\c{color(fill)}\3c{color(border or fill)}\alpha&H{alpha}&\fad(110,130)'+'}'+coords+r'{\p0}',layer)
 def box(e,x,y,bw,bh,fill='#477CAA',edge='#E8D9A7',layer=1):
  path(e,[(x+6*scale,y),(x+bw-6*scale,y),(x+bw,y+6*scale),(x+bw,y+bh-6*scale),(x+bw-6*scale,y+bh),(x+6*scale,y+bh),(x,y+bh-6*scale),(x,y+6*scale),(x+6*scale,y)],fill,edge,layer,'12')
  # Small corner ticks and inset line retain the programme's fine decorative structure.
  path(e,[(x+9*scale,y+5*scale),(x+bw-9*scale,y+5*scale),(x+bw-9*scale,y+6.4*scale),(x+9*scale,y+6.4*scale)],'#DDE9E8',None,layer+1,'60')
 def star(e,x,y,r=11,fill='#F0D897'):
  r*=scale;path(e,[(x,y-r),(x+r*.23,y-r*.23),(x+r,y),(x+r*.23,y+r*.23),(x,y+r),(x-r*.23,y+r*.23),(x-r,y),(x-r*.23,y-r*.23),(x,y-r)],fill,None,3)
 def dialogue_bar(e,x,y,bw,bh):
  # Blue/lavender programme strip, with a fine cream frame rather than a pill.
  c0=(116,153,192);c1=(157,142,198);n=80
  path(e,[(x,y),(x+bw,y),(x+bw,y+bh),(x,y+bh)],'#8994C3',layer=1)
  for i in range(n):
   t=i/(n-1);c='#'+''.join(f'{round(a+(b-a)*t):02X}' for a,b in zip(c0,c1))
   x0=round(x+bw*i/n);x1=round(x+bw*(i+1)/n)
   path(e,[(x0,y),(x1,y),(x1,y+bh),(x0,y+bh)],c,layer=1)
  b=1.5*scale
  for xx,yy,ww,hh in [(x,y,bw,b),(x,y+bh-b,bw,b),(x,y,b,bh),(x+bw-b,y,b,bh)]:
   path(e,[(xx,yy),(xx+ww,yy),(xx+ww,yy+hh),(xx,yy+hh)],'#FFF6E9',layer=2,alpha='15')
  path(e,[(x+7*scale,y+4*scale),(x+bw-7*scale,y+4*scale),(x+bw-7*scale,y+5*scale),(x+7*scale,y+5*scale)],'#E3EDF6',layer=2,alpha='80')
  # Open diamond straddling the right border, as in the supplied reference.
  d=5*scale;cx=x+bw;cy=y+bh/2
  path(e,[(cx,cy-d),(cx+d,cy),(cx,cy+d),(cx-d,cy)],'#FFF6E9',layer=3)
  path(e,[(cx,cy-d*.55),(cx+d*.55,cy),(cx,cy+d*.55),(cx-d*.55,cy)],'#9D8EC6',layer=4)
 for e in edl.get('events',[]):
  kind=e['kind'];text=e['text'];x=e.get('x',.5)*w;y=e.get('y',.7)*h
  if not text.strip():continue
  if kind=='dialogue':
   if not e.get('text_verified'):raise ValueError('Do not burn unverified dialogue into the film.')
   y=e.get('y',.80 if h>w else .885)*h;bw=(.82 if h>w else .70)*w;bh=68*scale;left=(w-bw)/2
   dialogue_bar(e,left,y-bh/2,bw,bh)
   name='';nw=0
   speaker=edl.get('speakers',{}).get(e.get('speaker_id'),{})
   if e.get('speaker_verified') and speaker.get('identity_source')=='user_provided':
    name=speaker.get('display_name','');nw=max(140,len(name)*39+30)*scale if name else 0
   if name:
    ty=y-bh/2
    path(e,[(left,ty),(left+nw,ty),(left+nw,ty+bh*.36),(left+nw+13*scale,ty+bh*.5),(left+nw,ty+bh*.64),(left+nw,ty+bh),(left,ty+bh)],'#FFF3DC',layer=3)
    txt(e,name,left+nw/2,y,40,'#344E71',extra=r'\b0\bord0\shad0',layer=4)
   size=max(22,min(42,(bw-nw-76*scale)/(max(1,len(text))*scale)-2.2))
   txt(e,text,left+nw+(bw-nw)/2,y,size,'#FFFCF5',extra=fr'\b0\fsp{2.2*scale:.2f}\bord0\shad0',layer=4)
   srts.append({'start':e['start'],'end':e['end'],'text':(name+'：' if name else '')+text})
  elif kind=='lyric':
   # True vertical layout, not a rotated horizontal subtitle.
   chars=[c for c in text if c not in '，。！？、；： \n'];x=e.get('x',.10 if h>w else .92)*w;y=e.get('y',.20)*h
   size=e.get('size',42);step=49*scale
   if y+step*len(chars)>h*.9:y=h*.9-step*len(chars)
   for j,ch in enumerate(chars):
    if e.get('animation')=='bounce':
     start=e['start']+j*.035
     ce={**e,'start':start}
     yy=y+j*step
     add(ce,'{'+fr'\an8\move({x:.2f},{yy+10*scale:.2f},{x:.2f},{yy:.2f},0,180)\fs{size*scale:.2f}\b0\c{color("#FFF7DE")}\3c{color("#397E9C")}\bord{1.7*scale:.2f}\shad0\fad(80,120)\fscx86\fscy86\t(0,110,\fscx112\fscy112)\t(110,230,\fscx100\fscy100)'+'}'+clean(ch),3)
    else:txt(e,ch,x,y+j*step,size,'#FFF4D1',outline='#7C724F',extra=r'\b0\shad1',align=8)
   if e.get('animation')=='bounce':
    beats=e.get('pulse_times',[])
    for k,bt in enumerate(beats):
     if not e['start']+.2<=bt<e['end']-.18:continue
     j=min(len(chars)-1,int((bt-e['start'])/max(.01,e['end']-e['start'])*len(chars)))
     pe={**e,'start':bt,'end':min(bt+.31,e['end'])};yy=y+j*step
     add(pe,'{'+fr'\an8\move({x:.2f},{yy-5*scale:.2f},{x:.2f},{yy:.2f},80,280)\fs{size*scale:.2f}\b0\c{color("#FFE899")}\3c{color("#3782A4")}\bord{2.1*scale:.2f}\shad0\fad(40,80)\fscx115\fscy115\t(80,280,\fscx100\fscy100)'+'}'+clean(chars[j]),4)
    pe={**e,'start':max(e['start'],e['end']-.45),'end':e['end']}
    star(pe,x+25*scale,y+len(chars)*step-15*scale,9,'#FFE4A0')
   lx=x-34*scale;path(e,[(lx,y+8*scale),(lx+1.3*scale,y+8*scale),(lx+1.3*scale,y+len(chars)*step-9*scale),(lx,y+len(chars)*step-9*scale)],'#F6E4AE',None,1,'30')
   star(e,lx,y-12*scale,8);star(e,lx,y+len(chars)*step+6*scale,6)
  elif kind in ('title','ending'):
   size=e.get('size',94 if kind=='title' else 66);rows=text.split('\n');step=size*1.19*scale
   width=max(len(row) for row in rows)*size*scale+40*scale
   for j,row in enumerate(rows):txt(e,row,x,y+j*step,size,e.get('color','#FFF7DB'),outline=e.get('outline','#477AAB'),extra=r'\bord3\shad2')
   yy=y+(len(rows)-1)*step+size*.7*scale
   path(e,[(x-width*.38,yy),(x+width*.38,yy),(x+width*.38,yy+2*scale),(x-width*.38,yy+2*scale)],'#E5C77C')
   star(e,x-width*.44,yy,12);star(e,x+width*.44,yy,12)
  else:
   size=e.get('size',48 if kind=='location' else 56);theme=e.get('theme','blue')
   palette={'blue':('#477DAE','#F7F5DD'),'pink':('#C8858E','#FFF4D9'),'cream':('#F8EDD0','#49749F')}
   fill,fg=palette.get(theme,palette['blue']);rows=text.split('\n');step=size*1.12*scale
   for j,row in enumerate(rows):
    yy=y+j*step;bw=(len(row)*size*.98+30)*scale;bh=size*1.12*scale
    box(e,x-bw/2,yy-bh/2,bw,bh,fill,'#E7DAB2')
    txt(e,row,x,yy,size,fg,outline=fill,extra=r'\shad0\bord0.6')
   star(e,x-bw/2-15*scale,y,9);star(e,x+bw/2+13*scale,y+(len(rows)-1)*step,7)
   if e.get('accent'):
    txt(e,e['accent'],x,y-size*.9*scale,25,'#FFF7DF',outline='#47658D',extra=r'\b0')
 brand=edl.get('branding',{})
 if brand.get('mode')=='text':
  total=sum(round((c['out']-c.get('in',0))*edl['fps'])/edl['fps'] for c in edl['clips'])
  e={'start':0,'end':total};x=brand.get('x',.03)*w;y=brand.get('y',.03)*h
  edge='#4C88AC' if brand.get('style','blue')=='blue' else '#BD963A'
  txt(e,brand['text'],x,y,44,'#FFFFFF',align=7,outline=edge,extra=r'\b0\bord2\shad0\fad(0,0)',layer=8)
 (out/'captions.ass').write_text(header+'\n'.join(events)+'\n',encoding='utf-8')
 def srtstamp(t):
  n=round(t*1000);hh,n=divmod(n,3600000);mm,n=divmod(n,60000);ss,n=divmod(n,1000);return f'{hh:02}:{mm:02}:{ss:02},{n:03}'
 (out/'captions.srt').write_text('\n'.join(f"{i}\n{srtstamp(e['start'])} --> {srtstamp(e['end'])}\n{e['text']}\n" for i,e in enumerate(srts,1)),encoding='utf-8')
