import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { SitesListFacade } from './sites-list.facade';

const company = { id: 7, name: 'Entreprise', code: 'C7', description: null, created_at: '', updated_at: '' };
const query = { company_id: 7, page: 1, page_size: 20 };
const empty = { items: [], total: 0, page: 1, page_size: 20, pages: 0 };

describe('SitesListFacade', () => {
  let facade: SitesListFacade;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), SitesListFacade] });
    facade = TestBed.inject(SitesListFacade);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.expectNone(req => req.method !== 'GET'); http.verify(); });
  const sites = () => http.expectOne(req => req.url === '/api/v1/sites');
  const parent = (id = 7) => http.expectOne(`/api/v1/companies/${id}`);

  it('starts idle and waits for a verified explicit company before listing sites', () => {
    expect(facade.state().status).toBe('idle'); facade.retry(); http.expectNone(() => true);
    const mutable = { ...query };
    facade.load(mutable); mutable.company_id = 9;
    expect(facade.query()).toEqual(query); expect(Object.isFrozen(facade.query())).toBe(true);
    http.expectNone(req => req.url === '/api/v1/sites');
    parent().flush(company);
    const req = sites(); expect(req.request.params.get('company_id')).toBe('7');
    req.flush(empty); expect(facade.state().status).toBe('empty');
  });

  it('distinguishes a truly empty list from an out-of-range page', () => {
    facade.load(query); parent().flush(company); sites().flush(empty);
    expect(facade.state().status).toBe('empty');
    facade.load({ ...query, page: 8 }); parent().flush(company);
    sites().flush({ ...empty, page: 8, total: 21, pages: 2 });
    expect(facade.state().status).toBe('success');
  });

  it('cancels obsolete parent checks, site reads and reads cleared by deselection', () => {
    facade.load(query); const oldParent = parent();
    facade.load({ ...query, company_id: 9 }); expect(oldParent.cancelled).toBe(true);
    parent(9).flush({ ...company, id: 9 }); const oldSites = sites();
    facade.load({ ...query, search: 'Recent' }); expect(oldSites.cancelled).toBe(true);
    parent().flush(company); const current = sites();
    facade.load(null); expect(current.cancelled).toBe(true);
    expect(facade.state().status).toBe('idle'); expect(facade.company()).toBeNull();
  });

  it('reports a missing company as an error and never requests its sites', () => {
    facade.load(query); parent().flush({ detail: 'Not found' }, { status: 404, statusText: 'Not found' });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: false });
    expect(JSON.stringify(facade.state())).toContain('Cette entreprise');
    facade.retry(); http.expectNone(() => true);
  });

  it.each([0, 403, 422, 500])('handles site error %s with a manual retry only when appropriate', status => {
    facade.load(query); parent().flush(company);
    const req = sites();
    if (status === 0) req.error(new ProgressEvent('error'));
    else req.flush({ detail: 'Error' }, { status, statusText: 'Error' });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: status === 0 || status >= 500 });
    facade.retry();
    if (status === 0 || status >= 500) { parent().flush(company); sites().flush(empty); expect(facade.state().status).toBe('empty'); }
    else http.expectNone(() => true);
  });

  it('cancels outstanding reads on destruction', () => {
    facade.load(query); parent().flush(company); const req = sites();
    TestBed.resetTestingModule(); expect(req.cancelled).toBe(true);
  });
});
