# Models and Animations

## Tools

* Use Blender 5.2.2 or newer.
* Use Blender Source Tools 3.4.3 or later to export SMD files from Blender.
* Use Python 3 to run the optional helper scripts. Requires [bpy](https://pypi.org/project/bpy/).
* Source SDK Base 2013 Multiplayer's `studiomdl.exe` compiles Source models.

## Exporting animations

In Blender, open Scene Properties > Source Engine Export and use **Scene Export** with these options:

* Set **Export Path** to `//` to write beside the Blender project.
* Set **Export Format** to SMD.
* Set **Engine Path** to the local `studiomdl.exe` location in Source SDK Base 2013 Multiplayer. (e.g. `C:\Program Files (x86)\Steam\steamapps\common\Source SDK Base 2013 Multiplayer\bin\`)
* Set the armature's **Action Selection** to **Slot Filter** to export every animation slot.
  The default first option, **Current Action Slot**, exports only the selected slot.
* For animation-only changes, leave mesh export disabled.

Note: Model and animation round trips can cause small floating-point and compiler compression differences.