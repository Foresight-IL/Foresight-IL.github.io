"""Import the reviewed single-view Push-T export without private training paths.

Usage: python scripts/import_pusht_demo.py /path/to/pusht_showcase/selected
The input comes from render_showcase.py in the local presentation workspace.
"""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
source = Path(sys.argv[1])
report = json.loads((source/'pusht_gated_demo_provenance.json').read_text())
video = source/'pusht_gated_demo.mp4'
digest = hashlib.sha256(video.read_bytes()).hexdigest()
assert digest == report['video_sha256']
info = json.loads(subprocess.check_output([
    'ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(video)]))
stream = next(s for s in info['streams'] if s['codec_type'] == 'video')
assert [stream['width'], stream['height']] == report['resolution'] == [1448, 940]
assert int(stream['nb_frames']) == report['frames']
assert report['single_environment_view'] and report['episode'] == 4
assert abs(report['final_coverage'] - .9863994412404705) < 1e-8
assert not any(s['codec_type'] == 'audio' for s in info['streams'])
shutil.copy2(video, ROOT/'assets/videos/pusht-gated.mp4')
shutil.copy2(source/'pusht_gated_demo.webp', ROOT/'assets/images/pusht-gated.webp')
# Explicit public fields prevent hostnames or private checkpoint paths leaking
# if the local renderer gains additional provenance fields later.
keys = ['episode', 'environment_seed', 'source_npz_sha256', 'source_json_sha256',
        'renderer_sha256', 'mapping_sha256', 'frames', 'fps', 'duration_seconds',
        'source_frames', 'source_environment_duration_seconds', 'resolution',
        'single_environment_view', 'environment_rect', 'palette', 'timing',
        'execution_alignment', 'uncertainty_display', 'warmup', 'coverage_display',
        'final_coverage', 'peak_coverage', 'plan_fraction', 'poster_source_frame']
public = {key: report[key] for key in keys}
public.update(asset='assets/videos/pusht-gated.mp4', sha256=digest,
              selection='Illustrative successful rollout selected after reviewing eight initial states; not an aggregate benchmark result.')
(ROOT/'scripts/pusht_manifest.json').write_text(json.dumps(public, indent=2)+'\n')
manifest_path = ROOT/'scripts/media_manifest.json'
manifest = json.loads(manifest_path.read_text())
manifest = [item for item in manifest if item['asset'] != public['asset']]
manifest.append(public)
manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
print(f"Imported Push-T: {public['frames']} frames, {public['duration_seconds']:.1f} s")
