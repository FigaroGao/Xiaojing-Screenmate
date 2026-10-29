"""Fetch the existing desktop pet at a pinned revision; never copy it into our Git tree."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REVISION = "b394cdacca07526a36a36373cb11bec603b74651"
URL = "https://github.com/LINNoot/dsh-co-pet.git"


def main():
    target = ROOT / "runtime" / "dsh-co-pet"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--no-checkout", URL, str(target)], check=True)
        subprocess.run(["git", "-C", str(target), "checkout", "--detach", REVISION], check=True)
    actual = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
    if actual != REVISION:
        raise SystemExit("桌宠依赖版本不同，请保留已有修改并手动检查；不自动重置。")
    print("Existing desktop pet ready:", target)
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("companion_assets", ROOT / "screenmate/companion_assets.py")
    assets = module_from_spec(spec)
    spec.loader.exec_module(assets)
    source = ROOT / "runtime/chibi-dafeiyu"
    if not source.exists():
        subprocess.run(["git", "clone", "--no-checkout", "https://github.com/bauerelizabeth07139/dsh-pet-dafeiyu.git", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "checkout", "--detach", assets.CHIBI_REVISION], check=True)
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != assets.CHIBI_REVISION:
        raise SystemExit("Q版素材版本不同，请先手动检查；不自动重置。")
    print("Chibi companion ready:", source)


if __name__ == "__main__":
    main()
