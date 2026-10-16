import { ReferencePageQuery } from '../../../core/models/page.model';

// Explicit company selection is an MVP requirement, not tenant authorization.
// FastAPI bounds: company_id >= 1, page >= 1, page_size 1..100, search 1..100.
export interface SiteListQuery extends ReferencePageQuery {
  company_id: number;
}
