# ReMediX

Drug-repurposing analysis: resolve a compound, gather its protein targets, and
score its therapeutic alignment against a disease using CREEDS gene-expression
signatures and ChEMBL bioactivity.

- **Backend**: FastAPI (Python 3.14, managed with [uv](https://docs.astral.sh/uv/))
- **Frontend**: React 18 + Vite + TypeScript + Tailwind, deployed to Netlify
- **Data**: local datasets under `src/data/` (see below) + external PubChem/ChEMBL APIs

Read `CONTEXT.md` first — it is the working map of the codebase, known issues,
and the production-hardening roadmap. `architecture.md` is an aspirational
target layout, **not** current reality.

## Quick start (development)

Prerequisites: [uv](https://docs.astral.sh/uv/) (Python), Node.js ≥ 20 (npm).

```bash
# Backend
uv sync                       # creates .venv from uv.lock
uv run fastapi dev main.py    # dev server on http://127.0.0.1:8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev                   # Vite dev server on http://127.0.0.1:5173
                              # proxies /api and /data to the backend
```

Or launch both at once: `uv run python run.py`

The FastAPI server also serves the built SPA from `frontend/dist` when present
(`cd frontend && npm run build`, then restart the backend).

API reference: http://127.0.0.1:8000/docs

## Local datasets

Several endpoints depend on large datasets that are **not committed** to git.
Place them under `src/data/` (exact paths the code expects):

| Dataset | Path |
|---|---|
| CREEDS disease signatures | `src/data/CREEDS/disease_signatures-v1.0.json` |
| CREEDS single-drug perturbations | `src/data/CREEDS/single_drug_perturbations-v1.0.json` |
| DrugBank full database | `src/data/drugBank/full database.xml` |
| GEO expression data | `src/data/geneCards/GEO DATA.xlsx` (sheet `REFER THIS `) |
| PPI Excel sheets | `src/data/PPInteraction/xlsxData/*.xlsx` |
| PPI images | `src/data/PPInteraction/*.png` |

Until the files are provisioned, the affected endpoints return a structured
`503` response naming the missing dataset. Check `GET /api/health` for a live
report of which datasets are available.

## Production

- Frontend: Netlify (`netlify.toml`, set `VITE_API_BASE_URL` in Netlify env).
- API: any Python host (Render/Railway/EC2/Docker). Set `ALLOWED_ORIGINS` to your
  Netlify origin(s). See `.env.example`.

```bash
# Container
docker build -t remedix-api .
docker run -p 8000:8000 --env-file .env remedix-api
```

## Project layout

```
main.py               FastAPI app: CORS, /data static, /api router, SPA serving
src/routers/          route table + handlers
src/clients/          PubChem, DrugBank, ChEMBL, CREEDS, GeneCards integrations
src/utils/            scoring math + Excel loaders
src/data_availability.py  dataset registry & health checks
frontend/             React SPA (Vite)
Dockerfile            API image
docker-compose.yaml   local Postgres (reserved for planned data migration)
.github/workflows/    CI
CONTEXT.md            working map of the codebase + roadmap
```
