# Tachi viewmodels


## Exporting Tachi animations

To export from Blender to SMD for both jinrai/nsf projects, run:

```sh
blender --background --python-exit-code 1 --python export_tachi.py
```


## Compiling Tachi models

Set `--compiler` to Source SDK Base 2013 Multiplayer's `studiomdl.exe`, and `--game` to the neo game directory containing `gameinfo.txt`:

```sh
python compile_tachi.py --compiler "C:/Program Files (x86)/Steam/steamapps/common/Source SDK Base 2013 Multiplayer/bin/studiomdl.exe" --game "C:/path/to/neo/game/neo"
```

To save the compiled models in neoAssets, copy the generated `v_*_tachi.*` files from the neo game directory's `models/weapons/` folder to `neo/models/weapons/`.
