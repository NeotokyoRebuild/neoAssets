# Editing weapon animations in Blender

The Tachi projects are editable sources, not just animation exports:

- [Jinrai Tachi](jinrai_tachi/README.md): `jinrai_tachi/v_jinrai_tachi.blend`
- [NSF Tachi](nsf_tachi/README.md): `nsf_tachi/v_nsf_tachi.blend`

Each project contains the skinned hands and pistol, all 16 animation clips,
and a preview camera. `reloadempty` is selected when the project opens.
Save animation changes in the `.blend` file first, then export SMDs and
compile the QC. Do not edit generated SMDs as your animation source.

## Requirements

- Blender 5.2 or newer; these projects were saved with 5.2.3 LTS.
- [Blender Source Tools](https://developer.valvesoftware.com/wiki/Blender_Source_Tools)
  3.4.3, enabled in Edit > Preferences > Add-ons.
- Source SDK Base 2013 Multiplayer's `bin/studiomdl.exe` for compilation.
- Python 3 for the optional compile helper; no extra Python packages needed.
- NEOTOKYO installed for the in-game materials. Blender preview images are
  included separately, so opening the project does not require finding Steam.

## Open and edit

1. Open either `.blend` above. Keep the surrounding folders together.
2. Play or scrub frames **0–63**, at **30 fps**, to inspect the empty reload.
   Timeline markers identify the slide release at frames **54–62**.
3. Select the `*_tachi_rig` armature and enter Pose Mode. Select the `slide`
   bone to adjust its movement, or select hand/finger bones to change the pose.
4. The Action Editor's slot selector contains the clips. Choose `reload` to
   compare the partial reload or `idle01empty` to inspect the locked-back pose.
   The clips are slots of one Action, not separate Action datablocks.
5. Save the `.blend` before exporting. Preserve bone names, hierarchy, and
   material names. A preview camera is provided for inspection, not a promise
   of matching the game's viewmodel FOV.

Blender preview PNGs are in `tachi/textures/`, referenced relative to each
project. They are decoded copies of the original NEOTOKYO base-color VTFs;
they are previews, not replacements for the game's VMT/VTF materials.
The preview does not reproduce the Source shader's normal/specular effects.

## Export SMDs

In Scene Properties > Source Engine Export, use **Export Scene**. The saved
configuration exports every animation slot into `anims/`.
The export root is `//` (beside the `.blend`), format SMD, with 54 bones and
no added implicit root. The skinned mesh is included for preview, but its
export is disabled: retain the original `reference.smd` unchanged for these
animation-only projects. Blender Source Tools 3.4.3 with Blender 5.2 changes
split normals on a reference-mesh round trip; exporting that mesh would
change shading unrelated to the animation.

For a repeatable export of both projects, from this directory:

```sh
blender --background --python-exit-code 1 --python export_tachi.py
```

Use the full path to `blender.exe` if Blender is not on PATH. Export does not
save edits for you. The helper opens the saved projects, checks preview-image
paths, and exports them with Blender Source Tools. It does not import SMDs or
recreate the Blender projects.

## Compile and preview in the game

Choose the **neo game directory containing `gameinfo.txt`**, not the checkout
root or the SDK's `bin` directory. Close the game/model viewer before
replacing its models. Back up any local Tachi model overrides you want to keep.

```sh
python compile_tachi.py --compiler "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Multiplayer/bin/studiomdl.exe" --game "C:/path/to/neo/game/neo"
```

The example compiler location is the default Steam library; change it to your
installation. The helper builds both QCs in a temporary staging game, then
copies the resulting model files into the chosen `models/weapons/` directory.
This avoids SDK tools' inability to resolve neo's `|appid_244630|` search path;
it does **not** edit your `gameinfo.txt` or Blender preferences. Compilation
requires no material files. Runtime materials remain the installed game's.

The QC remains the authority for activities, playback FPS, attachments,
transition nodes, and frame-0 muzzle-flash events. Exporting an animation does
not rewrite the QC. If adding a clip, add a matching `$sequence` there.

To retain compiled deliverables in neoAssets, copy all generated
`v_jinrai_tachi.*` and `v_nsf_tachi.*` files from the destination's
`models/weapons/` to this repository's `neo/models/weapons/`.

With companion game code that selects `ACT_VM_RELOAD_EMPTY`, fire the Tachi
dry and reload: the slide stays back until the magazine is seated. A partial
reload should still play `reload`. Check both teams. No game-code build is
needed merely to export or compile an animation.

## CMake and installed copies

neo's CMake configuration copies **everything below neoAssets `neo/`** into
`neo/game/neo/`, including `modelsrc/`, Blender projects, exports, and preview
textures. Separate resource packaging requires `NEO_INSTALL_RESOURCES=ON`
(default OFF); its resources directory also includes that subtree. Asset
copying happens during CMake configuration, not on each animation export:
copy updated sources/models explicitly or configure again to synchronize.
Open the installed
project at `neo/game/neo/modelsrc/weapons/<team>_tachi/v_<team>_tachi.blend`;
its image/export/QC paths still resolve relative to the project.

CMake downloads **upstream master** by default, not this PR. When working from
a branch, set `NEO_EXTRA_ASSETS_ALT_PATH` to the **neoAssets checkout root**
in your existing CMake configuration/preset. Otherwise a later configure can
overwrite local asset changes with the downloaded version. The setting is
not the checkout's `neo/` subfolder.

For an asset-only local preview, copying this branch's `neo/modelsrc/` and
Tachi `neo/models/weapons/v_*_tachi.*` into the game's matching directories
has the same layout; do not delete unrelated game files.

Treat installed projects as review copies. To contribute, edit in the
neoAssets checkout, export, compile, and include the `.blend`, SMD exports,
QC changes if any, and rebuilt models together. Copy any edits made in an
installed project back to the checkout **before** reconfiguring or reinstalling.

## Source history and review checks

These projects were migrated from the original NEOTOKYO Tachi viewmodels,
with one added `reloadempty` clip. The mesh and other animations retain their
original names; no separate decompiler is needed for normal editing.
`segments.csv` records the original empty-reload composition for provenance;
it is not the current authoring/build pipeline.

After an animation change, check clip length/FPS, hand deformation, slide
motion, and both team models. Ordinary reloads, draws, idle poses, firing,
attachments, and muzzle flashes should remain unchanged unless deliberately
edited. Small floating-point and compiler-compression differences can occur
on a Blender/SMD/model round trip; do not mistake a successful compile for a
complete visual review.
