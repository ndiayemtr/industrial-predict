from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.site import Site


class SiteRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_paginated(
        self,
        *,
        offset: int,
        limit: int,
    ) -> list[Site]:
        statement = (
            select(Site)
            .order_by(Site.id.asc())
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def count_all(self) -> int:
        statement = select(func.count(Site.id))
        return self.db.execute(statement).scalar_one()

    def get_all(self) -> list[Site]:
        statement = select(Site).order_by(Site.id)
        return list(self.db.scalars(statement).all())

    def get_by_id(self, site_id: int) -> Site | None:
        statement = select(Site).where(Site.id == site_id)
        return self.db.scalar(statement)

    def get_by_code(self, code: str) -> Site | None:
        statement = select(Site).where(Site.code == code)
        return self.db.scalar(statement)

    def get_by_company_id(self, company_id: int) -> list[Site]:
        statement = (
            select(Site)
            .where(Site.company_id == company_id)
            .order_by(Site.id)
        )
        return list(self.db.scalars(statement).all())

    def create(self, site: Site) -> Site:
        self.db.add(site)
        self.db.flush()
        self.db.refresh(site)
        return site

    def update(self, site: Site) -> Site:
        self.db.flush()
        self.db.refresh(site)
        return site

    def delete(self, site: Site) -> None:
        self.db.delete(site)
        self.db.flush()
