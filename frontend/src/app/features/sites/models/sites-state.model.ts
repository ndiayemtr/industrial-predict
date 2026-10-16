import { Page } from '../../../core/models/page.model';
import { SiteRead } from '../../../core/models/reference-data.model';
import { SiteListQuery } from './site-list-query.model';

export interface SitesQuery extends SiteListQuery {
  page: number;
  page_size: number;
}

export type SitesState =
  | { status: 'idle' }
  | { status: 'loading'; query: Readonly<SitesQuery> }
  | { status: 'success' | 'empty'; query: Readonly<SitesQuery>; data: Page<SiteRead> }
  | { status: 'error'; query: Readonly<SitesQuery>; message: string; retryable: boolean };
