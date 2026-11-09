"""Export saved viewmodel Blender sources with Blender Source Tools.

Run: blender --background --python-exit-code 1 --python export_viewmodels.py -- PROJECT [PROJECT ...] [--edit-shipped]
Each PROJECT (such as jinrai_zr68c) is a scene of viewmodels.blend beside this script, exported into the folder
of the same name, which holds the project's .qc, reference.smd and anims/. A gun has one scene, jinrai_GUN: one rig
and one action, with both teams' preview meshes (the Team toggle shows one). The NSF project nsf_GUN has no scene: it
compiles from its shipped SMDs on disk and from the Jinrai glued clips (../jinrai_GUN/glued.qci).
Requires Blender 5.2.3 or newer and Blender Source Tools 3.4.3 or newer.
This helper reads viewmodels.blend, and writes SMD exports.
An optional composites.txt in a project folder joins exported animations into one more SMD per line:
OUTPUT PART [PART ...] [blend=N], where PART is SLOT, SLOT:FIRST-LAST (inclusive frames; an empty LAST means
the end) or SLOT@STEP-LAST (from the frame after timeline marker SLOT:STEP.join, else SLOT:STEP). FIRST and LAST
may also name a marker STEP.KEY of the slot, meaning its frame (reload:0-2_load.exit). Across a join,
the last N frames (default 3) of the previous part are eased onto the pose the next part continues from.
Timeline markers time the rows of neo/scripts/weapon_GUN_reload_phases.txt (GUN: the folder name after its team
prefix): the step marker SLOT:STEP gives the step's "ammo" time, SLOT:STEP.KEY (KEY sound, sound2, ...) the others.
The export rewrites each time there, shifted into composites.
A sound entry weapon_GUN.KEY plays sound/weapons/GUN/GUN_KEY.wav (a convention; the sound script is not read).
A row's "resume" key names the composite that resumes the reload interrupted after that step; the composite must
join the row's sequence after that step (part SEQUENCE@STEP...), or, in a composite row, the part the step's marker
came from. A resume lists only the steps after STEP: it never replays an earlier step's sound.
A sequence's ammo times come before its last frame, and its sounds finish playing by then: the gun can fire there.
Every export then rebuilds viewmodels_post_export.blend, a preview of the glued clips of every project with a
composites.txt (also those not exported this run, from their SMDs on disk), unless its inputs are unchanged. Each
scene there carries both teams' preview meshes, like viewmodels.blend.
Before any SMD is written, the range-of-motion check of rom_limits.py runs over every slot of the listed projects
and fails the export when a ROM:* constraint clamps a keyed pose; the export itself runs with ROM:* muted, so the
SMDs are the keyed poses (an active Local-Space constraint changes them by float round-off even when nothing clamps).
The shipped slots (the SMDs the project's .qc compiles from its own anims/) stay the original clips: after Source
Tools writes them, a rewrite that differs only by float round-off gets its old bytes back (KEPT), and a real change
puts every shipped SMD back and fails the export, naming the slot, frame and bone. To change a shipped clip on purpose,
add --edit-shipped after the projects: the export then prints SHIPPED CHANGED and copies the changed SMD into the NSF
project too (nsf_GUN/anims/, when its .qc compiles that slot), so both teams play the edited clip.
After the export, each authored slot (a slot the .qc does not compile from the project's own anims/) is compared with
the shipped non-fire, non-melee clips of its project: a PACE WARN names the slot, bone and frames where the slot moves
a bone more than 10 % faster than any of them: hands and the gun by world speed (the gun also by world turn), fingers
by their local turn, parts on the gun by their motion on the gun. Bones that move no vertex of reference.smd (Dummy01,
Muzzle, ...) are skipped. A warning does not fail the export.
viewmodels.blend is never saved.
"""
from pathlib import Path
from typing import NamedTuple
import hashlib
import math
import re
import sys
import wave

import bpy
from mathutils import Euler, Quaternion

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rom_limits

SOURCE = 'viewmodels.blend'
FPS = 30
SOUND_LEAD = 0.02  # neo starts a reload sound piece this long before its time (RELOAD_SOUND_LEAD)
EXACT = 1e-4  # below the SMD print precision: the poses match, nothing is eased
TIME_KEY = re.compile(r'ammo|sound\d*')  # the phases keys the markers set; "sound_name" is not one
WAV_PATH = 'sound/weapons/{gun}/{gun}_{key}.wav'  # for sound entry weapon_GUN.KEY
SEAM_LIMIT_UNITS, SEAM_LIMIT_DEGREES = 0.5, 2.0  # eased over 3 frames: less than the reload moves per frame
# Each project's rig and the one action it may export. A new gun needs a row here (its Jinrai project only).
RIGS = {
    'jinrai_tachi': ('jinrai_tachi_rig', 'jinrai_tachi_animations'),
    'jinrai_zr68c': ('jinrai_zr68c_rig', 'jinrai_zr68c_animations'),
    'jinrai_mosok41': ('jinrai_mosok41_rig', 'jinrai_mosok41_animations'),
    'jinrai_mosok41s': ('jinrai_mosok41s_rig', 'jinrai_mosok41s_animations'),
    'jinrai_mosok41l': ('jinrai_mosok41l_rig', 'jinrai_mosok41l_animations'),
    'jinrai_mpn': ('jinrai_mpn_rig', 'jinrai_mpn_animations'),
    'jinrai_mpn_s': ('jinrai_mpn_s_rig', 'jinrai_mpn_s_animations'),
    'jinrai_mx': ('jinrai_mx_rig', 'jinrai_mx_animations'),
    'jinrai_mxs': ('jinrai_mxs_rig', 'jinrai_mxs_animations'),
    'jinrai_zr68s': ('jinrai_zr68s_rig', 'jinrai_zr68s_animations'),
    'jinrai_zr68l': ('jinrai_zr68l_rig', 'jinrai_zr68l_animations'),
    'jinrai_jitte': ('jinrai_jitte_rig', 'jinrai_jitte_animations'),
    'jinrai_jittes': ('jinrai_jittes_rig', 'jinrai_jittes_animations'),
    'jinrai_srm': ('jinrai_srm_rig', 'jinrai_srm_animations'),
    'jinrai_srm_s': ('jinrai_srm_s_rig', 'jinrai_srm_s_animations'),
    'jinrai_srs': ('jinrai_srs_rig', 'jinrai_srs_animations'),
    'jinrai_aa13': ('jinrai_aa13_rig', 'jinrai_aa13_animations'),
    'jinrai_pz': ('jinrai_pz_rig', 'jinrai_pz_animations'),
    'jinrai_milso': ('jinrai_milso_rig', 'jinrai_milso_animations'),
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


def marker_frame(markers, slot, value, part):
    """A range end as written: a frame number, empty, or a marker STEP.KEY of the slot (its frame)."""
    if not value or value.isdigit():
        return value
    if slot + ':' + value not in markers:
        raise RuntimeError('No timeline marker %s:%s for %s' % (slot, value, part))
    return str(markers[slot + ':' + value])


def write_composites(folder, markers, write=True):
    """Write the composites; return the marker frames per sequence, each composite's SLOT@STEP joins, and the
    exported slot each composite marker came from. With write=False, only return them."""
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
            part_header, frames = read_frames(part_path)
            if header is not None and part_header != header:
                raise RuntimeError('Composite parts have different nodes: ' + part)
            header = part_header
            first, last = (marker_frame(markers, slot, value, part) for value in span.partition('-')[::2])
            first, last = int(first or 0), int(last) if last else len(frames) - 1
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


def fill_phases(folder, times, joins, sources):
    """Set every ammo/sound time in the weapon's ReloadPhases file from the markers."""
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
                changes.append((row[key].span, '%.3f' % (frame / FPS)))
    for (start, end), seconds in sorted(changes, reverse=True):
        text = text[:start] + seconds + text[end:]
    check_ready(folder, path, text)
    path.write_text(text, encoding='ascii')
    print('PHASES', path.name, '\n' + text)


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
    digest = hashlib.sha1((root / SOURCE).read_bytes() + POST_EXPORT_NOTE.encode())
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
    open_scenes(root / SOURCE)
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
        rig = project_rig(scene)
        for pose_bone in rig.pose.bones:  # the preview plays the SMDs as they are
            for constraint in [c for c in pose_bone.constraints if c.name.startswith(rom_limits.PREFIX)]:
                pose_bone.constraints.remove(constraint)
        times = write_composites(folder, read_markers(scene), write=False)[0]
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


SHIPPED_SMD = re.compile(r'"anims/([^"/]+)\.smd"')  # a $sequence of the project's own SMDs, not ../jinrai_GUN/anims/
INCLUDE = re.compile(r'^\$include\s+"([^"]+)"', re.M)


def qc_text(folder):
    """The project's .qc with its $include files, as one text."""
    texts, pending = [], [next(folder.glob('*.qc'))]
    while pending:
        path = pending.pop(0)
        text = path.read_text(encoding='ascii')
        texts.append(text)
        pending += [(folder / include).resolve() for include in INCLUDE.findall(text)]
    return '\n'.join(texts)


def nsf_project(folder):
    """The NSF project folder of a Jinrai project, or None. It has no scene: it compiles from its own shipped SMDs."""
    partner = folder.parent / ('nsf_' + folder.name.partition('_')[2])
    return partner if folder.name.startswith('jinrai_') and partner.is_dir() else None


def shipped_slots(folder):
    """The slots the project's qc compiles from its own anims/."""
    return set(SHIPPED_SMD.findall(qc_text(folder)))


def read_markers(scene):
    return {marker.name: marker.frame for marker in scene.timeline_markers}


def project_rig(scene):
    """The scene's rig, failing unless it holds the project's own action."""
    if scene.name.startswith('nsf_'):
        raise RuntimeError('Scene %s: NSF projects have no scene since the team merge; export jinrai_%s' % (
            scene.name, scene.name[4:]))
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


def check_limits(scenes):
    """Fail when a range-of-motion limit clamps a keyed pose: the SMD would not show what the viewport shows."""
    clamps = [rom_limits.clamp_text(scene.name, clamp) for scene in scenes for clamp in rom_limits.find_clamps(scene)]
    if clamps:
        raise RuntimeError('Range-of-motion limits clamp %d keyed poses. Fix the keys, or if the pose is meant, widen '
                           'the limit (an entry in rom_widen.json, then rom_limits.py spec and apply):\n  %s' % (
                               len(clamps), '\n  '.join(clamps)))
    print('ROM CHECK', len(scenes), 'projects, no clamped pose')


PACE_MARGIN = 1.10  # an authored slot may move a bone up to 10 % faster than any shipped non-fire clip does
PACE_FLOOR = 0.3  # u/frame or deg/frame: slower peaks are never flagged
PACE_TURN_FLOOR = 2.0  # deg/frame: a gun or gun part turning slower than this is never flagged


def turn_degrees(matrix, earlier):
    """The rotation between two bone matrices, in degrees (0 to 180: a quaternion and its negation are one turn)."""
    angle = math.degrees(matrix.to_quaternion().rotation_difference(earlier.to_quaternion()).angle)
    return min(angle, 360 - angle)


def clip_speeds(path):
    """({bone: {measure: (peak per frame, frame)}}, {bone: parent bone}) of one SMD. Measures: 'move' (world
    position, u/frame), 'shift' (local position, u/frame), 'turn' (local rotation, deg/frame) and 'spin' (world
    rotation, deg/frame)."""
    from mathutils import Matrix
    lines = path.read_text(encoding='ascii').splitlines()
    nodes = {}
    for line in lines[lines.index('nodes') + 1:lines.index('end')]:
        index, name, parent = re.match(r'(\d+) "([^"]*)" (-?\d+)', line).groups()
        nodes[index] = (name, parent)
    peaks, previous = {}, None
    for number, frame in enumerate(read_frames(path)[1]):
        world, local = {}, {}
        for line in frame:
            index, *values = line.split()
            values = list(map(float, values))
            local[index] = Matrix.Translation(values[:3]) @ Euler(values[3:]).to_matrix().to_4x4()
        for index in nodes:  # SMD lists parents before children
            parent = nodes[index][1]
            world[index] = world[parent] @ local[index] if parent in world else local[index]
        if previous:
            for index, (name, _) in nodes.items():
                speeds = {
                    'move': (world[index].to_translation() - previous[0][index].to_translation()).length,
                    'shift': (local[index].to_translation() - previous[1][index].to_translation()).length,
                    'turn': turn_degrees(local[index], previous[1][index]),
                    'spin': turn_degrees(world[index], previous[0][index]),
                }
                bone = peaks.setdefault(name, {})
                for measure, speed in speeds.items():
                    if speed > bone.get(measure, (0.0, 0))[0]:
                        bone[measure] = speed, number
        previous = world, local
    return peaks, {name: nodes[parent][0] if parent in nodes else None for name, parent in nodes.values()}


def skin_bones(folder):
    """The bones that move vertices of the project's reference.smd. The others (Dummy01, Muzzle, Eject, ...) are
    never seen: the pace check skips them."""
    lines = (folder / 'reference.smd').read_text(encoding='ascii').splitlines()
    names = dict(re.match(r'\s*(\d+) "([^"]*)"', line).groups()
                 for line in lines[lines.index('nodes') + 1:lines.index('end')])
    used = set()
    for line in lines[lines.index('triangles') + 1:]:
        values = line.split()
        if len(values) == 9:  # no links: the vertex follows its parent bone
            used.add(values[0])
        elif len(values) > 9:
            used.update(values[10 + 2 * link] for link in range(int(values[9])) if float(values[11 + 2 * link]) > 0)
    return {names[index] for index in used}


def pace_measures(bone, parent, seen):
    """(role, [(measure, unit, floor)]) judged for a bone of the set seen (skin_bones). The hands and forearms go by
    world speed and the fingers by their local turn. The gun goes by world speed and world turn. A part on the gun (a
    bolt handle, a parked magazine) goes by its motion on the gun: the gun carrying it is judged itself."""
    if bone not in seen:
        return 'unseen', []
    if bone.startswith(rom_limits.ARM_PREFIX):
        if 'hand' in bone or 'forearm' in bone:
            return 'arm', [('move', 'u/f', PACE_FLOOR)]
        return 'finger', [('turn', 'deg/f local', PACE_FLOOR)]
    if parent not in seen or parent.startswith(rom_limits.ARM_PREFIX):  # the gun, held by the hand or the root
        return 'gun', [('move', 'u/f', PACE_FLOOR), ('spin', 'deg/f world', PACE_TURN_FLOOR)]
    return 'gun part', [('shift', 'u/f on the gun', PACE_FLOOR), ('turn', 'deg/f on the gun', PACE_TURN_FLOOR)]


def check_pace(folder, authored):
    """Warn when an authored slot moves a bone faster than every shipped non-fire, non-melee clip of the project.
    A warning does not fail the export: compare the motion with the shipped clip it imitates."""
    anims = folder / 'anims'
    envelope = {}
    for slot in sorted(shipped_slots(folder)):
        if slot.startswith(('fire', 'melee')) or not (anims / (slot + '.smd')).is_file():
            continue  # recoil and melee are not hand-paced motion
        for bone, peaks in clip_speeds(anims / (slot + '.smd'))[0].items():
            limit = envelope.setdefault(bone, {})
            for measure, (speed, frame) in peaks.items():
                if speed > limit.get(measure, (0.0, ''))[0]:
                    limit[measure] = speed, slot
    warned, seen = 0, skin_bones(folder)
    for slot in authored:
        peaks_of, parents = clip_speeds(anims / (slot + '.smd'))
        for bone, peaks in peaks_of.items():
            role, measures = pace_measures(bone, parents[bone], seen)
            for measure, unit, floor in measures:
                peak, frame = peaks.get(measure, (0.0, 0))
                limit, source = envelope.get(bone, {}).get(measure, (0.0, 'none'))
                if peak <= floor or peak <= PACE_MARGIN * max(limit, floor):
                    continue
                warned += 1
                print('PACE WARN %s slot %s %s "%s" f%d-%d: %.2f %s, shipped peak %.2f in %s (+%d %%): spread the '
                      'move over more frames if it reads too fast' % (
                          folder.name, slot, role, bone, frame - 1, frame, peak, unit, limit, source,
                          round(100 * (peak / max(limit, floor) - 1))))
    print('PACE', folder.name, len(authored), 'authored slots,', warned, 'warnings')


SHIPPED_TOLERANCE = 2e-6  # Blender's float round-off in the printed SMD digits (the Tachi drift is 1e-6)
EDIT_SHIPPED = '--edit-shipped'


def smd_change(old, new):
    """None when two SMD texts hold the same poses within SHIPPED_TOLERANCE, else (frame, bone, difference)."""
    old_lines, new_lines = old.splitlines(), new.splitlines()
    if len(old_lines) != len(new_lines):
        return ('-', '-', 'frame count %d -> %d' % (old_lines.count('end'), new_lines.count('end')))
    frame, names = None, dict(re.findall(r'^(\d+) "([^"]*)"', old, re.M))
    for a, b in zip(old_lines, new_lines):
        if a == b:
            frame = a[5:] if a.startswith('time ') else frame
            continue
        x, y = a.split(), b.split()
        try:
            worst = max(abs(float(i) - float(j)) for i, j in zip(x[1:], y[1:]))
        except ValueError:
            return (frame, '-', 'text %r -> %r' % (a, b))
        if len(x) != len(y) or x[0] != y[0] or worst > SHIPPED_TOLERANCE:
            return (frame, '"%s"' % names.get(x[0], x[0]), '%.4f' % worst)
    return None


def guard_shipped(folder, before, allow):
    """Keep the shipped SMDs original: restore round-off-only rewrites byte for byte, and fail on a real change
    unless the export was run with --edit-shipped. Return the changed SMDs (allowed changes only)."""
    changed = []
    for path, old in before.items():
        new = path.read_bytes()
        if new == old:
            continue
        change = smd_change(old.decode('ascii'), new.decode('ascii'))
        if change is None:
            path.write_bytes(old)
            print('KEPT %s/anims/%s (round-off only)' % (folder.name, path.name))
            continue
        changed.append((path, old, change))
    if not changed:
        return []
    if allow:
        for path, _, (frame, bone, difference) in changed:
            print('SHIPPED CHANGED %s/anims/%s frame %s bone %s: %s' % (
                folder.name, path.name, frame, bone, difference))
        return [path for path, _, _ in changed]
    for path, old, _ in changed:
        path.write_bytes(old)
    raise RuntimeError('Shipped slots of %s changed: %s. Shipped slots stay the original clip; the SMDs were put '
                       'back. Undo the edit in Blender (File > Revert, or delete the keys), or, if the change is '
                       'meant, export again with %s (both teams then get the edited clip)' % (
                           folder.name, '; '.join('%s frame %s bone %s by %s' % ((p.stem,) + c) for p, _, c in changed),
                           EDIT_SHIPPED))


def copy_shipped(folder, changed):
    """Copy the shipped SMDs an --edit-shipped export changed into the NSF project, where its .qc compiles them."""
    partner = nsf_project(folder)
    if partner is None:
        return
    compiled = shipped_slots(partner)
    for path in changed:
        if path.stem in compiled:
            (partner / 'anims' / path.name).write_bytes(path.read_bytes())
            print('SHIPPED CHANGED %s/anims/%s (copied from %s)' % (partner.name, path.name, folder.name))


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


def export_project(folder, scene, allow_shipped=False):
    if scene.render.fps != FPS or scene.render.fps_base != 1:
        raise RuntimeError('Scene %s must play at %d fps' % (scene.name, FPS))
    reference = folder / 'reference.smd'
    reference_bytes = reference.read_bytes()
    armature = project_rig(scene)
    rom_limits.set_mute(scene, True)  # this copy of the file is never saved
    expected = [folder / 'anims' / (slot.name_display + '.smd')
                for slot in armature.animation_data.action.slots]
    previous = {path: path.stat().st_mtime_ns if path.exists() else None
                for path in expected}
    before = {path: path.read_bytes() for path in (folder / 'anims' / (slot + '.smd') for slot in shipped_slots(folder))
              if path.is_file()}
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
    changed = guard_shipped(folder, before, allow_shipped)
    print('EXPORTED', scene.name, len(expected), 'animation SMD files; reference retained')
    copy_shipped(folder, changed)
    fill_phases(folder, *write_composites(folder, read_markers(scene)))
    shipped = shipped_slots(folder)
    check_pace(folder, [path.stem for path in expected if path.stem not in shipped])


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    projects = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    allow_shipped = EDIT_SHIPPED in projects
    projects = [project for project in projects if project != EDIT_SHIPPED]
    if not projects:
        raise RuntimeError('List the projects to export after --')
    try:
        found = open_scenes(root / SOURCE)
        merged = [project for project in projects if project.startswith('nsf_')]
        if merged:
            raise RuntimeError('%s: an NSF project has no scene; it compiles from its shipped SMDs and the Jinrai glued '
                               'clips. Export %s' % (', '.join(merged), ', '.join('jinrai_' + p[4:] for p in merged)))
        unknown = [project for project in projects if project not in found or not (root / project).is_dir()]
        if unknown:
            raise RuntimeError('No scene and folder named ' + ', '.join(unknown))
        for project in projects:
            project_rig(found[project])
        check_images()
        check_limits([found[project] for project in projects])
        for project in projects:
            export_project(root / project, open_scenes(root / SOURCE, keep=project), allow_shipped)
        build_post_export(root)
    except RuntimeError as problem:
        print('EXPORT FAILED:', problem)
        sys.exit(1)
