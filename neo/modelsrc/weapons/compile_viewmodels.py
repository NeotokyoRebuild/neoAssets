"""Compile exported viewmodel SMDs using Valve's Source SDK 2013 studiomdl.

Run with Python 3: compile_viewmodels.py SOURCE [SOURCE ...] --compiler PATH --game PATH

Each SOURCE is a folder beside this script that contains one .qc file.
The game path must contain gameinfo.txt.
Compilation uses a temporary game configuration because SDK tools cannot resolve the client's appid search path.
The resulting model files are copied to the chosen destination, while gameinfo.txt is not changed
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('sources', nargs='+', metavar='SOURCE',
                        help='Source folder beside this script, such as jinrai_tachi')
    parser.add_argument('--compiler', type=Path, required=True,
                        help='Path to studiomdl.exe in the Source SDK Base 2013 Multiplayer bin folder')
    parser.add_argument('--game', type=Path, required=True,
                        help='Destination neo game directory (contains gameinfo.txt)')
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    game = args.game.resolve()
    if not compiler.is_file():
        parser.error('Compiler does not exist: ' + str(compiler))
    if not (game / 'gameinfo.txt').is_file():
        parser.error('Game directory must contain gameinfo.txt: ' + str(game))
    root = Path(__file__).resolve().parent
    qcs = []
    for source in args.sources:
        found = sorted((root / source).glob('*.qc'))
        if len(found) != 1:
            parser.error('Source folder must contain one .qc file: ' + source)
        qcs.append(found[0])
    with tempfile.TemporaryDirectory(prefix='neo-viewmodel-') as temporary:
        staging = Path(temporary)
        (staging / 'gameinfo.txt').write_text(
            '"GameInfo" { "game" "Viewmodel compile" "FileSystem" { '
            '"SteamAppId" "243750" "SearchPaths" { '
            '"Game" "|gameinfo_path|." } } }\n', encoding='ascii')
        outputs = []
        for qc in qcs:
            name = qc.stem
            subprocess.run([str(compiler), '-nop4', '-game', str(staging), str(qc)], check=True)
            for extension in ('.mdl', '.vvd', '.dx90.vtx'):
                path = staging / 'models/weapons' / (name + extension)
                if not path.is_file():
                    raise RuntimeError('Compiler did not create ' + str(path))
            outputs.extend((staging / 'models/weapons').glob(name + '.*'))
        destination = game / 'models/weapons'
        destination.mkdir(parents=True, exist_ok=True)
        for path in outputs:
            shutil.copy2(path, destination / path.name)
            print('Installed', destination / path.name)


if __name__ == '__main__':
    main()
