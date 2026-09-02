"""FastAPI application entrypoint: the app instance"""

from fastapi import FastAPI

from app.core.config import settings
from app.games.router import build_game_router

app = FastAPI(
    title=settings.name,
    version=settings.version,
    description=settings.description,
)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


for game in ("miloto", "baloto", "revancha"):
    app.include_router(build_game_router(game))
