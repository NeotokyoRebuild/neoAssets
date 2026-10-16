# ZR68S viewmodels (Jinrai, NSF) with a partial reload - research branch

Sources for `models/weapons/v_jinrai_zr68s.mdl` and `v_nsf_zr68s.mdl` on the `research-reload-phases`
branch. Both are the original NEOTOKYO viewmodels, decompiled and recompiled unchanged, plus one new
sequence, `reload_partial` (67 frames, 2.200 s at 30 fps, no activity: code picks it by name).

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
`mdl2smd.py` (decompile), `bst_partial.py` (Blender + Blender Source Tools: cut 56, blend 10),
studiomdl under Wine. Recompile from this directory:

    studiomdl -nop4 -game <dir with gameinfo.txt mounting NEOTOKYO> v_jinrai_zr68s.qc
