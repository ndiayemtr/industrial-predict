import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Observable } from 'rxjs';
import { expectTypeOf } from 'vitest';
import { Page } from '../../../core/models/page.model';
import { SiteRead } from '../../../core/models/reference-data.model';
import { SiteCreate, SiteUpdate } from '../models/site-write.model';
import { SiteListQuery } from '../models/site-list-query.model';
import { SitesApiService } from './sites-api.service';

const SITE: SiteRead = { id: 3, company_id: 7, name: 'Usine', code: 'SITE-3', description: null,
  created_at: '2026-10-01T12:34:56.123456', updated_at: '2026-10-02T08:00:00.987654+02:00' };
const CREATE: SiteCreate = { name: 'Usine', code: 'SITE-3', company_id: 7 };
const OPERATIONS = ['list', 'detail', 'create', 'update'] as const;
type Operation = typeof OPERATIONS[number];

describe('SitesApiService', () => {
  let api: SitesApiService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(SitesApiService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.expectNone(request => request.method === 'DELETE');
    http.verify();
  });

  function request(operation: Operation): Observable<unknown> {
    switch (operation) {
      case 'list': return api.list({ company_id: 7 });
      case 'detail': return api.getById(3);
      case 'create': return api.create(CREATE);
      case 'update': return api.update(3, { code: 'UPDATED' });
    }
  }
  const url = (operation: Operation) => `/api/v1/sites${operation === 'detail' || operation === 'update' ? '/3' : '?company_id=7'}`;
  function pending(operation: Operation) {
    return http.expectOne(operation === 'create' ? '/api/v1/sites' : url(operation));
  }

  it('requires the creation company and excludes company_id from the MVP update type', () => {
    expectTypeOf<SiteCreate['company_id']>().toEqualTypeOf<number>();
    expectTypeOf<Pick<SiteCreate, 'company_id'>>().toEqualTypeOf<{ company_id: number }>();
    expectTypeOf<keyof SiteUpdate>().toEqualTypeOf<'name' | 'code' | 'description'>();
    expectTypeOf<SiteListQuery['company_id']>().toEqualTypeOf<number>();
  });

  it('has cold requests and no deletion method', () => {
    for (const operation of OPERATIONS) request(operation);
    expect('delete' in api).toBe(false);
    http.expectNone(() => true);
  });

  it('reuses the paginated reference endpoint with exact company, search and pagination parameters', () => {
    const query: SiteListQuery = { company_id: 7, page: 2, page_size: 100, search: ' Usine & énergie_% ' };
    let received: Page<SiteRead> | undefined;
    api.list(query).subscribe(value => received = value);
    const req = http.expectOne(request => request.url === '/api/v1/sites');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys().sort()).toEqual(['company_id', 'page', 'page_size', 'search']);
    expect(req.request.params.get('company_id')).toBe('7');
    expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.get('page_size')).toBe('100');
    expect(new URL(req.request.urlWithParams, 'https://test.invalid').searchParams.get('search')).toBe(query.search);
    const response = { items: [SITE], total: 101, page: 2, page_size: 100, pages: 2 };
    req.flush(response);
    expect(received).toEqual(response);
    expect(received?.items[0].created_at).toBe(SITE.created_at);
    expect(received?.items[0].updated_at).toBe(SITE.updated_at);
  });

  it.each([undefined, ''])('omits empty search %s and leaves pagination defaults to FastAPI', search => {
    api.list({ company_id: 7, ...(search !== undefined ? { search } : {}) }).subscribe();
    const req = http.expectOne('/api/v1/sites?company_id=7');
    expect(req.request.params.keys()).toEqual(['company_id']);
    req.flush({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
  });

  it.each([1, 100])('passes the supported page_size boundary %s unchanged', pageSize => {
    api.list({ company_id: 7, page: 1, page_size: pageSize, search: 'x'.repeat(100) }).subscribe();
    const req = http.expectOne(request => request.url === '/api/v1/sites');
    expect(req.request.params.get('page_size')).toBe(String(pageSize));
    expect(req.request.params.get('search')).toHaveLength(100);
    req.flush({ items: [], total: 0, page: 1, page_size: pageSize, pages: 0 });
  });

  it('leaves invalid limits to server validation instead of clamping or changing the company', () => {
    let error: HttpErrorResponse | undefined;
    api.list({ company_id: 0, page: 0, page_size: 101, search: 'x'.repeat(101) }).subscribe({ error: value => error = value });
    const req = http.expectOne(request => request.url === '/api/v1/sites');
    expect(req.request.params.get('company_id')).toBe('0');
    expect(req.request.params.get('page')).toBe('0');
    expect(req.request.params.get('page_size')).toBe('101');
    expect(req.request.params.get('search')).toHaveLength(101);
    const body = { detail: [{ loc: ['query', 'page_size'], type: 'less_than_equal', msg: 'Maximum 100' }] };
    req.flush(body, { status: 422, statusText: 'Unprocessable Entity' });
    expect(error?.status).toBe(422);
    expect(error?.error).toEqual(body);
  });

  it('returns the detail with original timestamps, nulls and no company filter', () => {
    let received: SiteRead | undefined;
    api.getById(3).subscribe(value => received = value);
    const req = http.expectOne('/api/v1/sites/3');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys()).toEqual([]);
    req.flush(SITE);
    expect(received).toEqual(SITE);
    expect(received?.created_at).toBe('2026-10-01T12:34:56.123456');
    expect(received?.updated_at).toBe('2026-10-02T08:00:00.987654+02:00');
  });

  it.each<SiteCreate>([CREATE, { ...CREATE, description: null }, { ...CREATE, description: '' },
    { ...CREATE, name: ' Usine 日本 🏭 ', code: ' Code-mixte ', description: 'Ligne 1\nLigne 2' }])
    ('serializes creation %j with its explicit company and no normalization', body => {
      let received: SiteRead | undefined;
      api.create(body).subscribe(value => received = value);
      const req = http.expectOne('/api/v1/sites');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual(body);
      expect(req.request.serializeBody()).toBe(JSON.stringify(body));
      req.flush(SITE, { status: 201, statusText: 'Created' });
      expect(received).toEqual(SITE);
    });

  it.each<SiteUpdate>([{ name: ' Nouveau nom ' }, { code: '' }, { description: null },
    { description: '' }, { name: null, code: null }, {}])
    ('serializes only supplied editable fields %j, retaining empty strings and explicit nulls', body => {
      let received: SiteRead | undefined;
      api.update(3, body).subscribe(value => received = value);
      const req = http.expectOne('/api/v1/sites/3');
      expect(req.request.method).toBe('PATCH');
      expect(req.request.body).toEqual(body);
      expect(req.request.serializeBody()).toBe(JSON.stringify(body));
      // Mocked transport only: a null name/code may be rejected by SQL.
      req.flush(SITE);
      expect(received).toEqual(SITE);
    });

  it('never serializes company_id or administrative fields from a structurally compatible object', () => {
    const body = { ...SITE, company_id: 99, description: '' };
    api.update(3, body).subscribe();
    const req = http.expectOne('/api/v1/sites/3');
    expect(req.request.body).toEqual({ name: SITE.name, code: SITE.code, description: '' });
    expect(req.request.serializeBody()).not.toContain('company_id');
    expect(req.request.serializeBody()).not.toContain('created_at');
    expect(body.company_id).toBe(99);
    req.flush(SITE);
  });

  it.each(OPERATIONS)('propagates errors for %s without interpreting conflicts or retrying', operation => {
    const cases = [
      { status: 404, body: { detail: 'Site not found' } },
      { status: 409, body: { detail: "Company with id '7' does not exist." } },
      { status: 409, body: { detail: "Site with code 'SITE-3' already exists." } },
      { status: 409, body: { detail: 'Unspecified conflict' } },
      { status: 422, body: { detail: [{ loc: ['body', 'company_id'], type: 'missing', msg: 'Field required' }] } },
      { status: 500, body: 'Internal Server Error' }
    ];
    for (const { status, body } of cases) {
      let error: HttpErrorResponse | undefined;
      let emitted = false;
      request(operation).subscribe({ next: () => emitted = true, error: value => error = value });
      pending(operation).flush(body, { status, statusText: 'Error' });
      expect(error).toBeInstanceOf(HttpErrorResponse);
      expect(error?.status).toBe(status);
      expect(error?.error).toEqual(body);
      expect(emitted).toBe(false);
      http.expectNone(() => true);
    }
  });

  it.each(OPERATIONS)('propagates network failures for %s without retries', operation => {
    let error: HttpErrorResponse | undefined;
    const failure = new ProgressEvent('error');
    request(operation).subscribe({ error: value => error = value });
    pending(operation).error(failure);
    expect(error?.status).toBe(0);
    expect(error?.error).toBe(failure);
    http.expectNone(() => true);
  });
});
