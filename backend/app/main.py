from app.core.config import settings
from fastapi import FastAPI;
from app.api.routes.companies import router as companies_router
from app.api.routes.sites import router as sites_router
from app.api.routes.equipment import router as equipment_router
from app.api.routes.sensors import router as sensors_router
from app.api.routes.measurements import router as measurements_router
from app.api.routes.maintenance import router as maintenance_router
from app.api.routes.dashboard import router as dashboard_router

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

app.include_router(
    sites_router,
    prefix="/api/v1",
)

app.include_router(
    equipment_router,
    prefix="/api/v1",
)

app.include_router(
    sensors_router,
    prefix="/api/v1",
)

app.include_router(
    measurements_router,
    prefix="/api/v1",
)

app.include_router(
    maintenance_router,
    prefix="/api/v1",
)

app.include_router(
    dashboard_router,
    prefix="/api/v1",
)