from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.workflows.routes import r as workflow_router

settings = get_settings()
if settings.environment.lower() not in {"development", "test"} and settings.secret_key.startswith("development-only"):
    raise RuntimeError("CARELINK_SECRET_KEY must be set to a strong secret outside development/test")
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="CARELINK clinical care coordination system — independent implementation.",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(workflow_router)

@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parent.parent / "frontend" / "index.html")

@app.get("/app", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parent.parent / "frontend" / "index.html")

@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment, "version": app.version}
