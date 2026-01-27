from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from src.routers import api, views

app = FastAPI()
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent / "src" / "static"), name="static")
app.include_router(api.router)
app.include_router(views.router)