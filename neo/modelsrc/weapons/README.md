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

Set `--compiler` to Source SDK Base 2013 Multiplayer's `studiomdl.exe`, and `--game` to the neo game directory containing `gameinfo.txt`:

```sh
python compile_viewmodels.py jinrai_tachi nsf_tachi --compiler "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Multiplayer/bin/studiomdl.exe" --game "C:/path/to/neo/game/neo"
```

To save the compiled models in neoAssets, copy the generated files (`v_*_tachi.*` for the Tachi, `v_*_zr68c.*` for the ZR68C) from the neo game directory's `models/weapons/` folder to `neo/models/weapons/`.

## Sketch `sketch-zr68c-full` (discovery branch, not for review)

Every ZR68C transition on the MVP: dry and chamber-live resume after `1_unload`, dry resume after `2_load`, and the fresh
chamber-live `reload_partial` (30+1, no cycle). **Placeholders:** `resume_after_2_load_transition.smd` (copy of the
1_unload slot), `exit_after_2_load_transition.smd` (copy of `idle01`), the composed `resume_after_1_unload`,
`resume_after_2_load_empty`, `reload_partial` SMDs (copies) and `zr68_reload_1_unload.wav` (copy of the 2_load piece).
The phases-file times of the new tables are placeholders too.

NEO TODO (sunzenshen): before the export can run, both .blend files need the markers `reload:1_unload.sound`,
`reload:2_load.exit` (f56), `reload:2_load.join` (f60) and the two authored slots at the original pace (U3: E, R).
Composite ranges may now end at a marker (`reload:0-2_load.exit`, M3).

## Sketch status

Discovery branch, parked until the ZR68C MVP gets reviewer feedback.

### Per-gun TODO (ZR68C full slice)

`composites.txt` takes no comments, so its stubs live here. Lines 1 and 3 are MVP-shaped; `resume_after_1_unload`,
`resume_after_2_load_empty`, `reload_partial` are glued from placeholder slots (combinatorics rows 4, 5, 2).
Open: author 3 transitions (U3 E and R), markers `reload:1_unload.sound`, `2_load.exit`, `2_load.join`, the unload sound
cut, export, compile; RELOAD_END port (U5b); dry-reload fallback for a lost resume; bot threshold; client tests. Plan:
`proposals/0057-reload-cue-timing/zr68c-slice-plan.md`, "Open TODO list (2026-11-07)".
