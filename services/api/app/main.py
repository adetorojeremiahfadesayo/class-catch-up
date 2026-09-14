from fastapi import FastAPI

from app.routes import auth, classes, exceptions, lessons, materials, packets, student


def create_app() -> FastAPI:
    api = FastAPI(title="Class Catch-Up API", version="0.1.0")
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

    return api


app = create_app()
