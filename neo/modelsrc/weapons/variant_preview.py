"""Add a Variant preview to each family base scene: the variants' gun models on the base gun's rig and action.

Run from this folder (Blender 5.2.3 or newer, Blender Source Tools 3.4.3 or newer):
  blender -b viewmodels.blend --python-exit-code 1 --python variant_preview.py -- [--dry-run]
Families come from the .qc files: a variant is a gun whose .qc includes another gun's glued.qci (export_viewmodels.py
family_base). A gun with its own motion (ZR68-L) is not a variant and gets no preview.

Per family base scene (jinrai_BASE):
- The team preview meshes keep the arms only. The gun moves to its own collection, BASE_gun.
- Each variant gets a collection VARIANT_gun: the gun faces of jinrai_VARIANT_preview, parented and skinned to the
  base rig. Variant-only parts (silencer, scope) are re-weighted to their nearest bone the base rig has, at the
  variant's rest pose. That is how the game places them in the glued clips: the clips carry no track for a bone the
  base lacks, so the part stays at its bind pose under its parent. No bone is added to the base rig.
- Each gun collection has the custom property `variant` (the gun name). One is visible at a time: the base gun.
  Show another with the eye of its collection in the Outliner, or Variant in the Viewmodel panel.
Nothing exported depends on these collections: their objects have Source Tools export off, and reference.smd is
never written.

Gate, before anything is saved: the split meshes keep every vertex (arms + gun = the old mesh), and for every slot the
variant shares with its base, at 4 frames, the variant gun posed by the base rig matches the variant's own scene within
GUN_TOLERANCE. A slot whose shipped clips differ (ZR68-S melee01: a gun bone over SAME_CLIP apart on the two rigs)
is listed, not compared. Runtime: a few seconds per family.
"""
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_viewmodels
from merge_teams import ARMS_MATERIAL, posed, slot_frames

VARIANT_KEY = 'variant'  # custom property on each gun collection; viewmodel_tools.py reads it
NOTE_KEY = 'variant_note'  # extra text the Viewmodel panel shows beside the gun name
GAME_DEFAULT = {}  # {variant gun: note}, for a variant that is the game's default model of its weapon
GUN_TOLERANCE = 0.03  # units: the shipped clips of a variant and its base differ by rest rounding only
SAME_CLIP = 0.1  # units: a gun bone further apart than this means the variant ships its own clip for the slot


def families(root):
    """{base gun: [variant guns]} from the .qc files of the Jinrai projects."""
    found = {}
    for folder in sorted(root.glob('jinrai_*')):
        if not next(folder.glob('*.qc'), None):
            continue
        base = export_viewmodels.family_base(folder)
        if base:
            found.setdefault(base.name[len('jinrai_'):], []).append(folder.name[len('jinrai_'):])
    return found


def arm_slots(obj):
    return {index for index, slot in enumerate(obj.material_slots)
            if slot.material and ARMS_MATERIAL in slot.material.name}


def keep_faces(data, keep):
    """Delete the faces whose material index fails keep, the vertices only they used, and loose vertices."""
    mesh = bmesh.new()
    mesh.from_mesh(data)
    doomed = [face for face in mesh.faces if not keep(face.material_index)]
    bmesh.ops.delete(mesh, geom=doomed, context='FACES')
    bmesh.ops.delete(mesh, geom=[vertex for vertex in mesh.verts if not vertex.link_faces], context='VERTS')
    mesh.to_mesh(data)
    mesh.free()


def gun_indices(obj):
    """Indices of the vertices on gun faces, in order (bmesh keeps the order of the vertices it keeps)."""
    arms = arm_slots(obj)
    return sorted({v for polygon in obj.data.polygons if polygon.material_index not in arms for v in polygon.vertices})


def gun_object(source, name, rig):
    """A new object with the gun faces of source, skinned to rig, export off."""
    arms = arm_slots(source)
    data = source.data.copy()
    data.name = name
    keep_faces(data, lambda index: index not in arms)
    obj = bpy.data.objects.new(name, data)
    for group in source.vertex_groups:
        obj.vertex_groups.new(name=group.name)
    obj.parent = rig
    obj.matrix_world = source.matrix_world
    modifier = obj.modifiers.new('Armature', 'ARMATURE')
    modifier.object = rig
    obj.vs.export = False
    return obj


def nearest_bone(bone, bones):
    """The bone itself if bones has it, else its nearest ancestor that bones has."""
    while bone is not None and bone.name not in bones:
        bone = bone.parent
    if bone is None:
        raise RuntimeError('no ancestor in the base rig')
    return bone.name


def reweight(obj, variant_rig, base_rig):
    """Move the weights of variant-only bones to their nearest bone in the base rig; return {old: new}."""
    moved = {}
    for group in list(obj.vertex_groups):
        if group.name in base_rig.data.bones or group.name not in variant_rig.data.bones:
            continue  # a group of no bone (Dummy01.001) deforms nothing on either rig
        target = nearest_bone(variant_rig.data.bones[group.name], base_rig.data.bones)
        into = obj.vertex_groups.get(target) or obj.vertex_groups.new(name=target)
        for vertex in obj.data.vertices:
            for link in vertex.groups:
                if link.group == group.index and link.weight > 0:
                    into.add([vertex.index], link.weight, 'ADD')
        moved[group.name] = target
        obj.vertex_groups.remove(group)
    return moved


def gun_collection(scene, name, gun, objects, shown):
    collection = bpy.data.collections.new(name)
    collection[VARIANT_KEY] = gun
    if gun in GAME_DEFAULT:
        collection[NOTE_KEY] = GAME_DEFAULT[gun]
    scene.collection.children.link(collection)
    for obj in objects:
        collection.objects.link(obj)
        obj[VARIANT_KEY] = gun
    collection.hide_render = not shown
    scene.view_layers[0].layer_collection.children[name].hide_viewport = not shown
    return collection


def split_base(base):
    """Move the base gun out of the team meshes into BASE_gun; return the gun object."""
    scene = bpy.data.scenes['jinrai_' + base]
    rig = scene.objects['jinrai_%s_rig' % base]
    if any(VARIANT_KEY in collection for collection in scene.collection.children):
        raise RuntimeError('jinrai_%s already has gun collections' % base)
    jinrai = scene.objects['jinrai_%s_preview' % base]
    gun = gun_object(jinrai, base + '_gun', rig)
    for team in ('jinrai', 'nsf'):
        mesh = scene.objects['%s_%s_preview' % (team, base)]
        arms = arm_slots(mesh)
        before = len({v for polygon in mesh.data.polygons for v in polygon.vertices})  # loose vertices go
        gun_count = len(gun_indices(mesh))
        if mesh.data.users > 1:
            mesh.data = mesh.data.copy()
        keep_faces(mesh.data, lambda index: index in arms)
        if len(mesh.data.vertices) + gun_count != before:
            raise RuntimeError('%s: arms %d + gun %d != %d vertices' % (
                mesh.name, len(mesh.data.vertices), gun_count, before))
    gun_collection(scene, base + '_gun', base, [gun], True)
    return gun


def bone_heads(scene, rig, bones, slot, frame):
    """World head positions [n, 3] of bones with the rig on slot at frame."""
    rig.animation_data.action_slot = next(s for s in rig.animation_data.action.slots if s.name_display == slot)
    scene.frame_set(frame)
    return np.array([(rig.matrix_world @ rig.pose.bones[name].matrix).translation[:] for name in bones])


def add_variant(base, variant):
    """Add VARIANT_gun to the base scene; return (gate max delta u, worst slot/frame, samples, reweighted, slots
    whose shipped clips differ between the variant and the base)."""
    scene, own = bpy.data.scenes['jinrai_' + base], bpy.data.scenes['jinrai_' + variant]
    rig, own_rig = scene.objects['jinrai_%s_rig' % base], own.objects['jinrai_%s_rig' % variant]
    source = own.objects['jinrai_%s_preview' % variant]
    gun = gun_object(source, variant + '_gun', rig)
    moved = reweight(gun, own_rig, rig)
    collection = gun_collection(scene, variant + '_gun', variant, [gun], True)  # visible while the gate poses it

    window = bpy.context.window
    indices = gun_indices(source)
    frames = slot_frames(own_rig)
    weighted = {link.group for vertex in gun.data.vertices for link in vertex.groups if link.weight > 0}
    carriers = [group.name for group in gun.vertex_groups if group.index in weighted and group.name in rig.data.bones]
    samples = [(slot, frame) for slot in sorted(set(frames) & {s.name_display for s in rig.animation_data.action.slots})
               for frame in frames[slot]]
    window.scene = own
    restore_own = own_rig.animation_data.action_slot, own.frame_current
    reference = {key: (posed(own, source, own_rig, *key)[indices], bone_heads(own, own_rig, carriers, *key))
                 for key in samples}
    own_rig.animation_data.action_slot = restore_own[0]
    own.frame_set(restore_own[1])
    window.scene = scene
    restore = rig.animation_data.action_slot, scene.frame_current
    worst, worst_at, differ = 0.0, None, set()
    for key, (expected, heads) in reference.items():
        if np.linalg.norm(bone_heads(scene, rig, carriers, *key) - heads, axis=1).max() > SAME_CLIP:
            differ.add(key[0])
    for key, (expected, _) in reference.items():
        if key[0] in differ:
            continue
        delta = float(np.linalg.norm(posed(scene, gun, rig, *key) - expected, axis=1).max())
        if delta > worst:
            worst, worst_at = delta, key
    rig.animation_data.action_slot = restore[0]
    scene.frame_set(restore[1])
    collection.hide_render = True
    scene.view_layers[0].layer_collection.children[collection.name].hide_viewport = True
    return worst, worst_at, sum(key[0] not in differ for key in reference), moved, sorted(differ)


def main():
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    dry = '--dry-run' in arguments
    bpy.ops.preferences.addon_enable(module='io_scene_valvesource')
    found = families(Path(bpy.data.filepath).parent)
    failed = []
    for base, variants in sorted(found.items()):
        split_base(base)
        print('SPLIT %-8s team meshes keep the arms; gun in %s_gun' % (base, base))
        for variant in variants:
            worst, at, samples, moved, differ = add_variant(base, variant)
            verdict = 'PASS' if worst <= GUN_TOLERANCE else 'FAIL'
            failed += [variant] if verdict == 'FAIL' else []
            print('VARIANT %-8s on %-8s %s gun max %.4f u at %s (%d samples); re-weighted %s; '
                  'own clip, not compared: %s' % (variant, base, verdict, worst, at, samples,
                     ', '.join('%s->%s' % item for item in moved.items()) or 'none', ', '.join(differ) or 'none'))
    if failed:
        raise RuntimeError('variant gun off its own scene by over %.2f u on %s: nothing saved' % (
            GUN_TOLERANCE, ', '.join(failed)))
    if dry:
        print('DRY RUN: not saved')
        return
    bpy.ops.wm.save_mainfile()
    backup = Path(bpy.data.filepath + '1')
    if backup.exists():
        backup.unlink()
    print('SAVED', bpy.data.filepath)


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as problem:
        print('VARIANT PREVIEW FAILED:', problem)
        sys.exit(1)
