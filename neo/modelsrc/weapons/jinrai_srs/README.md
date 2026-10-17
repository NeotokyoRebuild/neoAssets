# v_jinrai_srs with segmented reloads - research branch

Decompiled from the shipped viewmodel and recompiled with the SRS plan's partial, resume and draw-resume reload
sequences (`segments.csv`, rows `srs.*`). The magazine (Clip) jumps from the gun to the hand at f30 and back at
f56 (the seat); a resume after the drop picks the carry back to the well up at f45. The gun hand works the bolt;
the support hand's bolt-resume reach goes to its grip hold f69. Built with ntre's
`proposals/0057-reload-cue-timing/tools/` and studiomdl (MDL v48).
