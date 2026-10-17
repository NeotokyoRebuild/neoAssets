# v_nsf_milso with segmented reloads - research branch

Decompiled from the shipped viewmodel and recompiled with the Milso plan's resume and draw-resume reload
sequences (`segments.csv`, rows `milso.*`). A partial reload is the shipped `reload` (slide forward); a dry one is
`reloadempty`, which ends with the slide release. A resume after the seat on a dry pistol is the slide release alone.
Built with ntre's `proposals/0057-reload-cue-timing/tools/` and studiomdl (MDL v48).
