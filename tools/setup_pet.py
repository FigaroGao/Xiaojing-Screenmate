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


if __name__ == "__main__":
    main()
