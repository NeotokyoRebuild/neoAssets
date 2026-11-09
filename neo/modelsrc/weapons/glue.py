"""Glued clips and reload phase times for export_viewmodels.py, which runs this module's hooks when it is present.

An optional composites.txt in a project folder joins exported animations into one more SMD per line:
OUTPUT PART [PART ...] [blend=N], where PART is SLOT, SLOT:FIRST-LAST (inclusive frames; an empty LAST means
the end) or SLOT@STEP-LAST (from the frame after timeline marker SLOT:STEP.join, else SLOT:STEP). FIRST and LAST
may also name a marker STEP.KEY of the slot, meaning its frame (reload:0-2_load.exit). Across a join,
the last N frames (default 3) of the previous part are eased onto the pose the next part continues from.
Timeline markers time the rows of neo/scripts/weapon_GUN_reload_phases.txt (GUN: the folder name after its team
prefix): the step marker SLOT:STEP gives the step's "ammo" time, SLOT:STEP.KEY (KEY sound, sound2, ...) the others.
The export rewrites each time there, shifted into composites.
The NSF project (no scene) compiles its glued clips from the Jinrai SMDs: its .qc includes ../jinrai_GUN/glued.qci.
A sound entry weapon_GUN.KEY plays sound/weapons/GUN/GUN_KEY.wav (a convention; the sound script is not read).
A row's "resume" key names the composite that resumes the reload interrupted after that step; the composite must
join the row's sequence after that step (part SEQUENCE@STEP...), or, in a composite row, the part the step's marker
came from. A resume lists only the steps after STEP: it never replays an earlier step's sound.
A sequence's ammo times come before its last frame, and its sounds finish playing by then: the gun can fire there.
Every export then rebuilds viewmodels_post_export.blend, a preview of the glued clips of every project with a
composites.txt (also those not exported this run, from their SMDs on disk), unless its inputs are unchanged. Each
scene there carries both teams' preview meshes, like viewmodels.blend.
A family variant (a gun whose .qc includes another gun's ../jinrai_BASE/glued.qci, such as the ZR68-S with the ZR68C)
compiles the base's glued clips: its phases file is filled from the base's composites.txt with the base's markers,
overridden by its own (its shipped reload's step markers); the export fails if that moves a join.
"""
from pathlib import Path
from typing import NamedTuple
import hashlib
import math
import re
import wave

import bpy
from mathutils import Euler, Quaternion

import export_viewmodels as export
import rom_limits

RESULT_LINES = ('SEAM', 'READY')  # the panel's Export gun shows these lines too


def after_export(folder, scene):
    """Write the glued clips and the phases file."""
    fill_phases(folder, *write_composites(folder, export.read_markers(scene)))


def after_variant(folder, base, markers, base_markers):
    """Fill a family variant's phases file from its base's glued clips."""
    fill_phases(folder, *variant_times(folder, base, markers, base_markers), base=base)


SOUND_LEAD = 0.02  # neo starts a reload sound piece this long before its time (RELOAD_SOUND_LEAD)
EXACT = 1e-4  # below the SMD print precision: the poses match, nothing is eased
TIME_KEY = re.compile(r'ammo|sound\d*')  # the phases keys the markers set; "sound_name" is not one
WAV_PATH = 'sound/weapons/{gun}/{gun}_{key}.wav'  # for sound entry weapon_GUN.KEY
SEAM_LIMIT_UNITS, SEAM_LIMIT_DEGREES = 0.5, 2.0  # eased over 3 frames: less than the reload moves per frame


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


def marker_frame(markers, slot, value, part):
    """A range end as written: a frame number, empty, or a marker STEP.KEY of the slot (its frame)."""
    if not value or value.isdigit():
        return value
    if slot + ':' + value not in markers:
        raise RuntimeError('No timeline marker %s:%s for %s' % (slot, value, part))
    return str(markers[slot + ':' + value])


def write_composites(folder, markers, write=True, layout=None):
    """Write the composites; return the marker frames per sequence, each composite's SLOT@STEP joins, and the
    exported slot each composite marker came from. With write=False, only return them. layout, a list, gets each
    part's frame range."""
    composites = folder / 'composites.txt'
    times, joins, sources = {}, {}, {}
    for name, frame in markers.items():
        slot, _, key = name.partition(':')
        if key:
            times.setdefault(slot, {})[key] = frame
    if not composites.is_file():
        return times, joins, sources
    for line in composites.read_text(encoding='ascii').splitlines():
        if not line.strip():
            continue
        output, *parts = line.split()
        count = int(parts.pop()[6:]) if parts[-1].startswith('blend=') else 3
        header, joined = None, []
        for part in parts:
            slot, mark, span = re.match(r'(\w+)([:@]?)(.*)', part).groups()
            part_path = folder / 'anims' / (slot + '.smd')
            if not part_path.is_file():
                raise RuntimeError('%s in composites.txt names %s, which is no slot or earlier composite of %s' % (
                    part, slot, folder.name))
            if mark == '@':
                step, _, last = span.partition('-')
                joins.setdefault(output, set()).add((slot, step))
                join = markers.get(slot + ':' + step + '.join', markers.get(slot + ':' + step))
                if join is None:
                    raise RuntimeError('No timeline marker %s:%s for %s' % (slot, step, part))
                span = '%d-%s' % (join + 1, last)
            part_header, frames = export.read_frames(part_path)
            if header is not None and part_header != header:
                raise RuntimeError('Composite parts have different nodes: ' + part)
            header = part_header
            first, last = (marker_frame(markers, slot, value, part) for value in span.partition('-')[::2])
            first, last = int(first or 0), int(last) if last else len(frames) - 1
            if layout is not None:
                layout.append((output, part, first, last))
            if write and joined and first > 0 and count > 0:
                ease_seam(output, joined, frames[first - 1], count)
            for key, frame in times.get(slot, {}).items():
                if first <= frame <= last:
                    times.setdefault(output, {})[key] = len(joined) + frame - first
                    sources.setdefault(output, {})[key] = sources.get(slot, {}).get(key, slot)
            joined += frames[first:last + 1]
        if not write:
            continue
        body = [text for time, frame in enumerate(joined) for text in ['time %d' % time] + frame]
        (folder / 'anims' / (output + '.smd')).write_text(
            '\n'.join(header + body + ['end']) + '\n', encoding='ascii')
        print('COMPOSED', output, len(joined), 'frames')
    return times, joins, sources


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


def check_ready(folders, path, text):
    """Fail when a sound of a sequence plays past the sequence's last frame, where the gun can fire. The sequence's SMD
    is the first found in the folders' anims/."""
    for sequence, steps in read_phases(text).items():
        smd = next(smd for smd in (folder / 'anims' / (sequence + '.smd') for folder in folders) if smd.is_file())
        ready = (len(export.read_frames(smd)[1]) - 1) / export.FPS
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


def check_resume_rows(phases, joins, sources):
    """A row's "resume" names a composite that joins the row's sequence, or the part its step came from, after the
    step; a resume lists only later steps."""
    for sequence, steps in phases.items():
        for step, row in steps.items():
            if 'resume' not in row:
                continue
            resume = row['resume'].value
            source = sources.get(sequence, {}).get(step, sequence)
            if not {(sequence, step), (source, step)} & joins.get(resume, set()):
                raise RuntimeError('%s row %s: %s is no composite with a part %s@%s in composites.txt' % (
                    sequence, step, resume, source, step))
            for later in phases.get(resume, {}):
                if step_order(later) <= step_order(step):
                    raise RuntimeError('%s lists step %s: a resume after %s plays only later steps' % (resume, later, step))


def fill_phases(folder, times, joins, sources, base=None):
    """Set every ammo/sound time in the weapon's ReloadPhases file from the markers. A family variant's glued clips
    are in its base's anims/."""
    path = folder.parents[2] / 'scripts' / ('weapon_%s_reload_phases.txt' % folder.name.partition('_')[2])
    if not path.is_file():
        return
    text = path.read_text(encoding='ascii')
    changes = []
    phases = read_phases(text)
    check_resume_rows(phases, joins, sources)
    for sequence, steps in phases.items():
        for step, row in steps.items():
            for key in filter(TIME_KEY.fullmatch, row):
                marker = step if key == 'ammo' else step + '.' + key
                frame = times.get(sequence, {}).get(marker)
                if frame is None:
                    raise RuntimeError('No timeline marker %s:%s for %s' % (sequence, marker, path.name))
                changes.append((row[key].span, '%.3f' % (frame / export.FPS)))
    for (start, end), seconds in sorted(changes, reverse=True):
        text = text[:start] + seconds + text[end:]
    check_ready([folder] + ([base] if base else []), path, text)
    path.write_text(text, encoding='ascii')
    print('PHASES', path.name, '\n' + text)


def variant_times(folder, base, markers, base_markers):
    """The phases inputs of a variant: the base's composites with the base's markers, overridden by the variant's own
    markers. Fail when that moves a join or range, since the glued clips were built at the base's frames."""
    merged = dict(base_markers, **markers)
    base_layout, layout = [], []
    write_composites(base, base_markers, write=False, layout=base_layout)
    result = write_composites(base, merged, write=False, layout=layout)
    for expected, got in zip(base_layout, layout):
        if expected != got:
            raise RuntimeError('%s: marker of %s puts %s at frames %d-%d, but the shared clip %s of %s uses %d-%d. Move '
                               'the marker to match the family base' % (
                                   folder.name, got[1], got[0], got[2], got[3], got[0], base.name, expected[2], expected[3]))
    return result


POST_EXPORT = 'viewmodels_post_export.blend'
POST_EXPORT_INPUTS = 'post_export_inputs'  # text block: digest of the inputs, so an unchanged file is not rewritten
POST_EXPORT_NOTE = """Export output: never edit this file. export_viewmodels.py rebuilds it on every export.
Commit it with the exported SMDs whenever a glued clip changes.

It shows the glued clips (composites.txt) exactly as the game plays them, easing included: one scene per
project with a composites.txt, its rig, preview mesh and in-game camera, and one action PROJECT_glued whose
slots are the glued clips, imported from PROJECT/anims/*.smd. The timeline markers are the step and sound
markers shifted into each clip (CLIP:STEP, CLIP:STEP.sound), the times the phases file gets.
Pick a clip: Scene selector (top right), then Dope Sheet > Action Editor > Slot dropdown. Numpad 0 looks
through the camera. Each scene holds both teams' arms: show the other team with the eye of its collection
(Outliner: jinrai_GUN_preview, nsf_GUN_preview) or Team in the Viewmodel panel. Edit the animations in
viewmodels.blend, never here.
"""


def post_export_inputs(root, projects):
    """A digest of everything the post-export file is built from."""
    digest = hashlib.sha1((root / export.SOURCE).read_bytes() + POST_EXPORT_NOTE.encode())
    for name in projects:
        composites = (root / name / 'composites.txt').read_text(encoding='ascii')
        digest.update(composites.encode())
        for line in filter(str.strip, composites.splitlines()):
            digest.update((root / name / 'anims' / (line.split()[0] + '.smd')).read_bytes())
    return digest.hexdigest()


def saved_inputs(path):
    """The input digest stored in an earlier post-export file, if any."""
    if not path.is_file():
        return None
    with bpy.data.libraries.load(str(path)) as (source, target):
        target.texts = [name for name in source.texts if name == POST_EXPORT_INPUTS]
    if not target.texts:
        return None
    text = target.texts[0]
    digest = text.as_string().strip()
    bpy.data.texts.remove(text)
    for library in list(bpy.data.libraries):  # else Blender refuses to save over the file
        if Path(bpy.path.abspath(library.filepath)) == path:
            bpy.data.libraries.remove(library)
    return digest


def build_post_export(root):
    """Rebuild viewmodels_post_export.blend for every project with a composites.txt (all of them, whichever were
    exported), from viewmodels.blend and the glued SMDs now in each project's anims/. viewmodels.blend is not saved."""
    export.open_scenes(root / export.SOURCE)
    projects = [scene.name for scene in bpy.data.scenes if (root / scene.name / 'composites.txt').is_file()]
    if not projects:
        # Blender cannot remove the last scene, and with no glued clips there is nothing to preview
        print('POST-EXPORT none')
        return
    inputs = post_export_inputs(root, projects)
    if saved_inputs(root / POST_EXPORT) == inputs:
        print('POST-EXPORT unchanged', POST_EXPORT)  # Blender would save the same content with other bytes
        return
    for scene in list(bpy.data.scenes):
        if scene.name not in projects:
            bpy.data.scenes.remove(scene)
    for text in list(bpy.data.texts):
        bpy.data.texts.remove(text)
    for name in projects:
        scene, folder = bpy.data.scenes[name], root / name
        rig = export.project_rig(scene)
        for pose_bone in rig.pose.bones:  # the preview plays the SMDs as they are
            for constraint in [c for c in pose_bone.constraints if c.name.startswith(rom_limits.PREFIX)]:
                pose_bone.constraints.remove(constraint)
        times = write_composites(folder, export.read_markers(scene), write=False)[0]
        outputs = [line.split()[0] for line in (folder / 'composites.txt').read_text(encoding='ascii').splitlines()
                   if line.strip()]
        action = bpy.data.actions.new(name + '_glued')
        rig.animation_data.action = action
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0], active_object=rig, object=rig,
                                       selected_objects=[rig]):
            scene.view_layers[0].objects.active = rig
            for output in outputs:
                if bpy.ops.import_scene.smd(filepath=str(folder / 'anims' / (output + '.smd'))) != {'FINISHED'}:
                    raise RuntimeError('Source Tools could not import %s/anims/%s.smd' % (name, output))
        rig.animation_data.action = action
        rig.animation_data.action_slot = action.slots[0]
        scene.timeline_markers.clear()
        for output in outputs:
            for key, frame in sorted(times.get(output, {}).items(), key=lambda item: (item[1], item[0])):
                step, _, time_key = key.partition('.')
                if not time_key or TIME_KEY.fullmatch(time_key):  # the phases times, not join or range markers
                    scene.timeline_markers.new(output + ':' + key, frame=frame)
        print('POST-EXPORT', name, len(action.slots), 'glued clips,', len(scene.timeline_markers), 'markers')
    glued = {name + '_glued' for name in projects}
    for action in list(bpy.data.actions):
        if action.name not in glued:
            bpy.data.actions.remove(action)
    bpy.data.texts.new('README_POST_EXPORT').from_string(POST_EXPORT_NOTE)
    bpy.data.texts.new(POST_EXPORT_INPUTS).from_string(inputs)
    bpy.data.orphans_purge(do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(root / POST_EXPORT), compress=True)
    backup = root / (POST_EXPORT + '1')
    if backup.exists():
        backup.unlink()
    print('POST-EXPORT written', POST_EXPORT)

