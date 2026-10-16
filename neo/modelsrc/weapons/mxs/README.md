# MXS viewmodels (Jinrai, NSF) with segmented reloads - research branch

Sources for `models/weapons/v_jinrai_mxs.mdl` and `v_nsf_mxs.mdl` on the `research-reload-phases` branch: the
original NEOTOKYO viewmodels decompiled and recompiled with the partial, resume and draw-resume reload sequences of
the MX plan (`segments.csv`, rows `mx.*`, shared by the MX and MX-S; each model is built from its own animations).

- Partial: reload f0-52 (cut after the tap contact), 11-frame straight exit to the hold.
- Resumes reach from the idle hold to the next phase's grab pose: insert f30, tap f49, charging handle f62 (the hand
  holds the handle at f61-64 and pulls it f62-70; the bolt resume reaches straight up beside the gun to it).
- Draw-resume after the drop: the draw one-handed, support arm and magazine out of view, tilt to f30, then the insert.

Built by ntre's `proposals/0057-reload-cue-timing/tools/`: `mdl2smd.py`, then
`segments_build.py segments.csv mx . --write --qc *.qc`, studiomdl (Source SDK Base 2013 MP, MDL v48).
