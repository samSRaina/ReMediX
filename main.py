import logging
import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.data_availability import DatasetNotProvisionedError
from src.routers import api

logger = logging.getLogger("remedix")

app = FastAPI(title="ReMediX API", version="0.1.0")


# --- Logging -----------------------------------------------------------------
# Quiet the very chatty ChEMBL SDK logger (logs every HTTP call at INFO).
logging.getLogger("chembl_webresource_client").setLevel(logging.WARNING)


# --- CORS ---------------------------------------------------------------------
def _get_allowed_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _get_allowed_origin_regex() -> str | None:
    raw = os.getenv("ALLOWED_ORIGIN_REGEX", "").strip()
    return raw or None


_allowed_origins = _get_allowed_origins()
_allowed_origin_regex = _get_allowed_origin_regex()

if _allowed_origins or _allowed_origin_regex:
    # Explicit origins configured (production): credentials are safe to allow.
    allow_credentials = True
    if not _allowed_origins:
        logger.info("CORS: allowing origins matching regex %s", _allowed_origin_regex)
else:
    # No configuration: allow everything but WITHOUT credentials. Sending
    # Access-Control-Allow-Credentials together with "*" is forbidden by the
    # CORS spec and silently broken in browsers.
    _allowed_origins = ["*"]
    allow_credentials = False
    logger.warning(
        "CORS: ALLOWED_ORIGINS is not set; allowing all origins without credentials. "
        "Set ALLOWED_ORIGINS in production (e.g. your Netlify URL)."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=_allowed_origin_regex,
    allow_credentials=allow_credentials,
    allow_methods=["GET"],
    allow_headers=["*"],
    max_age=3600,
)


# --- Error handling -----------------------------------------------------------
@app.exception_handler(DatasetNotProvisionedError)
async def dataset_not_provisioned_handler(request: Request, exc: DatasetNotProvisionedError) -> JSONResponse:
    """Missing local dataset -> structured 503 naming the file that is absent."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": str(exc),
            "error": "dataset_not_provisioned",
            "dataset": exc.status.key,
            "expectedPath": exc.status.missing_path,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Keep HTTP exceptions as-is, but ensure JSON bodies (some default 404s
    from static mounts return plain-text otherwise)."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return field-level validation errors without leaking internals."""
    errors = [
        {"field": ".".join(str(part) for part in err.get("loc", [])), "message": err.get("msg", "Invalid value")}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Validation failed", "errors": errors})


# --- Static data & API ----------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "src" / "data"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST_DIR / "index.html"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")
app.include_router(api.router)


# --- Health ---------------------------------------------------------------------
@app.get("/api/health", tags=["health"])
async def health() -> dict:
    """Dataset availability report. 200 when fully provisioned, 200 with
    status=degraded when datasets are missing (still JSON, still informative)."""
    from src.data_availability import health_payload

    return health_payload()


# Serve React SPA in this branch when build output exists.
if FRONTEND_INDEX.exists():
    if FRONTEND_ASSETS_DIR.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/geneMatch", include_in_schema=False)
    @app.get("/geneExpressions", include_in_schema=False)
    @app.get("/excelViewer", include_in_schema=False)
    @app.get("/ppiInteraction", include_in_schema=False)
    async def serve_spa_entry() -> FileResponse:
        return FileResponse(FRONTEND_INDEX)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # This fallback only runs after mounted and API routes fail to match.
        return FileResponse(FRONTEND_INDEX)
else:
    @app.get("/", include_in_schema=False)
    async def frontend_not_built() -> dict[str, str]:
        return {
            "detail": "Frontend build not found. Build React UI in frontend/ and run backend again."
        }
