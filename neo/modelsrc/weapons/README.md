# Weapon model sources

The Tachi viewmodels are the first weapons maintained under these conventions, followed by the MilSO.
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
6. Commit `viewmodels.blend`, the changed SMDs, and `rom_widen.json` and `rom_spec.json` if a limit was widened.

Layout:

- `viewmodels.blend`: the Blender file for every viewmodel. It holds one **scene** per gun, called a project:
  `jinrai_tachi` and `jinrai_milso`. Each scene has one rig and one action, and both teams' arms (see One scene per
  gun).
- `PROJECT/` (such as `jinrai_tachi/`): the project's `.qc`, `reference.smd` and `anims/*.smd` (written by the
  export). The scripts take project names.
- `nsf_GUN/` (such as `nsf_tachi/`): the NSF model's `.qc`, `reference.smd` and its shipped clips in `anims/`. It has
  no scene and is never exported: it compiles from these SMDs.
- `GUN/viewmodel.qci` (such as `tachi/viewmodel.qci`): the QC lines both team models of a gun share. Each team's `.qc`
  sets only `$modelname` and includes this file. The MilSO keeps a whole `.qc` per team, as its team models differ
  in more than their bones.
- `arms/textures/` (Jinrai and NSF arms, shared by every weapon) and `GUN/textures/`: preview images the `.blend` loads.
- `rom_limits.py`, `rom_spec.json` and `rom_widen.json`: the range-of-motion limits on the rigs (see
  Range-of-motion limits).
- `merge_teams.py`: the one-time merge of the two team scenes of each gun into one (already applied; kept for the
  record and for a gun added later with two scenes).
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
- **Author every slot and marker once**, in that scene.
- **The NSF model has no scene.** It compiles from its shipped SMDs in `nsf_GUN/anims/` (the original NSF clips,
  never rewritten).
- The shipped slots (`reload`, `draw`, ...) stay the original clips. The export fails when a shipped slot's SMD would
  change, unless it runs with `--edit-shipped`; then the changed clip goes to both teams (see Exporting animations).
- `reference.smd` was not changed by the merge: each team's compiled model keeps its own rest pose.
- The MilSO team rigs differ by 0.006 units in the arms. The NSF mesh keeps this only in its compiled model; in the
  scene, `merge_teams.py` re-bound the NSF arm vertices for the preview only, so the NSF arms show as the NSF model
  plays them.

| term | meaning |
| :-- | :-- |
| sequence | one animation the game plays, such as `reload`. One SMD file in `anims/`, one `$sequence` line in the `.qc`. |
| slot | one animation inside the single Blender action of a project. One slot becomes one SMD, named like the slot. |
| marker | a named flag on the Blender timeline. |
| flag | a plain command-line option such as `--game`. |


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
4. Click **Team** to check the pose on the other team's arms. Save, then export (next section).

Success looks like `EXPORTED ...` (or `KEPT ...`) for each SMD. A failure prints one `EXPORT FAILED: ...` line.

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
  Forward in Blender is -Y, right is -X, up is +Z, so the camera sits at (right, forward, -up): Tachi (5, 5, 0).
  It looks along -Y with +Z up.
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

After the export, the export checks the pace of each authored slot (a slot the project's `.qc` does not compile
from its own `anims/`) against the shipped clips of the project, leaving out `fire*` and `melee*`. It prints `PACE WARN`
with the slot, bone and frames where a bone moves more than 10 % faster than in any of them:

- hands, forearms and the gun: world speed in units per frame; the gun also its world turn in degrees per frame;
- fingers: their turn on the hand;
- parts on the gun (slide, magazine): their motion on the gun, since the gun carrying them is judged
  itself.

Bones that move no vertex of `reference.smd` (`Dummy01`, `Muzzle`, `Eject`, ...) are not seen and are skipped. A
warning does not fail the export. Compare the motion with the shipped clip it imitates; if it reads too fast, spread
the move over more frames.


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

Then copy the generated files (`v_*_tachi.*` for the Tachi) from the game directory's
`models/weapons/` to neoAssets `neo/models/weapons/`. The compile overwrites older models in the game directory.


## Lowered pistols with an empty magazine

The Tachi and the MilSO hold their slide back when empty (`idle01empty`). Their shipped lowered clips (`idletolow`,
`lowidle`, `lowtoidle`) show the slide forward, so each scene has three authored slots for an empty gun:
`idletolowempty`, `lowidleempty` and `lowtoidleempty`. Each is the shipped clip with the slide and its catch held at
their `idle01empty` pose; no other bone differs.

- `lowidleempty` carries the activity `ACT_VM_IDLE_LOWERED_EMPTY`; the game plays it instead of `lowidle` while the
  magazine is empty.
- The two transitions connect node `0` (the idles) with node `3` (`lowidleempty`), so the engine plays them on the
  way into and out of the empty lowered pose, as it plays `idletolow` and `lowtoidle` for a loaded gun.
- Both team models compile the Jinrai SMDs of these slots. The MilSO NSF arms then sit 0.006 units from the NSF rig
  while lowered (see One scene per gun).

## Adding a gun

Files in neoAssets (this repo):

- `neo/modelsrc/weapons/viewmodels.blend`: one scene `jinrai_GUN`. Start from a copy of a similar scene
  (Scene selector > New Scene > Full Copy), name the scene, rig and action after the project (`jinrai_GUN`,
  `jinrai_GUN_rig`, `jinrai_GUN_animations`), and set the scene's Source Engine Export path to `//jinrai_GUN/`. Name
  the camera `jinrai_GUN_camera` and place it from the gun's `ViewModelOffset` (see Preview camera). The export finds
  the rig and the action by these names and fails for a project that does not follow them. Import the NSF preview
  into a second scene `nsf_GUN` with its own rig, then run `merge_teams.py -- GUN` to move it onto the Jinrai rig.
- `neo/modelsrc/weapons/TEAM_GUN/`: the `.qc`, `reference.smd` and `anims/`, for each team (the NSF `anims/` holds
  the shipped clips).
- `neo/modelsrc/weapons/GUN/viewmodel.qci`: the QC lines the two teams share.
- `neo/modelsrc/weapons/rom_spec.json`: once the shipped slots are in, run `rom_limits.py -- spec` and `apply`
  (Range-of-motion limits) so the new rigs get their limits.
- `neo/models/weapons/v_TEAM_GUN.*`: the compiled models.
