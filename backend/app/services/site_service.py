from sqlalchemy.orm import Session

from app.models.site import Site
from app.repositories.company_repository import CompanyRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.site import SiteCreate, SiteUpdate


class SiteService:

    def __init__(self, db: Session):
        self.db = db
        self.repository = SiteRepository(db)
        self.company_repository = CompanyRepository(db)

    def get_all(self) -> list[Site]:
        return self.repository.get_all()

    def get_by_id(self, site_id: int) -> Site | None:
        return self.repository.get_by_id(site_id)

    def get_by_company_id(self, company_id: int) -> list[Site]:
        return self.repository.get_by_company_id(company_id)

    def create(self, data: SiteCreate) -> Site:
        # Vérifier que la Company existe
        company = self.company_repository.get_by_id(data.company_id)

        if company is None:
            raise ValueError(
                f"Company with id '{data.company_id}' does not exist."
            )

        # Vérifier que le code du Site est unique
        existing_site = self.repository.get_by_code(data.code)

        if existing_site:
            raise ValueError(
                f"Site with code '{data.code}' already exists."
            )

        site = Site(
            name=data.name,
            code=data.code,
            description=data.description,
            company_id=data.company_id,
        )

        self.repository.create(site)

        self.db.commit()
        self.db.refresh(site)

        return site

    def update(self, site: Site, data: SiteUpdate) -> Site:
        update_data = data.model_dump(exclude_unset=True)

        # Vérifier le nouveau company_id s'il est modifié
        if "company_id" in update_data:
            company = self.company_repository.get_by_id(
                update_data["company_id"]
            )

            if company is None:
                raise ValueError(
                    f"Company with id '{update_data['company_id']}' does not exist."
                )

        # Vérifier l'unicité du code
        if "code" in update_data:
            existing_site = self.repository.get_by_code(
                update_data["code"]
            )

            if existing_site and existing_site.id != site.id:
                raise ValueError(
                    f"Site with code '{update_data['code']}' already exists."
                )

        # Appliquer les modifications
        for field, value in update_data.items():
            setattr(site, field, value)

        self.repository.update(site)

        self.db.commit()
        self.db.refresh(site)

        return site

    def delete(self, site: Site) -> None:
        self.repository.delete(site)

        self.db.commit()