from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from src.routers import api


app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "src" / "data"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST_DIR / "index.html"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")
app.include_router(api.router)


def _spa_index_response() -> FileResponse:
    response = FileResponse(FRONTEND_INDEX)
    # Avoid stale SPA shell in browsers/CDNs so latest hashed assets and routing logic are used.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Serve React SPA in this branch when build output exists.
if FRONTEND_INDEX.exists():
    if FRONTEND_ASSETS_DIR.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="assets")

    @app.get("/", include_in_schema=False)
    @app.get("/geneMatch", include_in_schema=False)
    @app.get("/gene_match", include_in_schema=False)
    @app.get("/geneExpressions", include_in_schema=False)
    @app.get("/excelViewer", include_in_schema=False)
    @app.get("/ppiInteraction", include_in_schema=False)
    async def serve_spa_entry() -> FileResponse:
        return _spa_index_response()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # This fallback only runs after mounted/static/api routes fail to match.
        return _spa_index_response()
else:
    @app.get("/", include_in_schema=False)
    async def frontend_not_built() -> dict[str, str]:
        return {
            "detail": "Frontend build not found. Build React UI in frontend/ and run backend again."
        }
