"""Compile exported Tachi SMDs using Valve's Source SDK 2013 studiomdl.

Run with Python 3: compile_tachi.py --compiler PATH --game PATH
The destination must be a game folder containing gameinfo.txt. Compilation
uses a temporary game configuration because SDK tools cannot resolve the
client's |appid_244630| material mount. Only the resulting Tachi model files
are copied to the chosen destination; its gameinfo.txt is never changed.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True,
                        help='Source SDK Base 2013 Multiplayer/bin/studiomdl.exe')
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
    with tempfile.TemporaryDirectory(prefix='neo-tachi-') as temporary:
        staging = Path(temporary)
        (staging / 'gameinfo.txt').write_text(
            '"GameInfo" { "game" "Tachi model compile" "FileSystem" { '
            '"SteamAppId" "243750" "SearchPaths" { '
            '"Game" "|gameinfo_path|." } } }\n', encoding='ascii')
        outputs = []
        for team in ('jinrai', 'nsf'):
            name = 'v_' + team + '_tachi'
            qc = root / (team + '_tachi') / (name + '.qc')
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
