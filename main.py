from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from src.routers import api


app = FastAPI()

# Add CORS middleware to allow the Netlify frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Recommend updating this to your Netlify URL once deployed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "src" / "data"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST_DIR / "index.html"
FRONTEND_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"

app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")
app.include_router(api.router)

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
