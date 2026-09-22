"""Rebuild local scientific figures and website demo edits, without publishing a PDF.

Usage: python scripts/build_assets.py /path/to/foresight_il
Requires Pillow, PyMuPDF, OpenCV, NumPy, ffmpeg and ffprobe.
"""
from pathlib import Path
import concurrent.futures, hashlib, json, subprocess, sys
import cv2
import pymupdf
from PIL import Image

SOURCE=Path(sys.argv[1]).resolve()
SITE=Path(__file__).resolve().parents[1]
ASSETS=SITE/'assets'
for folder in ['images','videos']:(ASSETS/folder).mkdir(parents=True,exist_ok=True)
manifest=[]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def save_image(im,name,width=1800):
    im=im.convert('RGB')
    if im.width>width:im=im.resize((width,round(im.height*width/im.width)),Image.Resampling.LANCZOS)
    im.save(ASSETS/'images'/(name+'.webp'),quality=93,method=6)
    return im.size

# The manuscript is an input only, never a deployable asset.
old=ASSETS/'papers/foresightil.pdf'
if old.exists():old.unlink()
if old.parent.exists() and not any(old.parent.iterdir()):old.parent.rmdir()
pdf=SOURCE/'ICRA27_6870_MS.pdf';doc=pymupdf.open(pdf)
pix=doc[1].get_pixmap(matrix=pymupdf.Matrix(4,4),clip=pymupdf.Rect(54,54,558,346),alpha=False)
save_image(Image.frombytes('RGB',(pix.width,pix.height),pix.samples),'hero',2016)
manifest.append({'asset':'assets/images/hero.webp','source':pdf.name,'page':2,'crop':[54,54,558,346],'source_sha256':sha(pdf)})
for name in ['latency','openloop','candidate_outcomes']:
    src=SOURCE/'icra27_assets'/(name+'.png');size=save_image(Image.open(src),name)
    manifest.append({'asset':'assets/images/'+name+'.webp','source':pdf.name,'source_crop':name+'.png','dimensions':size})
figdir=SOURCE/'foresightIL_icra27_overleaf_writing_20260915/figs'
for name in ['candidate_scaling','planning_horizon','value_geometry','uncertainty_diagnostics','appendix_policy_robustness','sim_openloop_comparison','yam_candidate_outcomes','yam_action_diagnostics']:
    src=figdir/(name+'.pdf');page=pymupdf.open(src)[0]
    pix=page.get_pixmap(matrix=pymupdf.Matrix(1800/page.rect.width,1800/page.rect.width),alpha=False)
    size=save_image(Image.frombytes('RGB',(pix.width,pix.height),pix.samples),name)
    manifest.append({'asset':'assets/images/'+name+'.webp','source':str(src.relative_to(SOURCE)),'source_sha256':sha(src),'dimensions':size})

# Preserve the legacy source recordings. Re-encoding is only needed on first build.
def legacy_copy(job):
    stem,speed=job;src=SITE/'mfiles/env/ForesightIL'/(stem+'.mp4')
    name='franka-'+stem if stem.startswith('pp') else stem;dest=ASSETS/'videos'/(name+'.mp4')
    if not dest.exists():
        vf='scale=min(1280\\,iw):-2'
        if speed!=1:vf=f'setpts=PTS/{speed},'+vf+',fps=30'
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(src),'-an','-vf',vf,'-c:v','libx264','-crf','23',
            '-preset','medium','-pix_fmt','yuv420p','-movflags','+faststart','-map_metadata','-1','-threads','2',str(dest)],check=True)
    cap=cv2.VideoCapture(str(dest));ok,f=cap.read();assert ok;cap.release()
    save_image(Image.fromarray(cv2.cvtColor(f,cv2.COLOR_BGR2RGB)),name,1000)
    return {'asset':str(dest.relative_to(SITE)),'source':str(src.relative_to(SITE)),'source_sha256':sha(src),'speed':speed,'sha256':sha(dest)}
jobs=[(stem,2) for stem in ['pp_0','pp_1','pp_2','pp_3','pp_fail_0','pp_fail_1','pp_fail_2']]
jobs += [(stem,1) for stem in ['blockpush_plan','blockpush_no_plan','pusht_plan','pusht_no_plan','libero_goal_plan','libero_goal_no_plan']]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:manifest.extend(pool.map(legacy_copy,jobs))
subprocess.run([sys.executable,str(SITE/'scripts/build_web_demos.py'),str(SOURCE)],check=True)
manifest.extend(json.loads((SITE/'scripts/demo_manifest.json').read_text())['clips'])
(SITE/'scripts/media_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Website assets built. No manuscript PDF is copied into the site.')
