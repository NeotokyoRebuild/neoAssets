"""Export saved viewmodel Blender sources with Blender Source Tools.

Run: blender --background --python-exit-code 1 --python export_viewmodels.py -- PROJECT [PROJECT ...]
Each PROJECT (such as jinrai_zr68c) is a scene of viewmodels.blend beside this script, exported into the folder
of the same name, which holds the project's .qc, reference.smd and anims/.
Requires Blender 5.2.3 or newer and Blender Source Tools 3.4.3 or newer.
This helper reads viewmodels.blend, and writes SMD exports.
An optional composites.txt in a project folder joins exported animations into one more SMD per line:
OUTPUT PART [PART ...] [blend=N], where PART is SLOT, SLOT:FIRST-LAST (inclusive frames; an empty LAST means
the end) or SLOT@STEP-LAST (from the frame after timeline marker SLOT:STEP.join, else SLOT:STEP). Across a join,
the last N frames (default 3) of the previous part are eased onto the pose the next part continues from.
Timeline markers time the rows of neo/scripts/weapon_GUN_reload_phases.txt (GUN: the folder name after its team
prefix): the step marker SLOT:STEP gives the step's "ammo" time, SLOT:STEP.KEY (KEY sound, sound2, ...) the others.
The export rewrites each time there, shifted into composites. Both team scenes of a gun must carry the same markers:
a mismatch fails before any SMD is written.
A sound entry weapon_GUN.KEY plays sound/weapons/GUN/GUN_KEY.wav (a convention; the sound script is not read).
A row's "resume" key names the composite that resumes the reload interrupted after that step; the composite must
join the row's sequence after that step (part SEQUENCE@STEP...). A resume lists only the steps after STEP:
it never replays an earlier step's sound.
A sequence's ammo times come before its last frame, and its sounds finish playing by then: the gun can fire there.
"""
from pathlib import Path
from typing import NamedTuple
import math
import re
import sys
import wave

import bpy
from mathutils import Euler, Quaternion

SOURCE = 'viewmodels.blend'
FPS = 30
SOUND_LEAD = 0.02  # neo starts a reload sound piece this long before its time (RELOAD_SOUND_LEAD)
EXACT = 1e-4  # below the SMD print precision: the poses match, nothing is eased
TIME_KEY = re.compile(r'ammo|sound\d*')  # the phases keys the markers set; "sound_name" is not one
WAV_PATH = 'sound/weapons/{gun}/{gun}_{key}.wav'  # for sound entry weapon_GUN.KEY
SEAM_LIMIT_UNITS, SEAM_LIMIT_DEGREES = 0.5, 2.0  # eased over 3 frames: less than the reload moves per frame
# Each project's rig and the one action it may export. A new project needs a row here.
RIGS = {
    'jinrai_tachi': ('jinrai_tachi_rig', 'jinrai_tachi_animations'),
    'nsf_tachi': ('nsf_tachi_rig', 'nsf_tachi_animations'),
    'jinrai_zr68c': ('jinrai_zr68c_rig', 'jinrai_zr68c_animations'),
    'nsf_zr68c': ('nsf_zr68c_rig', 'nsf_zr68c_animations'),
}


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
    values = list(map(float, values))
    return bone, values[:3], Euler(values[3:])


def ease_seam(output, joined, target, count):
    """Spread the gap to the target pose over the last frames; fail on a gap no short ease can hide."""
    distance = angle = 0.0
    count = min(count, len(joined))
    for index, goal in enumerate(target):
        bone, position, rotation = pose(joined[-1][index])
        _, goal_position, goal_rotation = pose(goal)
        move = [g - p for g, p in zip(goal_position, position)]
        turn = goal_rotation.to_quaternion() @ rotation.to_quaternion().inverted()
        distance = max(distance, math.dist(position, goal_position))
        angle = max(angle, math.degrees(turn.angle))
        if max(map(abs, move)) < EXACT and turn.angle < EXACT:
            continue
        for step in range(1, count + 1):
            frame, weight = joined[step - count - 1], step / count
            _, at, spin = pose(frame[index])
            eased_at = [a + weight * m for a, m in zip(at, move)]
            eased_turn = Quaternion().slerp(turn, weight)
            eased_spin = (eased_turn @ spin.to_quaternion()).to_euler('XYZ', spin)
            values = eased_at + list(eased_spin)
            frame[index] = bone + '  ' + ' '.join('%.6f' % value for value in values)
    text = '%s seam gap %.4f u, %.3f deg (blend %d frames)' % (output, distance, angle, count)
    if distance > SEAM_LIMIT_UNITS or angle > SEAM_LIMIT_DEGREES:
        raise RuntimeError('SEAM TOO FAR ' + text + ': pose the transition\'s last frame on the marked frame')
    print('SEAM', text)


def write_composites(folder, markers):
    """Write the composites; return the marker frames per sequence and each composite's SLOT@STEP joins."""
    composites = folder / 'composites.txt'
    times, joins = {}, {}
    for name, frame in markers.items():
        slot, _, key = name.partition(':')
        if key:
            times.setdefault(slot, {})[key] = frame
    if not composites.is_file():
        return times, joins
    for line in composites.read_text(encoding='ascii').splitlines():
        if not line.strip():
            continue
        output, *parts = line.split()
        count = int(parts.pop()[6:]) if parts[-1].startswith('blend=') else 3
        header, joined = None, []
        for part in parts:
            slot, mark, span = re.match(r'(\w+)([:@]?)(.*)', part).groups()
            if mark == '@':
                step, _, last = span.partition('-')
                joins.setdefault(output, set()).add((slot, step))
                join = markers.get(slot + ':' + step + '.join', markers.get(slot + ':' + step))
                if join is None:
                    raise RuntimeError('No timeline marker %s:%s for %s' % (slot, step, part))
                span = '%d-%s' % (join + 1, last)
            part_header, frames = read_frames(folder / 'anims' / (slot + '.smd'))
            if header is not None and part_header != header:
                raise RuntimeError('Composite parts have different nodes: ' + part)
            header = part_header
            first, _, last = span.partition('-')
            first, last = int(first or 0), int(last) if last else len(frames) - 1
            if joined and first > 0 and count > 0:
                ease_seam(output, joined, frames[first - 1], count)
            for key, frame in times.get(slot, {}).items():
                if first <= frame <= last:
                    times.setdefault(output, {})[key] = len(joined) + frame - first
            joined += frames[first:last + 1]
        body = [text for time, frame in enumerate(joined) for text in ['time %d' % time] + frame]
        (folder / 'anims' / (output + '.smd')).write_text(
            '\n'.join(header + body + ['end']) + '\n', encoding='ascii')
        print('COMPOSED', output, len(joined), 'frames')
    return times, joins


def sound_end(path, name, at):
    """When the sound entry name (weapon_GUN.KEY) started for time at stops playing."""
    gun, _, key = name.partition('_')[2].partition('.')
    wav = path.parents[1] / WAV_PATH.format(gun=gun, key=key)
    with wave.open(str(wav)) as clip:
        return at - SOUND_LEAD + clip.getnframes() / clip.getframerate()


class Entry(NamedTuple):
    """A KeyValues value: a string (with its character span in the text) or a block (a dict of entries)."""
    value: object
    span: tuple = None


KEYVALUES_TOKEN = re.compile(r'//[^\n]*|"([^"]*)"|([{}])')


def read_keyvalues(text):
    """The top-level entries of a KeyValues text as {key: Entry}; // comments are skipped."""
    tokens = [match for match in KEYVALUES_TOKEN.finditer(text) if match[0][0] != '/']

    def read_block(position):
        entries = {}
        while position < len(tokens):
            key, value = tokens[position], tokens[position + 1] if position + 1 < len(tokens) else None
            if key[0] == '}':
                return entries, position + 1
            if key[1] is None or value is None:
                raise RuntimeError('Malformed KeyValues text near character %d' % key.start())
            if value[0] == '{':
                block, position = read_block(position + 2)
                entries[key[1]] = Entry(block)
            else:
                entries[key[1]] = Entry(value[1], value.span(1))
                position += 2
        return entries, position

    return read_block(0)[0]


def read_phases(text):
    """The ReloadPhases block as {sequence: {step: {key: Entry}}}."""
    phases = read_keyvalues(text)['WeaponData'].value['ReloadPhases'].value
    return {sequence: {step: row.value for step, row in steps.value.items()} for sequence, steps in phases.items()}


def check_ready(folder, path, text):
    """Fail when a sound of a sequence plays past the sequence's last frame, where the gun can fire."""
    for sequence, steps in read_phases(text).items():
        ready = (len(read_frames(folder / 'anims' / (sequence + '.smd'))[1]) - 1) / FPS
        for row in steps.values():
            if 'ammo' in row and float(row['ammo'].value) >= ready - 1e-6:
                raise RuntimeError('%s ends at %.3f s, not after an ammo time %s s' % (sequence, ready, row['ammo'].value))
        for row in steps.values():
            for key in filter(re.compile(r'sound\d*').fullmatch, row):
                at, name = row[key].value, row[key + '_name'].value
                end = sound_end(path, name, float(at))
                if ready < end - 1e-6:
                    raise RuntimeError('%s ends at %.3f s, before %s ends at %.3f s' % (sequence, ready, name, end))
                print('READY %s %.3f s >= %s end %.3f s (%s - %.2f + wav)' % (sequence, ready, name, end, at, SOUND_LEAD))


def step_order(step):
    """The order of a reload step, from its name (1_unload -> 1)."""
    return int(step.partition('_')[0])


def check_resume_rows(phases, joins):
    """A row's "resume" names a composite that joins the row's sequence after its step; a resume lists only later steps."""
    for sequence, steps in phases.items():
        for step, row in steps.items():
            if 'resume' not in row:
                continue
            resume = row['resume'].value
            if (sequence, step) not in joins.get(resume, ()):
                raise RuntimeError('%s row %s: %s is no composite with a part %s@%s in composites.txt' % (
                    sequence, step, resume, sequence, step))
            for later in phases.get(resume, {}):
                if step_order(later) <= step_order(step):
                    raise RuntimeError('%s lists step %s: a resume after %s plays only later steps' % (resume, later, step))


WRITTEN = {}  # phases file -> text from the first team project of this run


def fill_phases(folder, times, joins):
    """Set every ammo/sound time in the weapon's ReloadPhases file from the markers; both teams must agree."""
    path = folder.parents[2] / 'scripts' / ('weapon_%s_reload_phases.txt' % folder.name.partition('_')[2])
    if not path.is_file():
        return
    text = path.read_text(encoding='ascii')
    changes = []
    phases = read_phases(text)
    check_resume_rows(phases, joins)
    for sequence, steps in phases.items():
        for step, row in steps.items():
            for key in filter(TIME_KEY.fullmatch, row):
                marker = step if key == 'ammo' else step + '.' + key
                frame = times.get(sequence, {}).get(marker)
                if frame is None:
                    raise RuntimeError('No timeline marker %s:%s for %s' % (sequence, marker, path.name))
                changes.append((row[key].span, '%.3f' % (frame / FPS)))
    for (start, end), seconds in sorted(changes, reverse=True):
        text = text[:start] + seconds + text[end:]
    check_ready(folder, path, text)
    if WRITTEN.setdefault(path, text) != text:
        raise RuntimeError('The team projects give different times for ' + path.name)
    path.write_text(text, encoding='ascii')
    print('PHASES', path.name, '\n' + text)


def read_markers(scene):
    return {marker.name: marker.frame for marker in scene.timeline_markers}


def check_teams_agree(scenes):
    """Fail before any export when the team scenes of a gun carry different markers."""
    first = {}
    for scene in scenes:
        gun = scene.name.partition('_')[2]
        markers = read_markers(scene)
        if gun not in first:
            first[gun] = (scene, markers)
            continue
        other, expected = first[gun]
        for name in sorted(set(markers) | set(expected)):
            if markers.get(name) != expected.get(name):
                raise RuntimeError('Marker %s is at frame %s in scene %s but at frame %s in scene %s: edit both team scenes' % (
                    name, expected.get(name, 'missing'), other.name, markers.get(name, 'missing'), scene.name))


def project_rig(scene):
    """The scene's rig, failing unless it holds the project's own action."""
    if scene.name not in RIGS:
        raise RuntimeError('Scene %s has no row in RIGS in export_viewmodels.py: add its rig and action there' % scene.name)
    rig_name, action_name = RIGS[scene.name]
    rig = scene.objects.get(rig_name)
    if rig is None or rig.type != 'ARMATURE':
        raise RuntimeError('Scene %s has no armature named %s' % (scene.name, rig_name))
    action = rig.animation_data.action if rig.animation_data else None
    if action is None or action.name != action_name:
        raise RuntimeError('Scene %s: rig %s has action %s but needs %s. In Blender, select the rig, open '
                           'Dope Sheet > Action Editor and pick %s, then save; or use File > Revert' % (
                               scene.name, rig_name, action.name if action else 'none', action_name, action_name))
    return rig


def check_images():
    missing = [image.filepath for image in bpy.data.images
               if image.source == 'FILE' and not image.packed_file
               and not Path(bpy.path.abspath(image.filepath)).is_file()]
    if missing:
        raise RuntimeError('Missing preview images: ' + ', '.join(missing))


def open_scenes(path, keep=None):
    """Open the source file; with keep, drop the other scenes so Source Tools exports the kept one."""
    bpy.ops.wm.open_mainfile(filepath=str(path))
    bpy.ops.preferences.addon_enable(module='io_scene_valvesource')
    if keep is None:
        return bpy.data.scenes
    for scene in list(bpy.data.scenes):
        if scene.name != keep:
            bpy.data.scenes.remove(scene)
    return bpy.context.scene


def export_project(folder, scene):
    if scene.render.fps != FPS or scene.render.fps_base != 1:
        raise RuntimeError('Scene %s must play at %d fps' % (scene.name, FPS))
    reference = folder / 'reference.smd'
    reference_bytes = reference.read_bytes()
    armature = project_rig(scene)
    expected = [folder / 'anims' / (slot.name_display + '.smd')
                for slot in armature.animation_data.action.slots]
    previous = {path: path.stat().st_mtime_ns if path.exists() else None
                for path in expected}
    name = scene.name
    result = bpy.ops.export_scene.smd(export_scene=True)
    scene = bpy.data.scenes[name]  # the export replaces the scene's Python object
    if result != {'FINISHED'}:
        raise RuntimeError('Source Tools export failed: ' + str(result))
    if any(not path.is_file() or path.stat().st_mtime_ns == previous[path]
           for path in expected):
        raise RuntimeError('Source Tools did not freshly export every expected SMD')
    if reference.read_bytes() != reference_bytes:
        raise RuntimeError('The preview mesh must not overwrite reference.smd')
    print('EXPORTED', scene.name, len(expected), 'animation SMD files; reference retained')
    fill_phases(folder, *write_composites(folder, read_markers(scene)))


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    projects = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if not projects:
        raise RuntimeError('List the projects to export after --')
    try:
        found = open_scenes(root / SOURCE)
        unknown = [project for project in projects if project not in found or not (root / project).is_dir()]
        if unknown:
            raise RuntimeError('No scene and folder named ' + ', '.join(unknown))
        for project in projects:
            project_rig(found[project])
        check_teams_agree([found[project] for project in projects])
        check_images()
        for project in projects:
            export_project(root / project, open_scenes(root / SOURCE, keep=project))
    except RuntimeError as problem:
        print('EXPORT FAILED:', problem)
        sys.exit(1)
