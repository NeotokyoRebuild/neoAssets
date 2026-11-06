# neoAssets

This repository contains the runtime assets used by the [neo](https://github.com/NeotokyoRebuild/neo/) repo.


## Installation

When neo configures CMake, it copies the `neo/` tree from this repository into neo's `game/neo/` directory.
By default, CMake downloads and installs the `NeotokyoRebuild/neoAssets` `master` branch.


## Using a local checkout

To use a local neoAssets checkout, set neo's CMake variable `NEO_EXTRA_ASSETS_ALT_PATH` to the `neoAssets` checkout root configuring CMake.
(Do not set it to the `neo/` subfolder.)

Without a local checkout override, a later neo CMake configure can replace changes in the game copy with files from the downloaded `master` branch.
This can result in lost work if the only copies were in the local neo/game/neo installation.

Setting this override allows one to edit this repository to version changes locally, while enabling the use of CMake configure from `neo` to update the game copy.
