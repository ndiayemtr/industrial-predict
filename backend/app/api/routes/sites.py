from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.site import SiteCreate, SiteRead, SiteUpdate
from app.services.site_service import SiteService


router = APIRouter(
    prefix="/sites",
    tags=["Sites"],
)


@router.get(
    "",
    response_model=list[SiteRead],
)
def get_sites(db: Session = Depends(get_db)):
    service = SiteService(db)
    return service.get_all()


@router.get(
    "/{site_id}",
    response_model=SiteRead,
)
def get_site(
    site_id: int,
    db: Session = Depends(get_db),
):
    service = SiteService(db)

    site = service.get_by_id(site_id)

    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    return site


@router.get(
    "/company/{company_id}",
    response_model=list[SiteRead],
)
def get_sites_by_company(
    company_id: int,
    db: Session = Depends(get_db),
):
    service = SiteService(db)

    return service.get_by_company_id(company_id)


@router.post(
    "",
    response_model=SiteRead,
    status_code=status.HTTP_201_CREATED,
)
def create_site(
    data: SiteCreate,
    db: Session = Depends(get_db),
):
    service = SiteService(db)

    try:
        return service.create(data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.patch(
    "/{site_id}",
    response_model=SiteRead,
)
def update_site(
    site_id: int,
    data: SiteUpdate,
    db: Session = Depends(get_db),
):
    service = SiteService(db)

    site = service.get_by_id(site_id)

    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    try:
        return service.update(site, data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.delete(
    "/{site_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_site(
    site_id: int,
    db: Session = Depends(get_db),
):
    service = SiteService(db)

    site = service.get_by_id(site_id)

    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found",
        )

    service.delete(site)

    return None