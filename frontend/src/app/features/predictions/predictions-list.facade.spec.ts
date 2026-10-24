import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { PredictionsListFacade } from './predictions-list.facade';
import { PredictionRead } from './models/prediction.model';

const company = { id: 7, name: 'Entreprise', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7 };
const equipment = { ...company, id: 12, site_id: 9, equipment_type: 'pump', status: 'operational', criticality: 'high' };
const row: PredictionRead = { id: 17, equipment_id: 12, sensor_id: null, measurement_id: null, prediction_type: 'anomaly',
  score: 0.85, level: null, is_alert: false, model_name: null, model_version: null, horizon_hours: null, details: null,
  predicted_at: '2026-10-23T12:00:00.123456Z', created_at: '2026-10-23T12:00:01Z' };
const page = { items: [row], total: 1, page: 1, page_size: 20, pages: 1 };
const query = { company_id: 7, site_id: 9, equipment_id: 12, page: 1, page_size: 20 };

describe('PredictionsListFacade verified scope', () => {
  let facade: PredictionsListFacade, http: HttpTestingController;
  const list = (id = 12) => http.expectOne(req => req.url === `/api/v1/equipments/${id}/predictions`);
  function parents(id = 12) {
    http.expectOne(`/api/v1/equipments/${id}`).flush({ ...equipment, id });
    http.expectOne('/api/v1/sites/9').flush(site);
    http.expectNone(req => req.url.endsWith('/predictions'));
    http.expectOne('/api/v1/companies/7').flush(company);
  }
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), PredictionsListFacade] });
    facade = TestBed.inject(PredictionsListFacade); http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.expectNone(req => req.method !== 'GET' || /\/(rul|health-score)$/.test(req.url)); http.verify(); });

  it('waits for all explicit choices, verifying partial scopes without choosing descendants', () => {
    facade.load({ page: 1, page_size: 20 }); expect(facade.state().status).toBe('idle'); http.expectNone(() => true);
    facade.load({ company_id: 7, page: 1, page_size: 20 }); http.expectOne('/api/v1/companies/7').flush(company);
    expect(facade.company()?.id).toBe(7); expect(facade.site()).toBeNull(); expect(facade.state().status).toBe('idle');
    facade.load({ company_id: 7, site_id: 9, page: 1, page_size: 20 });
    http.expectOne('/api/v1/sites/9').flush(site); http.expectOne('/api/v1/companies/7').flush(company);
    expect(facade.equipment()).toBeNull(); http.expectNone(() => true);
  });
  it.each([{ equipment_id: 12 }, { site_id: 9 }, { company_id: 7, equipment_id: 12 }, { company_id: 0 }])('blocks missing/invalid ancestors %j', scope => {
    facade.load({ ...scope, page: 1, page_size: 20 }); expect(facade.state()).toMatchObject({ status: 'error', retryable: false }); http.expectNone(() => true);
  });
  it('sends only API filters after every real reference is verified', () => {
    const start_time = '2026-10-23T17:30:00.123456+05:30', end_time = '2026-10-23T12:00:00.123456Z';
    facade.load({ ...query, is_alert: false, prediction_type: 'rul', level: 'custom', start_time, end_time });
    parents(); const req = list(); expect(req.request.params.keys().sort()).toEqual(['page', 'page_size', 'is_alert', 'prediction_type', 'level', 'start_time', 'end_time'].sort());
    expect(req.request.params.get('is_alert')).toBe('false'); expect(req.request.params.get('start_time')).toBe(start_time);
    expect(req.request.params.get('end_time')).toBe(end_time); req.flush(page); expect(facade.state()).toEqual({ status: 'success', data: page });
  });
  it.each(['equipment', 'site', 'company'])('rejects contradictory real %s data without a Predictions GET', field => {
    facade.load(query);
    http.expectOne('/api/v1/equipments/12').flush(field === 'equipment' ? { ...equipment, site_id: 99 } : equipment);
    if (field !== 'equipment') http.expectOne('/api/v1/sites/9').flush(field === 'site' ? { ...site, company_id: 99 } : site);
    if (field === 'company') http.expectOne('/api/v1/companies/7').flush({ ...company, id: 99 });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: false }); expect(facade.company()).toBeNull(); http.expectNone(() => true);
  });
  it.each(['bad', '2026-10-23T12:00:00', ''])('blocks invalid times %s before any reference GET', start_time => {
    facade.load({ ...query, start_time }); expect(facade.state().status).toBe('error'); http.expectNone(() => true);
  });
  it('cancels obsolete history and never exposes old equipment data during a switch', () => {
    facade.load(query); parents(); const old = list();
    facade.load({ ...query, equipment_id: 13 }); expect(old.cancelled).toBe(true); expect(facade.state()).toEqual({ status: 'loading' });
    expect(facade.equipment()).toBeNull(); parents(13); list(13).flush({ ...page, items: [{ ...row, equipment_id: 13 }] });
    const state = facade.state(); expect(state.status).toBe('success'); if (state.status === 'success') expect(state.data.items[0].equipment_id).toBe(13);
    facade.load({ company_id: 8, page: 1, page_size: 20 }); expect(facade.equipment()).toBeNull(); expect(facade.company()).toBeNull();
    http.expectOne('/api/v1/companies/8').flush({ ...company, id: 8 }); expect(facade.state().status).toBe('idle');
  });
  it('cancels obsolete parent lookups and block clears results and references', () => {
    facade.load(query); const old = http.expectOne('/api/v1/equipments/12'); facade.block('URL invalide');
    expect(old.cancelled).toBe(true); expect(facade.query()).toBeNull(); expect(facade.state()).toMatchObject({ status: 'error', retryable: false }); http.expectNone(() => true);
  });
  it.each([false, true])('distinguishes empty history and out-of-range page: %s', out => {
    facade.load({ ...query, page: out ? 3 : 1 }); parents();
    list().flush({ ...page, items: [], total: out ? 1 : 0, pages: out ? 1 : 0, page: out ? 3 : 1 });
    expect(facade.state().status).toBe(out ? 'out-of-range' : 'empty');
  });
  it('rejects foreign response data and does not retry an invalid contract', () => {
    facade.load(query); parents(); list().flush({ ...page, items: [{ ...row, equipment_id: 99 }] });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: false }); facade.retry(); http.expectNone(() => true);
  });
  it.each([404, 422, 401, 403, 500, 503, 0])('handles status %s with manual retry only for network/5xx', status => {
    facade.load({ ...query, is_alert: false }); parents(); const req = list();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush({ detail: 'failure' }, { status, statusText: 'Failure' });
    expect(facade.state()).toMatchObject({ status: 'error', retryable: status === 0 || status >= 500 }); http.expectNone(() => true);
    facade.retry();
    if (status === 0 || status >= 500) { parents(); const retry = list(); expect(retry.request.params.get('is_alert')).toBe('false'); retry.flush(page); }
    else http.expectNone(() => true);
  });
  it('releases all pending requests when the local facade is destroyed', () => {
    facade.load(query); const req = http.expectOne('/api/v1/equipments/12'); TestBed.resetTestingModule(); expect(req.cancelled).toBe(true);
  });
});
