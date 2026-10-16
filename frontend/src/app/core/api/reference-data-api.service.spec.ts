import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ReferenceDataApiService } from './reference-data-api.service';

describe('ReferenceDataApiService', () => {
  let api: ReferenceDataApiService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(ReferenceDataApiService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('does not make requests on injection or before subscription', () => {
    api.getCompanies();
    http.expectNone(() => true);
  });

  it.each(['companies', 'sites', 'equipments'] as const)('gets paginated %s with the real parent parameter', (kind) => {
    const query = { page: 2, page_size: 50, search: 'Pompe & moteur' };
    let received: unknown;
    const result = kind === 'companies' ? api.getCompanies(query)
      : kind === 'sites' ? api.getSites(7, query) : api.getEquipments(9, query);
    result.subscribe(value => received = value);
    const req = http.expectOne(request => request.url === `/api/v1/${kind}`);
    expect(req.request.method).toBe('GET');
    expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.get('page_size')).toBe('50');
    expect(new URL(req.request.urlWithParams, 'https://test.invalid').searchParams.get('search')).toBe(query.search);
    expect(req.request.params.get('company_id')).toBe(kind === 'sites' ? '7' : null);
    expect(req.request.params.get('site_id')).toBe(kind === 'equipments' ? '9' : null);
    const response = { items: [], total: 75, page: 2, page_size: 50, pages: 2 };
    req.flush(response);
    expect(received).toEqual(response);
  });

  it('keeps backend pagination defaults when the query is absent', () => {
    api.getCompanies().subscribe();
    const req = http.expectOne('/api/v1/companies');
    expect(req.request.params.keys()).toEqual([]);
    req.flush({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
  });

  it('loads an individual company reference without rewriting timestamps or requesting its list', () => {
    let received: unknown;
    const response = { id: 7, name: 'Entreprise', code: 'C7', description: null,
      created_at: '2026-10-01T12:34:56.123456', updated_at: '2026-10-02T08:00:00Z' };
    api.getCompanyById(7).subscribe(value => received = value);
    const req = http.expectOne('/api/v1/companies/7');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys()).toEqual([]);
    req.flush(response);
    expect(received).toEqual(response);
    http.expectNone(() => true);
  });

  it.each([404, 422, 500])('propagates company reference HTTP %s unchanged without retry', status => {
    let error: HttpErrorResponse | undefined;
    api.getCompanyById(7).subscribe({ error: value => error = value });
    const body = { detail: 'Company reference error' };
    http.expectOne('/api/v1/companies/7').flush(body, { status, statusText: 'Error' });
    expect(error?.status).toBe(status);
    expect(error?.error).toEqual(body);
    http.expectNone(() => true);
  });

  it.each([400, 404, 422, 500])('propagates HTTP %s without retries', status => {
    let error: HttpErrorResponse | undefined;
    api.getSites(7).subscribe({ error: value => error = value });
    const body = { detail: 'Reference error' };
    http.expectOne(request => request.url === '/api/v1/sites').flush(body, { status, statusText: 'Error' });
    expect(error?.status).toBe(status);
    expect(error?.error).toEqual(body);
    http.expectNone(() => true);
  });

  it('propagates network errors', () => {
    let error: HttpErrorResponse | undefined;
    api.getEquipments(9).subscribe({ error: value => error = value });
    http.expectOne(request => request.url === '/api/v1/equipments').error(new ProgressEvent('error'));
    expect(error?.status).toBe(0);
  });
});
