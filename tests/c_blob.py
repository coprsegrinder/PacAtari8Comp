"""Stage 80a: the C test programs install the core's tables from the asset blob (resources/pack/assets.pmab), which the C installer makes from the owner's ROM.
`ensure(build_folder)` runs the installer of that build (the ROM is in original/, the main folder is the repository) so that the programs can run; without the ROM it does nothing and the tests that need it fail
with the programs' own message ("tables not installed")."""
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def ensure(folder):
    exe = os.path.join(folder, "assets", "install_assets" + (".exe" if os.name == "nt" else ""))
    if os.path.exists(os.path.join(ROOT, "original", "Pac-Man.rom")) and os.path.exists(exe):
        r = subprocess.run([exe], cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout
    return folder
