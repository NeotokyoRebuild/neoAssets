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
Each line names the output animation and its parts in order; a part is a slot, or `slot:first-last` for a frame range
(inclusive, an empty `last` runs to the end). For example, `draw_resume_drop_dry draw_resume_drop reload:31-` writes
`anims/draw_resume_drop_dry.smd`: all of the `draw_resume_drop` slot, then `reload` from frame 31.


## Reload resume animations (ZR68C)

When the player switches weapons after the old magazine has dropped out, the reload continues when the gun is drawn again.
The game plays `draw_resume_drop_dry` for this: a draw that brings the fresh magazine up, then the rest of `reload`.

- The `draw_resume_drop` slot holds only the new motion. Its last frame must match the pose of `reload` frame 30.
  A timeline marker in the `.blend` marks that frame.
- `composites.txt` appends `reload` from frame 31, so the exported sequence plays the reload's own frames after the join.
- The `.qc` compiles `draw_resume_drop_dry`; the transition slot itself is not compiled.

To add a resume clip for another point in the reload:

1. Add a slot that ends on the pose of the `reload` frame where the reload continues, and mark that frame on the timeline.
2. Add a line to `composites.txt` that appends `reload` from the next frame.
3. Add a `$sequence` line for the composite to the `.qc`, then export and compile.
4. In neo, add the sequence's phase times to the weapon script (`ReloadPhases` in `weapon_*.txt`).


## Compiling models

Set `--compiler` to Source SDK Base 2013 Multiplayer's `studiomdl.exe`, and `--game` to the neo game directory containing `gameinfo.txt`:

```sh
python compile_viewmodels.py jinrai_tachi nsf_tachi --compiler "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Multiplayer/bin/studiomdl.exe" --game "C:/path/to/neo/game/neo"
```

To save the compiled models in neoAssets, copy the generated files (`v_*_tachi.*` for the Tachi, `v_*_zr68c.*` for the ZR68C) from the neo game directory's `models/weapons/` folder to `neo/models/weapons/`.
