import { Page, ReferencePageQuery } from '../../../core/models/page.model';
import { CompanyRead } from '../../../core/models/reference-data.model';

export interface CompaniesQuery extends ReferencePageQuery {
  page: number;
  page_size: number;
}

export type CompaniesState =
  | { status: 'idle' }
  | { status: 'loading'; query: Readonly<CompaniesQuery> }
  | { status: 'success' | 'empty'; query: Readonly<CompaniesQuery>; data: Page<CompanyRead> }
  | { status: 'error'; query: Readonly<CompaniesQuery>; error: { message: string; retryable: boolean } };
