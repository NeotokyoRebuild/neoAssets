# v_nsf_tachi: reload of an empty Tachi with the slide held back

The shipped viewmodel recompiled with one added sequence, `reloadempty` (ACT_VM_RELOAD_EMPTY, 64 frames, 2.1 s
like `reload`): the shipped `reload` with the `slide` bone held at its `idle01empty` value (back), eased
forward over frames 54-62 (1.80-2.07 s) to the `reload` pose, as the Milso's shipped `reloadempty` releases its
slide over frames 53-62. Every other sequence is the shipped one; the QC keeps the fire sequences' muzzle flash
event.

Only the new animation is stored here. The reference mesh and the other animations are the shipped model
decompiled with ntre's `proposals/0057-reload-cue-timing/tools/mdl2smd.py`; `segments.csv` is the row
`segments_build.py` composed `reloadempty` from. Compiled with Valve's studiomdl (Source SDK Base 2013 MP),
MDL v48. Recompiled shipped sequences match the shipped model within 0.01 u (`reload` within 0.14 u / 0.44 deg).
