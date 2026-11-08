# Weapon model sources

The Tachi viewmodels are the first weapons maintained under these conventions, followed by the ZR68C (`jinrai_zr68c/`, `nsf_zr68c/`).
Preview images the `.blend` files load live in `arms/textures/` for the Jinrai and NSF arms (shared by every weapon)
and in a weapon folder for the weapon, such as `tachi/textures/` or `zr68c/textures/`.
Expect the folder layout, scripts and steps here to change as more weapons are added.

Each model has a source folder here, such as `jinrai_tachi/`, containing one `.blend` file and one `.qc` file.
The scripts take the names of the source folders to work on.
Run them from this folder (`neo/modelsrc/weapons`).

Requirements: Blender 5.2.3 or newer with Blender Source Tools 3.4.3 or newer enabled; Python 3 and Valve's
`studiomdl.exe` (Source SDK Base 2013 Multiplayer) for compiling.

Each gun has one project per team (`jinrai_zr68c/`, `nsf_zr68c/`). There is no shared project yet, so
**edit both team projects the same way**: the same poses, the same markers at the same frames. The export fails, before it
writes any SMD, when the two projects give a marker different frames.

| term | meaning |
| :-- | :-- |
| sequence | one animation the game plays, such as `reload`. One SMD file in `anims/`, one `$sequence` line in the `.qc`. |
| slot | one animation inside the single Blender action of a project. One slot becomes one SMD, named like the slot. |
| marker | a named flag on the Blender timeline. Its frame sets a time in the phases file. |
| composite | a sequence the export builds by gluing parts of slots together (`composites.txt`). |
| join | the frame where the glued parts meet. The export eases the poses across it (the "seam"). |
| phases file | `neo/scripts/weapon_GUN_reload_phases.txt`: per sequence and reload step, when its ammo counts and its sounds play. The export writes its times. |
| flag | a plain command-line option such as `--game`, or a `blend=N` option in `composites.txt`. |


## Working in Blender

1. Open the team's `.blend` (for example `jinrai_zr68c/v_jinrai_zr68c.blend`). The `README_ANIMATOR` text block
   in it summarizes the rules.
2. All animations of a project live in **one action** (`jinrai_zr68c_animations`), one slot per sequence. To work on
   a slot: select the armature (`jinrai_zr68c_rig`), open an Action Editor (Dope Sheet > Action Editor), and pick the
   slot in the **Slot** dropdown beside the action name. To add a slot, use the new-slot button next to that dropdown
   and give it the sequence name. Do not rename existing slots: the `.qc` and the weapon script use the names.
3. Pose the bones of the two arms: `bone forearm01` / `bone hand01` (and the finger bones under `bone hand01`)
   for one arm, `bone forearm` / `bone hand` for the other, under the roots `Dummy01` and `Dummy02`.
   Key them at the frames you edit.
4. Place markers on the timeline (Marker menu > Add Marker, then rename). Marker names are listed below.
5. Save, repeat in the other team's project, then export (next section).

Landmarks of `resume_after_1_unload_transition` (frames 0-30): the draw brings the gun up from frame 0 to about frame 24;
from frame 24 to the end of the slot (frame 30, the join) the hands tilt to the pose of `reload` at its join marker.
The last frame must match that pose; a small difference is eased at export.

Success looks like `EXPORTED ...` for each project, a `SEAM` line with small gaps, and one `READY` line per sound.
A failure prints one `EXPORT FAILED: ...` line.


## Exporting animations

To export from Blender to SMD, for example for both Tachi projects, run:

```sh
blender --background --python-exit-code 1 --python export_viewmodels.py -- jinrai_tachi nsf_tachi
```

A sequence made of parts of other animations is written after the export, when the source folder has a `composites.txt`.
Each line names the output animation and its parts in order; a part is a slot, `slot:first-last` for a frame range
(inclusive, an empty `last` runs to the end), or `slot@step-last` to start after the step's join marker (see below).
For example, `resume_after_1_unload_empty resume_after_1_unload_transition reload@1_unload-` writes
`anims/resume_after_1_unload_empty.smd`: all of the `resume_after_1_unload_transition` slot, then `reload` from the frame after
the marker `reload:1_unload.join` to its end. Across each join, the last 3 frames of the previous part are eased onto the pose the
next part continues from (`blend=N` at the end of the line sets the count). The export prints the gap and fails if it
exceeds 0.5 units or 2 degrees.


## Reload resume animations (ZR68C)

When the player switches weapons after the old magazine is out, the reload continues when the gun is drawn again.
The game plays `resume_after_1_unload_empty` for this: a draw that brings the fresh magazine up, then the rest of `reload`.
The `"resume"` key on the `1_unload` row of `reload` in the phases file names it.

The animator makes the motion look right and places markers; the export does the frame and time arithmetic.
The `README_ANIMATOR` text block in each `.blend` repeats these rules.

### Naming

| name | meaning |
| :-- | :-- |
| `1_unload`, `2_load`, `3_cycle` | reload steps: old magazine out, new magazine in, round chambered. The number belongs to the step type; a gun without a step skips its number. |
| `reload:1_unload` | step marker on `reload`: the frame the step is done and its ammo counts, and the default join of `resume_after_1_unload` |
| `reload:1_unload.join` | optional: moves that join (the ZR68C joins at f30, after the ammo point at f21) |
| `slot:step.sound`, `.sound2` | sound markers: when each of the step's sounds first hits |
| `resume_after_1_unload_transition` | authored slot: the draw up to the join pose, named after the last finished step |
| `resume_after_1_unload_empty` | generated: the slot glued to the rest of `reload`. Source style: `_empty` (as in `reloadempty`, `idle01empty`) is the clip for an empty gun, the bare name `resume_after_1_unload` the one with a round left. |
| `weapon_zr68.reload_2_load`, `reload_2_load_2` | sound entries of a step (`_2` for its second sound, the tap after loading), wav files named the same |

A resume after step N plays only the sounds of the steps after N: `resume_after_2_load` would never play the tap.
The export fails on a `resume_after_N` row for step N or earlier.

### Markers and times

- The `resume_after_1_unload_transition` slot holds only the new motion. It ends on the `reload` pose at the join marker.
  A small difference is eased out at export.
- The export shifts the timing markers into every composite and rewrites every time in
  `neo/scripts/weapon_<gun>_reload_phases.txt`, the `ReloadPhases` block that neo's weapon script includes with `#base`.
  A row without a marker fails the export, and so does an ammo time at or after the sequence's last frame.
- A marker sits on a frame of the slot it is named after, and is copied to every composite that uses that frame.
  Worked example: `reload:2_load.sound` is at frame 39 of `reload`. `resume_after_1_unload_empty` is the transition
  slot (31 frames, composite frames 0-30) followed by `reload` from frame 31 (join 30, plus 1). Frame 39 of `reload`
  becomes composite frame 31 + (39 - 31) = 39, so the phases file gets `"sound" "1.300"` (39 / 30 fps) on the
  `2_load` row of `resume_after_1_unload_empty`. `reload` itself lists no `2_load` sound: it plays whole, as on master.
  The marker still goes on `reload`, because that is where the frame is.
- Marker kinds: `SLOT:STEP` sets the step's `ammo` time; `SLOT:STEP.sound` and `.sound2` set the first hit of the
  step's sounds; `SLOT:STEP.join` moves the join. The sound's own length comes from its wav (below).
- A row's `"resume"` key names the sequence the draw plays when a switch interrupts that sequence after the step.
  The export keeps the key and fails unless it names a `resume_after_STEP...` sequence of the row's own step.
- A sequence ends where the gun can fire: the export fails if one of its sounds plays past its last frame. A clip
  that keeps moving after both hands are at rest is trimmed in its source slot; there is no marker for it.

To add a resume clip after another step:

1. Place the step marker `reload:STEP` (and `reload:STEP.join` if the join is elsewhere), and add a slot
   `resume_after_STEP_transition` that ends on that pose.
2. Add a line to `composites.txt`, such as `resume_after_STEP_empty resume_after_STEP_transition reload@STEP-`, and a
   `$sequence` line for it to the `.qc`.
3. In `neo/scripts/weapon_<gun>_reload_phases.txt`, add `"resume" "resume_after_STEP_empty"` to the `STEP` row of
   `reload`, and a table for the resume with the rows of the later steps (any time). Then export and compile.
   A new weapon also needs `#base "weapon_<gun>_reload_phases.txt"` and an empty `"ReloadPhases" {}` in its neo script.


## Compiling models

`--compiler` is Source SDK Base 2013 Multiplayer's `studiomdl.exe`. `--game` is a game directory that contains
`gameinfo.txt`, such as `game/neo` in a neo checkout (neoAssets has no `gameinfo.txt`, so it cannot be used).
The compile writes the models into that game directory's `models/weapons/`, not into the source tree.

```sh
python compile_viewmodels.py jinrai_zr68c nsf_zr68c --compiler "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Multiplayer/bin/studiomdl.exe" --game "C:/path/to/neo/game/neo"
```

On Linux, run `studiomdl.exe` with Wine: pass a small wrapper script that calls `wine studiomdl.exe "$@"` as `--compiler`.

Then copy the generated files (`v_*_tachi.*` for the Tachi, `v_*_zr68c.*` for the ZR68C) from the game directory's
`models/weapons/` to neoAssets `neo/models/weapons/`. The compile overwrites older models in the game directory.


## Adding a gun

Files in neoAssets (this repo):

- `neo/modelsrc/weapons/TEAM_GUN/`: the `.blend`, `.qc`, `composites.txt` (if used), `reference.smd` and `anims/`, for each team.
- `neo/scripts/weapon_GUN_reload_phases.txt`: the phases file. Copy the ZR68C one and edit the sequences and steps.
- `neo/sound/weapons/GUN/GUN_<key>.wav`: one wav per sound entry.
- `neo/models/weapons/v_TEAM_GUN.*`: the compiled models.

Files in the neo repo:

- `game/neo/scripts/weapon_GUN.txt`: the weapon script. It starts with `#base "weapon_GUN_reload_phases.txt"` and holds
  an empty `"ReloadPhases" {}` inside `WeaponData`, which the base file fills.
- `game/neo/scripts/game_sounds_weapons.txt`: one entry per sound, named `weapon_GUN.<key>` (for example
  `weapon_zr68.reload_2_load`), whose `"wave"` is `)weapons/GUN/GUN_<key>.wav`. The export does not read this file: it
  assumes the wav path from the entry name (`sound/weapons/GUN/GUN_<key>.wav` in neoAssets) to measure the sound's length.
- The game uses the phases only while the server cvar `sv_neo_reload_experimental` is 1.
