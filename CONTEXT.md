# ReMediX — Project Context

> Generated for future work sessions. Read this before touching the codebase.
> Last verified against commit `42984c2` (branch `copilot/implement-drug-repurposing-scoring`).
> **2026 update**: Phases 0–3 of the hardening roadmap below are IMPLEMENTED (see §10).

## 1. What this project is

**ReMediX** is a drug-repurposing analysis web app: it takes a compound (by name or
SMILES), resolves its chemistry and protein targets, then scores how "therapeutically
aligned" the compound is against a chosen **disease** by comparing drug-induced gene
perturbation directions against disease gene-expression directions.

Two tiers of analysis:
1. **Compound workflow** (HomePage): PubChem identity → DrugBank annotation → ChEMBL
   bioactivity table with gene symbols → pass the derived gene set into scoring.
2. **Scoring workflows**:
   - `/api/match` + `/api/finalGeneScore` — gene-set level scoring via CREEDS
     perturbation direction consensus (beneficial/harmful counts, Final Score).
   - `/api/remedix/inchikey/{key}/score` — compound-level ReMediX Score (0–100),
     combining CREEDS direction consensus (DC) with ChEMBL activity strength.

## 2. Architecture (as-is)

```
run.py                     dev launcher: uv run fastapi + npm run dev (frontend/)
main.py                    FastAPI app: CORS ×2, /data static mount, /api router,
                           SPA serving from frontend/dist when built, SPA fallback
src/
  routers/api.py           route table (prefix /api)
  routers/api_handlers.py  all endpoint handlers (async defs, mostly sync work inside)
  clients/
    pubchem_client.py      PubChem REST (requests, 10s timeout) — works, no cache
    drugbank_client.py     lxml iterparse over src/data/drugBank/full database.xml
    chembl_client.py       chembl-webresource-client SDK wrapper + class-level dict
                           caches + ThreadPoolExecutor(10) batch target fetching
    creeds_client.py       CREEDS datasets (lru_cache) + direction consensus logic
    geneCards_client.py    GEO DATA.xlsx via pandas (lru_cache)
  utils/
    remedix_scoring.py     compound-level score math (DC × activity strength)
    final_gene_score.py    gene-set score + Excel sheet loader (openpyxl, lru_cache)
    gene_scorer.py         standalone script, mutates data_set.xlsx (one-off tool)
    set_creator.py         standalone script, mutates data_set.xlsx (one-off tool)
  data/                    (mostly ABSENT locally — see §4)
frontend/                  React 18 + Vite 7 + TS 5 + Tailwind 3 + headlessui
  src/pages/*              9 pages; api.ts typed client; types/api.ts response models
  vite.config.ts           dev proxy /api and /data → 127.0.0.1:8000
netlify.toml               Netlify build (base frontend/, SPA redirect)
docker-compose.yaml        postgres-only skeleton (unused; .env required, malformed
                           indentation, POSTGRES_DATABASE vs POSTGRES_DB mismatch)
architecture.md             aspirational DDD layout — NOT the actual structure
srs-document.pdf           software requirements spec (199 KB, untracked? — it's in
                           repo root; requirements source of truth)
```

### Endpoint inventory (17 API routes)

| Route | Handler | Deps | Status when data missing |
|---|---|---|---|
| `GET /api/health` | data_availability | filesystem | ✅ 200 status report (NEW) |
| `GET /api/compound/name/{name}/properties` | PubChem | external API | ✅ works |
| `GET /api/compound/smile/{smile}/properties` | PubChem | external API | ✅ works |
| `GET /api/drugbank/inchikey/{key}/properties` | DrugBank | `full database.xml` | ✅ 503 dataset_not_provisioned |
| `GET /api/chembl/inchikey/{key}/bioactivity` | ChEMBL | external API | ✅ works (bounded + cached now) |
| `GET /api/chembl/.../target` | ChEMBL target | external API | ✅ works |
| `GET /api/match` | CREEDS match | 2 CREEDS JSONs | ✅ 503 dataset_not_provisioned |
| `GET /api/finalGeneScore` | CREEDS+final | 2 CREEDS JSONs | ✅ 503 dataset_not_provisioned |
| `GET /api/remedix/inchikey/{key}/score` | ChEMBL+CREEDS+scoring | both | ✅ 503 dataset_not_provisioned |
| `GET /api/geneAnalysis/accession/{id}` | CREEDS | 2 CREEDS JSONs | ✅ 503 dataset_not_provisioned |
| `GET /api/diseaseSignature/table` | CREEDS | signatures JSON | ✅ 503 dataset_not_provisioned |
| `GET /api/diseases` | CREEDS | signatures JSON | ✅ 503 dataset_not_provisioned |
| `GET /api/geneExpressions` | geneCards | `GEO DATA.xlsx` | ✅ 503 dataset_not_provisioned |
| `GET /api/geneExpressions/images` | filesystem | `src/data/PPInteraction/` images | ✅ 503 dataset_not_provisioned |
| `GET /api/excelData/meta` | openpyxl | `PPInteraction/xlsxData/` | ✅ 503 dataset_not_provisioned |
| `GET /api/excelData/sheet` | openpyxl | `PPInteraction/xlsxData/` | ✅ 503 dataset_not_provisioned |
| `GET /` + SPA fallback | filesystem | `frontend/dist` | ✅ works when built |

## 3. Verified runtime facts (this machine, 2026 session)

- **Python**: system 3.14.7 at `C:\Python314`; project requires `>=3.14`.
  **uv 0.12.9** installed at `C:\Users\saman\.local\bin\uv.exe` (installer used;
  NOT on PATH by default — prepend `C:\Users\saman\.local\bin` per shell).
  `uv sync` works; venv at `.venv`.
  - ⚠️ venv creation via plain `python -m venv` + ensurepip hits sandbox
    tempfile issues; `uv` is the sanctioned workflow.
- **Node**: v24.20.0 at `E:\Program Files\nodejs`. `npm install` + `npm run build`
  in `frontend/` succeed (1856 modules, ~250 KB gz bundle). `dist/` now exists.
- **External APIs reachable**: PubChem ✅ (fast), ChEMBL ✅ (EBI, works but the
  chembl-webresource-client paginates activities at limit=20 — ~28+ HTTP calls for
  CHEMBL1000; observed >45 s wall time under probing).
- **git**: NOT installed on PATH. Repo is a clean clone of
  `https://github.com/samSRaina/ReMediX.git`, branch
  `copilot/implement-drug-repurposing-scoring` @ `42984c2`, 14 remote `copilot/*`
  branches exist; NO main/master branch in this clone. `.git/lfs` absent —
  **no LFS objects were ever fetched**.

## 4. The core defect: missing data files (graceful degradation required)

All heavy datasets are gitignored (`/src/data/CREEDS`, `/src/data/drugBank/`,
`/src/data/PPInteraction`, `/src/data/data_set.xlsx`, plus `geneCards/GEO DATA.xlsx`
via the broad `src/data` comment) and are **absent from this clone**. Exact expected
paths (all resolved relative to `src/`):

| File / dir | Expected path | Used by |
|---|---|---|
| Disease signatures | `src/data/CREEDS/disease_signatures-v1.0.json` | creeds_client |
| Drug perturbations | `src/data/CREEDS/single_drug_perturbations-v1.0.json` | creeds_client |
| Disease sig table (generated) | `src/data/CREEDS/disease_signature_table.json` | written by export fn |
| DrugBank XML | `src/data/drugBank/full database.xml` | drugbank_client |
| GEO data | `src/data/geneCards/GEO DATA.xlsx`, sheet `REFER THIS ` (trailing space!) | geneCards_client |
| PPI Excel files | `src/data/PPInteraction/xlsxData/*.xlsx` (10 files, numbered) | final_gene_score, PPI page |
| PPI images | `src/data/PPInteraction/*.png` (7 files, numbered) | images endpoint, PPI page |

User decision: **user will copy the real files into `src/data` later**; until then
endpoints must degrade gracefully (structured 503 "dataset not provisioned" listing
the missing file) instead of raw 500s. Postgres migration is a **future** task, not now.

## 5. Known bugs & code smells (audit findings)

### Bugs (high priority)
1. **CORS middleware added twice** in `main.py` (lines 13–20 and 43–50): the first
   is `allow_origins=["*"]` + `allow_credentials=True` (invalid combo per CORS spec
   — Starlette silently ignores credentials in that case), the second reads env
   vars. Duplicate middleware runs both; the first one wins for preflights. Must be
   consolidated into one.
2. **500 instead of structured 503** on every missing-data path (see §4).
3. **Blocking sync work inside async handlers**: `api_handlers.py` handlers are
   `async def` but call requests/lxml/pandas directly — blocks the event loop
   (ChEMBL pagination 45 s+ = frozen server for other users). Needs
   `run_in_threadpool` or real async HTTP.
4. **chembl-webresource-client pagination**: `list(self.activity.filter(...))`
   fetches 20 records per HTTP call (see INFO logs) — hundreds of round trips for
   well-studied compounds. Also `executor.map` without consuming results hides
   exceptions; ThreadPoolExecutor created per request (not pooled).
5. **Class-level mutable caches** (`ChEMBLClient._target_cache` / `_activities_cache`)
   shared across instances/requests with no lock — dict races under concurrency,
   unbounded growth (memory leak in long-running prod).
6. **`docker-compose.yaml` broken**: 2-space indentation makes `services:` nested
   under nothing (actually `services` is at col 2 → invalid), `env_file: .env` where
   no `.env` exists, `${POSTGRES_*}` unbound, `postgres_dat` volume name typo-ish,
   `POSTGRES_DATABASE` vs healthcheck's `POSTGRES_DB` mismatch. It cannot boot as-is.
7. **`get_available_diseases` catches broad `Exception` then raises 500 with str(e)** —
   leaks internals; should follow the same graceful-degradation policy.
8. **Duplicate config pairs**: `frontend/vite.config.{ts,js}` and
   `frontend/tailwind.config.{ts,js}` both exist (identical content). Vite loads the
   `.ts` one; the `.js` twins are dead weight and drift risk.
9. **Root `package.json`** contains only a stray `build` dependency — junk from an
   experiment; `package-lock.json` at root also tracks it. Should be removed.
10. **`run.py` uses `fastapi run`** (fastapi-cli) — fine — but backend command
    prefers `uv` via PATH which is not on PATH on this machine by default.

### Design smells (medium)
- No `.env.example`, no settings module, no 12-factor config; secrets/config ad hoc.
- `sources.json` timestamps are literal `"ISO_TIMESTAMP"` placeholders.
- No tests at all; no lint/format config for Python.
- `logging.basicConfig` at module import inside clients (fights app-level logging).
- `gene_scorer.py` / `set_creator.py` mutate the Excel dataset in place — dev-time
  scripts shipped inside the app package.
- SPA fallback `@app.get("/{full_path:path}")` is registered only when
  `frontend/dist` exists at import time — after a fresh clone without build, the
  app serves the JSON notice forever until restart (import-time coupling).
- Frontend `GeneMatchPage` fetches ALL pages of the disease signature table
  sequentially then stitches (N+1 pattern) — should be a server-side "all rows" param.
- `creeds_client.export_disease_signature_table` writes a file into `src/data` as a
  side effect of a GET request (non-idempotent, breaks on read-only FS containers).

### Scoring-logic notes (explicitly OUT of scope for now — user decision 2026 session)
User: scoring model is NOT final, but for the time being only infra is modified.
Recorded for later:
- `_load_single_gene_perturbation_index` counts FULL up/down lists of every
  experiment touching a gene (an experiment with ~5000 up-genes adds 5000 to a
  gene's up_count) — consensus can be swamped by single huge signatures.
- `_compute_ratio` treats denominator 0 as 1 (arbitrary floor).
- `RATIO_THRESHOLD = 1.1` module constant; `compute_beneficial_score` default 1.2.
- ChEMBL activity type → action mapping is hard-coded (`IC50/Ki=INHIBITION`,
  `AC50=ACTIVATION`) — pharmacology simplification.
- `final_gene_score` denominator = beneficial+harmful sums only (genes with no
  disease match contribute nothing to denominator).

## 6. Environment setup (this machine)

```powershell
# Backend (from repo root)
$env:Path = "C:\Users\saman\.local\bin;$env:Path"   # uv not on PATH by default
uv sync                                              # create/update .venv
uv run uvicorn main:app --port 8000                  # production-style serve
# or: uv run fastapi run main.py  (what run.py does; adds --reload in dev)

# Frontend (from frontend/)
npm install
npm run build        # tsc -b && vite build → frontend/dist (served by FastAPI)
npm run dev          # vite dev server :5173, proxies /api,/data → :8000

# Combined dev (repo root) — launches both
uv run python run.py
```

- Backend alone: http://127.0.0.1:8000 (API + SPA when dist built; /docs for OpenAPI).
- Frontend dev: http://127.0.0.1:5173.
- CORS env vars understood by main.py: `ALLOWED_ORIGINS` (comma list, default `*`),
  `ALLOWED_ORIGIN_REGEX`. `VITE_API_BASE_URL` sets frontend API base (default '' →
  same origin / proxy).

## 7. Decisions locked in for the production effort (2026 session)

1. **Scope**: fix bugs + error handling; containerize + CI/CD. Tests and the DDD
   restructure are NOT selected for now (may come later).
2. **Data files**: graceful degradation with clear structured errors now; user
   copies real data into `src/data` later; Postgres migration deferred.
3. **Deployment target**: **Netlify frontend + separate API host** (matches
   netlify.toml + ALLOWED_ORIGINS support). CORS hardening is therefore required
   (consolidated middleware, env-driven origins, credentials only with explicit
   origins).
4. **Scoring logic**: treat as frozen for now (fix crashes only); correctness review
   deferred to a dedicated later effort.

## 8. Production-hardening roadmap

> **Status: Phases 0–3 implemented 2026 — see §10 for the record. Phase 4 (post-data
> verification) runs when the datasets are copied into `src/data`.**

**Phase 0 — hygiene (immediate)**
- Remove duplicate `vite.config.js` / `tailwind.config.js`, stray root `package.json`
  + `package-lock.json`.
- Add `.env.example` (+ `frontend/.env.example`), `.dockerignore`, `README.md`.

**Phase 1 — correctness fixes**
- Single CORS middleware (env-driven, credentials-safe), drop the `*`+credentials one.
- Graceful dataset registry: a small `src/data_availability.py` (or similar) that
  checks all expected files at startup and per-request; handlers raise a structured
  `HTTPException(503, "Dataset 'CREEDS disease signatures' not provisioned:
  src/data/CREEDS/disease_signatures-v1.0.json missing")`. `/api/health` (or
  `/api/ready`) endpoint exposing dataset status.
- Stop blocking the loop: wrap sync client calls with `fastapi.concurrency.run_in_threadpool`
  (or make PubChem httpx-async). Bound ChEMBL pagination (cap + optional standard_type
  pushdown); reuse a single ThreadPoolExecutor.
- Fix `get_available_diseases` broad catch; never leak raw exception strings.
- Make `export_disease_signature_table` not write to disk on GET (or move to explicit
  admin/CLI action).
- Lock-safe caches: per-process locks or TTL cache (e.g. cachetools) for ChEMBL
  target/activity caches; consider `requests-cache` (already a transitive dep of
  chembl client) for PubChem.

**Phase 2 — containerization**
- Backend `Dockerfile` (python:3.14-slim, uv-based, non-root user, `frontend/dist`
  COPY optional since deployment splits), `.dockerignore` (venv, node_modules, data).
- Fix `docker-compose.yaml` (indentation, `POSTGRES_DB`, healthcheck, named volume)
  so `docker compose up` boots postgres for future migration work.
- Optional compose service for the API for local prod-parity.

**Phase 3 — CI/CD**
- GitHub Actions: backend job (uv sync, `python -m compileall` / ruff if added,
  uvicorn smoke boot + hit /api/health), frontend job (npm ci, build, typecheck).
- Netlify build already configured via netlify.toml; set `VITE_API_BASE_URL` in
  Netlify env; API host env: `ALLOWED_ORIGINS=https://<netlify-domain>`.

**Phase 4 — post-data verification (once user copies files in)**
- Re-probe all 17 endpoints against real data; verify ChEMBL enrichment speed,
  CREEDS matching, Excel viewer, PPI links/images.
- Then (separate effort, user-scoped later): scoring-logic audit and Postgres
  migration per architecture.md direction.

## 9. Gotchas for future sessions

- Sheet name `"REFER THIS "` has a **trailing space** — matters when reading GEO DATA.
- Excel paths contain spaces: `full database.xml`, `GEO DATA.xlsx` — quote in shells.
- `src/data` subtree is gitignored: `git status` won't remind you data is missing;
  use the new health endpoint (once added) or check paths directly.
- Frontend `npm run build` output `frontend/dist` is served by FastAPI only if it
  existed at **import time** — rebuilds require server restart to take effect.
- The repo's `architecture.md` does NOT describe current reality; `srs-document.pdf`
  is the requirements source; this file is the code reality map.
- Windows: long paths + spaces; `uv` not on PATH; `git` not on PATH (this clone was
  made elsewhere/with another tool; raw `.git` inspection works via filesystem).
- Chembl client logs every HTTP call at INFO to stderr — noisy; lower logger level
  (`chembl_webresource_client`) when cleaning logs.
- `lru_cache` on dataset loaders means file changes after first load are invisible
  until process restart (dev annoyance; document or add cache invalidation).

## 10. Implementation record — 2026 hardening session (Phases 0–3 DONE)

All verification below ran on this machine after each change.

### Phase 0 — hygiene (DONE)
- Deleted `frontend/vite.config.js`, `frontend/tailwind.config.js` (`.ts` twins remain authoritative).
- Deleted stray root `package.json` + `package-lock.json` (only contained a `build` dep).
- Added `.env.example` (backend CORS + reserved Postgres vars), `frontend/.env.example`
  (`VITE_API_BASE_URL`), `.dockerignore`, `README.md`.

### Phase 1 — correctness (DONE)
- **`src/data_availability.py` (NEW)**: dataset registry (`DatasetSpec`, `_BoundedCache`-free
  status map with lock). `require_dataset(key…)` raises `DatasetNotProvisionedError` →
  mapped to **503 JSON** `{"detail", "error": "dataset_not_provisioned", "dataset", "expectedPath"}`.
  `health_payload()` backs **`GET /api/health`** (200, `status: "ok"|"degraded"`, per-dataset map).
  Status is re-checked per call (`refresh=True` in health; guards use cached).
- **`main.py` rewritten**: ONE CORS middleware (env-driven `ALLOWED_ORIGINS` +
  `ALLOWED_ORIGIN_REGEX`; default `*` WITHOUT credentials + startup warning);
  `allow_methods=["GET"]`; exception handlers for dataset-missing (503), HTTPException
  (JSON bodies), RequestValidationError (field-level, no internals); quieted the
  ChEMBL SDK logger to WARNING; health route.
- **`src/routers/api_handlers.py` rewritten**: every data-dependent handler calls
  `require_dataset(...)` first; ALL blocking client work wrapped in
  `fastapi.concurrency.run_in_threadpool` (event loop never blocks on HTTP/pandas/lxml);
  `/api/diseaseSignature/table` now uses `build_disease_signature_table` (pure) instead of
  `export_…` (which wrote a file to disk on GET — side effect removed from request path);
  `get_available_diseases` no longer has the broad-catch 500.
- **`src/clients/chembl_client.py`**: thread-safe bounded caches (`_BoundedCache`, FIFO
  eviction: targets 20k, activities 500); shared process-wide `ThreadPoolExecutor(8)`
  with `submit`/`result` (exceptions surfaced, not swallowed by `executor.map`);
  **pagination capped via QuerySet slicing** (`activity.filter(...)[:2000]`) — the SDK's
  `get_page` stops at the slice stop, so this bounds both payload and HTTP calls;
  raised `Settings.Instance().MAX_LIMIT` 20→100 (5× fewer round trips; SDK reads it
  at query time; must be set before first query construction — done under the lazy
  import lock); failed batches/lookups are NOT cached (retryable).
  Live-verified: CHEMBL1000 = 485 activities in ~13 s first fetch, **0.02 s cached**
  (SDK's requests-cache sqlite), batch target filter OK.
- **`src/clients/pubchem_client.py`**: URL-encodes inputs (`requests.utils.quote`);
  explicit malformed-JSON guard (`KeyError/IndexError/ValueError`); removed module-level
  `logging.basicConfig` (side effect); verified aspirin by name AND by SMILES (quoting
  does not break SMILES paths).
- **`src/clients/creeds_client.py`**: `encoding='utf-8'` on all `open()`s (Windows was
  using cp1252 — would have crashed on CREEDS gene names with non-ASCII);
  `export_disease_signature_table` documented as CLI/admin-only (no longer on GET path).

### Phase 2 — containerization (DONE)
- **`Dockerfile` (NEW)**: `python:3.14-slim` + official uv image copy; layer-cached
  `uv sync --frozen --no-dev --no-install-project`; non-root `remedix` user; HEALTHCHECK
  against `/api/health`; CMD `uvicorn main:app --host 0.0.0.0 --port 8000`.
  Datasets are NOT baked in — mount `./src/data:/app/src/data:ro` (compose does this).
- **`docker-compose.yaml` fixed**: valid top-level `services:`; `postgres:16-alpine`;
  `POSTGRES_DB` (was `POSTGRES_DATABASE`, mismatched the healthcheck); `pg_isready`
  healthcheck with `$$` escaping; named volume `postgres_data`; `api` service building
  the Dockerfile, mounting data read-only, optional `.env`; `depends_on: service_healthy`.
  YAML structure validated via PyYAML (Docker not installed on this machine — image
  build is exercised by CI).

### Phase 3 — CI/CD (DONE)
- **`.github/workflows/ci.yaml` (NEW)**: three jobs on push/PR:
  `backend` (uv sync --frozen, compileall, import check, uvicorn boot + /api/health curl
  loop), `frontend` (npm ci, typecheck, build), `docker` (buildx image build, GHA cache,
  only after the first two pass). Concurrency group cancels superseded runs.
  All backend/frontend steps verified locally: compileall exit 0, typecheck exit 0,
  build exit 0, boot + health 200.
- Netlify: `netlify.toml` unchanged; set `VITE_API_BASE_URL` in Netlify env and
  `ALLOWED_ORIGINS` on the API host when deploying.

### Post-change endpoint verification (all on this machine)
- `/api/health` → 200 `status: degraded` with per-dataset paths (expected: no data yet).
- All 10 data-dependent endpoints → **503** with structured payload naming dataset + path
  (was raw 500 FileNotFoundError).
- PubChem name+SMILES → 200; ChEMBL target lookup → 200; SPA `/` → 200.
- Frontend `tsc --noEmit` clean; `vite build` clean (248 KB gz 77.6 KB).

### Bioactivity AC50/IC50/Ki correctness fix (2026 session #2)
- **Defect found**: filtered bioactivity queries (AC50/IC50/Ki) were served from a
  `[:2000]`-capped UNFILTERED fetch, then standard_type-filtered client-side. For
  well-studied compounds (CHEMBL25/aspirin: 4087 activities) the cap silently truncated
  per-type results (client saw IC50 388 vs true 458, Ki 144 vs 152, AC50 **1 vs 133**) —
  gene sets and scoring inputs were incomplete. Exact-match filtering also meant any
  case-variant input (`ki`) returned nothing. The no-data fallback refetched everything
  unfiltered; SDK HTTP errors (BaseHttpException) escaped the `except ConnectionError`
  503 mapping.
- **Fix** (`src/clients/chembl_client.py`, `src/routers/api_handlers.py`):
  - `parse_activity_types()` canonicalises user input (case-insensitive, multi-value,
    `KI`→`Ki`, list/string/None accepted) — stable sorted tuple as cache key.
  - **Server-side filter pushdown**: typed fetches use
    `activity.filter(molecule_chembl_id=…, standard_type__in=[…])` — the API returns the
    COMPLETE per-type row set (verified: aspirin IC50 458 / Ki 152 / AC50 133 = 743;
    combined `standard_type__in` REST form returns exactly 743 = 458+152+133).
    ChEMBL's data API rejects POST (405) — the SDK's GETs with
    `X-HTTP-Method-Override: GET` are the only working transport; slice caps stay
    (unfiltered 2000 / typed 5000) and now LOG a warning when truncation occurs
    (`_warn_if_truncated` reads `api_total_count` off the *sliced* queryset — filter()
    and [:n] both return clones).
  - `get_by_inchikey`, `get_gene_set`, `get_aggregated_targets_by_inchikey` all use the
    typed fetch; aggregation compares upper-cased forms (emits `activity_type: "KI"` per
    the historical contract — scoring + frontend compare case-insensitively).
  - `_resolve_molecule_chembl_id()` cached (inchi_key→chembl_id, failures never cached);
    molecule lookup sliced `[:1]`. `has_bioactivity_data()` = 1-row existence probe; the
    bioactivity handler uses it for the no-data 404 instead of a full unfiltered refetch.
  - `_get_target_cached` degrades to `{}` (→ `'--'` enrichment) on target fetch failure
    instead of 500-ing the whole response.
- **Live verification** (fresh caches each run, real API): aspirin IC50=458, Ki=152,
  AC50=133 (case variants `ki`/`KI`/`ac50` all OK); combined 743; aggregated targets
  155 genes / 465 measurements — exact match to an independent recount of gene-symbol-
  bearing rows (278 rows target gene-symbol-less targets, skipped by design as before);
  CHEMBL1000 IC50 23 / Ki 11 / AC50 123 (under cap — matches pre-fix behavior).
  Endpoint tests (uvicorn): 200s, cold typed fetch ~4.5 s then ~0.02–0.05 s cached;
  unknown compound → 404; `/api/remedix/.../score` → 200 with score 0.1173 (raw
  activities path still the bounded unfiltered 2000-row view); target endpoint 200.

### Scoring policies spec v2 — configurable & traceable (2026 session #3)
- **Why**: the 21-step pipeline spec (pvt.txt, updated v2) resolved the 4 open architectural
  questions; implementation makes them explicit, configurable policies with full traceability
  (Option B). ChEMBL Step 3 now mandates **median** aggregation; Step 9 a **bounded log ramp**
  (`max(0, min(1, 1-(log10(nM)-1)/3))`) with **0.5 default** for missing nM; Step 8 U==D →
  AMBIGUOUS + UNRESOLVED + 0 contribution; Step 21 original ChEMBL type casing.
- **`src/utils/scoring_policies.py` (NEW)**: frozen `ScoringPolicies` dataclass —
  `assay_aggregation` (median|min|mean, default median), `activity_strength_model`
  (log_ramp|legacy_inverse_log, default log_ramp), `missing_activity_strength` (default 0.5),
  `ambiguous_policy` (unresolved|exclude, default unresolved). `from_env()` reads
  `REMEDIX_SCORING_*` vars; `with_overrides()` for per-request; `describe()` snapshot embedded
  in every response. Illegal values → ValueError (→ 422 at the endpoint).
- **`src/utils/remedix_scoring.py` (rewritten)**: `_representative_nm()` collapses per-gene
  valid nM values by policy (median default); `_activity_strength_from_nm()` implements both
  models, returns `(strength, defaulted_flag)`; legacy model hardened (denominator ≤ 0 → 1.0 —
  the historic 10 nM `ZeroDivisionError` can never recur, asserted by tests). Gene records
  carry traceability: `representative_value_nm`, `representative_aggregation`,
  `valid_measurement_count`, `activity_strength_defaulted`, `activity_type` in original ChEMBL
  casing (`["AC50","IC50","Ki"]`). Response embeds `"policies"`. `CONSENSUS_WEIGHT=0.7` /
  `POTENCY_WEIGHT=0.3` named constants. Legacy behavioral note: `min`-aggregation +
  `legacy_inverse_log` reproduces the old scores exactly (verified: aspirin vs "cocaine
  dependence" raw -0.6948 legacy vs -0.6765 spec v2).
- **`src/clients/chembl_client.py`**: measurements gain `standard_type` (original casing);
  per-type `activity_summary` gains `median_value_nm` (min-based
  `representative_value_nm` kept for display continuity; scoring uses the policy value).
- **`src/routers/api_handlers.py`**: `/api/remedix/inchikey/{key}/score` accepts optional
  validated query params `assay_aggregation`, `strength_model`, `missing_activity_strength`
  (0–1), `ambiguous_policy`; effective policies echoed in `scoring.policies`
  (request > env > spec default).
- **`frontend/src/types/api.ts`**: `ScoringPoliciesInfo` + new optional traceability fields
  (no page changes; `tsc --noEmit` clean).
- **`tests/test_scoring_policies.py` (NEW)**: 20 tests, stdlib unittest runner
  (`python -m tests.test_scoring_policies`) + pytest compatible, network-free (CREEDS
  consensus mocked). Covers: log_ramp anchors (1/10/100 nM→1.0/1.0/0.667, 10 µM→0) and
  monotonicity; legacy 10 nM crash regression + anchors (100→1.0, 1 µM→0.5, 10 µM→0.333);
  median (odd/even, invalid-ignored, none-valid) / min / mean; missing-value default +
  configurability; U==D unresolved-vs-exclude; policy validation; env loading; end-to-end
  fixture with hand-computed B/H/coverages/public score; policy echo.
- **Verification**: 20/20 tests green; `compileall` clean; `tsc --noEmit` clean; live endpoint
  A/B — spec defaults raw −0.6765 vs legacy −0.6948 vs missing=0.9 raw −0.749 (all 200);
  all 5 illegal param values → 422; ADORA3 median (30000 nM, 2 measurements) hand-verified;
  exclude-ambiguous drops 14 rows (70→56) with matched count and B/H unchanged (those genes
  contribute 0 by definition).

### Gene-level Traceability UI + "identical output for every medicine" investigation (2026 session #3, cont.)
- **User symptom**: the Gene-level Traceability table on GeneMatchPage showed the same 2 rows
  (MMP9 BENEFICIAL 0.850, PTGS1 HARMFUL) "for multiple medicines". Suspected stale state/cache.
- **Investigation result — NOT a bug; three compounding data realities** (all verified against
  the live ChEMBL REST API, bypassing our client and its sqlite cache):
  1. The matrix only contains the intersection of the compound's typed targets with the
     disease signature. "pulmonary hypertension" has 600 signature genes; aspirin's 155 typed
     targets ∩ 600 = 2 genes (MMP9, PTGS1). Small matrices are the norm for targeted diseases
     vs HTS-panel-rich compounds — aspirin had 48 of 333 diseases with a 2-gene intersection.
  2. Many deposited rows are **DRUGMATRIX-style HTS panel data with `standard_value: null`**
     (aspirin: 287/743 typed rows 39% null; paracetamol 64% null). The MMP9 rows for aspirin,
     paracetamol, metformin, sildenafil etc. all come from the same DRUGMATRIX panel
     (doc CHEMBL1909046, assay CHEMBL1909197) — so those compounds genuinely share
     `target={MMP9,PTGS1}, strength=defaulted 0.5` rows on this disease. Verified live: each
     of 9 medicines (aspirin, paracetamol, diclofenac, metformin, warfarin, sildenafil, statin,
     losartan, amlodipine) returns matched=2 with identical gene rows. Not a cache leak:
     per-(inchikey, type-tuple) cache keys were audited and cross-drug outputs verified
     distinct where the data differs (ibuprofen/celecoxib/naproxen → 3 rows incl. ALOX5).
  3. The old UI hid the cause: strength 0.500 rendered identically for "measured 0.5" and
     "no usable value → policy default".
- **Fix — surface the traceability that the API already returned**
  (`valid_measurement_count`, `activity_strength_defaulted`, `representative_value_nm`,
  `representative_aggregation` were in the payload since spec v2 but never displayed):
  - `GeneMatchPage.tsx`: table gains **Activity Types** (original ChEMBL casing), **Rep. Value
    (nM)** with aggregation mode, **N mM Data** (`valid/total` measurements), and a
    **"no potency data"** amber badge on defaulted rows; context line explains matrix size
    ("2 of the compound's 155 targets appear in the 600-gene disease signature") and the
    DRUGMATRIX duplication effect; explainer banner when any row is defaulted.
  - `types/api.ts`: `disease_total`, `target_gene_total`, `matched_target_count` added to
    `RemedixScoringSummary` (non-optional; backend already always sends them).
  - `HomePage.tsx` + `api_handlers.py` (same session, earlier): bioactivity tab switch no
    longer re-fetches static gene_set/aggregated_targets (`include=activities` slice; first
    load per compound fetches `include=all`).
- **Verification**: `tsc --noEmit` clean, `compileall` clean, 20/20 tests green; live flow
  through uvicorn: 20 medicines × "pulmonary hypertension" batch-scored — outputs vary by
  drug where data varies (identical groups are data-real, e.g. 9 medicines share the
  DRUGMATRIX MMP9+PTGS1 rows); vite serves the updated page (new columns present in served
  module).
- **Design note for future sessions**: strength 0.5 defaults make DRUGMATRIX-heavy rows
  contribute 0.85×DC — if that overcredits valueless HTS evidence, consider a policy like
  `missing_activity_strength=0` or excluding `standard_value IS NULL` rows at fetch; both are
  now one-line config/routing changes.

### Still open (from §5, not in this session's scope)
- Blocking-but-bounded ChEMBL work still runs in threadpool workers (fine); a full
  httpx/async rewrite is optional future work.
- Frontend GeneMatchPage N+1 table fetch pattern (§5) untouched.
- `sources.json` placeholder timestamps; dev scripts `gene_scorer.py`/`set_creator.py`
  still mutate Excel in place; scoring-logic audit deferred (§5 notes stand).
- Tests: CI does compile/import/boot smoke; a real pytest suite remains future work.
- Postgres migration: compose + env reserved, schema work not started.
