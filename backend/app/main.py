from app.core.config import settings
from fastapi import FastAPI;

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