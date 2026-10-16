# v_nsf_tachi with segmented reloads - research branch

Decompiled from the shipped viewmodel and recompiled with the Tachi plan's resume and draw-resume reload
sequences (`segments.csv`, rows `tachi.*`). A partial reload is the shipped `reload` (slide forward); a dry one is
`reloadempty`, which ends with the slide release (built here: the slide held back as in idle01empty, then eased forward over f54-62 like the Milso's). A resume after the seat on a dry pistol is the slide release alone.
Built with ntre's `proposals/0057-reload-cue-timing/tools/` and studiomdl (MDL v48).
The fire sequences keep the shipped model's muzzle flash event (`AE_MUZZLEFLASH "PISTOL MUZZLE"` at frame 0), which `mdl2smd.py` does not carry.
