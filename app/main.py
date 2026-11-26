from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.database import Base, engine
from app.routers import ai, applications, auth


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Simple schema bootstrap; swap for Alembic migrations as the schema grows.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=get_settings().app_name,
    version="1.0.0",
    description="Track job applications and score your resume against job descriptions.",
    lifespan=lifespan,
)
app.include_router(auth.router)
app.include_router(applications.router)
app.include_router(ai.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
