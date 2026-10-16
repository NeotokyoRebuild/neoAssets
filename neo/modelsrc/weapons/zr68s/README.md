# ZR68S viewmodels (Jinrai, NSF) with a partial reload - research branch

Sources for `models/weapons/v_jinrai_zr68s.mdl` and `v_nsf_zr68s.mdl` on the `research-reload-phases`
branch. Both are the original NEOTOKYO viewmodels, decompiled and recompiled unchanged, plus one new
sequences for segmented reloads (no activity: code picks them by name), built by `segments_build.py` from
`segments.csv` (one row per sequence, the machine twin of ntre's `segment-inventory.md`):

| sequence | frames / s | composition |
| --- | --- | --- |
| `reload_partial` | 67 / 2.200 | reload f0-56, 10-frame exit to idle |
| `reload_from_drop_dry` | 79 / 2.600 | 27-frame reach idle -> f30, reload f30-81 |
| `reload_from_drop_partial` | 64 / 2.100 | reach 27 -> f30, f30-56, exit 10 |
| `reload_from_seat_dry` | 54 / 1.767 | reach 20 -> f48, f48-81 |
| `reload_from_seat_partial` | 39 / 1.267 | reach 20 -> f48, f48-56, exit 10 |
| `reload_from_slap_dry` | 51 / 1.667 | reach 30 -> f61, f61-81 |
| `draw_resume_drop_dry` | 85 / 2.800 | resume after the drop: the draw one-handed, support arm and magazine held out of view as at reload f30, 9-frame tilt to f30, f30-81 |
| `draw_resume_drop_partial` | 70 / 2.300 | the same draw and tilt, f30-56, exit 10 |

A reach starts at idle frame 0 (where every resume starts, after `draw`) and moves the support hand on a gun-local
arc to the grab pose of the next phase, at even steps along the arc with a smoothstep ease; its length
keeps the hand's peak speed at or under 2.5 units a frame, the pace of the shipped reaches.

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
