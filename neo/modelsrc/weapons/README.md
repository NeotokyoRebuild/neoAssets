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


## Compiling models

Set `--compiler` to Source SDK Base 2013 Multiplayer's `studiomdl.exe`, and `--game` to the neo game directory containing `gameinfo.txt`:

```sh
python compile_viewmodels.py jinrai_tachi nsf_tachi --compiler "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Multiplayer/bin/studiomdl.exe" --game "C:/path/to/neo/game/neo"
```

To save the compiled models in neoAssets, copy the generated files (`v_*_tachi.*` for the Tachi, `v_*_zr68c.*` for the ZR68C) from the neo game directory's `models/weapons/` folder to `neo/models/weapons/`.
