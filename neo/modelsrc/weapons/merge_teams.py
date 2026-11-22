"""Merge the two team scenes of each gun into one: one rig and one action, both teams' arms.

Run from this folder (Blender 5.2.3 or newer, Blender Source Tools 3.4.3 or newer):
  blender -b viewmodels.blend --python-exit-code 1 --python merge_teams.py -- [GUN ...] [--dry-run]
Without GUN, every gun that still has an nsf_GUN scene. --dry-run checks and reports but does not save.

Per gun, the jinrai_GUN scene keeps its rig and action. The NSF preview mesh (arms and gun) moves into that scene,
parented and skinned to the kept rig (its Armature modifier points at the kept rig; the vertex groups keep their bone
names). Each team's preview mesh stays in its own collection, jinrai_GUN_preview and nsf_GUN_preview: the team
toggle is that collection's visibility (Outliner eye, or Team in the Viewmodel panel). The NSF collection starts
hidden. Then the nsf_GUN scene, rig, armature, action and camera are deleted. The NSF project folder is not touched:
it compiles from its shipped SMDs on disk.

Preview-only re-bind: where a bone's rest pose differs between the two rigs (the SRS Release bone, 22 deg; the MilSO
arm and slide bones, 0.006 u), the NSF vertices weighted to it are moved by the rest difference, so the kept rig poses
them as the NSF rig did.
reference.smd is never written; the compiled NSF model keeps its own rest pose.

Gate: for every shipped slot of the NSF scene, at 4 frames, the NSF arms posed by the kept rig must match the NSF arms
posed by the NSF rig within ARMS_TOLERANCE. Any gun over it fails the run before anything is saved.
Runtime: ~1 min for all 19 guns.
"""
from pathlib import Path
import sys

import bpy
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rom_limits

ARMS_TOLERANCE = 0.03  # units: well above the team clip differences (M41 0.026 u at the muzzle), far below a visible pose
REST_TOLERANCE = 1e-3  # units or matrix entries: a smaller rest difference needs no re-bind
ARMS_MATERIAL = 'armsheet'  # the arm materials (jinrai_armsheet1, nsf_armsheet2.004, ...)
TEAM_KEY = 'team'  # custom property on each team collection and preview mesh


def slot_frames(rig):
    """{slot name: 4 frames spread over the slot's keys}."""
    frames = {}
    for slot, _, first, last in rom_limits.slot_bags(rig):
        frames[slot.name_display] = sorted({first, first + (last - first) // 3, first + 2 * (last - first) // 3, last})
    return frames


def posed(scene, mesh, rig, slot, frame):
    """World positions [n, 3] of the evaluated mesh with the rig on slot at frame."""
    rig.animation_data.action_slot = next(s for s in rig.animation_data.action.slots if s.name_display == slot)
    scene.frame_set(frame)
    depsgraph = scene.view_layers[0].depsgraph
    depsgraph.update()
    evaluated = mesh.evaluated_get(depsgraph)
    data = evaluated.data
    co = np.empty(len(data.vertices) * 3)
    data.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    matrix = np.array(evaluated.matrix_world)
    return co @ matrix[:3, :3].T + matrix[:3, 3]


def arm_vertices(mesh):
    """Indices of the vertices on arm-material faces."""
    arms = {index for index, slot in enumerate(mesh.material_slots)
            if slot.material and ARMS_MATERIAL in slot.material.name}
    return sorted({v for polygon in mesh.data.polygons if polygon.material_index in arms for v in polygon.vertices})


def rebind(mesh, kept, old):
    """Move the vertices weighted to bones whose rest differs between the rigs by that difference (weighted blend);
    return the bones whose vertices moved."""
    to_rig = old.matrix_world.inverted() @ mesh.matrix_world
    moved = {}
    for group in mesh.vertex_groups:
        bone_old, bone_kept = old.data.bones.get(group.name), kept.data.bones.get(group.name)
        if bone_old is None or bone_kept is None:
            continue
        if np.abs(np.array(bone_old.matrix_local) - np.array(bone_kept.matrix_local)).max() < REST_TOLERANCE:
            continue
        moved[group.index] = (group.name, bone_kept.matrix_local @ bone_old.matrix_local.inverted())
    if not moved:
        return []
    from_rig, used = to_rig.inverted(), set()
    for vertex in mesh.data.vertices:
        links = [(g.group, g.weight) for g in vertex.groups if g.weight > 0]
        total = sum(weight for _, weight in links)
        hits = [(moved[group][1], weight / total) for group, weight in links if group in moved]
        if not hits:
            continue
        used.update(moved[group][0] for group, _ in links if group in moved)
        at = to_rig @ vertex.co
        shift = sum(((change @ at - at) * share for change, share in hits), at * 0)
        vertex.co = from_rig @ (at + shift)
    return sorted(used)


def merge_gun(gun):
    """Merge nsf_GUN into jinrai_GUN; return (arms max delta, whole-mesh max delta, worst slot/frame, re-bound bones)."""
    kept_scene, old_scene = bpy.data.scenes['jinrai_' + gun], bpy.data.scenes['nsf_' + gun]
    kept, old = kept_scene.objects['jinrai_%s_rig' % gun], old_scene.objects['nsf_%s_rig' % gun]
    mesh = old_scene.objects['nsf_%s_preview' % gun]
    team_collection = bpy.data.collections['nsf_%s_preview' % gun]
    old_camera = old_scene.camera
    arms = arm_vertices(mesh)
    window = bpy.context.window
    window.scene = old_scene
    frames = slot_frames(old)
    reference = {(slot, frame): posed(old_scene, mesh, old, slot, frame) for slot in frames for frame in frames[slot]}
    kept_slots = {slot.name_display for slot in kept.animation_data.action.slots}
    missing = sorted(set(frames) - kept_slots)
    if missing:
        raise RuntimeError('%s: NSF slots %s are missing from the Jinrai action' % (gun, missing))

    old_scene.collection.children.unlink(team_collection)
    kept_scene.collection.children.link(team_collection)
    relative = old.matrix_world.inverted() @ mesh.matrix_world
    bound = rebind(mesh, kept, old)
    mesh.parent = kept
    mesh.matrix_world = kept.matrix_world @ relative
    for modifier in mesh.modifiers:
        if modifier.type == 'ARMATURE':
            modifier.object = kept
    for collection, team in ((team_collection, 'nsf'), (bpy.data.collections['jinrai_%s_preview' % gun], 'jinrai')):
        collection[TEAM_KEY] = team
        for obj in collection.objects:
            obj[TEAM_KEY] = team

    window.scene = kept_scene
    restore = kept.animation_data.action_slot, kept_scene.frame_current
    worst_arms = worst_all = 0.0
    worst_at = None
    for (slot, frame), before in reference.items():
        delta = np.linalg.norm(posed(kept_scene, mesh, kept, slot, frame) - before, axis=1)
        if delta[arms].max() > worst_arms:
            worst_arms, worst_at = float(delta[arms].max()), (slot, frame)
        worst_all = max(worst_all, float(delta.max()))
    kept.animation_data.action_slot = restore[0]
    kept_scene.frame_set(restore[1])
    layer = kept_scene.view_layers[0].layer_collection.children[team_collection.name]
    layer.hide_viewport = True
    team_collection.hide_render = True

    action, armature = old.animation_data.action, old.data
    bpy.data.scenes.remove(old_scene)
    bpy.data.objects.remove(old)
    bpy.data.armatures.remove(armature)
    bpy.data.actions.remove(action)
    if old_camera is not None:
        camera = old_camera.data
        bpy.data.objects.remove(old_camera)
        if camera.users == 0:
            bpy.data.cameras.remove(camera)
    return worst_arms, worst_all, worst_at, bound, len(reference), len(arms)


def main():
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    dry = '--dry-run' in arguments
    guns = [a for a in arguments if a != '--dry-run'] or sorted(
        s.name[4:] for s in bpy.data.scenes if s.name.startswith('nsf_'))
    bpy.ops.preferences.addon_enable(module='io_scene_valvesource')
    failed = []
    for gun in guns:
        arms, whole, at, bound, samples, count = merge_gun(gun)
        verdict = 'PASS' if arms <= ARMS_TOLERANCE else 'FAIL'
        failed += [gun] if verdict == 'FAIL' else []
        print('MERGED %-9s %s arms max %.4f u at %s (%d samples, %d arm vertices); whole mesh max %.4f u; re-bound %s' % (
            gun, verdict, arms, at, samples, count, whole, bound or 'none'))
    if failed:
        raise RuntimeError('NSF arms moved over %.2f u on %s: nothing saved' % (ARMS_TOLERANCE, ', '.join(failed)))
    if dry:
        print('DRY RUN: not saved')
        return
    bpy.data.orphans_purge(do_recursive=True)  # the removed rigs' bone shapes; a save drops one level only
    bpy.ops.wm.save_mainfile()
    backup = Path(bpy.data.filepath + '1')
    if backup.exists():
        backup.unlink()
    print('SAVED', bpy.data.filepath)


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as problem:
        print('MERGE FAILED:', problem)
        sys.exit(1)
