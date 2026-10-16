# v_nsf_mosok41s with segmented reloads - research branch

Decompiled from the shipped viewmodel and recompiled with the M41 plan's partial, resume and draw-resume reload
sequences (`segments.csv`, rows `m41.*`, shared by the M41, M41S and M41L; frame counts resolved on the M41 and
reused, each model built from its own animations). The slap is a phase: the partial cuts after it (f76, 7-frame
straight exit to the hold); a reload interrupted after the seat replays the slap (reach to f66, slap f66-76), then
the hold (partial) or a reach from the slap pose to the bolt grab f92 and the bolt (dry); after the slap a dry resume
reaches straight to f92. Built with ntre's `proposals/0057-reload-cue-timing/tools/` (mdl2smd.py,
segments_build.py) and studiomdl (MDL v48).
