from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BACKEND_ROOT / "outputs"
DATA_DIR = BACKEND_ROOT / "data"
STOCK_DB = DATA_DIR / "building_stock.sqlite"
BLENDER_SCRIPT = BACKEND_ROOT / "blender" / "generate_building.py"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

BLENDER_CANDIDATES = [
    os.environ.get("BLENDER_PATH"),
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    "blender",
]


def find_blender() -> str | None:
    for candidate in BLENDER_CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return str(path)
    return None
