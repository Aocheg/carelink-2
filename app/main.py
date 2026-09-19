from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", description="Clinical care coordination API")
from app.workflows.routes import r as workflow_router
app.include_router(workflow_router)


@app.get("/app", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse("frontend/index.html")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}
