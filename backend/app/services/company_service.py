from sqlalchemy.orm import Session

from app.models.company import Company
from app.repositories.company_repository import CompanyRepository
from app.schemas.company import (
    CompanyCreate,
    CompanyUpdate,
)
from app.core.pagination import build_page


class CompanyService:

    def __init__(self, db: Session):
        self.db = db
        self.repository = CompanyRepository(db)

    def get_all(self) -> list[Company]:
        return self.repository.get_all()

    def get_by_id(self, company_id: int) -> Company | None:
        return self.repository.get_by_id(company_id)

    def create(self, data: CompanyCreate) -> Company:
        existing_company = self.repository.get_by_code(data.code)

        if existing_company:
            raise ValueError(
                f"Company with code '{data.code}' already exists."
            )

        company = Company(
            name=data.name,
            code=data.code,
            description=data.description,
        )

        self.repository.create(company)
        self.db.commit()
        self.db.refresh(company)

        return company

    def update(
        self,
        company: Company,
        data: CompanyUpdate,
    ) -> Company:

        update_data = data.model_dump(
            exclude_unset=True,
        )

        if "code" in update_data:
            existing_company = self.repository.get_by_code(
                update_data["code"]
            )

            if (
                existing_company
                and existing_company.id != company.id
            ):
                raise ValueError(
                    f"Company with code "
                    f"'{update_data['code']}' already exists."
                )

        for field, value in update_data.items():
            setattr(company, field, value)

        self.repository.update(company)
        self.db.commit()
        self.db.refresh(company)

        return company

    def delete(self, company: Company) -> None:
        self.repository.delete(company)
        self.db.commit()
        
    def get_paginated(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
    ):
        offset = (page - 1) * page_size

        items = self.repository.get_paginated(
            offset=offset,
            limit=page_size,
            search=search,
        )

        total = self.repository.count_all(
            search=search,
        )

        return build_page(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )