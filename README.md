# Eco Infra Studio

A sustainable infrastructure design app: enter a site and preferences, cross-check **open environmental data** and **model building-code rules**, then generate an editable **Blender** building with STL for 3D printing.

This matches the project abstract, with Blender used for the 3D design instead of generic CAD.

## Stack

- **Angular + Bootstrap** — design wizard, impact dashboard, 3D preview
- **Python (FastAPI)** — geocoding, climate, green-space, compliance, carbon comparison
- **Blender 4.3 / 5.x** — parametric `.blend` / `.glb` / `.stl` + optional preview render

## Run locally

Install [Blender](https://www.blender.org/) if needed (this machine already has 4.3 and 5.2). Then from the repo root:

```powershell
.\start.ps1
```

Or in two terminals:

```powershell
# terminal 1 — API
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

```powershell
# terminal 2 — UI
cd frontend
npm install
npm start
```

Open [http://localhost:4200](http://localhost:4200).

Optional: set `BLENDER_PATH` if Blender is not in `C:\Program Files\Blender Foundation\`.

## What a run produces

For each design, `backend/outputs/<id>/` contains:

| File | Use |
| --- | --- |
| `model.blend` | Open and refine in Blender |
| `model.stl` | 3D-print the massing |
| `model.glb` | Web preview |
| `preview.png` | Still image |
| `spec.json` | Dimensions fed to Blender |

## Data sources

- Open-Meteo geocoding, climate archive, and air quality
- OpenStreetMap / Overpass for parks and habitat within 900 m
- IBC-inspired zoning envelope (setbacks, height, coverage, FAR, open space, stormwater)
- NYC [PLUTO](https://data.cityofnewyork.us/City-Government/Primary-Land-Use-Tax-Lot-Output-PLUTO-/64uk-42ks) lots + [LL84](https://data.cityofnewyork.us/Environment/NYC-Building-Energy-and-Water-Data-Disclosure-for-/5zyy-y8am) measured site EUI
- CLF WBLCA typical embodied intensities (labels, not per-lot measured carbon)
- ResStock/ComStock typical EUI only when LL84 has no reading

Refresh the local stock (from `backend/`):

```powershell
python scripts/import_nyc_stock.py
```

The searcher only sends **code-passing** designs to Blender. Carbon savings vs conventional still use the defined concrete / high-coverage twin in `app/services/analysis.py`. Peer EUI is a separate comparison against NYC LL84.

If an API is unreachable, the backend falls back to plausible defaults so you can still generate a model.
