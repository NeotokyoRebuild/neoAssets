# ZR68S viewmodels (Jinrai, NSF) with a partial reload - research branch

Sources for `models/weapons/v_jinrai_zr68s.mdl` and `v_nsf_zr68s.mdl` on the `research-reload-phases`
branch. Both are the original NEOTOKYO viewmodels, decompiled and recompiled unchanged, plus one new
sequences for segmented reloads (no activity: code picks them by name), built by `segments_build.py` from
`segments.csv` (one row per sequence, the machine twin of ntre's `segment-inventory.md`):

| sequence | frames / s | composition |
| --- | --- | --- |
| `reload_partial` | 67 / 2.200 | reload f0-56, 10-frame exit to idle |
| `reload_from_drop_dry` | 64 / 2.100 | 12-frame reach idle -> f30, reload f30-81 |
| `reload_from_drop_partial` | 49 / 1.600 | reach 12 -> f30, f30-56, exit 10 |
| `reload_from_seat_dry` | 40 / 1.300 | reach 6 -> f48, f48-81 |
| `reload_from_seat_partial` | 25 / 0.800 | reach 6 -> f48, f48-56, exit 10 |
| `reload_from_slap_dry` | 37 / 1.200 | reach 16 -> f61, f61-81 |

A reach starts at idle frame 0 (where every resume starts, after `draw`) and moves the support hand on a gun-local
arc to the grab pose of the next phase.

`reload_partial` is `reload` frames 0-56 (magazine out, new magazine in and seated, the tap at 51),
then 10 frames easing every bone from the frame-56 pose to `idle01` frame 0 (smoothstep). It skips
the charging-handle pull, for a reload with a round still chambered.

Files:

- `v_jinrai_zr68s.qc`, `v_nsf_zr68s.qc`: one QC per team. Sequences keep the shipped transition nodes
  (`node "0"`, fire sequences `node "2"`).
- `v_jinrai_zr68s_reference.smd`, `v_nsf_zr68s_reference.smd`: the mesh and bind pose of each model.
- `anims/`: every animation, shared by both models (the two shipped models carry identical skeletons
  and animations).

Not carried over from the shipped models: LODs 1+, the `.xbox.vtx`, events (the ZR68S has none).
Compiled with Valve's studiomdl (Source SDK Base 2013 MP), so the output is MDL v48 (the shipped
files are v44).

Built by the ntre harness tools (`proposals/0057-reload-cue-timing/tools/` in the ntre repo):
`mdl2smd.py` (decompile), `segments_build.py segments.csv zr68s . --write --qc *.qc` (the segmented
sequences; `reload_partial` equals the earlier Blender + Blender Source Tools build to 0.00002 u), studiomdl under Wine. Recompile from this directory:

    studiomdl -nop4 -game <dir with gameinfo.txt mounting NEOTOKYO> v_jinrai_zr68s.qc
