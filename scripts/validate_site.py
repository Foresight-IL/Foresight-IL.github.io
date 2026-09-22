"""Content, media and browser checks for the local website; no publishing."""
from pathlib import Path
import concurrent.futures, hashlib, json, re, subprocess, sys
from urllib.parse import unquote, urlparse
from bs4 import BeautifulSoup
import pymupdf
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
URL=sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8817'
if len(sys.argv)<3:raise SystemExit('Usage: python scripts/validate_site.py URL /path/to/foresight_il')
SOURCE=Path(sys.argv[2])
OUT=SOURCE/'website_review';OUT.mkdir(exist_ok=True)
html=(ROOT/'index.html').read_text();soup=BeautifulSoup(html,'html.parser')
ids=[e['id'] for e in soup.select('[id]')];assert len(ids)==len(set(ids))
for element in soup.find_all(True):
    for attr in ['src','href','poster','data-src']:
        value=element.get(attr)
        if not value:continue
        if value.startswith('#'):
            assert value[1:] in ids,value
        elif not urlparse(value).scheme:
            assert (ROOT/unquote(value.split('#')[0])).is_file(),value
assert not soup.select('[autoplay]')
assert all(not v.get('src') and v['preload']=='none' for v in soup.find_all('video'))
assert len(soup.select('main table'))==5
assert not soup.select('#analysis table')
assert soup.select_one('main img')['src']=='assets/images/hero.webp'
assert html.index('<section id="simulation"') < html.index('<section id="robots"')
assert len(soup.select('#simulation .sim-grid video'))==6
assert len(soup.select('#pusht-gated video'))==1
assert all(v.find_parent('details') is None for v in soup.select('#simulation .sim-grid video'))
assert not list((ROOT/'assets').rglob('*.pdf'))
assert not re.search(r'author|anonymous|6870|\.pdf',html,re.I)
assert all(img.get('alt') for img in soup.select('main img'))
assert not re.search(r'polyfill.io|bootstrap|MathJax|29%|attest time',html)

# Independently locate the original PDF table rows and compare every numeric cell.
doc=pymupdf.open(SOURCE/'ICRA27_6870_MS.pdf')
table_specs={'simulation':(4,(103,223,509,318)),'value':(5,(154,84,458,158)),
             'gate':(5,(139,203,473,283)),'robots':(5,(144,318,468,398)),
             'composition':(5,(333,460,538,514))}
data=json.loads((ROOT/'scripts/result_data.json').read_text())
row_counts={}
for key,(page,box) in table_specs.items():
    words=doc[page].get_text('words',clip=pymupdf.Rect(box))
    numeric=[w for w in words if re.search(r'\d+\.\d+',w[4])]
    groups=[]
    for w in sorted(numeric,key=lambda w:(w[1],w[0])):
        center=(w[1]+w[3])/2
        nearest=next((g for g in groups if abs(g['y']-center)<3),None)
        if nearest is None:nearest={'y':center,'words':[]};groups.append(nearest)
        nearest['words'].append(w)
    got=[[number for w in sorted(g['words'],key=lambda w:w[0]) for number in re.findall(r'\d+\.\d+',w[4])] for g in sorted(groups,key=lambda g:g['y'])]
    expected=[re.findall(r'\d+\.\d+',' '.join(row)) for row in data[key]['rows']]
    assert got==expected,(key,got,expected)
    row_counts[key]=len(got)

media=list((ROOT/'assets/videos').glob('*.mp4'))
def media_check(path):
    subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','null','-'],check=True,stdout=subprocess.DEVNULL)
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))
    streams=info['streams'];video=next(s for s in streams if s['codec_type']=='video')
    assert video['codec_name']=='h264' and video['pix_fmt']=='yuv420p'
    assert not any(s['codec_type']=='audio' for s in streams)
    return {'file':path.name,'duration':float(info['format']['duration']),'bytes':path.stat().st_size}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:media_reports=list(pool.map(media_check,media))

errors=[];bad_responses=[];requests=[];playback=[]
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('response',lambda r:bad_responses.append((r.status,r.url)) if r.status>=400 else None)
    page.on('request',lambda r:requests.append(r.url))
    page.goto(URL,wait_until='networkidle')
    assert not any('.mp4' in r for r in requests),'Unexpected initial video download'
    assert not [r for r in requests if not r.startswith(URL)],'Unexpected external request'
    initial=page.evaluate('({bytes:performance.getEntriesByType("resource").reduce((s,r)=>s+r.transferSize,0),requests:performance.getEntriesByType("resource").length,overflow:document.documentElement.scrollWidth>innerWidth})')
    assert not initial['overflow']
    assert page.evaluate('getComputedStyle(document.body).backgroundColor')=='rgb(255, 255, 255)'
    assert page.locator('main table:visible').count()==5
    assert page.locator('#simulation .sim-grid video:visible').count()==6
    page.screenshot(path=str(OUT/'desktop.png'))
    # Open every section and decode every image before capturing section previews.
    page.locator('details').evaluate_all('(els)=>els.forEach(e=>e.open=true)')
    page.locator('main img').evaluate_all('(els)=>els.forEach(e=>e.loading="eager")')
    page.wait_for_function('Array.from(document.querySelectorAll("main img")).every(i=>i.complete&&i.naturalWidth>0)')
    page.locator('details').evaluate_all('(els)=>els.forEach(e=>e.open=false)')
    for section in ['toy-kitchen','desk-cleanup','method','simulation','results','analysis','overview']:
        page.locator('#'+section).evaluate('(e)=>window.scrollTo({top:scrollY+e.getBoundingClientRect().top-95,behavior:"instant"})')
        page.screenshot(path=str(OUT/(section+'.png')))
    page.locator('[data-zoom]').first.click();assert page.locator('dialog').is_visible()
    page.keyboard.press('Escape');assert not page.locator('dialog').is_visible()

    page.locator('details').evaluate_all('(els)=>els.forEach(e=>e.open=true)')
    for i in range(page.locator('.player').count()):
        player=page.locator('.player').nth(i);video=player.locator('video')
        player.locator('.play-button').click()
        video.evaluate('(v)=>new Promise((resolve,reject)=>{if(v.currentTime>0.05&&!v.paused)return resolve();const timer=setTimeout(()=>reject(new Error("Playback did not advance")),10000);v.addEventListener("timeupdate",()=>{if(v.currentTime>0.05){clearTimeout(timer);resolve()}},{once:true});})')
        assert video.evaluate('(v)=>v.videoWidth>0 && !v.error')
        duration=video.evaluate('(v)=>v.duration')
        video.evaluate('(v)=>{v.pause();v.currentTime=Math.max(0,v.duration-.3)}')
        video.evaluate('(v)=>new Promise(resolve=>{if(!v.seeking)return resolve();v.addEventListener("seeked",resolve,{once:true})})')
        playback.append({'source':video.get_attribute('data-src'),'duration':duration,'played_and_seeked':True})

    mobile_reports=[]
    for width in [360,390,768]:
        mobile=browser.new_page(viewport={'width':width,'height':844},device_scale_factor=1,is_mobile=True,has_touch=True)
        mobile.goto(URL,wait_until='networkidle')
        assert not mobile.evaluate('document.documentElement.scrollWidth>innerWidth'),width
        if width==390:mobile.screenshot(path=str(OUT/'mobile.png'))
        for key in data:
            assert mobile.locator('#result-'+key).is_visible()
            assert not mobile.evaluate('document.documentElement.scrollWidth>innerWidth'),(width,key)
        assert mobile.locator('#simulation .sim-grid video:visible').count()==6
        mobile_reports.append({'width':width,'no_page_overflow':True,'all_tables_and_simulation_videos_visible':True})
        if width==390:
            mobile.locator('#toy-kitchen').evaluate('(e)=>window.scrollTo({top:scrollY+e.getBoundingClientRect().top-108,behavior:"instant"})')
            mobile.screenshot(path=str(OUT/'mobile-demos.png'))
            mobile.locator('#simulation').evaluate('(e)=>window.scrollTo({top:scrollY+e.getBoundingClientRect().top-108,behavior:"instant"})')
            mobile.screenshot(path=str(OUT/'mobile-simulation.png'))
        mobile.close()
    nojs=browser.new_page(java_script_enabled=False)
    nojs.goto(URL,wait_until='networkidle')
    assert nojs.locator('main table:visible').count()==5
    assert nojs.locator('noscript a').first.is_visible()
    browser.close()
assert not errors,errors
assert not bad_responses,bad_responses
report={'pdf_table_rows_verified':row_counts,'video_decode_checks':media_reports,'browser_players':playback,
        'initial_load':initial,'initial_video_requests':0,'external_requests':0,'javascript_errors':errors,
        'http_errors':bad_responses,'mobile':mobile_reports,'figure_dialog_keyboard_close':True,
        'hero_is_first_figure':True,'simulation_before_real_robots':True,'all_six_simulation_videos_visible':True,'pusht_gated_showcase_visible':True,'paper_download_removed':True,
        'no_javascript_fallback':True,'no_commits_or_pushes_performed':True}
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'table_rows_checked':sum(row_counts.values()),'videos_decoded':len(media_reports),'players_tested':len(playback),'initial_load':initial,'mobile':mobile_reports,'errors':errors}),flush=True)
