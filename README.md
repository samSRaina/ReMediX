# drugRepurpose-app

FastAPI app for compound lookup, bioactivity exploration, and disease-direction gene matching workflows.

## Run locally

```bash
python -m uvicorn main:app --reload
```

App routes:
- `/` Home (compound lookup + bioactivity)
- `/geneMatch` Directional therapeutic effect
- `/geneExpressions` Gene expression browser
- `/excelViewer` Dataset viewer

## Validation in this environment

```bash
python -m compileall src main.py
```

## Core API endpoints

- `GET /api/compound/name/{name}/properties`
- `GET /api/compound/smile/{smile}/properties`
- `GET /api/drugbank/inchikey/{inchikey}/properties`
- `GET /api/chembl/inchikey/{inchikey}/bioactivity`
- `GET /api/geneExpressions`
- `GET /api/diseaseSignature/table`
- `GET /api/diseases`

## Cancellable job endpoints

Long-running operations now support job lifecycle + cancellation:

- `POST /api/jobs/match`
  - body: `{ "genes": ["GENE1", "GENE2"], "disease": "..." }`
- `POST /api/jobs/finalGeneScore`
  - body: `{ "genes": ["GENE1", "GENE2"], "disease": "..." }`
- `POST /api/jobs/diseaseSignatureTable`
  - body: `{ "disease": "...", "page": 1, "page_size": 100 }`
- `GET /api/jobs/{job_id}` (status)
- `GET /api/jobs/{job_id}/result` (completed result)
- `POST /api/jobs/{job_id}/cancel` (cooperative cancellation)

Job statuses: `queued`, `running`, `cancelling`, `cancelled`, `completed`, `failed`.

