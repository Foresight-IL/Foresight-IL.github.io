"""Build the website overview from the reviewed final video segments.

Run: python scripts/build_overview.py /path/to/foresight_il
Only the website copy is edited; the submission video and sources are read only.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import tempfile

from PIL import Image


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_overview(source, site):
    source, site = Path(source).resolve(), Path(site).resolve()
    reviewed = source / 'icra27_assets/submission_video_v3'
    manifest = json.loads((reviewed / 'build_manifest.json').read_text())
    scenes = manifest['scenes']
    submission = source / 'ICRA27_6870_video.mp4'
    assert sha(submission) == manifest['video_sha256'], 'Submission differs from the reviewed build'
    masks = {
        'title': (90, 950, 465, 55),
        'openloop': (90, 1016, 285, 48),
        'candidates': (90, 1016, 285, 48),
    }
    target = site / 'assets/videos/overview.mp4'
    poster = site / 'assets/images/overview.webp'
    with tempfile.TemporaryDirectory(prefix='foresight-web-overview-') as temporary:
        temporary = Path(temporary)
        segments = []
        for scene in scenes:
            name = scene['title']
            original = reviewed / 'segments' / (name + '.mp4')
            assert sha(original) == scene['segment_sha256'], name
            if name not in masks:
                segments.append(original)
                continue
            x, y, width, height = masks[name]
            segment = temporary / (name + '.mp4')
            subprocess.run([
                'ffmpeg', '-v', 'error', '-y', '-i', str(original),
                '-map', '0:v:0', '-an', '-vf',
                f'drawbox=x={x}:y={y}:w={width}:h={height}:color=white:t=fill',
                '-frames:v', str(round(scene['duration_seconds'] * manifest['fps'])),
                '-r', str(manifest['fps']), '-c:v', 'libx264', '-preset', 'fast',
                '-crf', '18', '-threads', '4', '-pix_fmt', 'yuv420p',
                '-profile:v', 'high', '-level:v', '4.0', '-video_track_timescale', '15360',
                '-map_metadata', '-1', str(segment),
            ], check=True)
            segments.append(segment)
        listing = temporary / 'concat.txt'
        listing.write_text(''.join("file '" + str(p).replace("'", "'\\''") + "'\n" for p in segments))
        output = temporary / 'overview.mp4'
        subprocess.run([
            'ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(listing),
            '-map', '0:v:0', '-an', '-c:v', 'copy', '-map_metadata', '-1',
            '-movflags', '+faststart', str(output),
        ], check=True)
        info = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(output),
        ]))
        stream = info['streams'][0]
        assert len(info['streams']) == 1 and stream['codec_name'] == 'h264'
        assert int(stream['nb_frames']) == round(manifest['duration_seconds'] * manifest['fps'])
        assert [stream['width'], stream['height']] == manifest['resolution']
        assert abs(float(info['format']['duration']) - manifest['duration_seconds']) < 0.001
        # Decode the entire output before replacing the published website asset.
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(output), '-f', 'null', '-'], check=True)
        png = temporary / 'poster.png'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '1', '-i', str(output), '-frames:v', '1', str(png)], check=True)
        with Image.open(png) as image:
            image.thumbnail((1100, 1100))
            image.save(poster, quality=92, method=6)
        target.write_bytes(output.read_bytes())
    return {
        'asset': 'assets/videos/overview.mp4',
        'source': 'icra27_assets/submission_video_v3',
        'source_video_sha256': manifest['video_sha256'],
        'duration_seconds': manifest['duration_seconds'],
        'frames': round(manifest['duration_seconds'] * manifest['fps']),
        'fps': manifest['fps'],
        'resolution': manifest['resolution'],
        'sha256': sha(target),
        'website_only': True,
        'venue_labels_removed': True,
        'source_video_unchanged': sha(submission) == manifest['video_sha256'],
        'scene_count': len(scenes),
        'unchanged_scene_streams': [s['title'] for s in scenes if s['title'] not in masks],
        'redacted_scene_regions': {name: list(rect) for name, rect in masks.items()},
        'second_scene_title': 'Complete multi-step tasks with ForesightIL',
    }


def update_manifests(site, overview):
    site = Path(site)
    demo_path = site / 'scripts/demo_manifest.json'
    demos = json.loads(demo_path.read_text())
    demos['overview'] = overview
    demo_path.write_text(json.dumps(demos, indent=2) + '\n')
    media_path = site / 'scripts/media_manifest.json'
    media = json.loads(media_path.read_text())
    matches = [i for i, entry in enumerate(media) if entry['asset'] == overview['asset']]
    assert len(matches) == 1, 'Expected one overview entry in media manifest'
    media[matches[0]] = overview
    media_path.write_text(json.dumps(media, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('--site', type=Path, default=Path(__file__).resolve().parents[1])
    arguments = parser.parse_args()
    overview = build_overview(arguments.source, arguments.site)
    update_manifests(arguments.site, overview)
    print(json.dumps(overview, indent=2))
