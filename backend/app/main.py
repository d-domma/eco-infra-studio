from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import OUTPUT_DIR, find_blender
from app.models import DesignRequest, DesignResult
from app.services.analysis import _metrics, summarize
from app.services.blender import generate_model, write_spec
from app.services.compliance import evaluate_compliance
from app.services.cost import cost_report
from app.services.environment import analyze_environment
from app.services.search import search_legal_designs
from app.services.stock import stats_overview
from app.services.zoning import resolve_zoning

app = FastAPI(title="Eco Infra Studio", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS: dict[str, DesignResult] = {}


@app.get("/api/health")
def health():
    return {"ok": True, "blender": find_blender(), "stock": stats_overview()}


@app.get("/api/stock")
def stock():
    return stats_overview()


@app.post("/api/designs", response_model=DesignResult)
async def create_design(req: DesignRequest):
    env = await analyze_environment(req)
    zoning = await resolve_zoning(req, env)
    spec, search = search_legal_designs(req, env, zoning)
    compliance = evaluate_compliance(req, spec, env, zoning)
    cost = cost_report(req, spec)
    proposed = _metrics(req, spec, env, conventional=False)
    conventional = _metrics(req, spec, env, conventional=True)
    summary, recs = summarize(req, env, proposed, conventional, compliance.passed)
    recs.insert(0, f"Zoning overlay: {zoning.source}.")
    recs.insert(
        1,
        f"{req.budget_tier.title()} budget cap ${cost.cap_usd:,}; screening construction ${cost.estimate_usd:,}"
        + (" (within cap)." if cost.within_budget else " (over cap — review program or tier)."),
    )
    if search.knn_eui_kbtu_ft2 is not None:
        recs.insert(
            2,
            f"KNN energy model (from {search.knn_n:,} LL84 peers) predicts {search.knn_eui_kbtu_ft2} kBtu/ft² site EUI.",
        )
    elif search.peers.n_peers:
        recs.insert(
            2,
            f"Legal search scored {search.n_legal} code-passing variants against {search.peers.n_peers} NYC stock lots.",
        )

    job_id = uuid.uuid4().hex[:12]
    write_spec(job_id, req, spec, env)
    ready, error, files = generate_model(job_id)

    result = DesignResult(
        id=job_id,
        request=req,
        environment=env,
        zoning=zoning,
        cost=cost,
        compliance=compliance,
        proposed=spec,
        proposed_impact=proposed,
        conventional_impact=conventional,
        summary=summary,
        recommendations=recs,
        blender_ready=ready,
        blender_error=error,
        files=files,
        search=search,
    )
    JOBS[job_id] = result
    (OUTPUT_DIR / job_id / "result.json").write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return result


@app.get("/api/designs/{job_id}", response_model=DesignResult)
def get_design(job_id: str):
    if job_id in JOBS:
        return JOBS[job_id]
    path = OUTPUT_DIR / job_id / "result.json"
    if path.exists():
        return DesignResult.model_validate_json(path.read_text(encoding="utf-8"))
    raise HTTPException(404, "Design not found")


@app.get("/api/designs/{job_id}/files/{filename}")
def get_file(job_id: str, filename: str):
    if filename not in {
        "model.blend",
        "model.glb",
        "model.stl",
        "preview.png",
        "interior.png",
        "cutaway.png",
        "views.json",
        "spec.json",
        "blender.log",
    }:
        raise HTTPException(400, "Unknown file")
    path = OUTPUT_DIR / job_id / filename
    if not path.exists():
        raise HTTPException(404, "File not generated")
    media = {
        "model.blend": "application/octet-stream",
        "model.glb": "model/gltf-binary",
        "model.stl": "model/stl",
        "preview.png": "image/png",
        "interior.png": "image/png",
        "cutaway.png": "image/png",
        "views.json": "application/json",
        "spec.json": "application/json",
        "blender.log": "text/plain",
    }
    return FileResponse(path, media_type=media[filename], filename=filename)


@app.get("/api/materials")
def materials():
    return {
        "building_types": [
            {"id": "single_family", "label": "Single-family house"},
            {"id": "duplex", "label": "Duplex"},
            {"id": "townhouse", "label": "Townhouse"},
            {"id": "apartment", "label": "Apartment building"},
            {"id": "mixed_use", "label": "Mixed-use"},
            {"id": "office", "label": "Office / workspace"},
            {"id": "community", "label": "Community facility"},
        ],
        "roofs": [
            {"id": "pitched", "label": "Pitched"},
            {"id": "flat", "label": "Flat"},
            {"id": "green", "label": "Green roof"},
            {"id": "solar_green", "label": "Green roof + solar"},
        ],
        "materials": [
            {"id": "mass_timber", "label": "Mass timber", "hint": "Lowest structural carbon"},
            {"id": "rammed_earth", "label": "Rammed earth", "hint": "High thermal mass, very low carbon"},
            {"id": "brick", "label": "Brick", "hint": "Durable, moderate carbon"},
            {"id": "recycled_steel", "label": "Recycled steel", "hint": "Long spans, mid carbon"},
            {"id": "concrete", "label": "Concrete", "hint": "Conventional, highest carbon"},
        ],
    }


# Optional: serve built Angular app from the API in production
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "frontend" / "browser"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")
