# Weapon model sources

The Tachi viewmodels are the first weapons maintained under these conventions, followed by the ZR68C (`jinrai_zr68c/`, `nsf_zr68c/`).
Preview images the `.blend` files load live in `arms/textures/` for the Jinrai and NSF arms (shared by every weapon)
and in a weapon folder for the weapon, such as `tachi/textures/` or `zr68c/textures/`.
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
(inclusive, an empty `last` runs to the end), or `slot@step-` to start after the step's join marker (see below).
For example, `resume_after_1_unload_empty resume_after_1_unload reload@1_unload-` writes
`anims/resume_after_1_unload_empty.smd`: all of the `resume_after_1_unload` slot, then `reload` from the frame after
the marker `reload:1_unload.join`. Across each join, the last 3 frames of the previous part are eased onto the pose the
next part continues from (`blend=N` at the end of the line sets the count). The export prints the gap and fails if it
exceeds 0.5 units or 2 degrees.


## Reload resume animations (ZR68C)

When the player switches weapons after the old magazine is out, the reload continues when the gun is drawn again.
The game plays `resume_after_1_unload_empty` for this: a draw that brings the fresh magazine up, then the rest of `reload`.

The animator makes the motion look right and places markers; the export does the frame and time arithmetic.
The `README_ANIMATOR` text block in each `.blend` repeats these rules.

### Naming

| name | meaning |
| :-- | :-- |
| `1_unload`, `2_load`, `3_cycle` | reload steps: old magazine out, new magazine in, round chambered. The number belongs to the step type; a gun without a step skips its number. |
| `reload:1_unload` | step marker on `reload`: the frame the step is done, and the default join of `resume_after_1_unload` |
| `reload:1_unload.join` | optional: moves that join (the ZR68C joins at f30, after the ammo point at f21) |
| `slot:step.ammo`, `.sound`, `.sound2` | timing markers: when the step's ammo counts, when each of its sounds first hits |
| `resume_after_1_unload` | authored slot: the draw up to the join pose, named after the last finished step |
| `resume_after_1_unload_empty` | generated: the slot glued to the rest of `reload`. `_empty` as in `reloadempty`, `idle01empty`. |
| `weapon_zr68.reload_2_load`, `reload_2_load_2` | sound entries of a step (`_2` for its second sound, the tap after loading), wav files named the same |

A resume after step N plays only the sounds of the steps after N: `resume_after_2_load` would never play the tap.
The export fails on a `resume_after_N` row for step N or earlier.

### Markers and times

- The `resume_after_1_unload` slot holds only the new motion. It ends on the `reload` pose at the join marker.
  A small difference is eased out at export.
- The export shifts the timing markers into every composite and rewrites every time in
  `neo/scripts/weapon_<gun>_reload_phases.txt`, the `ReloadPhases` block that neo's weapon script includes with `#base`.
  A row without a marker fails the export.

To add a resume clip after another step:

1. Place the step marker `reload:STEP` (and `reload:STEP.join` if the join is elsewhere), and add a slot
   `resume_after_STEP` that ends on that pose.
2. Add a line to `composites.txt`, such as `resume_after_STEP_empty resume_after_STEP reload@STEP-`, and a `$sequence`
   line for it to the `.qc`.
3. Add the rows for the later steps to `neo/scripts/weapon_<gun>_reload_phases.txt` (any time), then export and compile.
   A new weapon also needs `#base "weapon_<gun>_reload_phases.txt"` and an empty `"ReloadPhases" {}` in its neo script.


## Compiling models

Set `--compiler` to Source SDK Base 2013 Multiplayer's `studiomdl.exe`, and `--game` to the neo game directory containing `gameinfo.txt`:

```sh
python compile_viewmodels.py jinrai_tachi nsf_tachi --compiler "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Multiplayer/bin/studiomdl.exe" --game "C:/path/to/neo/game/neo"
```

To save the compiled models in neoAssets, copy the generated files (`v_*_tachi.*` for the Tachi, `v_*_zr68c.*` for the ZR68C) from the neo game directory's `models/weapons/` folder to `neo/models/weapons/`.
