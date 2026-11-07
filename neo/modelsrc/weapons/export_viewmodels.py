"""Export saved viewmodel Blender sources with Blender Source Tools.

Run: blender --background --python-exit-code 1 --python export_viewmodels.py -- SOURCE [SOURCE ...]
Each SOURCE is a folder beside this script that contains one .blend file.
Requires Blender 5.2.2 and Blender Source Tools 3.4.3 or newer.
This helper reads .blend sources, and writes SMD exports.
"""
from pathlib import Path
import sys

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
    sources = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if not sources:
        raise RuntimeError('List the source folders to export after --')
    projects = []
    for source in sources:
        found = sorted((root / source).glob('*.blend'))
        if len(found) != 1:
            raise RuntimeError('Source folder must contain one .blend file: ' + source)
        projects.append(found[0])
    for project in projects:
        export_project(project)
