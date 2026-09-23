"""Website-only edits from original cameras and verified execution/frame mappings.

The submission PPTX, submission MP4, and original recordings are not modified.
Run: python scripts/build_web_demos.py /path/to/foresight_il
"""
from pathlib import Path
import bisect, concurrent.futures, csv, hashlib, json, math, subprocess, sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from build_overview import build_overview, update_manifests

SOURCE=Path(sys.argv[1]).resolve()
SITE=Path(__file__).resolve().parents[1]
VIDEOS=SITE/'assets/videos';IMAGES=SITE/'assets/images'
SIZE=(1448,724)
GATED_SIZE=(1448,940)
BLUE,AMBER,TEAL,INK='#007CB6','#CA8A2B','#188476','#27343C'
FONT_DIR=Path('/usr/share/fonts/truetype/liberation2')
FONTS={(size,bold):ImageFont.truetype(str(FONT_DIR/('LiberationSans-Bold.ttf' if bold else 'LiberationSans-Regular.ttf')),size)
       for size in [20,22,24,26,28,30,42] for bold in [True,False]}
CAMS=['zed_left_im','left_wrist_im','right_wrist_im']
RECTS=[(0,2,960,720),(968,0,480,360),(968,364,480,360)]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def compose(images,mode,speed,held=False,observations=False):
    im=Image.new('RGB',SIZE,'white')
    for src,(x,y,w,h) in zip(images,RECTS):
        if not isinstance(src,Image.Image):src=Image.fromarray(cv2.cvtColor(src,cv2.COLOR_BGR2RGB))
        im.paste(src.resize((w,h),Image.Resampling.LANCZOS),(x,y))
    d=ImageDraw.Draw(im,'RGBA')
    mode_text='Model-based plan' if mode=='plan' else 'Model-free policy'
    status='Recorded frames' if observations else ('Final frame' if held else f'{speed}× speed')
    color=AMBER if mode=='plan' else BLUE
    # Fill the entire badge with the paper's mode color; retain text as a second cue.
    foreground=INK if mode=='plan' else 'white'
    d.rounded_rectangle((18,19,520,99),radius=7,fill=color)
    d.text((38,27),'Last action' if held else 'Executing',font=FONTS[22,False],fill=foreground)
    d.text((38,56),mode_text,font=FONTS[30,True],fill=foreground)
    sw=d.textlength(status,font=FONTS[22,True])
    d.text((500-sw,29),status,font=FONTS[22,True],fill=foreground)
    for x,y,label in [(18,672,'Main view'),(983,313,'Left wrist'),(983,676,'Right wrist')]:
        width=d.textlength(label,font=FONTS[22,False])
        d.rounded_rectangle((x,y,x+width+20,y+34),radius=4,fill=(39,52,60,215))
        d.text((x+10,y+3),label,font=FONTS[22,False],fill='white')
    return im

def encoder(path,size=SIZE):
    return subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{size[0]}x{size[1]}','-r','30','-i','pipe:0',
        '-an','-c:v','libx264','-crf','22','-preset','medium','-pix_fmt','yuv420p','-movflags','+faststart',
        '-map_metadata','-1','-threads','3',str(path)],stdin=subprocess.PIPE)

class ExecutionTrace:
    """Scores are held over the action chunks they produced, not request issue times."""
    def __init__(self,audit):
        self.segments=audit['execution_segments']
        self.first=self.segments[0]['start_frame']/30
        self.last=audit['raw_frames']/30
        self.maximum=max(2,math.ceil(max(s['gate'] for s in self.segments)))
        self.x0,self.x1,self.y0,self.y1=370,1418,768,862
        self.base=Image.new('RGB',GATED_SIZE,'white');d=ImageDraw.Draw(self.base)
        d.line((0,724,1448,724),fill='#E4E9EC',width=2)
        d.text((24,739),'Uncertainty / threshold',font=FONTS[26,False],fill=INK)
        d.text((24,836),'Plan at ≥ 1',font=FONTS[24,False],fill=TEAL)
        for x,label,color in [(370,'Model-free',BLUE),(560,'Model-based',AMBER)]:
            d.rectangle((x,738,x+16,754),fill=color)
            d.text((x+25,731),label,font=FONTS[24,False],fill=INK)
        label='Recorded time (s)'
        d.text((self.x1-d.textlength(label,font=FONTS[22,False]),733),label,font=FONTS[22,False],fill=INK)
        for s in self.segments:
            a,b=self.x(s['start_frame']/30),self.x(s['end_frame_exclusive']/30)
            color=AMBER if s['mode']=='plan' else BLUE
            d.rectangle((a,self.y0,b,self.y1),fill='#F9ECD7' if s['mode']=='plan' else '#EAF3F8')
            d.rectangle((a,876,b,892),fill=color)
        for value in [0,1,self.maximum]:
            yy=self.y(value)
            label=str(value)
            d.text((self.x0-12-d.textlength(label,font=FONTS[22,False]),yy-13),label,font=FONTS[22,False],fill=TEAL if value==1 else INK)
        for x in range(self.x0,self.x1,14):
            d.line((x,self.y(1),min(x+8,self.x1),self.y(1)),fill=TEAL,width=2)
        previous=None
        for s in self.segments:
            a,b=self.x(s['start_frame']/30),self.x(s['end_frame_exclusive']/30)
            yy=self.y(s['gate'])
            if previous is not None:d.line((a,previous,a,yy),fill='#7F898F',width=2)
            d.line((a,yy,b,yy),fill='#7F898F',width=2)
            d.ellipse((a-4,yy-4,a+4,yy+4),fill=AMBER if s['mode']=='plan' else BLUE)
            previous=yy
        # Absolute source seconds: startup trims and speed changes do not shift the axis.
        ticks=[(self.first,f'{self.first:.2f}')]
        ticks.extend((t,str(t)) for t in range(5,math.ceil(self.last),5) if self.first<t<self.last-1.3)
        ticks.append((self.last,f'{self.last:.2f}'))
        for t,label in ticks:
            x=self.x(t);width=d.textlength(label,font=FONTS[22,False])
            d.line((x,894,x,900),fill=INK,width=2)
            d.text((max(self.x0,min(x-width/2,self.x1-width)),903),label,font=FONTS[22,False],fill=INK)

    def x(self,t):return round(self.x0+(t-self.first)/(self.last-self.first)*(self.x1-self.x0))
    def y(self,value):return round(self.y1-value/self.maximum*(self.y1-self.y0))

    def render(self,cameras,row):
        im=self.base.copy();im.paste(cameras,(0,0));d=ImageDraw.Draw(im)
        gate=float(row['gate']);time=float(row['source_seconds'])
        color=AMBER if row['mode']=='plan' else BLUE
        d.text((24,775),f'{gate:.3f}',font=FONTS[42,True],fill=color)
        d.text((24,890),f't = {time:.2f} s',font=FONTS[26,True],fill=INK)
        x,y=self.x(time),self.y(gate)
        d.line((x,self.y0-3,x,897),fill=INK,width=3)
        d.ellipse((x-8,y-8,x+8,y+8),fill=color,outline='white',width=2)
        return im

class PolicyTimeline:
    """Match the WM+BC canvas using only recorded BC timing, with no gate values."""
    def __init__(self,last):
        self.last=last
        self.x0,self.x1=370,1418
        self.base=Image.new('RGB',GATED_SIZE,'white');d=ImageDraw.Draw(self.base)
        d.line((0,724,1448,724),fill='#E4E9EC',width=2)
        d.text((24,739),'Controller',font=FONTS[26,False],fill=INK)
        d.text((24,775),'BC only',font=FONTS[42,True],fill=BLUE)
        d.text((24,836),'No planning',font=FONTS[24,False],fill=INK)
        d.rectangle((370,738,386,754),fill=BLUE)
        d.text((395,731),'Model-free',font=FONTS[24,False],fill=INK)
        label='Recorded time (s)'
        d.text((self.x1-d.textlength(label,font=FONTS[22,False]),733),label,font=FONTS[22,False],fill=INK)
        d.rectangle((self.x0,768,self.x1,862),fill='#EAF3F8')
        label='Model-free policy throughout'
        d.text(((self.x0+self.x1-d.textlength(label,font=FONTS[28,False]))/2,799),label,font=FONTS[28,False],fill=BLUE)
        d.rectangle((self.x0,876,self.x1,892),fill=BLUE)
        ticks=[(0,'0')]+[(t,str(t)) for t in range(5,math.ceil(last),5) if t<last-1.3]+[(last,f'{last:.2f}')]
        for time,label in ticks:
            x=self.x(time);width=d.textlength(label,font=FONTS[22,False])
            d.line((x,894,x,900),fill=INK,width=2)
            d.text((max(self.x0,min(x-width/2,self.x1-width)),903),label,font=FONTS[22,False],fill=INK)

    def x(self,time):return round(self.x0+time/self.last*(self.x1-self.x0))

    def render(self,cameras,time):
        im=self.base.copy();im.paste(cameras,(0,0));d=ImageDraw.Draw(im)
        d.text((24,890),f't = {time:.2f} s',font=FONTS[26,True],fill=INK)
        x=self.x(time)
        d.line((x,869,x,897),fill=INK,width=3)
        return im

def wm_clip(name,tag,episode):
    rows=list(csv.DictReader((SOURCE/'icra27_assets/video_edit'/f'{tag}_frames.csv').open()))
    audit=json.loads((SOURCE/'icra27_assets/video_edit'/f'{tag}_audit.json').read_text())
    trace=ExecutionTrace(audit)
    base=SOURCE/'videos/wm_planning_videos'/episode/'raw_episode/robot/all_videos'
    caps=[cv2.VideoCapture(str(base/(c+'_30hz.mp4'))) for c in CAMS]
    dest=VIDEOS/(name+'.mp4');proc=encoder(dest,GATED_SIZE);last=-1;images=None
    for row in rows:
        ix=int(row['source_frame'])
        while last<ix:
            images=[]
            for cap in caps:
                ok,f=cap.read();assert ok;images.append(f)
            last+=1
        im=compose(images,row['mode'],int(row['speed']),row['held']=='True')
        proc.stdin.write(trace.render(im,row).tobytes())
    proc.stdin.close();assert proc.wait()==0
    for cap in caps:cap.release()
    return {'asset':str(dest.relative_to(SITE)),'source_episode':episode,'source_mapping':f'icra27_assets/video_edit/{tag}_frames.csv',
            'frames':len(rows),'duration':len(rows)/30,'mode_alignment':'Same verified executed-chunk labels and source frames as the submission edit.',
            'resolution':GATED_SIZE,
            'uncertainty_display':'Recorded signal / threshold of the currently executed action chunk; step trace held over that chunk.',
            'timeline':'Executed modes on an absolute source-seconds axis; the cursor follows source frames, including speed changes and the final hold.',
            'sha256':sha(dest)}

def fruit_bc():
    base=SOURCE/'videos/wm_planning_videos/bc_rollouts/fruit/bc_20260910_041100/raw_episode/robot'
    rows=[json.loads(line) for line in (base/'replies.jsonl').read_text().splitlines()]
    rows=[r for r in rows if 'mode' in r];assert all(r['mode']=='bc' for r in rows)
    times=[r['t_frames_tick'][-1] for r in rows]
    images=[]
    for r in rows:
        cameras=[Image.open(base/'frames_full'/f'{r["n"]:05d}_{cam}.jpg').convert('RGB') for cam in CAMS]
        images.append(compose(cameras,'bc',1,observations=True))
    duration=times[-1]-times[0];timeline=PolicyTimeline(duration)
    frames=math.ceil((duration+1)*30);dest=VIDEOS/'toy-kitchen-bc.mp4';proc=encoder(dest,GATED_SIZE)
    for i in range(frames):
        index=bisect.bisect_right(times,times[0]+i/30)-1
        proc.stdin.write(timeline.render(images[index],min(i/30,duration)).tobytes())
    proc.stdin.close();assert proc.wait()==0
    return {'asset':str(dest.relative_to(SITE)),'source_episode':'bc_rollouts/fruit/bc_20260910_041100',
            'frames':frames,'duration':frames/30,'timing':'Observed frame sets at their recorded timestamps, final frame held 1 s.',
            'observations':len(rows),'comparison_note':'Earlier trained policy; illustrative low-rate recording, not a matched-policy comparison.',
            'resolution':GATED_SIZE,'timeline':'Model-free execution throughout; elapsed recorded seconds from the first observation, frozen during the final hold. No uncertainty values are displayed.',
            'sha256':sha(dest)}

def desk_bc():
    base=SOURCE/'videos/wm_planning_videos/bc_rollouts/table_cleanup/bc_20260913_015019/raw_episode/robot'
    assert json.loads((base/'meta.json').read_text())['force_mode']=='bc'
    caps=[cv2.VideoCapture(str(base/'all_videos'/(c+'_30hz.mp4'))) for c in CAMS]
    count=int(caps[0].get(cv2.CAP_PROP_FRAME_COUNT));rows=[];i=0
    while i<count:
        speed=1 if 5.8<=i/30<10.5 else 2
        rows.append({'source_frame':i,'speed':speed,'held':False});i+=speed
    rows.extend({'source_frame':count-1,'speed':0,'held':True} for _ in range(30))
    timeline=PolicyTimeline(count/30)
    dest=VIDEOS/'desk-cleanup-bc.mp4';proc=encoder(dest,GATED_SIZE);last=-1;images=None
    for row in rows:
        while last<row['source_frame']:
            images=[]
            for cap in caps:
                ok,f=cap.read();assert ok;images.append(f)
            last+=1
        im=compose(images,'bc',row['speed'],row['held'])
        proc.stdin.write(timeline.render(im,row['source_frame']/30).tobytes())
    proc.stdin.close();assert proc.wait()==0
    for cap in caps:cap.release()
    return {'asset':str(dest.relative_to(SITE)),'source_episode':'bc_rollouts/table_cleanup/bc_20260913_015019',
            'frames':len(rows),'duration':len(rows)/30,'frame_map':rows,'resolution':GATED_SIZE,
            'timeline':'Model-free execution throughout; recorded source seconds follow the frame mapping and freeze during the final hold. No uncertainty values are displayed.',
            'sha256':sha(dest)}

def poster(name,time):
    cap=cv2.VideoCapture(str(VIDEOS/(name+'.mp4')));cap.set(cv2.CAP_PROP_POS_MSEC,time*1000)
    ok,f=cap.read();assert ok;cap.release()
    im=Image.fromarray(cv2.cvtColor(f,cv2.COLOR_BGR2RGB));im.thumbnail((1100,1100));im.save(IMAGES/(name+'.webp'),quality=92,method=6)

def overview():
    return build_overview(SOURCE,SITE)

if __name__=='__main__':
    jobs=[lambda:wm_clip('toy-kitchen','toy_kitchen_demo','fruit/wm_bc_20260913_022245'),
          lambda:wm_clip('desk-cleanup','desk_cleanup_demo','table_cleanup/wm_bc_20260913_015538'),fruit_bc,desk_bc]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        reports=list(pool.map(lambda job:job(),jobs))
    for name,t in [('toy-kitchen',4),('desk-cleanup',4),('toy-kitchen-bc',8),('desk-cleanup-bc',7)]:poster(name,t)
    print('Four website demos rebuilt from original cameras.',flush=True)
    overview_report=overview()
    (SITE/'scripts/demo_manifest.json').write_text(json.dumps({'bc_resolution':GATED_SIZE,'wm_bc_resolution':GATED_SIZE,'camera_rectangles':RECTS,'palette':{'policy':BLUE,'planning':AMBER,'value':TEAL,'ink':INK},'clips':reports,'overview':overview_report},indent=2)+'\n')
    update_manifests(SITE,overview_report)
    print('Website overview rebuilt; original submission files untouched.',flush=True)
