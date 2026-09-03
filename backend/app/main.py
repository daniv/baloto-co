"""FastAPI application entrypoint: the app instance."""

from fastapi import FastAPI

from app.core.config import settings
from app.games.router import baloto_router, miloto_router, revancha_router

app = FastAPI(
    title=settings.name,
    version=settings.version,
    description=settings.description,
)


@app.get("/")
async def read_root() -> dict[str, str]:
    """Return a trivial health-check response."""
    return {"Hello": "World"}


for router in (miloto_router, baloto_router, revancha_router):
    app.include_router(router)
