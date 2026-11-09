"""Export saved viewmodel Blender sources with Blender Source Tools.

Run: blender --background --python-exit-code 1 --python export_viewmodels.py -- PROJECT [PROJECT ...] [--edit-shipped]
Each PROJECT (such as jinrai_tachi) is a scene of viewmodels.blend beside this script, exported into the folder
of the same name, which holds the project's .qc, reference.smd and anims/.
Requires Blender 5.2.3 or newer and Blender Source Tools 3.4.3 or newer.
This helper reads viewmodels.blend, and writes SMD exports.
glue.py beside this script, when present, adds glued clips, reload phase times and team sharing
(its docstring has the rules).
Before any SMD is written, the range-of-motion check of rom_limits.py runs over every slot of the listed projects
and fails the export when a ROM:* constraint clamps a keyed pose; the export itself runs with ROM:* muted, so the
SMDs are the keyed poses (an active Local-Space constraint changes them by float round-off even when nothing clamps).
The shipped slots (the SMDs the project's .qc compiles from its own anims/) stay the original clips: after Source
Tools writes them, a rewrite that differs only by float round-off gets its old bytes back (KEPT), and a real change
puts every shipped SMD back and fails the export, naming the slot, frame and bone. To change a shipped clip on purpose,
edit both team scenes the same way and add --edit-shipped after the projects; the export then prints SHIPPED CHANGED.
After the export, each authored slot (a slot the .qc does not compile from the project's own anims/) is compared with
the shipped non-fire, non-melee clips of its project: a PACE WARN names the slot, bone and frames where the slot moves
a bone more than 10 % faster than any of them: hands and the gun by world speed (the gun also by world turn), fingers
by their local turn, parts on the gun by their motion on the gun. Bones that move no vertex of reference.smd (Dummy01,
Muzzle, ...) are skipped. A warning does not fail the export.
viewmodels.blend is never saved.
"""
from pathlib import Path
import math
import re
import sys

import bpy
from mathutils import Euler

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rom_limits
if (Path(__file__).resolve().parent / 'glue.py').is_file():
    import glue
else:
    glue = None

SOURCE = 'viewmodels.blend'
FPS = 30


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


def shipped_slots(folder):
    """The slots the project's qc compiles from its own anims/."""
    return set(SHIPPED_SMD.findall(qc_text(folder)))


def read_markers(scene):
    return {marker.name: marker.frame for marker in scene.timeline_markers}


def check_teams_agree(root, scenes):
    """Fail before any export when the team scenes of a gun carry different markers."""
    first, shipped = {}, glue.compared_slots(root, scenes) if glue else {}
    for scene in scenes:
        gun = scene.name.partition('_')[2]
        markers = read_markers(scene)
        if gun in shipped:
            markers = {name: frame for name, frame in markers.items() if name.partition(':')[0] in shipped[gun]}
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
    rig_name, action_name = scene.name + '_rig', scene.name + '_animations'  # named after the project
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
    unless the export was run with --edit-shipped."""
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
        return
    if allow:
        for path, _, (frame, bone, difference) in changed:
            print('SHIPPED CHANGED %s/anims/%s frame %s bone %s: %s' % (
                folder.name, path.name, frame, bone, difference))
        return
    for path, old, _ in changed:
        path.write_bytes(old)
    raise RuntimeError('Shipped slots of %s changed: %s. Shipped slots stay the original clip; the SMDs were put '
                       'back. Undo the edit in Blender (File > Revert, or delete the keys), or, if the change is '
                       'meant, edit both team scenes the same way and export again with %s' % (
                           folder.name, '; '.join('%s frame %s bone %s by %s' % ((p.stem,) + c) for p, _, c in changed),
                           EDIT_SHIPPED))


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
    if glue:
        glue.before_export(folder, scene, armature)
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
    guard_shipped(folder, before, allow_shipped)
    print('EXPORTED', scene.name, len(expected), 'animation SMD files; reference retained')
    if glue and glue.after_export(folder, scene):
        return
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
        unknown = [project for project in projects if project not in found or not (root / project).is_dir()]
        if unknown:
            raise RuntimeError('No scene and folder named ' + ', '.join(unknown))
        for project in projects:
            project_rig(found[project])
        check_teams_agree(root, [found[project] for project in projects])
        check_images()
        check_limits([found[project] for project in projects])
        for project in projects:
            export_project(root / project, open_scenes(root / SOURCE, keep=project), allow_shipped)
        if glue:
            glue.build_post_export(root)
    except RuntimeError as problem:
        print('EXPORT FAILED:', problem)
        sys.exit(1)
