"""Export saved viewmodel Blender sources with Blender Source Tools.

Run: blender --background --python-exit-code 1 --python export_viewmodels.py -- SOURCE [SOURCE ...]
Each SOURCE is a folder beside this script that contains one .blend file.
Requires Blender 5.2.2 and Blender Source Tools 3.4.3 or newer.
This helper reads .blend sources, and writes SMD exports.
An optional composites.txt in a source folder joins exported animations into one more SMD per line:
OUTPUT PART [PART ...] [blend=N], where PART is SLOT, SLOT:FIRST-LAST (inclusive frames; an empty LAST means
the end) or SLOT@KEY-LAST (from the frame after timeline marker SLOT:KEY). Across a join, the last N frames
(default 3) of the previous part are eased onto the pose the next part continues from.
Timeline markers SLOT:PHASE.KEY (KEY credit, at, at2, ...) give ReloadPhases times; they are written,
shifted into every composite, to reload_phases.txt. --script WEAPON_SCRIPT checks its ReloadPhases rows.
"""
from pathlib import Path
import math
import re
import sys

import bpy
from mathutils import Euler, Quaternion

FPS = 30
EXACT = 1e-4  # below the SMD print precision: the poses match, nothing is eased
SEAM_LIMIT_UNITS, SEAM_LIMIT_DEGREES = 0.5, 2.0  # eased over 3 frames: less than the reload moves per frame


def read_frames(path):
    """The header up to 'skeleton', and the frames as lists of bone lines."""
    lines = path.read_text(encoding='ascii').splitlines()
    start = lines.index('skeleton')
    frames = []
    for line in lines[start + 1:]:
        if line.startswith('time '):
            frames.append([])
        elif line != 'end':
            frames[-1].append(line)
    return lines[:start + 1], frames


def pose(line):
    bone, *values = line.split()
    x, y, z, rx, ry, rz = map(float, values)
    return bone, (x, y, z), Euler((rx, ry, rz)).to_quaternion()


def ease_seam(output, joined, target, count):
    """Spread the gap to the target pose over the last frames; fail on a gap no short ease can hide."""
    gaps, count = [], min(count, len(joined))
    for index, (line, goal) in enumerate(zip(joined[-1], target)):
        bone, position, rotation = pose(line)
        _, goal_position, goal_rotation = pose(goal)
        move = [g - p for g, p in zip(goal_position, position)]
        turn = goal_rotation @ rotation.inverted()
        gaps.append((math.dist(position, goal_position), math.degrees(rotation.rotation_difference(goal_rotation).angle), bone))
        if max(map(abs, move)) < EXACT and turn.angle < EXACT:
            continue
        for step in range(1, count + 1):
            weight = step / count
            frame = joined[len(joined) - count + step - 1]
            _, at, spin = pose(frame[index])
            spin = Quaternion().slerp(turn, weight) @ spin
            euler = spin.to_euler('XYZ', Euler(tuple(map(float, frame[index].split()[4:]))))
            frame[index] = '%s  %s' % (bone, ' '.join('%.6f' % v for v in
                                       [a + weight * m for a, m in zip(at, move)] + list(euler)))
    distance, angle = max(g[0] for g in gaps), max(g[1] for g in gaps)
    text = '%s seam gap %.4f u, %.3f deg (blend %d frames)' % (output, distance, angle, count)
    if distance > SEAM_LIMIT_UNITS or angle > SEAM_LIMIT_DEGREES:
        raise RuntimeError('SEAM TOO FAR ' + text + ': pose the transition\'s last frame on the marked frame')
    print('SEAM', text)


def write_composites(folder, markers):
    composites = folder / 'composites.txt'
    times = {}
    for name, frame in markers.items():
        slot, _, key = name.partition(':')
        if '.' in key:
            times.setdefault(slot, {})[key] = frame / FPS
    if not composites.is_file():
        return times
    for line in composites.read_text(encoding='ascii').splitlines():
        if not line.strip():
            continue
        output, *parts = line.split()
        count = int(parts.pop()[6:]) if parts[-1].startswith('blend=') else 3
        header, joined = None, []
        for part in parts:
            slot, mark, span = re.match(r'(\w+)([:@]?)(.*)', part).groups()
            if mark == '@':
                key, _, last = span.partition('-')
                if slot + ':' + key not in markers:
                    raise RuntimeError('No timeline marker %s:%s for %s' % (slot, key, part))
                span = '%d-%s' % (markers[slot + ':' + key] + 1, last)
            part_header, frames = read_frames(folder / 'anims' / (slot + '.smd'))
            if header is not None and part_header != header:
                raise RuntimeError('Composite parts have different nodes: ' + part)
            header = part_header
            first, _, last = span.partition('-')
            first, last = int(first or 0), int(last) if last else len(frames) - 1
            if joined and first > 0 and count > 0:
                ease_seam(output, joined, frames[first - 1], count)
            for key, seconds in times.get(slot, {}).items():
                if first <= round(seconds * FPS) <= last:
                    times.setdefault(output, {})[key] = (len(joined) + round(seconds * FPS) - first) / FPS
            joined += frames[first:last + 1]
        body = [text for time, frame in enumerate(joined) for text in ['time %d' % time] + frame]
        (folder / 'anims' / (output + '.smd')).write_text(
            '\n'.join(header + body + ['end']) + '\n', encoding='ascii')
        print('COMPOSED', output, len(joined), 'frames')
    return times


def write_phases(folder, times, script):
    """reload_phases.txt in weapon-script form; with a script, its credit/at rows must match within half a frame."""
    if not times:
        return
    rows = ['// Generated by export_viewmodels.py from timeline markers SLOT:PHASE.KEY', '"ReloadPhases"', '{']
    for sequence, keys in sorted(times.items()):
        phases = {}
        for key, seconds in keys.items():
            phase, _, name = key.partition('.')
            phases.setdefault(phase, []).append('"%s" "%.3f"' % (name, seconds))
        rows += ['\t"%s"' % sequence, '\t{'] + ['\t\t"%s" { %s }' % (p, ' '.join(v)) for p, v in phases.items()] + ['\t}']
    (folder / 'reload_phases.txt').write_text('\n'.join(rows + ['}']) + '\n', encoding='ascii')
    print('\n'.join(rows[3:]))
    if not script:
        return
    text = Path(script).read_text(encoding='ascii').partition('"ReloadPhases"')[2]
    bad = []
    for sequence, body in re.findall(r'"(\w+)"\s*\{((?:\s*"\w+"\s*\{[^}]*\})+)\s*\}', text):
        for phase, row in re.findall(r'"(\w+)"\s*\{([^}]*)\}', body):
            for name, value in re.findall(r'"(credit|at\d*)"\s*"([\d.]+)"', row):
                marked = times.get(sequence, {}).get(phase + '.' + name)
                if marked is None or abs(marked - float(value)) > 0.5 / FPS:
                    bad.append('%s %s.%s script %s marker %s' % (sequence, phase, name, value, marked))
    if bad:
        raise RuntimeError('ReloadPhases rows do not match the markers: ' + '; '.join(bad))
    print('PHASES OK', script)


def export_project(project, script):
    bpy.ops.wm.open_mainfile(filepath=str(project))
    bpy.ops.preferences.addon_enable(module='io_scene_valvesource')
    missing = [image.filepath for image in bpy.data.images
               if image.source == 'FILE' and not image.packed_file
               and not Path(bpy.path.abspath(image.filepath)).is_file()]
    if missing:
        raise RuntimeError('Missing preview images: ' + ', '.join(missing))
    folder = project.parent
    reference = folder / 'reference.smd'
    reference_bytes = reference.read_bytes()
    armature = next(obj for obj in bpy.context.scene.objects if obj.type == 'ARMATURE')
    expected = [folder / 'anims' / (slot.name_display + '.smd')
                for slot in armature.animation_data.action.slots]
    previous = {path: path.stat().st_mtime_ns if path.exists() else None
                for path in expected}
    result = bpy.ops.export_scene.smd(export_scene=True)
    if result != {'FINISHED'}:
        raise RuntimeError('Source Tools export failed: ' + str(result))
    if any(not path.is_file() or path.stat().st_mtime_ns == previous[path]
           for path in expected):
        raise RuntimeError('Source Tools did not freshly export every expected SMD')
    if reference.read_bytes() != reference_bytes:
        raise RuntimeError('The preview mesh must not overwrite reference.smd')
    print('EXPORTED', project.name, len(expected), 'animation SMD files; reference retained')
    markers = {marker.name: marker.frame for marker in bpy.context.scene.timeline_markers}
    write_phases(folder, write_composites(folder, markers), script)


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    sources = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    script = sources[sources.index('--script') + 1] if '--script' in sources else None
    sources = [s for s in sources if s not in ('--script', script)]
    if not sources:
        raise RuntimeError('List the source folders to export after --')
    projects = []
    for source in sources:
        found = sorted((root / source).glob('*.blend'))
        if len(found) != 1:
            raise RuntimeError('Source folder must contain one .blend file: ' + source)
        projects.append(found[0])
    for project in projects:
        export_project(project, script)
