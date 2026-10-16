# Jinrai Tachi animation source

Open **`v_jinrai_tachi.blend`** in Blender 5.2 or newer with Blender Source
Tools enabled. The skinned hands and pistol are included, with `reloadempty`
selected in the Action Editor. Preview textures resolve from
`../tachi/textures/`; keep that folder alongside the team projects.

See [the animation workflow](../README.md) for editing, exporting, compiling,
CMake asset installation, and contributing changes.

- Authoritative editable source: `v_jinrai_tachi.blend`.
- Preserved original reference mesh: `reference.smd` (not re-exported).
- Generated clips: `anims/*.smd` (all 16 clips).
- Compile definition: `v_jinrai_tachi.qc`.
- Runtime output: `models/weapons/v_jinrai_tachi.*` in the chosen game folder.

The empty reload spans frames **0–63 at 30 fps** (2.1 seconds between the
first and last frame). The `slide` bone stays in its `idle01empty` pose, then
returns forward over frames **54–62**, after the new magazine is seated.
Compare the `reload` slot for a partial reload and `idle01empty` for the
locked-back pose. Every clip uses the original 54-bone hierarchy.

Use Scene Properties > Source Engine Export > **Export Scene** to rebuild
all SMDs beside this project. Save the Blender file first. The QC preserves
activities, attachments, transition nodes, and firing muzzle-flash events;
review it when adding or renaming animation slots.

`segments.csv` records the initial empty-reload composition. It is historical
provenance, not an input required to edit or rebuild this Blender project.
