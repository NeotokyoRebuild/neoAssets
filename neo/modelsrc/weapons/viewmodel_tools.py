"""Viewmodel tools: a 3D Viewport sidebar tab (N panel > Viewmodel) for viewmodels.blend.

Load it with the file, from this folder (nothing is installed, and the file is always the one in the repository):
  blender viewmodels.blend --python viewmodel_tools.py
Or, with viewmodels.blend already open: Text Editor > Open > viewmodel_tools.py > Run Script.
It imports rom_limits.py and export_viewmodels.py from the folder of the open .blend.

The panel shows the project, the active slot and its kind: shipped (keep the original clip; edit both teams),
authored (new motion) or ignored (an NSF scene of a sharing gun: author it in the Jinrai scene). Buttons:
- Frame range to slot: set the scene frame range to the active slot's keys and list its markers.
- Check slot: the export's range-of-motion check on the active slot only; selects the clamped bones.
- Mute limits / Unmute: every ROM:* constraint of the scene. Transform locks stay on.
- Free selected bones: mute ROM:* and clear the transform locks of the selected bones, to key a pose past the
  shipped range. Widen (or rom_limits.py apply) puts the limits back.
- Widen to this slot: ask for the reason, add the selected bones and the active slot to rom_widen.json, then rewrite
  rom_spec.json and the limits of every rig in this session (~8 s). Save the .blend afterwards.
- Export gun: save the .blend, then run export_viewmodels.py for both team projects of the gun in a background
  Blender (~20 s with the preview rebuild) and show its result lines (Window > Toggle System Console, or the terminal, has them all).
Runtime of the panel itself: nothing measurable; the .qc files are read once per project and cached.
"""
import json
import subprocess
import sys
from pathlib import Path

import bpy

bl_info = {'name': 'Viewmodel tools (NT;RE)', 'blender': (5, 2, 0), 'category': 'Animation',
           'location': '3D Viewport > Sidebar > Viewmodel'}

RESULT_LINES = ('ROM CHECK', 'EXPORTED', 'SEAM', 'READY', 'KEPT', 'SHIPPED', 'SKIPPED', 'PACE', 'EXPORT FAILED', '  ')
TEAMS = ('jinrai', 'nsf')
KIND_CACHE = {}  # (project, slot) -> kind text; the .qc files do not change while Blender runs


def tools():
    """(folder, rom_limits, export_viewmodels) from the folder of the open .blend."""
    root = Path(bpy.data.filepath).parent
    if not (root / 'rom_limits.py').is_file():
        raise RuntimeError('Open viewmodels.blend from neo/modelsrc/weapons first')
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    sys.dont_write_bytecode = True
    import rom_limits
    import export_viewmodels
    return root, rom_limits, export_viewmodels


def project(context):
    scene = context.scene
    return scene, scene.objects.get(scene.name + '_rig')


def active_slot(rig):
    data = rig.animation_data if rig else None
    return data.action_slot.name_display if data and data.action_slot else None


def slot_kind(scene, slot):
    key = (scene.name, slot)
    if key not in KIND_CACHE:
        root, _, export = tools()
        folder = root / scene.name
        if not folder.is_dir():
            KIND_CACHE[key] = 'not a project'
        elif slot in export.shipped_slots(folder):
            KIND_CACHE[key] = 'shipped: keep the original; edit both teams'
        elif export.shared_from(folder):
            KIND_CACHE[key] = 'ignored: author it in ' + export.shared_from(folder)
        else:
            KIND_CACHE[key] = 'authored: new motion'
    return KIND_CACHE[key]


def keep_view(scene, rig):
    """Remember the active slot and frame, which the checks move."""
    slot, frame = rig.animation_data.action_slot, scene.frame_current

    def restore():
        rig.animation_data.action_slot = slot
        scene.frame_set(frame)
    return restore


class ProjectOperator(bpy.types.Operator):
    @classmethod
    def poll(cls, context):
        _, rig = project(context)
        return active_slot(rig) is not None


class VM_OT_slot_range(ProjectOperator):
    """Set the scene frame range to the keys of the active slot and list the slot's markers"""
    bl_idname = 'viewmodel.slot_range'
    bl_label = 'Frame range to slot'

    def execute(self, context):
        _, rom, _ = tools()
        scene, rig = project(context)
        name = active_slot(rig)
        for slot, _, first, last in rom.slot_bags(rig):
            if slot.name_display == name:
                scene.frame_start, scene.frame_end = first, last
        own = sorted((m.frame, m.name) for m in scene.timeline_markers if m.name.partition(':')[0] == name)
        text = 'RANGE %s f%d-%d; markers: %s' % (name, scene.frame_start, scene.frame_end,
                                                 ', '.join('%s f%d' % (n, f) for f, n in own) or 'none')
        print(text)
        self.report({'INFO'}, text)
        return {'FINISHED'}


class VM_OT_check_slot(ProjectOperator):
    """Run the export's range-of-motion check on the active slot and select the clamped bones"""
    bl_idname = 'viewmodel.check_slot'
    bl_label = 'Check slot'

    def execute(self, context):
        _, rom, _ = tools()
        scene, rig = project(context)
        restore, name = keep_view(scene, rig), active_slot(rig)
        clamps = rom.find_clamps(scene, slots={name})
        restore()
        for pose_bone in rig.pose.bones:
            pose_bone.select = any(clamp[1] == pose_bone.name for clamp in clamps)
        if not clamps:
            print('CHECK', scene.name, name, 'no clamped pose')
            self.report({'INFO'}, 'CHECK %s: no clamped pose' % name)
            return {'FINISHED'}
        for clamp in clamps:
            print('CLAMP', rom.clamp_text(scene.name, clamp))
            self.report({'WARNING'}, 'CLAMP ' + rom.clamp_text(scene.name, clamp))
        self.report({'WARNING'}, '%d clamped bones selected: fix the keys, or Free and Widen if the pose is meant'
                    % len(clamps))
        return {'FINISHED'}


class VM_OT_mute(ProjectOperator):
    """Mute or unmute every ROM:* constraint of this scene; the transform locks stay on"""
    bl_idname = 'viewmodel.mute'
    bl_label = 'Mute limits'
    mute: bpy.props.BoolProperty(default=True)

    def execute(self, context):
        _, rom, _ = tools()
        rom.set_mute(context.scene, self.mute)
        text = ('MUTED ' if self.mute else 'UNMUTED ') + context.scene.name
        print(text)
        self.report({'INFO'}, text)
        return {'FINISHED'}


class VM_OT_free_selected(ProjectOperator):
    """Mute the limits and clear the transform locks of the selected bones, to key a pose past the shipped range"""
    bl_idname = 'viewmodel.free_selected'
    bl_label = 'Free selected bones'

    def execute(self, context):
        _, rom, _ = tools()
        _, rig = project(context)
        freed = []
        for pose_bone in rig.pose.bones:
            if not pose_bone.select:
                continue
            for constraint in pose_bone.constraints:
                if constraint.name.startswith(rom.PREFIX):
                    constraint.mute = True
            pose_bone.lock_location = pose_bone.lock_rotation = (False,) * 3
            freed.append(pose_bone.name)
        if not freed:
            self.report({'ERROR'}, 'Select the bones to free first (Pose Mode)')
            return {'CANCELLED'}
        text = 'FREED %s: key the pose, then Widen to this slot' % ', '.join(freed)
        print(text)
        self.report({'INFO'}, text)
        return {'FINISHED'}


class VM_OT_widen(ProjectOperator):
    """Widen the limits of the selected bones to cover their keys in the active slot (recorded in rom_widen.json)"""
    bl_idname = 'viewmodel.widen'
    bl_label = 'Widen to this slot'
    why: bpy.props.StringProperty(name='Reason', description='Why the pose is meant (kept in rom_spec.json)')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=500)

    def execute(self, context):
        _, rom, _ = tools()
        scene, rig = project(context)
        bones = [pose_bone.name for pose_bone in rig.pose.bones if pose_bone.select]
        if not self.why.strip():
            self.report({'ERROR'}, 'Give a reason: it goes into rom_widen.json and rom_spec.json beside the limit')
            return {'CANCELLED'}
        if not bones:
            self.report({'ERROR'}, 'Select the bones to widen first (Pose Mode)')
            return {'CANCELLED'}
        slot, gun = active_slot(rig), rom.gun_of(scene.name)
        for bone in bones:
            rom.add_widen(gun, bone, [slot], self.why.strip())
        scenes = rom.project_scenes([])
        restores = [keep_view(other, rom.rig_of(other)) for other in scenes]
        rom.make_spec(scenes)
        spec = json.loads(rom.SPEC.read_text(encoding='ascii'))
        for other in scenes:
            rom.apply_limits(other, spec)
        clamps = rom.find_clamps(scene, slots={slot})
        for restore in restores:
            restore()
        text = 'WIDENED %s for %s/%s; rom_widen.json and rom_spec.json rewritten; %d clamps left. Save the file.' % (
            ', '.join(bones), gun, slot, len(clamps))
        print(text)
        self.report({'WARNING'} if clamps else {'INFO'}, text)
        return {'FINISHED'}


class VM_OT_export_gun(ProjectOperator):
    """Save the .blend, then export both team projects of this gun in a background Blender"""
    bl_idname = 'viewmodel.export_gun'
    bl_label = 'Export gun'

    def execute(self, context):
        root, _, export = tools()
        gun = context.scene.name.partition('_')[2]
        projects = [team + '_' + gun for team in TEAMS if team + '_' + gun in export.RIGS]
        bpy.ops.wm.save_mainfile()
        run = subprocess.run([bpy.app.binary_path, '--background', '--python-exit-code', '1', '--python',
                              str(root / 'export_viewmodels.py'), '--'] + projects,
                             cwd=root, capture_output=True, text=True)
        for line in run.stdout.splitlines():
            if line.startswith(RESULT_LINES):
                print(line)
                self.report({'ERROR'} if line.startswith('EXPORT FAILED') else {'INFO'}, line)
        verdict = 'EXPORT %s %s (exit code %d)' % (' '.join(projects), 'FAILED' if run.returncode else 'done',
                                                   run.returncode)
        print(verdict)
        self.report({'ERROR'} if run.returncode else {'INFO'}, verdict)
        return {'CANCELLED'} if run.returncode else {'FINISHED'}


class VM_PT_panel(bpy.types.Panel):
    bl_label = 'Viewmodel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Viewmodel'

    def draw(self, context):
        layout = self.layout
        scene, rig = project(context)
        if rig is None:
            layout.label(text='Pick a project scene (top right)')
            return
        _, rom, _ = tools()
        slot = active_slot(rig)
        layout.label(text='Project: ' + scene.name)
        layout.label(text='Slot: %s' % (slot or 'none'))
        layout.label(text=slot_kind(scene, slot) if slot else 'Pick a slot in the Action Editor')
        muted = any(c.mute for b in rig.pose.bones for c in b.constraints if c.name.startswith(rom.PREFIX))
        layout.label(text='Limits: ' + ('some muted' if muted else 'on'))
        layout.operator(VM_OT_slot_range.bl_idname, icon='PREVIEW_RANGE')
        layout.operator(VM_OT_check_slot.bl_idname, icon='CHECKMARK')
        row = layout.row()
        row.operator(VM_OT_mute.bl_idname, text='Mute limits').mute = True
        row.operator(VM_OT_mute.bl_idname, text='Unmute').mute = False
        layout.operator(VM_OT_free_selected.bl_idname, icon='UNLOCKED')
        layout.operator(VM_OT_widen.bl_idname, icon='CON_ROTLIMIT')
        layout.operator(VM_OT_export_gun.bl_idname, icon='EXPORT')


CLASSES = (VM_OT_slot_range, VM_OT_check_slot, VM_OT_mute, VM_OT_free_selected, VM_OT_widen, VM_OT_export_gun,
           VM_PT_panel)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
