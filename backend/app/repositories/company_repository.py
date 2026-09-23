from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company


class CompanyRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[Company]:
        statement = select(Company).order_by(Company.id)
        return list(self.db.scalars(statement).all())

    def get_by_id(self, company_id: int) -> Company | None:
        statement = select(Company).where(Company.id == company_id)
        return self.db.scalar(statement)

    def get_by_code(self, code: str) -> Company | None:
        statement = select(Company).where(Company.code == code)
        return self.db.scalar(statement)

    def create(self, company: Company) -> Company:
        self.db.add(company)
        self.db.flush()
        self.db.refresh(company)

        return company

    def update(self, company: Company) -> Company:
        self.db.flush()
        self.db.refresh(company)

        return company

    def delete(self, company: Company) -> None:
        self.db.delete(company)
        self.db.flush()
        
    def get_paginated(
        self,
        *,
        offset: int,
        limit: int,
    ) -> list[Company]:
        statement = (
            select(Company)
            .order_by(Company.id.asc())
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )


    def count_all(self) -> int:
        statement = select(
            func.count(Company.id)
        )

        return self.db.execute(
            statement
        ).scalar_one()