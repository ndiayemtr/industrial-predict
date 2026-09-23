from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.company import (
    CompanyCreate,
    CompanyRead,
    CompanyUpdate,
)
from app.services.company_service import CompanyService
from app.schemas.pagination import Page


router = APIRouter(
    prefix="/companies",
    tags=["Companies"],
)


@router.get(
    "",
    response_model=Page[CompanyRead],
)
def get_companies(
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
):
    service = CompanyService(db)

    return service.get_paginated(
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{company_id}",
    response_model=CompanyRead,
)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
):
    service = CompanyService(db)

    company = service.get_by_id(company_id)

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    return company


@router.post(
    "",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_company(
    data: CompanyCreate,
    db: Session = Depends(get_db),
):
    service = CompanyService(db)

    try:
        return service.create(data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.patch(
    "/{company_id}",
    response_model=CompanyRead,
)
def update_company(
    company_id: int,
    data: CompanyUpdate,
    db: Session = Depends(get_db),
):
    service = CompanyService(db)

    company = service.get_by_id(company_id)

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    try:
        return service.update(company, data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.delete(
    "/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
):
    service = CompanyService(db)

    company = service.get_by_id(company_id)

    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    service.delete(company)

    return None