from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from .config import BASE_DIR, settings
from .database import Base, engine
from .routers import parser

FRONTEND_BUILD = BASE_DIR.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="SkillBridge API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(parser.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


class SinglePageApp(StaticFiles):
    """Serves the built frontend, sending page routes like /student to index.html."""

    async def get_response(self, path, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or scope["path"].startswith("/api/"):
                raise
            return await super().get_response("index.html", scope)


if FRONTEND_BUILD.exists():
    app.mount("/", SinglePageApp(directory=FRONTEND_BUILD, html=True))
