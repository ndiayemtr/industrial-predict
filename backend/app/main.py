from app.core.config import settings
from fastapi import FastAPI;
from app.api.routes.companies import router as companies_router

app = FastAPI(
    title=settings.app_name,
    description="API de maintenance prédictive industrielle",
    version=settings.app_version,
)

@app.get("/health")
def health_check():
    return {
        "environment": settings.app_env,
        "status": "healthy"
        }

app.include_router(
    companies_router,
    prefix="/api/v1",
)