"""Range-of-motion limits on the viewmodel rigs: write rom_spec.json, put its limits on the rigs, check them.

Run from this folder (Blender 5.2.3 or newer, Blender Source Tools 3.4.3 or newer):
  blender -b viewmodels.blend --python-exit-code 1 --python rom_limits.py -- COMMAND [PROJECT ...]
COMMAND:
  spec        write rom_spec.json from the keyed poses of the shipped slots (the slots the project's .qc compiles
              from its own anims/). Changes nothing in viewmodels.blend. Runtime ~7 s for every project.
  apply       put the limits of rom_spec.json on the rigs and save viewmodels.blend. Runtime ~4 s.
  check       change nothing; list every (slot, bone) whose constrained pose differs from its keys (a clamp);
              exit code 3 if any. export_viewmodels.py runs this check before it writes any SMD. ~12 s for all.
  mute-on, mute-off   mute or unmute every ROM:* constraint and save viewmodels.blend.
Without PROJECT, every project scene. check also takes --plant PROJECT/BONE:SLOT:FRAME:AXIS:DEGREES, which keys a
test rotation in memory first (to see the check fail).

Each limited bone gets ROM:loc (Limit Location) and ROM:rot (Limit Rotation), Local Space, Affect Transform on, and
transform locks on the axes it never moves. The limit is the bone's range in the shipped slots of its gun (both
teams, where the two rigs have the same rest pose) plus a margin. Gun bones take their range without the melee slot,
which swings them freely; their ROM:* influence is keyed to 0 in that slot. Bones that move freely (roots,
forearms, magazines) get no limit. rom_widen.json lists the authored poses a limit is widened to cover, with the
reason (one entry per line: gun, bone, slots, why).
apply deletes and re-adds every ROM:* constraint, so a second run changes nothing.
"""
from pathlib import Path
import json
import math
import sys

import bpy
from mathutils import Euler

sys.dont_write_bytecode = True  # importing export_viewmodels must not leave __pycache__ in the tree

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / 'rom_spec.json'
PREFIX = 'ROM:'
COLLECTION = 'ROM limited'
MARGIN_UNITS, MARGIN_DEGREES = 0.05, 0.5  # above the keys' own noise, below a visible pose change
STILL_UNITS, STILL_DEGREES = 0.02, 0.2  # a bone moving less than this on an axis is locked there
LINE = 0.05  # a motion whose second spread is below this share of the first runs along one axis
REST_TOLERANCE = 1e-3  # two team rigs share a limit only when their rest poses agree this closely
CLAMP_UNITS, CLAMP_DEGREES = 1e-4, 0.01  # above the float round-off of an active constraint (4e-5 u, 1.1e-4 deg)
ARM_PREFIX = 'bone '
MELEE = 'melee'
WIDEN_FILE = ROOT / 'rom_widen.json'  # authored poses a limit is widened to cover: one entry per line


def read_widen():
    """{(gun, bone): (slots, reason)} from rom_widen.json: the authored poses a limit is widened to cover. The pose is
    meant; the limit follows it."""
    widen = {}
    if not WIDEN_FILE.is_file():
        return widen
    for entry in json.loads(WIDEN_FILE.read_text(encoding='ascii')):
        if set(entry) != {'gun', 'bone', 'slots', 'why'} or not entry['slots'] or not entry['why'].strip():
            raise RuntimeError('%s: each entry needs gun, bone, slots and a reason (why): %s' % (
                WIDEN_FILE.name, entry))
        key = (entry['gun'], entry['bone'])
        if key in widen:
            raise RuntimeError('%s lists %s / %s twice: merge the entries' % ((WIDEN_FILE.name,) + key))
        widen[key] = (tuple(entry['slots']), entry['why'])
    return widen


def write_widen(widen):
    """Write rom_widen.json, one entry per line and sorted, so a new widening is a one-line diff."""
    rows = [json.dumps({'gun': gun, 'bone': bone, 'slots': sorted(slots), 'why': why})
            for (gun, bone), (slots, why) in sorted(widen.items())]
    WIDEN_FILE.write_text('[\n' + ',\n'.join('  ' + row for row in rows) + '\n]\n', encoding='ascii')


def add_widen(gun, bone, slots, why):
    """Widen one bone's limit to cover the given slots, with the reason; earlier slots and reasons are kept."""
    widen = read_widen()
    old_slots, old_why = widen.get((gun, bone), ((), ''))
    reasons = old_why if why in old_why.split('; ') else '; '.join(filter(None, (old_why, why)))
    widen[(gun, bone)] = (tuple(sorted(set(old_slots) | set(slots))), reasons)
    write_widen(widen)
    WIDEN.clear()
    WIDEN.update(widen)


WIDEN = read_widen()


def project_scenes(names):
    scenes = [scene for scene in bpy.data.scenes if scene.objects.get(scene.name + '_rig')]
    if names:
        missing = sorted(set(names) - {scene.name for scene in scenes})
        if missing:
            raise RuntimeError('No project scene named ' + ', '.join(missing))
        scenes = [scene for scene in scenes if scene.name in names]
    return scenes


def rig_of(scene):
    return scene.objects[scene.name + '_rig']


def gun_of(project):
    return project.partition('_')[2]


def slot_bags(rig):
    """(slot, channelbag, first frame, last frame) for every slot of the rig's action; the frames of the pose keys."""
    action = rig.animation_data.action
    strip = action.layers[0].strips[0]
    for slot in action.slots:
        bag = strip.channelbag(slot)
        frames = [key.co[0] for curve in bag.fcurves if PREFIX not in curve.data_path for key in curve.keyframe_points]
        yield slot, bag, int(round(min(frames))), int(round(max(frames)))


def is_limited(pose_bone):
    return any(c.name.startswith(PREFIX) and not c.mute and c.influence > 0 for c in pose_bone.constraints)


# ---- spec ----

def keyed_poses(scene):
    """{slot: array [frames, bones, 7]} of the keyed local pose (location, normalized quaternion wxyz), read from
    the F-curves before any constraint, and the bones' rest matrices relative to their parents."""
    import numpy as np
    rig = rig_of(scene)
    names = [bone.name for bone in rig.data.bones]
    poses = {}
    for slot, bag, first, last in slot_bags(rig):
        curves = {(curve.data_path, curve.array_index): curve for curve in bag.fcurves}
        frames = range(first, last + 1)
        values = np.zeros((len(frames), len(names), 7))
        values[:, :, 3] = 1.0
        for index, name in enumerate(names):
            for offset, path, count in ((0, 'location', 3), (3, 'rotation_quaternion', 4)):
                for axis in range(count):
                    curve = curves.get(('pose.bones["%s"].%s' % (name, path), axis))
                    if curve is not None:
                        values[:, index, offset + axis] = [curve.evaluate(frame) for frame in frames]
        quaternions = values[:, :, 3:]
        values[:, :, 3:] = quaternions / np.linalg.norm(quaternions, axis=2, keepdims=True)
        poses[slot.name_display] = values
    rest = []
    for bone in rig.data.bones:
        matrix = bone.matrix_local if bone.parent is None else bone.parent.matrix_local.inverted() @ bone.matrix_local
        rest.append(np.array(matrix))
    return names, poses, np.array(rest)


EULER_ORDERS = {'XYZ': ((0, 1, 2), 0), 'XZY': ((0, 2, 1), 1), 'YXZ': ((1, 0, 2), 1),
                'YZX': ((1, 2, 0), 0), 'ZXY': ((2, 0, 1), 0), 'ZYX': ((2, 1, 0), 1)}


def quaternion_matrices(q):
    import numpy as np
    w, x, y, z = (q[..., i] for i in range(4))
    m = np.empty(q.shape[:-1] + (3, 3))
    m[..., 0, 0] = 1 - 2 * (y * y + z * z); m[..., 0, 1] = 2 * (x * y - w * z); m[..., 0, 2] = 2 * (x * z + w * y)
    m[..., 1, 0] = 2 * (x * y + w * z); m[..., 1, 1] = 1 - 2 * (x * x + z * z); m[..., 1, 2] = 2 * (y * z - w * x)
    m[..., 2, 0] = 2 * (x * z - w * y); m[..., 2, 1] = 2 * (y * z + w * x); m[..., 2, 2] = 1 - 2 * (x * x + y * y)
    return m


def matrix_eulers(m, order):
    """Blender's mat3_normalized_to_eulO in numpy (the angles Limit Rotation limits), radians [..., 3]."""
    import numpy as np
    (i, j, k), parity = EULER_ORDERS[order]
    c = lambda a, b: m[..., b, a]
    cy = np.hypot(c(i, i), c(i, j))
    first, second = np.zeros(m.shape[:-2] + (3,)), np.zeros(m.shape[:-2] + (3,))
    big = cy > 16.0 * np.finfo(np.float32).eps
    first[..., i] = np.where(big, np.arctan2(c(j, k), c(k, k)), np.arctan2(-c(k, j), c(j, j)))
    first[..., j] = np.arctan2(-c(i, k), cy)
    first[..., k] = np.where(big, np.arctan2(c(i, j), c(i, i)), 0.0)
    second[..., i] = np.where(big, np.arctan2(-c(j, k), -c(k, k)), first[..., i])
    second[..., j] = np.where(big, np.arctan2(-c(i, k), -cy), first[..., j])
    second[..., k] = np.where(big, np.arctan2(-c(i, j), -c(i, i)), first[..., k])
    if parity:
        first, second = -first, -second
    pick = np.abs(first).sum(-1) > np.abs(second).sum(-1)
    return np.where(pick[..., None], second, first)


def rotation_vectors(q):
    import numpy as np
    q = np.where(q[..., :1] < 0, -q, q)
    sine = np.linalg.norm(q[..., 1:], axis=-1)
    angle = 2 * np.arctan2(sine, q[..., 0])
    return q[..., 1:] * np.where(sine > 1e-12, angle / np.maximum(sine, 1e-12), 2.0)[..., None]


def arc(degrees):
    """The shortest circular range [low, high] (low < high) that holds every angle."""
    import numpy as np
    a = np.sort(np.mod(degrees, 360.0))
    gaps = np.diff(np.concatenate([a, [a[0] + 360]]))
    widest = int(np.argmax(gaps))
    low = (a[(widest + 1) % len(a)] + 180) % 360 - 180
    return float(low), float(low + 360.0 - gaps[widest])


def motion_class(samples):
    """fixed, rail, hinge, rail+hinge, free_translate, free_rotate or free, from the spread of the motion."""
    import numpy as np

    def spreads(x):
        centered = x - x.mean(0)
        return np.linalg.svd(centered, compute_uv=False) / math.sqrt(len(x)) if len(x) > 1 else np.zeros(3)

    location, rotation = samples[:, :3], np.degrees(rotation_vectors(samples[:, 3:]))
    moves = np.ptp(location, 0).max() > STILL_UNITS, np.ptp(rotation, 0).max() > STILL_DEGREES
    lines = [move and s[1] < LINE * s[0] for move, s in zip(moves, (spreads(location), spreads(rotation)))]
    if not any(moves):
        return 'fixed'
    if not moves[1]:
        return 'rail' if lines[0] else 'free_translate'
    if not moves[0]:
        return 'hinge' if lines[1] else 'free_rotate'
    return 'rail+hinge' if all(lines) else 'free'


def limits(samples, label):
    """The spec entry of a bone that moves through samples [n, 7]: Euler order with the smallest summed range,
    locked axes, and Limit Location / Limit Rotation ranges widened by the margin, rounded outward."""
    import numpy as np
    if label == 'free':
        return {'cls': 'free'}
    matrices = quaternion_matrices(samples[:, 3:])
    best = None
    for order in EULER_ORDERS:
        eulers = np.degrees(matrix_eulers(matrices, order))
        ranges = [arc(eulers[:, axis]) for axis in range(3)]
        total = sum(high - low for low, high in ranges)
        if best is None or total < best[0] - 0.01:
            best = (total, order, ranges)
    location = samples[:, :3]
    spin = np.ptp(np.degrees(rotation_vectors(samples[:, 3:])), 0)
    down = lambda x, digits: math.floor(x * 10 ** digits) / 10 ** digits
    up = lambda x, digits: math.ceil(x * 10 ** digits) / 10 ** digits
    return {'cls': label, 'order': best[1],
            'lock_loc': [bool(np.ptp(location[:, axis]) < STILL_UNITS) for axis in range(3)],
            'lock_rot': [bool(s < STILL_DEGREES) for s in spin],
            'loc': [[down(location[:, axis].min() - MARGIN_UNITS, 3), up(location[:, axis].max() + MARGIN_UNITS, 3)]
                    for axis in range(3)],
            'rot_deg': [[down(low - MARGIN_DEGREES, 2), up(high + MARGIN_DEGREES, 2)] for low, high in best[2]]}


def outside(entry, samples):
    """Whether any sample lies outside the entry's limits."""
    import numpy as np
    eulers = np.degrees(matrix_eulers(quaternion_matrices(samples[:, 3:]), entry['order']))
    for axis in range(3):
        low, high = entry['loc'][axis]
        if ((samples[:, axis] < low) | (samples[:, axis] > high)).any():
            return True
        low, high = entry['rot_deg'][axis]
        middle = (low + high) / 2
        wrapped = (eulers[:, axis] - middle + 180) % 360 - 180 + middle
        if ((wrapped < low) | (wrapped > high)).any():
            return True
    return False


def bone_entry(projects, bone, data, is_arm):
    """The limit of one bone over the given team projects of a gun."""
    import numpy as np

    def samples(slots_of):
        return [data[p]['poses'][s][:, data[p]['names'].index(bone)] for p in projects for s in slots_of(p)
                if s in data[p]['poses']]

    widened = WIDEN.get((gun_of(projects[0]), bone))
    calm = samples(lambda p: [s for s in data[p]['shipped'] if not s.startswith(MELEE)])
    melee = samples(lambda p: [s for s in data[p]['shipped'] if s.startswith(MELEE)])
    extra = samples(lambda p: widened[0]) if widened else []
    label = motion_class(np.concatenate(calm))
    shipped = calm + melee
    if is_arm:
        entry = limits(np.concatenate(shipped + extra), label)
    else:
        entry = limits(np.concatenate(calm + extra), label)
        if label != 'free' and melee and outside(entry, np.concatenate(melee)):
            entry['exempt_slots'] = sorted({s for p in projects for s in data[p]['shipped'] if s.startswith(MELEE)})
    if extra and label != 'free':
        entry['why'] = widened[1]
    return entry


def differs(union, own):
    if 'free' in (union['cls'], own['cls']):
        return union['cls'] != own['cls']
    if union['order'] != own['order'] or union.get('exempt_slots') != own.get('exempt_slots'):
        return True
    return any(abs(a - b) > margin for key, margin in (('loc', MARGIN_UNITS), ('rot_deg', MARGIN_DEGREES))
               for x, y in zip(union[key], own[key]) for a, b in zip(x, y))


def make_spec(scenes):
    import numpy as np
    import export_viewmodels
    data = {}
    for scene in scenes:
        names, poses, rest = keyed_poses(scene)
        shipped = sorted(export_viewmodels.shipped_slots(ROOT / scene.name) & set(poses))
        data[scene.name] = dict(names=names, poses=poses, rest=rest, shipped=shipped)
    guns = {}
    for project in sorted(data):
        guns.setdefault(gun_of(project), []).append(project)
    spec = {'version': 2, 'space': 'LOCAL', 'margin': {'loc': MARGIN_UNITS, 'rot_deg': MARGIN_DEGREES},
            'lock_eps': {'loc': STILL_UNITS, 'rot_deg': STILL_DEGREES},
            'note': 'written by rom_limits.py spec from the shipped slots; change rom_widen.json or rom_limits.py, '
                    'not this file',
            'guns': {}}
    for gun, projects in sorted(guns.items()):
        section = spec['guns'][gun] = {'projects': projects, 'bones': {}, 'team': {}}
        bones = sorted({b for p in projects for b in data[p]['names']})
        for bone in bones:
            have = [p for p in projects if bone in data[p]['names']]
            rest = lambda p: data[p]['rest'][data[p]['names'].index(bone)]
            same = [p for p in have if np.abs(rest(p) - rest(have[0])).max() < REST_TOLERANCE]
            is_arm = bone.startswith(ARM_PREFIX)
            union = bone_entry(same, bone, data, is_arm)
            section['bones'][bone] = union
            for project in have:
                own = bone_entry([project], bone, data, is_arm)
                if project not in same or differs(union, own):
                    section['team'].setdefault(project, {})[bone] = own
        for project in projects:
            print('SPEC', project, len(data[project]['shipped']), 'shipped slots',
                  sorted(set(data[project]['poses']) - set(data[project]['shipped'])), 'left out')
    SPEC.write_text(spec_text(spec), encoding='ascii')
    print('WROTE', SPEC.name, len(spec['guns']), 'guns')


def spec_text(spec):
    """JSON with one bone per line, keys sorted: a limit change is a one-line diff."""
    def bones(entries, indent):
        rows = ['%s  %s: %s' % (indent, json.dumps(b), json.dumps(entries[b], sort_keys=True)) for b in sorted(entries)]
        return '{\n' + ',\n'.join(rows) + '\n' + indent + '}'
    head = ['  %s: %s' % (json.dumps(k), json.dumps(v, sort_keys=True)) for k, v in sorted(spec.items()) if k != 'guns']
    guns = []
    for gun in sorted(spec['guns']):
        section = spec['guns'][gun]
        team = ',\n'.join('        %s: %s' % (json.dumps(p), bones(section['team'][p], '        '))
                          for p in sorted(section['team']))
        guns.append('    %s: {\n      "projects": %s,\n      "bones": %s,\n      "team": {%s}\n    }' % (
            json.dumps(gun), json.dumps(section['projects']), bones(section['bones'], '      '),
            ('\n' + team + '\n      ') if team else ''))
    text = '{\n' + ',\n'.join(head + ['  "guns": {\n' + ',\n'.join(guns) + '\n  }']) + '\n}\n'
    assert json.loads(text) == json.loads(json.dumps(spec))
    return text


# ---- apply, mute, check ----

def spec_entry(spec, project, bone):
    section = spec['guns'].get(gun_of(project))
    if section is None or project not in section['projects']:
        raise RuntimeError('rom_spec.json has no gun section for %s: run rom_limits.py spec' % project)
    entry = section['team'].get(project, {}).get(bone) or section['bones'].get(bone)
    if entry is None:
        raise RuntimeError('rom_spec.json has no entry for %s / %s: run rom_limits.py spec' % (project, bone))
    return entry


def apply_limits(scene, spec):
    rig = rig_of(scene)
    collection = rig.data.collections_all.get(COLLECTION) or rig.data.collections.new(COLLECTION)
    exempt = {}
    for pose_bone in rig.pose.bones:
        for constraint in [c for c in pose_bone.constraints if c.name.startswith(PREFIX)]:
            pose_bone.constraints.remove(constraint)
        entry = spec_entry(spec, scene.name, pose_bone.name)
        if entry['cls'] == 'free':
            pose_bone.lock_location = pose_bone.lock_rotation = (False,) * 3
            collection.unassign(pose_bone.bone)
            continue
        location = pose_bone.constraints.new('LIMIT_LOCATION')
        location.name = PREFIX + 'loc'
        for axis, name in enumerate('xyz'):
            setattr(location, 'use_min_' + name, True)
            setattr(location, 'use_max_' + name, True)
            setattr(location, 'min_' + name, entry['loc'][axis][0])
            setattr(location, 'max_' + name, entry['loc'][axis][1])
        rotation = pose_bone.constraints.new('LIMIT_ROTATION')
        rotation.name = PREFIX + 'rot'
        rotation.euler_order = entry['order']
        rotation.use_legacy_behavior = False
        for axis, name in enumerate('xyz'):
            setattr(rotation, 'use_limit_' + name, True)
            setattr(rotation, 'min_' + name, math.radians(entry['rot_deg'][axis][0]))
            setattr(rotation, 'max_' + name, math.radians(entry['rot_deg'][axis][1]))
        for constraint in (location, rotation):
            constraint.owner_space = 'LOCAL'
            constraint.use_transform_limit = True
            constraint.influence = 1.0
            constraint.mute = False
        pose_bone.lock_location = entry['lock_loc']
        pose_bone.lock_rotation = entry['lock_rot']
        collection.assign(pose_bone.bone)
        if entry.get('exempt_slots'):
            exempt[pose_bone.name] = set(entry['exempt_slots'])
    for slot, bag, first, last in slot_bags(rig):
        for curve in [curve for curve in bag.fcurves if PREFIX in curve.data_path]:
            bag.fcurves.remove(curve)
        for bone in sorted(exempt):
            for name in (PREFIX + 'loc', PREFIX + 'rot'):
                curve = bag.fcurves.new('pose.bones["%s"].constraints["%s"].influence' % (bone, name))
                key = curve.keyframe_points.insert(first, 0.0 if slot.name_display in exempt[bone] else 1.0)
                key.interpolation = 'CONSTANT'
    limited = sum(1 for pose_bone in rig.pose.bones if is_limited(pose_bone))
    print('APPLIED', scene.name, limited, 'limited bones,', len(exempt), 'free in the melee slot')


def set_mute(scene, mute):
    for pose_bone in rig_of(scene).pose.bones:
        for constraint in pose_bone.constraints:
            if constraint.name.startswith(PREFIX):
                constraint.mute = mute


def plant_key(scene, text):
    """Key a test rotation (degrees about a local axis) on BONE:SLOT:FRAME:AXIS:DEGREES; never saved."""
    bone, slot_name, frame, axis, degrees = text.split(':')
    rig = rig_of(scene)
    action = rig.animation_data.action
    slot = next(s for s in action.slots if s.name_display == slot_name)
    bag = action.layers[0].strips[0].channelbag(slot)
    rig.animation_data.action_slot = slot
    scene.frame_set(int(frame))
    turn = Euler((0, 0, 0))
    turn['xyz'.index(axis)] = math.radians(float(degrees))
    rotation = rig.pose.bones[bone].rotation_quaternion @ turn.to_quaternion()
    for index in range(4):
        curve = bag.fcurves.find('pose.bones["%s"].rotation_quaternion' % bone, index=index)
        curve.keyframe_points.insert(int(frame), rotation[index])
    print('PLANTED', scene.name, text)


def find_clamps(scene, slots=None):
    """[(slot, bone, first frame, last frame, frames, worst units, worst degrees)] where an active ROM constraint
    moves the evaluated pose off the keyed pose. Leaves the rig on its first slot."""
    rig = rig_of(scene)
    if not any(is_limited(pose_bone) for pose_bone in rig.pose.bones):
        return []
    with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
        depsgraph = bpy.context.evaluated_depsgraph_get()  # a background scene has none until asked
    clamps = []
    for slot, bag, first, last in slot_bags(rig):
        if slots is not None and slot.name_display not in slots:
            continue
        rig.animation_data.action_slot = slot
        worst = {}
        for frame in range(first, last + 1):
            scene.frame_set(frame)
            evaluated = rig.evaluated_get(depsgraph)
            for pose_bone in evaluated.pose.bones:
                if not is_limited(pose_bone):
                    continue
                local = evaluated.convert_space(pose_bone=pose_bone, matrix=pose_bone.matrix,
                                                from_space='POSE', to_space='LOCAL')
                keyed = pose_bone.matrix_basis
                units = (local.to_translation() - keyed.to_translation()).length
                angle = local.to_quaternion().rotation_difference(keyed.to_quaternion()).angle
                degrees = math.degrees(min(angle, 2 * math.pi - angle))
                if units > CLAMP_UNITS or degrees > CLAMP_DEGREES:
                    w = worst.setdefault(pose_bone.name, [frame, frame, 0, 0.0, 0.0])
                    w[1] = frame
                    w[2] += 1
                    w[3] = max(w[3], units)
                    w[4] = max(w[4], degrees)
        clamps += [(slot.name_display, bone) + tuple(w) for bone, w in sorted(worst.items())]
    rig.animation_data.action_slot = rig.animation_data.action.slots[0]
    return clamps


def clamp_text(project, clamp):
    slot, bone, first, last, count, units, degrees = clamp
    return '%s slot %s bone "%s" frames %d-%d (%d clamped): %.4f u, %.3f deg past its limit' % (
        project, slot, bone, first, last, count, units, degrees)


def main():
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if not arguments:
        raise RuntimeError('Name a command: spec, apply, check, mute-on or mute-off')
    command, names, plants = arguments[0], [], []
    rest = iter(arguments[1:])
    for argument in rest:
        if argument == '--plant':
            plants.append(next(rest))
        else:
            names.append(argument)
    bpy.ops.preferences.addon_enable(module='io_scene_valvesource')
    sys.path.insert(0, str(ROOT))
    scenes = project_scenes(names)
    if command == 'spec':
        make_spec(scenes)
        return
    if command in ('apply', 'mute-on', 'mute-off'):
        spec = json.loads(SPEC.read_text(encoding='ascii')) if command == 'apply' else None
        for scene in scenes:
            if spec:
                apply_limits(scene, spec)
            else:
                set_mute(scene, command == 'mute-on')
                print('MUTED' if command == 'mute-on' else 'UNMUTED', scene.name)
        bpy.ops.wm.save_mainfile()
        backup = Path(bpy.data.filepath + '1')
        if backup.exists():
            backup.unlink()
        print('SAVED', bpy.data.filepath)
        return
    if command != 'check':
        raise RuntimeError('Unknown command ' + command)
    found = 0
    for scene in scenes:
        for text in plants:
            if text.startswith(scene.name + '/'):
                plant_key(scene, text.partition('/')[2])
        clamps = find_clamps(scene)
        for clamp in clamps:
            print('CLAMP', clamp_text(scene.name, clamp))
        print('CHECK', scene.name, len(clamps), 'clamped (slot, bone) pairs')
        found += len(clamps)
    if found:
        sys.exit(3)


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as problem:
        print('ROM FAILED:', problem)
        sys.exit(1)
