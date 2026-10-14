import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { DashboardFacade } from './dashboard.facade';
import { emptyDashboardResponse } from './testing/dashboard-testing';

const filters = { company_id: 7, start_time: '2026-10-01T00:00:00Z', end_time: '2026-10-08T00:00:00Z' };
describe('DashboardFacade', () => {
  let facade: DashboardFacade;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [DashboardFacade, provideHttpClient(), provideHttpClientTesting()] });
    facade = TestBed.inject(DashboardFacade); http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());
  const request = () => http.expectOne(req => req.url === '/api/v1/dashboard');

  it('starts idle without requests, applied filters or a refresh/retry action', () => {
    expect(facade.state()).toEqual({ status: 'idle' }); expect(facade.appliedFilters()).toBeNull();
    facade.refresh(); facade.retry(); expect(facade.canRefresh()).toBe(false); http.expectNone(() => true);
  });
  it('loads and preserves the unmodified response, including a site without measurements', () => {
    facade.applyFilters(filters); expect(facade.state().status).toBe('loading');
    const response = emptyDashboardResponse(); response.assets.sites = 1;
    request().flush(response);
    const state = facade.state(); expect(state.status).toBe('success');
    if (state.status === 'success') expect(state.data).toEqual(response);
  });
  it('uses empty only when every asset count is zero, even with zero-filled daily rows', () => {
    facade.applyFilters(filters); request().flush(emptyDashboardResponse());
    expect(facade.state().status).toBe('empty'); expect(facade.canRefresh()).toBe(true);
  });
  it('cancels an obsolete request when new filters are applied', () => {
    facade.applyFilters(filters); const old = request();
    facade.applyFilters({ ...filters, company_id: 8 }); expect(old.cancelled).toBe(true);
    const current = request(); expect(current.request.params.get('company_id')).toBe('8');
    current.flush(emptyDashboardResponse()); expect(facade.appliedFilters()?.company_id).toBe(8);
  });
  it('refreshes a copied snapshot rather than edited values and keeps its period fixed', () => {
    const edited = { ...filters }; facade.applyFilters(edited); request().flush(emptyDashboardResponse());
    edited.company_id = 99; edited.end_time = '2026-10-09T00:00:00Z';
    facade.refresh(); const req = request();
    expect(req.request.params.get('company_id')).toBe('7'); expect(req.request.params.get('end_time')).toBe(filters.end_time);
    facade.refresh(); http.expectNone(() => true); req.flush(emptyDashboardResponse());
  });
  it.each([400, 422, 404, 500])('classifies HTTP %s and retries only server errors', status => {
    facade.applyFilters(filters); request().flush({ detail: 'Test error' }, { status, statusText: 'Error' });
    const state = facade.state(); expect(state.status).toBe('error');
    if (state.status !== 'error') throw new Error('Expected error');
    expect(state.error.kind).toBe(status === 404 ? 'not-found' : status === 500 ? 'server' : 'validation');
    expect(state.error.retryable).toBe(status === 500);
    facade.retry();
    if (status === 500) request().flush(emptyDashboardResponse()); else http.expectNone(() => true);
  });
  it('allows a manual retry for a network error and then accepts new filters after an error', () => {
    facade.applyFilters(filters); request().error(new ProgressEvent('error'));
    const state = facade.state(); if (state.status !== 'error') throw new Error('Expected error');
    expect(state.error.kind).toBe('network'); facade.retry(); request().flush(emptyDashboardResponse());
    facade.applyFilters({ ...filters, equipment_id: 9 }); request().flush(emptyDashboardResponse());
    expect(facade.appliedFilters()?.equipment_id).toBe(9);
  });
  it.each([
    { ...filters, company_id: 0 }, { ...filters, start_time: 'invalid' },
    { ...filters, start_time: filters.end_time }, { ...filters, end_time: '2999-01-01T00:00:00Z' },
    { ...filters, start_time: '2026-10-01T00:00:00' }
  ])('ignores invalid filters without starting a request: %j', invalid => {
    facade.applyFilters(invalid); expect(facade.state().status).toBe('idle'); http.expectNone(() => true);
  });
  it('cancels pending work when the local injector is destroyed', () => {
    facade.applyFilters(filters); const req = request(); TestBed.resetTestingModule(); expect(req.cancelled).toBe(true);
  });
});
