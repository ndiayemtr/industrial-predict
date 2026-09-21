from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.dashboard import DashboardRead
from app.services.dashboard_service import DashboardService


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get(
    "",
    response_model=DashboardRead,
)
def get_dashboard(
    company_id: int = Query(..., gt=0),
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    site_id: int | None = Query(default=None, gt=0),
    equipment_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    service = DashboardService(db)

    try:
        return service.get_dashboard(
            company_id=company_id,
            start_time=start_time,
            end_time=end_time,
            site_id=site_id,
            equipment_id=equipment_id,
        )

    except ValueError as exc:
        detail = str(exc)

        if detail in {
            "Company not found",
            "Site not found",
            "Equipment not found",
            "Equipment site not found",
        }:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc