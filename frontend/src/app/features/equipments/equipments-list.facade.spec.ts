import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { EquipmentsListFacade } from './equipments-list.facade';

const company = { id: 7, name: 'Entreprise test', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7, name: 'Usine' };
const equipment = { ...company, id: 12, site_id: 9, equipment_type: 'Pompe', status: 'operational', criticality: 'high' };
const page = { items: [equipment], total: 1, page: 1, page_size: 20, pages: 1 };
const query = { company_id: 7, site_id: 9, page: 1, page_size: 20 };

describe('EquipmentsListFacade scope and cancellation', () => {
  let facade: EquipmentsListFacade;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), EquipmentsListFacade] });
    facade = TestBed.inject(EquipmentsListFacade); http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.expectNone(req => req.method !== 'GET'); http.verify(); });
  const list = () => http.expectOne(req => req.url === '/api/v1/equipments');
  function parents() { http.expectOne('/api/v1/companies/7').flush(company); http.expectOne('/api/v1/sites/9').flush(site); }

  it('waits for explicit parents and never reads an unscoped equipment list', () => {
    facade.load({ page: 1, page_size: 20 }); expect(facade.state().status).toBe('idle');
    facade.load({ company_id: 7, page: 1, page_size: 20 });
    http.expectOne('/api/v1/companies/7').flush(company);
    expect(facade.state().status).toBe('idle'); expect(facade.site()).toBeNull(); http.expectNone(() => true);
  });
  it('checks both parents before requesting exact filters without company_id', () => {
    facade.load({ ...query, search: 'Pompe', status: 'maintenance', criticality: 'critical', page: 3, page_size: 50 });
    expect(facade.state().status).toBe('loading'); http.expectNone(req => req.url === '/api/v1/equipments');
    parents(); const req = list();
    expect(req.request.params.keys().sort()).toEqual(['criticality', 'page', 'page_size', 'search', 'site_id', 'status']);
    expect(req.request.params.get('site_id')).toBe('9'); expect(req.request.params.get('status')).toBe('maintenance');
    expect(req.request.params.get('criticality')).toBe('critical'); expect(req.request.params.get('search')).toBe('Pompe');
    expect(req.request.params.get('page')).toBe('3'); expect(req.request.params.get('page_size')).toBe('50');
    req.flush(page); expect(facade.state()).toEqual({ status: 'success', data: page });
  });
  it('resolves the actual company for an explicit site-only link', () => {
    facade.load({ site_id: 9, page: 1, page_size: 20 });
    http.expectOne('/api/v1/sites/9').flush(site); http.expectOne('/api/v1/companies/7').flush(company);
    list().flush(page); expect(facade.query()?.company_id).toBe(7); expect(facade.site()).toEqual(site);
  });
  it('blocks a company/site mismatch without requesting equipment', () => {
    facade.load(query); http.expectOne('/api/v1/companies/7').flush(company);
    http.expectOne('/api/v1/sites/9').flush({ ...site, company_id: 8 });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: false });
    expect(facade.site()).toBeNull(); http.expectNone(() => true);
  });
  it.each([0, -1, NaN, Number.MAX_SAFE_INTEGER + 1])('rejects invalid parent %s without breaking subsequent loads', id => {
    facade.load({ ...query, company_id: id }); expect(facade.state().status).toBe('error');
    facade.load({ ...query, site_id: id }); http.expectOne('/api/v1/companies/7').flush(company);
    expect(facade.state().status).toBe('error');
    facade.load(query); parents(); list().flush(page); expect(facade.state().status).toBe('success');
  });
  it.each(['company', 'site'])('rejects a mismatched returned %s reference', type => {
    facade.load(query);
    http.expectOne('/api/v1/companies/7').flush(type === 'company' ? { ...company, id: 8 } : company);
    if (type === 'site') http.expectOne('/api/v1/sites/9').flush({ ...site, id: 10 });
    expect(facade.state().status).toBe('error'); http.expectNone(() => true);
  });
  it('rejects equipment returned from another site', () => {
    facade.load(query); parents(); list().flush({ ...page, items: [{ ...equipment, site_id: 10 }] });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: false });
  });
  it('cancels obsolete reference requests', () => {
    facade.load(query); const obsolete = http.expectOne('/api/v1/companies/7');
    facade.load(null); expect(obsolete.cancelled).toBe(true); expect(facade.state().status).toBe('idle');
    expect(facade.company()).toBeNull(); expect(facade.site()).toBeNull();
  });
  it('cancels obsolete equipment requests and immediately removes old data', () => {
    facade.load(query); parents(); const obsolete = list(); facade.load(null);
    expect(obsolete.cancelled).toBe(true); expect(facade.state()).toEqual({ status: 'idle' });
    facade.load(query); parents(); list().flush(page); facade.load({ ...query, site_id: 10 });
    expect(facade.state()).toEqual({ status: 'loading' }); expect(facade.site()).toBeNull();
    http.expectOne('/api/v1/companies/7').flush(company); http.expectOne('/api/v1/sites/10').flush({ ...site, id: 10 });
    list().flush({ ...page, items: [], total: 0, pages: 0 }); expect(facade.state().status).toBe('empty');
  });
  it.each([0, 401, 403, 404, 422, 500])('handles HTTP %s and retries only safe transient reads', status => {
    facade.load(query); parents();
    if (status === 0) list().error(new ProgressEvent('error')); else list().flush({}, { status, statusText: 'Error' });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: status === 0 || status >= 500 });
    facade.retry();
    if (status === 0 || status >= 500) { parents(); list().flush(page); expect(facade.state().status).toBe('success'); }
    http.expectNone(() => true);
  });
  it('preserves a positive total on a page out of range', () => {
    facade.load({ ...query, page: 99 }); parents(); list().flush({ ...page, items: [], page: 99 });
    expect(facade.state()).toMatchObject({ status: 'success', data: { total: 1, page: 99 } });
  });
});
