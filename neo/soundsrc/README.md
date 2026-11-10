# Sound sources

Scripts that make a shipped sound from a source file. Run them with Python 3, numpy and scipy.

## murata/make_fire_nopump.py

Makes `neo/sound/weapons/murata/murata_fire_nopump.wav`, the Supa-7 shell shot without its pump clicks.
The input is classic NEOTOKYO's `sound/weapons/murata/murata_fire.wav`, which this repository does not contain.

    python3 weapons/murata/make_fire_nopump.py path/to/murata_fire.wav murata_fire_nopump.wav
    sha256sum murata_fire_nopump.wav

The output is deterministic (fixed seed). Its sha256 is
`df56877859a534f1236a6b03f21bce36215af943cbccd094abc400722720b2ec` with numpy 1.26.4 / scipy 1.11.4 and with
numpy 2.5.4 / scipy 1.18.1. The script's docstring lists the steps.
