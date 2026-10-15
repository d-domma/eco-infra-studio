from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.config import BLENDER_SCRIPT, OUTPUT_DIR, find_blender
from app.models import BuildingSpec, DesignRequest, EnvironmentReport


def write_spec(job_id: str, req: DesignRequest, spec: BuildingSpec, env: EnvironmentReport) -> Path:
    folder = OUTPUT_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": job_id,
        "address": env.location.name,
        "latitude": env.location.latitude,
        "longitude": env.location.longitude,
        "lot_width": req.lot_width_m,
        "lot_depth": req.lot_depth_m,
        "building": spec.model_dump(),
        "bedrooms": req.bedrooms,
        "units": req.units,
        "label": f"{req.building_type.replace('_', ' ').title()} — {env.location.name}",
    }
    path = folder / "spec.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def generate_model(job_id: str) -> tuple[bool, str | None, dict[str, str]]:
    blender = find_blender()
    folder = OUTPUT_DIR / job_id
    spec = folder / "spec.json"
    files = {}
    if not blender:
        return False, "Blender was not found. Install Blender 4.3+ or set BLENDER_PATH.", files

    cmd = [
        blender,
        "--background",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
        "--spec",
        str(spec),
        "--out",
        str(folder),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
        (folder / "blender.log").write_text(log, encoding="utf-8", errors="replace")
        for name in ("model.blend", "model.glb", "model.stl", "preview.png", "interior.png", "cutaway.png", "views.json"):
            p = folder / name
            if p.exists():
                files[name] = f"/api/designs/{job_id}/files/{name}"
        if proc.returncode != 0:
            tail = "\n".join(log.splitlines()[-12:])
            return False, tail or f"Blender exited with code {proc.returncode}", files
        if "model.blend" not in files:
            return False, "Blender ran but did not write model.blend.", files
        return True, None, files
    except subprocess.TimeoutExpired:
        return False, "Blender timed out while generating the model.", files
    except Exception as exc:
        return False, str(exc), files
