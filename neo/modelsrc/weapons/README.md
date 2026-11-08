# Weapon model sources

The Tachi viewmodels are the first weapons maintained under these conventions, followed by the ZR68C (`jinrai_zr68c/`, `nsf_zr68c/`).
Preview images the `.blend` files load live in a shared weapon folder, such as `tachi/textures/` or `zr68c/textures/`.
Expect the folder layout, scripts and steps here to change as more weapons are added.

Each model has a source folder here, such as `jinrai_tachi/`, containing one `.blend` file and one `.qc` file.
The scripts take the names of the source folders to work on.


## Exporting animations

To export from Blender to SMD, for example for both Tachi projects, run:

```sh
blender --background --python-exit-code 1 --python export_viewmodels.py -- jinrai_tachi nsf_tachi
```

A sequence made of parts of other animations is written after the export, when the source folder has a `composites.txt`.
Each line names the output animation and its parts in order; a part is a slot, `slot:first-last` for a frame range
(inclusive, an empty `last` runs to the end), or `slot@key-` to start after the timeline marker `slot:key`.
For example, `draw_resume_drop_dry draw_resume_drop reload@resume_insert-` writes `anims/draw_resume_drop_dry.smd`:
all of the `draw_resume_drop` slot, then `reload` from the frame after the marker `reload:resume_insert`.
Across each join, the last 3 frames of the previous part are eased onto the pose the next part continues from
(`blend=N` at the end of the line sets the count). The export prints the gap and fails if it exceeds 0.5 units or 2 degrees.


## Reload resume animations (ZR68C)

When the player switches weapons after the old magazine has dropped out, the reload continues when the gun is drawn again.
The game plays `draw_resume_drop_dry` for this: a draw that brings the fresh magazine up, then the rest of `reload`.

The animator makes the motion look right and places markers; the export does the frame and time arithmetic.
The `README_ANIMATOR` text block in each `.blend` repeats these rules.

- The `draw_resume_drop` slot holds only the new motion. It ends on the `reload` pose at the timeline marker
  `reload:resume_insert`. A small difference is eased out at export.
- Timeline markers `slot:phase.key` mark when a reload step counts (`credit`) and when its sound hits (`at`, `at2`).
  The export shifts them into every composite and writes `reload_phases.txt` in weapon-script form.
- With `--script` set to the neo weapon script, the export fails when a `ReloadPhases` row differs from its marker by
  more than half a frame:

```sh
blender --background --python-exit-code 1 --python export_viewmodels.py -- jinrai_zr68c nsf_zr68c --script path/to/neo/game/neo/scripts/weapon_zr68c.txt
```

To add a resume clip for another point in the reload:

1. Mark the `reload` frame where the reload continues, and add a slot that ends on that pose.
2. Add a line to `composites.txt`, such as `NAME CLIP reload@KEY-`, and a `$sequence` line for `NAME` to the `.qc`.
3. Export, copy the times for `NAME` from `reload_phases.txt` into the weapon script's `ReloadPhases`, and compile.


## Compiling models

Set `--compiler` to Source SDK Base 2013 Multiplayer's `studiomdl.exe`, and `--game` to the neo game directory containing `gameinfo.txt`:

```sh
python compile_viewmodels.py jinrai_tachi nsf_tachi --compiler "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Multiplayer/bin/studiomdl.exe" --game "C:/path/to/neo/game/neo"
```

To save the compiled models in neoAssets, copy the generated files (`v_*_tachi.*` for the Tachi, `v_*_zr68c.*` for the ZR68C) from the neo game directory's `models/weapons/` folder to `neo/models/weapons/`.
