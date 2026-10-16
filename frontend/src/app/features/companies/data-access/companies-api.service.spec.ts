import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController } from '@angular/common/http/testing';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Observable } from 'rxjs';

import { Page, ReferencePageQuery } from '../../../core/models/page.model';
import { CompanyRead } from '../../../core/models/reference-data.model';
import { CompanyCreate, CompanyUpdate } from '../models/company-write.model';
import { CompaniesApiService } from './companies-api.service';

// Transport fixtures only: naive timestamps must not acquire an assumed timezone.
const COMPANY: CompanyRead = {
  id: 7,
  name: 'Entreprise de test',
  code: 'TEST-7',
  description: null,
  created_at: '2026-10-01T12:34:56.123456',
  updated_at: '2026-10-02T08:00:00'
};
const CREATE: CompanyCreate = { name: COMPANY.name, code: COMPANY.code };
const OPERATIONS = ['list', 'detail', 'create', 'update'] as const;
type Operation = typeof OPERATIONS[number];

describe('CompaniesApiService', () => {
  let api: CompaniesApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(CompaniesApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.expectNone(request => request.method === 'DELETE');
    http.verify();
  });

  function request(operation: Operation): Observable<unknown> {
    switch (operation) {
      case 'list': return api.list();
      case 'detail': return api.getById(COMPANY.id);
      case 'create': return api.create(CREATE);
      case 'update': return api.update(COMPANY.id, { name: 'Nouveau nom' });
    }
  }

  function url(operation: Operation): string {
    return `/api/v1/companies${operation === 'detail' || operation === 'update' ? '/7' : ''}`;
  }

  it('does not send requests on injection or method calls without subscription', () => {
    OPERATIONS.forEach(operation => request(operation));
    http.expectNone(() => true);
  });

  it('omits pagination parameters so FastAPI keeps page 1 and page_size 20', () => {
    let received: Page<CompanyRead> | undefined;
    api.list().subscribe(value => received = value);
    const req = http.expectOne('/api/v1/companies');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys()).toEqual([]);
    const response: Page<CompanyRead> = { items: [COMPANY], total: 1, page: 1, page_size: 20, pages: 1 };
    req.flush(response);
    expect(received).toEqual(response);
  });

  it.each([1, 100])('serializes the supported page_size boundary %s without loading other pages', pageSize => {
    api.list({ page: 2, page_size: pageSize }).subscribe();
    const req = http.expectOne(request => request.url === '/api/v1/companies');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys().sort()).toEqual(['page', 'page_size']);
    expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.get('page_size')).toBe(String(pageSize));
    req.flush({ items: [], total: 0, page: 2, page_size: pageSize, pages: 0 });
  });

  // HTTP mocks verify forwarding and error propagation, not FastAPI validation itself.
  it.each<ReferencePageQuery>([{ page: 0 }, { page: -1 }, { page_size: 0 }, { page_size: -1 }, { page_size: 101 }])(
    'preserves invalid pagination %j and propagates backend validation without clamping', query => {
      let error: HttpErrorResponse | undefined;
      api.list(query).subscribe({ error: value => error = value });
      const req = http.expectOne(request => request.url === '/api/v1/companies');
      for (const [key, value] of Object.entries(query)) expect(req.request.params.get(key)).toBe(String(value));
      const body = { detail: [{ loc: ['query', Object.keys(query)[0]], msg: 'Invalid bound', type: 'bound' }] };
      req.flush(body, { status: 422, statusText: 'Unprocessable Entity' });
      expect(error?.status).toBe(422);
      expect(error?.error).toEqual(body);
    }
  );

  it.each(['Entreprise de test', 'TEST-7', 'Énergie & ports + 50%_ #/?', ' alpha '])(
    'sends server-side name/code search %s without local filtering or normalization', search => {
      api.list({ page: 3, page_size: 20, search }).subscribe();
      const req = http.expectOne(request => request.url === '/api/v1/companies');
      expect(req.request.params.get('search')).toBe(search);
      const decoded = new URL(req.request.urlWithParams, 'https://test.invalid').searchParams;
      expect(decoded.get('search')).toBe(search);
      expect(decoded.get('page')).toBe('3');
      expect(decoded.get('page_size')).toBe('20');
      expect(req.request.params.keys().sort()).toEqual(['page', 'page_size', 'search']);
      req.flush({ items: [], total: 0, page: 3, page_size: 20, pages: 0 });
    }
  );

  it('omits an empty search instead of sending a parameter rejected by FastAPI', () => {
    api.list({ search: '' }).subscribe();
    const req = http.expectOne('/api/v1/companies');
    expect(req.request.params.has('search')).toBe(false);
    req.flush({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
  });

  it('keeps an out-of-range empty page distinct from an empty database', () => {
    const response: Page<CompanyRead> = { items: [], total: 21, page: 3, page_size: 20, pages: 2 };
    let received: Page<CompanyRead> | undefined;
    api.list({ page: 3 }).subscribe(value => received = value);
    http.expectOne('/api/v1/companies?page=3').flush(response);
    expect(received).toEqual(response);
  });

  it('gets a company by id with null description and timestamps preserved as strings', () => {
    let received: CompanyRead | undefined;
    api.getById(COMPANY.id).subscribe(value => received = value);
    const req = http.expectOne('/api/v1/companies/7');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys()).toEqual([]);
    req.flush(COMPANY);
    expect(received).toEqual(COMPANY);
    expect(received?.description).toBeNull();
    expect(received?.created_at).toBe('2026-10-01T12:34:56.123456');
    expect(received?.updated_at).toBe('2026-10-02T08:00:00');
  });

  it.each<CompanyCreate>([CREATE, { ...CREATE, description: null }, {
    name: ' Entreprise & associés ', code: ' Code-mixte ', description: 'Première ligne\nSeconde ligne'
  }])('posts the exact create body %j and returns the created company', body => {
    let received: CompanyRead | undefined;
    api.create(body).subscribe(value => received = value);
    const req = http.expectOne('/api/v1/companies');
    expect(req.request.method).toBe('POST');
    expect(req.request.serializeBody()).toBe(JSON.stringify(body));
    expect(req.request.body).toEqual(body);
    const response: CompanyRead = { ...COMPANY, ...body, description: body.description ?? null };
    req.flush(response, { status: 201, statusText: 'Created' });
    expect(received).toEqual(response);
  });

  it.each<CompanyUpdate>([
    { name: 'Nouveau nom' }, { code: ' Code-mixte ' }, { description: null },
    { description: '' }, { name: null, code: null }, {}
  ])('patches only the supplied fields in %j, preserving explicit nulls', body => {
    let received: CompanyRead | undefined;
    api.update(COMPANY.id, body).subscribe(value => received = value);
    const req = http.expectOne('/api/v1/companies/7');
    expect(req.request.method).toBe('PATCH');
    expect(req.request.serializeBody()).toBe(JSON.stringify(body));
    expect(Object.keys(req.request.body)).toEqual(Object.keys(body));
    // This mocked response checks transport only; SQL may reject a null name/code.
    req.flush(COMPANY);
    expect(received).toEqual(COMPANY);
  });

  it.each(OPERATIONS)('propagates HTTP errors for %s with their original bodies and no retries', operation => {
    const cases = [
      { status: 404, body: { detail: 'Company not found' } },
      { status: 409, body: { detail: "Company with code 'TEST-7' already exists." } },
      { status: 422, body: { detail: [{ loc: ['body', 'name'], msg: 'Field required', type: 'missing' }] } },
      { status: 500, body: 'Internal Server Error' }
    ];
    for (const { status, body } of cases) {
      let error: HttpErrorResponse | undefined;
      let emitted = false;
      request(operation).subscribe({ next: () => emitted = true, error: value => error = value });
      http.expectOne(url(operation)).flush(body, { status, statusText: 'Error' });
      expect(error).toBeInstanceOf(HttpErrorResponse);
      expect(error?.status).toBe(status);
      expect(error?.error).toEqual(body);
      expect(emitted).toBe(false);
      http.expectNone(() => true);
    }
  });

  it.each(OPERATIONS)('propagates network failures for %s without retrying reads or writes', operation => {
    const failure = new ProgressEvent('error');
    let error: HttpErrorResponse | undefined;
    let emitted = false;
    request(operation).subscribe({ next: () => emitted = true, error: value => error = value });
    http.expectOne(url(operation)).error(failure);
    expect(error?.status).toBe(0);
    expect(error?.error).toBe(failure);
    expect(emitted).toBe(false);
    http.expectNone(() => true);
  });
});
