"""Export the saved Tachi Blender sources with Blender Source Tools.

Run: blender --background --python-exit-code 1 --python export_tachi.py
Runtime: approximately 5 seconds for both models on an i7-12700H.
Requires Blender 5.2 or newer and Blender Source Tools 3.4.3.
This reads .blend sources; it never reconstructs them from SMD exports.
"""
from pathlib import Path

import bpy


def export_project(project):
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


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    for team in ('jinrai', 'nsf'):
        export_project(root / (team + '_tachi') / ('v_' + team + '_tachi.blend'))
