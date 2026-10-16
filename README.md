# NEOTOKYO Rebuild assets

Runtime content and editable sources live under `neo/`. neo's CMake setup
copies this tree into its local game directory.

## Weapon animation authoring

Start with the [Blender animation workflow](neo/modelsrc/weapons/README.md).
The Jinrai and NSF Tachi projects include editable rigs, animations, preview
textures, SMD exports, and QC compile definitions. Edit and save in Blender,
export with Blender Source Tools, then compile the exported files for Source.
