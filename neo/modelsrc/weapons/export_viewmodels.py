"""Export saved viewmodel Blender sources with Blender Source Tools.

Run: blender --background --python-exit-code 1 --python export_viewmodels.py -- SOURCE [SOURCE ...]
Each SOURCE is a folder beside this script that contains one .blend file.
Requires Blender 5.2.2 and Blender Source Tools 3.4.3 or newer.
This helper reads .blend sources, and writes SMD exports.
An optional composites.txt in a source folder joins exported animations into one more SMD per line:
OUTPUT PART [PART ...], where PART is SLOT or SLOT:FIRST-LAST (inclusive frames; an empty LAST means the end).
"""
from pathlib import Path
import sys

import bpy


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


def write_composites(folder):
    composites = folder / 'composites.txt'
    if not composites.is_file():
        return
    for line in composites.read_text(encoding='ascii').splitlines():
        if not line.strip():
            continue
        output, *parts = line.split()
        header, joined = None, []
        for part in parts:
            slot, _, span = part.partition(':')
            part_header, frames = read_frames(folder / 'anims' / (slot + '.smd'))
            if header is not None and part_header != header:
                raise RuntimeError('Composite parts have different nodes: ' + part)
            header = part_header
            first, _, last = span.partition('-')
            joined += frames[int(first or 0):int(last) + 1 if last else None]
        body = [text for time, frame in enumerate(joined) for text in ['time %d' % time] + frame]
        (folder / 'anims' / (output + '.smd')).write_text(
            '\n'.join(header + body + ['end']) + '\n', encoding='ascii')
        print('COMPOSED', output, len(joined), 'frames')


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
    write_composites(folder)


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
