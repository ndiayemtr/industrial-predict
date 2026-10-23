import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { MaintenanceListFacade } from './maintenance-list.facade';

const company = { id: 7, name: 'Entreprise', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7 };
const equipment = { ...company, id: 12, site_id: 9, equipment_type: 'pump', status: 'operational', criticality: 'high' };
const record = { id: 17, equipment_id: 12, maintenance_type: 'preventive', status: 'planned', priority: 'medium', title: 'Inspection',
 description: null, failure_code: null, root_cause: null, action_taken: null, technician: null, planned_at: null, started_at: null,
 completed_at: null, cost: null, downtime_minutes: null, created_at: '2026-10-23T12:00:00.123456', updated_at: '2026-10-23T12:00:00Z' };
const page = { items: [record], total: 1, page: 1, page_size: 20, pages: 1 };
const query = { company_id: 7, site_id: 9, equipment_id: 12, page: 1, page_size: 20 };

describe('MaintenanceListFacade verified scope and cancellation', () => {
  let facade: MaintenanceListFacade;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), MaintenanceListFacade] });
    facade = TestBed.inject(MaintenanceListFacade); http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { try { http.expectNone(req => req.method !== 'GET'); http.verify(); } finally { TestBed.resetTestingModule(); } });
  const list = () => http.expectOne(req => req.url === '/api/v1/maintenance');
  function parents() {
    http.expectOne('/api/v1/equipments/12').flush(equipment);
    http.expectOne('/api/v1/sites/9').flush(site);
    http.expectNone(req => req.url === '/api/v1/maintenance');
    http.expectOne('/api/v1/companies/7').flush(company);
  }

  it('waits for every explicit selection without choosing a first child', () => {
    facade.load({ page: 1, page_size: 20 }); expect(facade.state().status).toBe('idle');
    facade.load({ company_id: 7, page: 1, page_size: 20 });
    http.expectOne('/api/v1/companies/7').flush(company);
    expect(facade.site()).toBeNull(); expect(facade.state().status).toBe('idle');
    facade.load({ company_id: 7, site_id: 9, page: 1, page_size: 20 });
    http.expectOne('/api/v1/sites/9').flush(site); http.expectOne('/api/v1/companies/7').flush(company);
    expect(facade.equipment()).toBeNull(); expect(facade.state().status).toBe('idle'); http.expectNone(() => true);
  });
  it('validates the chain before sending only backend-recognized filters', () => {
    facade.load({ ...query, status: 'cancelled', search: 'mm/s', page: 3, page_size: 50 });
    parents(); const req = list();
    expect(req.request.params.keys().sort()).toEqual(['equipment_id', 'page', 'page_size', 'search', 'status']);
    expect(req.request.params.get('equipment_id')).toBe('12'); expect(req.request.params.get('status')).toBe('cancelled');
    expect(req.request.params.get('search')).toBe('mm/s'); expect(req.request.params.get('page')).toBe('3');
    expect(req.request.params.get('page_size')).toBe('50'); req.flush(page);
    expect(facade.state()).toEqual({ status: 'success', data: page });
  });
  it.each([{ equipment_id: 12 }, { site_id: 9 }, { company_id: 7, equipment_id: 12 }])('blocks incomplete explicit ancestors %s', scope => {
    facade.load({ ...scope, page: 1, page_size: 20 });
    expect(facade.state().status).toBe('error'); http.expectNone(() => true);
  });
  it.each(['2026-10-23T12:00:00', '', 'bad'])('blocks invalid periods %s before any read', start_time => {
    facade.load({ ...query, start_time }); expect(facade.state().status).toBe('error'); http.expectNone(() => true);
  });
  it('preserves precise offsets and all allowed filters', () => {
    const start_time = '2026-10-23T12:00:00.123456+02:00', end_time = '2026-10-23T10:00:00.123457Z';
    facade.load({ ...query, start_time, end_time, maintenance_type: 'predictive', priority: 'critical' }); parents(); const req = list();
    expect(req.request.params.get('start_time')).toBe(start_time); expect(req.request.params.get('end_time')).toBe(end_time);
    expect(req.request.params.get('maintenance_type')).toBe('predictive'); expect(req.request.params.get('priority')).toBe('critical'); req.flush(page);
  });
  it('reports an invalid response separately without an empty fallback', () => {
    facade.load(query); parents(); list().flush({ ...page, items: [{ ...record, cost: 'unknown' }] });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: false });
  });
  it.each(['equipment', 'site', 'company'])('rejects a returned %s id that differs from the requested reference', field => {
    facade.load(query); http.expectOne('/api/v1/equipments/12').flush(field === 'equipment' ? { ...equipment, id: 99 } : equipment);
    if (field !== 'equipment') http.expectOne('/api/v1/sites/9').flush(field === 'site' ? { ...site, id: 99 } : site);
    if (field === 'company') http.expectOne('/api/v1/companies/7').flush({ ...company, id: 99 });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: false }); http.expectNone(() => true);
  });
  it.each(['site', 'company'])('blocks inconsistent %s parentage', field => {
    facade.load(query); http.expectOne('/api/v1/equipments/12').flush(field === 'site' ? { ...equipment, site_id: 10 } : equipment);
    if (field === 'company') http.expectOne('/api/v1/sites/9').flush({ ...site, company_id: 8 });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: false }); expect(facade.equipment()).toBeNull(); http.expectNone(() => true);
  });
  it.each([0, -1, NaN, Number.MAX_SAFE_INTEGER + 1])('rejects invalid equipment %s locally and recovers on a valid selection', id => {
    facade.load({ ...query, equipment_id: id }); expect(facade.state().status).toBe('error'); http.expectNone(() => true);
    facade.load(query); parents(); list().flush(page); expect(facade.state().status).toBe('success');
  });
  it('rejects maintenance belonging to another equipment', () => {
    facade.load(query); parents(); list().flush({ ...page, items: [{ ...record, equipment_id: 99 }] });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: false });
  });
  it.each(['equipment', 'site', 'company', 'maintenance'])('cancels an obsolete %s read and clears old results', stage => {
    facade.load(query);
    if (stage !== 'equipment') http.expectOne('/api/v1/equipments/12').flush(equipment);
    if (stage === 'company' || stage === 'maintenance') http.expectOne('/api/v1/sites/9').flush(site);
    if (stage === 'maintenance') http.expectOne('/api/v1/companies/7').flush(company);
    const req = http.expectOne(stage === 'equipment' ? '/api/v1/equipments/12' : stage === 'site' ? '/api/v1/sites/9'
      : stage === 'company' ? '/api/v1/companies/7' : req => req.url === '/api/v1/maintenance');
    facade.load(null); expect(req.cancelled).toBe(true); expect(facade.state()).toEqual({ status: 'idle' });
    expect(facade.company()).toBeNull(); expect(facade.site()).toBeNull(); expect(facade.equipment()).toBeNull();
  });
  it.each([0, 401, 403, 404, 422, 500])('handles HTTP %s without automatic retries', status => {
    facade.load(query); parents();
    if (status === 0) list().error(new ProgressEvent('error')); else list().flush({}, { status, statusText: 'Error' });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: status === 0 || status >= 500 });
    facade.retry();
    if (status === 0 || status >= 500) { parents(); list().flush(page); expect(facade.state().status).toBe('success'); }
    http.expectNone(() => true);
  });
  it('keeps a positive total on an out-of-range page', () => {
    facade.load({ ...query, page: 99 }); parents(); list().flush({ ...page, items: [], page: 99 });
    expect(facade.state()).toMatchObject({ status: 'success', data: { total: 1, page: 99 } });
  });
});
