# v_nsf_shotgun with a standalone rack - research branch

Decompiled from the shipped Supa7 viewmodel and recompiled with one new sequence, `rack` (48 frames, 1.567 s): a
straight 25-frame reach of the support hand from the hold to the pump grip (`reloadend` f8), then the shipped
rack `reloadend` f8-30. The game plays it when reload is pressed with the tube full. Built with ntre's
`proposals/0057-reload-cue-timing/tools/` (`segments_build.py ... --base reloadend`) and studiomdl (MDL v48).
