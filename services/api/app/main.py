from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import auth, classes, exceptions, lessons, materials, packets, student


def add_routes(api: FastAPI) -> None:
    api.include_router(auth.router)
    api.include_router(classes.router)
    api.include_router(materials.router)
    api.include_router(lessons.router)
    api.include_router(packets.router)
    api.include_router(student.router)
    api.include_router(exceptions.router)

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}


def create_app() -> FastAPI:
    api = FastAPI(title="Class Catch-Up API", version="0.1.0")
    add_routes(api)

    web_dist = Path(__file__).resolve().parents[3] / "apps" / "web" / "dist"
    if web_dist.is_dir():
        browser_api = FastAPI(
            title="Class Catch-Up API",
            version="0.1.0",
            docs_url=None,
            redoc_url=None,
            openapi_url=None,
        )
        add_routes(browser_api)
        api.mount("/api", browser_api)
        api.mount("/", StaticFiles(directory=web_dist, html=True), name="web")

    return api


app = create_app()
