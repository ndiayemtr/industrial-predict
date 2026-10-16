export interface SiteCreate {
  name: string;
  // Site codes are globally unique, including across companies.
  code: string;
  company_id: number;
  description?: string | null;
}

// MVP subset of FastAPI SiteUpdate: company transfers are deliberately excluded.
// Null name/code are accepted by Pydantic but can fail SQL NOT NULL constraints.
// Form validation belongs to the future UI, not to this transport model.
export interface SiteUpdate {
  name?: string | null;
  code?: string | null;
  description?: string | null;
}
