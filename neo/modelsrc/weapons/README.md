# Weapon model sources

The Tachi and ZR68C viewmodels are the first weapons maintained under these conventions.
Expect the folder layout, scripts and steps here to change as more weapons are added.

## Change an animation (quick recipe)

For example, a new pose in a slot of the Tachi. Run the commands from this folder.

1. Open the file with the Viewmodel panel: `blender viewmodels.blend --python viewmodel_tools.py`. In the 3D
   Viewport, press N and pick the **Viewmodel** tab.
2. Pick the scene `jinrai_tachi` (top right) and the slot in Dope Sheet > Action Editor > Slot. The panel shows the
   slot's kind: **authored** (a new slot: edit freely) or **shipped** (keep the original; see Exporting animations).
   Click **Frame range to slot**. **Team** shows the other team's arms; the same keys move both.
3. Pose and key the bones. Click **Check slot**: it selects any bone a range-of-motion limit stops.
4. If such a pose is meant: click **Free selected bones**, key the pose, then click **Widen to this slot** and type
   the reason. This adds a line to `rom_widen.json` and refreshes the limits of every rig (about 8 s).
5. Click **Export gun**. It saves the file and exports the gun's project. The status bar shows the result; the
   terminal has every line. Read any `PACE WARN` (Exporting animations).
6. Commit `viewmodels.blend`, the changed SMDs, and for the ZR68C also `viewmodels_post_export.blend` and the phases
   file, and `rom_widen.json` and `rom_spec.json` if a limit was widened.

Layout:

- `viewmodels.blend`: the Blender file for every viewmodel. It holds one **scene** per gun, called a project:
  `jinrai_tachi` and `jinrai_zr68c`. Each scene has one rig and one action, and both teams' arms (see One scene per
  gun).
- `PROJECT/` (such as `jinrai_tachi/`): the project's `.qc`, `reference.smd`, `anims/*.smd` (written by the
  export) and `composites.txt` (if used). The scripts take project names.
- `nsf_GUN/` (such as `nsf_zr68c/`): the NSF model's `.qc`, `reference.smd` and its shipped clips in `anims/`. It has
  no scene and is never exported: it compiles from these SMDs and from the Jinrai glued clips.
- `jinrai_GUN/glued.qci` (guns with glued clips, now the ZR68C): the `$sequence` lines of the glued clips, read from
  `jinrai_GUN/anims/`. Both team `.qc` files include it, so the NSF model compiles the Jinrai glued clips.
- `GUN/viewmodel.qci` (such as `tachi/viewmodel.qci`): the QC lines both team models of a gun share. Each team's `.qc`
  sets only `$modelname` and includes this file.
- `arms/textures/` (Jinrai and NSF arms, shared by every weapon) and `GUN/textures/`: preview images the `.blend` loads.
- `rom_limits.py`, `rom_spec.json` and `rom_widen.json`: the range-of-motion limits on the rigs (see
  Range-of-motion limits).
- `merge_teams.py`: the one-time merge of the two team scenes of each gun into one (already applied; kept for the
  record and for a gun added later with two scenes).
- `glue.py`: the glued clips, the phases file and the post-export preview; the export uses it (see Reload resume
  animations).
- `viewmodels_post_export.blend`: export output, a preview of the glued clips (see Previewing the glued clips).
- `viewmodel_tools.py`: the Viewmodel sidebar panel (see Change an animation). It is not installed: load it with
  `blender viewmodels.blend --python viewmodel_tools.py`, or, with the file open, Text Editor > Open >
  `viewmodel_tools.py` > Run Script. It always uses the scripts beside the open `.blend`.

Run the scripts from this folder (`neo/modelsrc/weapons`).

Requirements: Blender 5.2.3 or newer with Blender Source Tools 3.4.3 or newer enabled; Python 3 and Valve's
`studiomdl.exe` (Source SDK Base 2013 Multiplayer) for compiling.

### One scene per gun

Each gun has one scene, `jinrai_GUN`: one rig (`jinrai_GUN_rig`) and one action (`jinrai_GUN_animations`). Both
teams' arm meshes are skinned to that rig, so a key moves both. Each team's mesh is in its own collection,
`jinrai_GUN_preview` and `nsf_GUN_preview`; one is visible at a time.

- **Team toggle:** click **Team** in the Viewmodel panel, or click the eye of the two collections in the Outliner.
  It changes only what the viewport shows; the export does not depend on it.
- **Author every slot and marker once**, in that scene: new slots (`drawunloaded`, ...) and edits of shipped slots. The Jinrai
  project holds `composites.txt` and `glued.qci`, and the export writes the phases file from it.
- **The NSF model has no scene.** It compiles from its shipped SMDs in `nsf_GUN/anims/` (the original NSF clips,
  never rewritten) and, for the glued clips, from `jinrai_GUN/anims/` through `../jinrai_GUN/glued.qci`. So both
  teams play one motion for every new clip.
- The shipped slots (`reload`, `draw`, ...) stay the original clips. The export fails when a shipped slot's SMD would
  change, unless it runs with `--edit-shipped`; then the changed clip goes to both teams (see Exporting animations).
- `reference.smd` was not changed by the merge: each team's compiled model keeps its own rest pose.

The Tachi has no glued clips.

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

1. Open `viewmodels.blend` and pick the project in the **Scene** selector at the top right (for example
   `jinrai_tachi`). The `README_ANIMATOR` text block (Text Editor) summarizes the rules.
2. All animations of a project live in **one action** (`PROJECT_animations`, such as `jinrai_tachi_animations`), one
   slot per sequence. To work on a slot: select the project's armature (`PROJECT_rig`), open an Action Editor
   (Dope Sheet > Action Editor), and pick the slot in the **Slot** dropdown beside the action name. To add a slot, use
   the new-slot button next to that dropdown and give it the sequence name. Do not rename existing slots: the `.qc`
   and the weapon script use the names. The action browser lists every project's action; keep each rig on its own.
3. Pose the bones of the two arms: `bone forearm01` / `bone hand01` (and the finger bones under `bone hand01`)
   for one arm, `bone forearm` / `bone hand` for the other, under the roots `Dummy01` and `Dummy02`.
   Key them at the frames you edit.
4. Place markers on the timeline (Marker menu > Add Marker, then rename). Marker names are listed in Reload resume
   animations.
5. Click **Team** to check the pose on the other team's arms. Save, then export (next section).

`drawunloaded` (frames 0-32) is a one-handed draw with the magazine out: the draw brings the gun up, then the hands
tilt to the pose of `reload` at its join marker. The last frame must match that pose; a small difference is eased at
export.

Success looks like `EXPORTED ...` (or `KEPT ...`) for each SMD, and for the ZR68C a `SEAM` line with small gaps and
one `READY` line per sound. A failure prints one `EXPORT FAILED: ...` line.

### Preview camera

Each scene's camera (`PROJECT_camera`) shows the viewmodel as a player sees it in game on a 16:9 screen
(1920x1080), with default settings and the player standing still. To look through it:

1. Move the mouse over the 3D Viewport.
2. Press Numpad 0, or pick View > Cameras > Active Camera.
3. To leave the camera view, rotate the view with the middle mouse button.

The player's field of view setting (75 to 90) does not change the picture: the game draws the viewmodel with its own
field of view. The camera matches the game this way:

- The game puts the model at the player's eye, then moves it by `ViewModelOffset` (`forward`, `right`, `up`) in
  `game/neo/scripts/weapon_GUN.txt`. The camera moves by the opposite amount instead, so the export is unchanged.
  Forward in Blender is -Y, right is -X, up is +Z, so the camera sits at (right, forward, -up): ZR68C (8, 10, 0),
  Tachi (5, 5, 0). It looks along -Y with +Z up.
- The lens has a vertical field of view of 46.83 degrees (Sensor Fit: Vertical). That is the game's `VMFov` of 60,
  which Source measures horizontally on a 4:3 screen. The game reads `VMFov` at the top level of the weapon script
  (60 if absent); the `fov` key inside `ViewModelOffset` is not used.
- If a gun's `ViewModelOffset` or `VMFov` changes, move the camera or change its lens to match.

Units: one Blender unit is one Hammer unit. Blender Source Tools writes Blender coordinates to the SMD unchanged;
the "m" that Blender shows is only its label for the metric system at unit scale 1. So the offsets from the weapon
script can be typed into Blender as they are.



### Range-of-motion limits

Each rig's bones carry limits that stop a pose outside the range the bone moves through in the shipped clips. They
prevent a finger that bends backwards or a charging handle that leaves its rail.

- A limited bone has two constraints, `ROM:loc` (Limit Location) and `ROM:rot` (Limit Rotation), in Local Space with
  *Affect Transform* on: a drag, a rotation or a typed value stops at the limit. The bone's Transform panel also
  locks the axes the bone never moves on (for example, a charging handle moves on one axis only).
- The limit is the bone's range in the shipped slots of its gun, plus 0.05 units and 0.5 degrees. Bones
  that move freely (`Dummy01`, the forearms, magazines) have no limit.
- The melee slot (`melee01`, or `melee` on the M41 family) swings the gun parts freely. Their `ROM:*` influence is
  keyed to 0 in that slot and to 1 in the others, so the Influence field shows as keyed.
- Bone collection `ROM limited` (Armature > Bone Collections) holds the limited bones: show or select them there.
- To mute one constraint, click its eye icon in the Bone Constraints tab. To mute or unmute all of them, use
  **Mute limits** / **Unmute** in the Viewmodel panel, or, with Blender closed (it saves the file):
  `blender -b viewmodels.blend --python rom_limits.py -- mute-on` (or `mute-off`). Muted or not, the export is the same.
  Muting leaves the transform locks on; **Free selected bones** clears them too.
- A key that is already outside a limit (pasted, or moved in the Graph Editor) shows clamped in the viewport only.
  The Graph Editor shows the key as it is, and the export fails on it (next section).

The limits come from `rom_spec.json`; do not edit the constraints by hand. To widen a limit for an authored pose,
use **Widen to this slot** in the Viewmodel panel, or add a line to `rom_widen.json`: the gun (folder name without
the team prefix), the bone, the slots the limit must cover, and the reason. For example:

```json
  {"gun": "tachi", "bone": "bone index 06", "slots": ["SLOT"], "why": "the reason the pose is meant"},
```

The margins are in `rom_limits.py`. After an edit by hand, close Blender and run:

```sh
blender -b viewmodels.blend --python-exit-code 1 --python rom_limits.py -- spec
blender -b viewmodels.blend --python-exit-code 1 --python rom_limits.py -- apply
```

`spec` writes `rom_spec.json` from the keyed poses of the shipped slots (the slots the project's `.qc` compiles from
its own `anims/`); `apply` puts its limits on the rigs and saves `viewmodels.blend`. A new shipped slot or a new gun
needs both. `apply` deletes and re-adds every `ROM:*` constraint, so it can run again at any time. Commit
`rom_spec.json` with `viewmodels.blend`. `rom_spec.json` has one section per gun.

## Exporting animations

To export from Blender to SMD, for example for the Tachi, run:

```sh
blender --background --python-exit-code 1 --python export_viewmodels.py -- jinrai_tachi
```

Name the `jinrai_GUN` project; an `nsf_GUN` project has no scene and the export refuses it.

Before it writes any SMD, the export checks the range-of-motion limits: it plays every frame of every slot of the
listed projects and fails when a limit clamps a key. The message names the project, slot, bone, frames and how far
past the limit the key is. Fix the key, or, if the pose is meant, widen the limit (a line in `rom_widen.json`, then
`spec` and `apply`). `rom_limits.py -- check` runs the same check alone. The export itself runs with `ROM:*` muted:
an active constraint changes the exported numbers slightly even when it clamps nothing, so the SMDs are the keys.

The shipped slots stay the original clips. After Source Tools writes them, the export compares each shipped SMD with
the file it replaced:

- A difference of float round-off only (2e-6 or less): the old file is put back and the export prints `KEPT`.
- A real change: every shipped SMD of the project is put back and the export fails, naming the slot, frame and bone.
  Undo the edit in Blender (File > Revert, or delete the keys).
- A change you mean: add `--edit-shipped` after the project names. The export prints `SHIPPED CHANGED` for each
  changed file and copies it into `nsf_GUN/anims/` when the NSF `.qc` compiles that slot, so the NSF model plays the
  edited clip too.

After it writes the glued clips, the export checks the pace of each authored slot (a slot the project's `.qc` does
not compile from its own `anims/`, such as `drawunloaded`) against the shipped clips of the project, leaving out `fire*` and `melee*`. It prints `PACE WARN`
with the slot, bone and frames where a bone moves more than 10 % faster than in any of them:

- hands, forearms and the gun: world speed in units per frame; the gun also its world turn in degrees per frame;
- fingers: their turn on the hand;
- parts on the gun (slide, bolt handle, magazine, clasp): their motion on the gun, since the gun carrying them is judged
  itself.

Bones that move no vertex of `reference.smd` (`Dummy01`, `Muzzle`, `Eject`, ...) are not seen and are skipped. A
warning does not fail the export. Compare the motion with the shipped clip it imitates; if it reads too fast, spread
the move over more frames.

A sequence made of parts of other animations is written after the export, when the project folder has a `composites.txt`.
Each line names the output animation and its parts in order; a part is a slot, `slot:first-last` for a frame range
(inclusive, an empty `last` runs to the end), or `slot@step-last` to start after the step's join marker (see below).
For example, `drawunloaded_reload drawunloaded reload@1_unload-` writes
`anims/drawunloaded_reload.smd`: all of the `drawunloaded` slot, then `reload` from the frame after
the marker `reload:1_unload.join` to its end. Across each join, the last 3 frames of the previous part are eased onto the pose the
next part continues from (`blend=N` at the end of the line sets the count). The export prints the gap and fails if it
exceeds 0.5 units or 2 degrees.

A composite has no slot or action in Blender, so it is not in the action browser: it is an export output, like the
compiled model. Do not edit its SMD; edit the slots it is made of and export again.


## Reload resume animations (ZR68C)

When the player switches weapons after the old magazine is out (`1_unload`) and before the reload ends, the reload
continues when the gun is drawn again (neo, while `sv_neo_reload_experimental` is 1). The ZR68C has one glued clip
besides `reload`:

| sequence | plays when | made of |
| :-- | :-- | :-- |
| `drawunloaded_reload` | drawn after `1_unload`, chamber empty | `drawunloaded`, then `reload` from f31 |

The `"resume"` key on a row of the phases file names the clip to draw after that step.

The animator makes the motion look right and places markers; the export does the frame and time arithmetic.
The `README_ANIMATOR` text block in `viewmodels.blend` repeats these rules.

### Naming

| name | meaning |
| :-- | :-- |
| `1_unload`, `2_load`, `3_cycle` | reload steps: old magazine out, new magazine in, round chambered. The number belongs to the step type; a gun without a step skips its number. |
| `reload:1_unload` | step marker on `reload`: the frame the step is done and its ammo counts, and the default join of a resume composite (`reload@1_unload`) |
| `reload:1_unload.join` | optional: moves that join (the ZR68C joins at f30, after the ammo point at f21) |
| `slot:step.sound`, `.sound2` | sound markers: when each of the step's sounds first hits |
| `drawunloaded` | authored slot: a one-handed draw with the magazine out, up to the join pose (Source style, as `drawempty`) |
| `drawunloaded_reload` | generated: `drawunloaded` glued to the rest of `reload`. Pattern: the parts in play order, joined by `_`. |
| `weapon_zr68.reload_load`, `reload_load_part2`, `reload_cycle` | sound entries of a step, named `reload_<step>` (`_part2` for its second sound, the tap after loading), wav files named the same. A glued clip plays these pieces; `reload` plays its whole original sound. |

A resume after step N plays only the sounds of the steps after N: a resume after `2_load` would never play the tap.
The export fails when a resume's table lists step N or earlier.

### Markers and times

- The `drawunloaded` slot holds only the new motion. It ends on the `reload` pose at its join marker. A small
  difference is eased out at export.
- The export shifts the timing markers into every composite and rewrites every time in
  `neo/scripts/weapon_<gun>_reload_phases.txt`, the `ReloadPhases` block that neo's weapon script includes with `#base`.
  A row without a marker fails the export, and so does an ammo time at or after the sequence's last frame.
- A marker sits on a frame of the slot it is named after, and is copied to every composite that uses that frame.
  Worked example: `reload:2_load.sound` is at frame 39 of `reload`. `drawunloaded_reload` is the `drawunloaded`
  slot (33 frames, composite frames 0-32) followed by `reload` from frame 31 (join 30, plus 1). Frame 39 of `reload`
  becomes composite frame 33 + (39 - 31) = 41, so the phases file gets `"sound" "1.367"` (41 / 30 fps) on the
  `2_load` row of `drawunloaded_reload`. `reload` itself lists no `2_load` sound: it plays whole, as on master.
  The marker still goes on `reload`, because that is where the frame is.
- Marker kinds: `SLOT:STEP` sets the step's `ammo` time; `SLOT:STEP.sound` and `.sound2` set the first hit of the
  step's sounds; `SLOT:STEP.join` moves the join. The sound's own length comes from its wav (Adding a gun).
- A row's `"resume"` key names the sequence the draw plays when a switch interrupts that sequence after the step.
  The export keeps the key and fails unless it names a composite that joins that sequence after the row's step
  (a part such as `reload@1_unload` in `composites.txt`). In a glued clip, the composite may instead join the
  part the step came from.
- A sequence ends where the gun can fire: the export fails if one of its sounds plays past its last frame. A clip
  that keeps moving after both hands are at rest is trimmed in its source slot; there is no marker for it.

To add a resume clip after another step:

1. Place the step marker `reload:STEP` (and `reload:STEP.join` if the join is elsewhere), and add a slot
   for the draw that ends on that pose (ZR68C: `drawunloaded`).
2. In the Jinrai project, add a line to `composites.txt`, such as `DRAW_reload DRAW reload@STEP-`, and a
   `$sequence` line for it to `jinrai_GUN/glued.qci`, with the path `../jinrai_GUN/anims/DRAW_reload.smd`.
3. In `neo/scripts/weapon_<gun>_reload_phases.txt`, add `"resume" "DRAW_reload"` to the `STEP` row of
   `reload`, and a table for the resume with the rows of the later steps (any time). Then export and compile.
   A new weapon also needs `#base "weapon_<gun>_reload_phases.txt"` and an empty `"ReloadPhases" {}` in its neo script.


### Previewing the glued clips

`viewmodels_post_export.blend` shows each glued clip exactly as the game plays it, easing included. It is an export
output: every export rebuilds it from `viewmodels.blend` and the glued SMDs, for every project with a
`composites.txt` (the Jinrai projects; the NSF models play the same clips). Each scene there has both teams' arms:
**Team** or the collection eye shows the other. Never edit it; edit `viewmodels.blend` and export. Commit it together with the SMDs whenever a
glued clip changes.

1. Open `viewmodels_post_export.blend` in Blender.
2. Pick the project in the Scene box at the top right.
3. Select the rig. Open Dope Sheet > Action Editor and pick a clip in the Slot dropdown.
4. Move the mouse over the 3D Viewport and press Numpad 0 to look through the in-game camera.

The timeline markers carry the step and sound times of each clip (`CLIP:STEP`, `CLIP:STEP.sound`), the times the
phases file gets. The export rewrites the file only when its inputs change: two builds show the same content, but
Blender saves the window layout and some camera properties in a varying order, so the bytes differ.

## Compiling models

`--compiler` is Source SDK Base 2013 Multiplayer's `studiomdl.exe` (the 32-bit one in `bin/`). `--game` is a game
directory that contains `gameinfo.txt`: the `game/neo` folder of a neo checkout. neoAssets has no `gameinfo.txt`, so it
cannot be used. The compile writes the models into that directory's `models/weapons/`, not into the source tree.

```sh
python compile_viewmodels.py jinrai_tachi nsf_tachi --compiler "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Multiplayer/bin/studiomdl.exe" --game "C:/src/neo/game/neo"
```

On Linux, run `studiomdl.exe` with Wine. Pass this wrapper script as `--compiler`; it turns path arguments into
Windows paths, which studiomdl needs:

```bash
#!/bin/bash
args=()
for arg in "$@"; do
    if [ -e "$arg" ]; then args+=("$(winepath -w "$arg")"); else args+=("$arg"); fi
done
exec wine "$HOME/sdk2013mp/bin/studiomdl.exe" "${args[@]}"
```

```sh
python3 compile_viewmodels.py jinrai_tachi nsf_tachi --compiler ~/bin/studiomdl-wine --game ~/src/neo/game/neo
```

Then copy the generated files (`v_*_tachi.*` for the Tachi, `v_*_zr68c.*` for the ZR68C) from the game directory's
`models/weapons/` to neoAssets `neo/models/weapons/`. The compile overwrites older models in the game directory.


## Adding a gun

Files in neoAssets (this repo):

- `neo/modelsrc/weapons/viewmodels.blend`: one scene `jinrai_GUN`. Start from a copy of a similar scene
  (Scene selector > New Scene > Full Copy), name the scene, rig and action after the project (`jinrai_GUN`,
  `jinrai_GUN_rig`, `jinrai_GUN_animations`), and set the scene's Source Engine Export path to `//jinrai_GUN/`. Name
  the camera `jinrai_GUN_camera` and place it from the gun's `ViewModelOffset` (see Preview camera). The export finds
  the rig and the action by these names and fails for a project that does not follow them. Import the NSF preview
  into a second scene `nsf_GUN` with its own rig, then run `merge_teams.py -- GUN` to move it onto the Jinrai rig.
- `neo/modelsrc/weapons/TEAM_GUN/`: the `.qc`, `reference.smd` and `anims/`, for each team (the NSF `anims/` holds
  the shipped clips only).
- `neo/modelsrc/weapons/GUN/viewmodel.qci`: the QC lines the two teams share.
- `neo/modelsrc/weapons/jinrai_GUN/composites.txt` and `glued.qci` (if the gun has glued clips): Jinrai project only.
  End both team `.qc` files with `$include "../jinrai_GUN/glued.qci"`.
- `neo/scripts/weapon_GUN_reload_phases.txt`: the phases file. Copy the ZR68C one and edit the sequences and steps.
- `neo/sound/weapons/GUN/GUN_<key>.wav`: one wav per sound entry.
- `neo/modelsrc/weapons/rom_spec.json`: once the shipped slots are in, run `rom_limits.py -- spec` and `apply`
  (Range-of-motion limits) so the new rigs get their limits.
- `neo/models/weapons/v_TEAM_GUN.*`: the compiled models.

Files in the neo repo:

- `game/neo/scripts/weapon_GUN.txt`: the weapon script. It starts with `#base "weapon_GUN_reload_phases.txt"` and holds
  an empty `"ReloadPhases" {}` inside `WeaponData`, which the base file fills.
- `game/neo/scripts/game_sounds_weapons.txt`: one entry per sound, named `weapon_GUN.<key>` (for example
  `weapon_zr68.reload_load`), whose `"wave"` is `)weapons/GUN/GUN_<key>.wav`. The export does not read this file: it
  assumes the wav path from the entry name (`sound/weapons/GUN/GUN_<key>.wav` in neoAssets) to measure the sound's length.
- The game uses the phases only while the server cvar `sv_neo_reload_experimental` is 1.
