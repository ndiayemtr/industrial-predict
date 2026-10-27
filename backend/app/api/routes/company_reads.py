"""Opt-in company detail read adapter; no historical router/runtime or default access."""

from collections.abc import Callable
from dataclasses import dataclass
from inspect import iscoroutinefunction

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.schemas.company import CompanyRead
from app.services.company_service import CompanyService


@dataclass(frozen=True, repr=False)
class CompanyReadAuthorization:
    """Server-provider result, not a token or independently authenticated proof.

    Only a trusted provider that already checked the subject's identity and
    company read permission may issue this result. Never build it from a client
    body, header or company_id alone. This adapter supplies no authentication.
    """

    subject_id: str
    company_id: int
    permission: str


class CompanyReadRouterError(ValueError):
    """Constant construction diagnostic without provider or request values."""


def create_company_read_router(
    *,
    authorize_company_read: Callable[[Request, int], CompanyReadAuthorization],
) -> APIRouter:
    """Build only the detail GET. The mandatory server provider is synchronous.

    The provider receives Request and the requested resource id; it must resolve
    trusted authentication/permissions itself and return a typed authorization.
    Denials, invalid results and provider errors fail closed before SQL acquisition.
    Mount explicitly on an isolated application; no DEV/production wiring here.
    """
    if (not callable(authorize_company_read) or iscoroutinefunction(authorize_company_read)
            or iscoroutinefunction(getattr(authorize_company_read, "__call__", None))):
        raise CompanyReadRouterError("COMPANY_READ_AUTHORIZER_REQUIRED")

    def require_authorization(request: Request, company_id: int) -> CompanyReadAuthorization:
        grant = None
        try:
            grant = authorize_company_read(request, company_id)
        except Exception:
            grant = None
        if (type(grant) is not CompanyReadAuthorization
                or type(grant.subject_id) is not str or not grant.subject_id.strip()
                or type(grant.company_id) is not int or grant.company_id < 1
                or grant.company_id != company_id
                or type(grant.permission) is not str or grant.permission != "companies:read"):
            raise HTTPException(403, "COMPANY_READ_FORBIDDEN") from None
        return grant

    def authorized_db(
        authorization: CompanyReadAuthorization = Depends(require_authorization),
        db: Session = Depends(get_db),
    ) -> Session:
        # Dependency order is intentional: access is checked before get_db.
        return db

    router = APIRouter(prefix="/api/v1/companies", tags=["Companies"])

    @router.get("/{company_id}", response_model=CompanyRead)
    def get_company(company_id: int, db: Session = Depends(authorized_db)):
        company = CompanyService(db).get_by_id(company_id)
        if company is None:
            raise HTTPException(404, "Company not found")
        if type(company.id) is not int or company.id != company_id:
            raise HTTPException(503, "COMPANY_READ_UNAVAILABLE")
        return company

    return router
