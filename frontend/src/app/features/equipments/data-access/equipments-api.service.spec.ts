import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Observable } from 'rxjs';
import { expectTypeOf } from 'vitest';
import { ReferenceDataApiService } from '../../../core/api/reference-data-api.service';
import { Page } from '../../../core/models/page.model';
import { EquipmentCriticality, EquipmentRead, EquipmentStatus } from '../../../core/models/reference-data.model';
import { EquipmentCreate, EquipmentUpdate } from '../models/equipment-write.model';
import { EquipmentListQuery } from '../models/equipment-list-query.model';
import { EquipmentsApiService } from './equipments-api.service';

const EQUIPMENT: EquipmentRead = { id: 12, site_id: 9, name: 'Pompe 日本', code: 'P-12',
  equipment_type: 'pump', description: null, status: 'operational', criticality: 'medium',
  created_at: '2026-10-01T12:34:56.123456', updated_at: '2026-10-02T08:00:00.987654+02:00' };
const CREATE: EquipmentCreate = { site_id: 9, name: 'Pompe 日本', code: 'P-12', equipment_type: 'pump' };
const OPERATIONS = ['list', 'detail', 'create', 'update'] as const;
type Operation = typeof OPERATIONS[number];

describe('EquipmentsApiService', () => {
  let api: EquipmentsApiService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(EquipmentsApiService); http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.expectNone(req => req.method === 'DELETE'); http.verify(); vi.restoreAllMocks(); });
  function request(operation: Operation): Observable<unknown> {
    switch (operation) {
      case 'list': return api.list({ site_id: 9 });
      case 'detail': return api.getById(12);
      case 'create': return api.create(CREATE);
      case 'update': return api.update(12, { name: 'Autre nom' });
    }
  }
  const pending = (operation: Operation) => http.expectOne(operation === 'list'
    ? '/api/v1/equipments?site_id=9' : operation === 'create' ? '/api/v1/equipments' : '/api/v1/equipments/12');

  it('defines only MVP fields with required creation site and non-nullable editable values', () => {
    expectTypeOf<Pick<EquipmentCreate, 'name' | 'code' | 'equipment_type' | 'site_id'>>()
      .toEqualTypeOf<{ name: string; code: string; equipment_type: string; site_id: number }>();
    expectTypeOf<EquipmentCreate['status']>().toEqualTypeOf<EquipmentStatus | undefined>();
    expectTypeOf<EquipmentCreate['criticality']>().toEqualTypeOf<EquipmentCriticality | undefined>();
    expectTypeOf<EquipmentUpdate['name']>().toEqualTypeOf<string | undefined>();
    expectTypeOf<EquipmentUpdate['status']>().toEqualTypeOf<EquipmentStatus | undefined>();
    expectTypeOf<EquipmentUpdate['criticality']>().toEqualTypeOf<EquipmentCriticality | undefined>();
    expectTypeOf<EquipmentUpdate['description']>().toEqualTypeOf<string | null | undefined>();
    expectTypeOf<keyof EquipmentUpdate>().toEqualTypeOf<'name' | 'code' | 'equipment_type' | 'description' | 'status' | 'criticality'>();
    expectTypeOf<keyof EquipmentCreate>().toEqualTypeOf<keyof EquipmentUpdate | 'site_id'>();
    expectTypeOf<EquipmentListQuery['site_id']>().toEqualTypeOf<number>();
    expectTypeOf<keyof EquipmentListQuery>().toEqualTypeOf<'site_id' | 'search' | 'page' | 'page_size' | 'status' | 'criticality'>();
  });

  it('has cold requests and no deletion method', () => {
    for (const operation of OPERATIONS) request(operation);
    expect('delete' in api).toBe(false); http.expectNone(() => true);
  });
  it('delegates list and detail to the existing core transport', () => {
    const references = TestBed.inject(ReferenceDataApiService);
    const list = vi.spyOn(references, 'getEquipments'), detail = vi.spyOn(references, 'getEquipmentById');
    const query: EquipmentListQuery = { site_id: 9, status: 'maintenance' };
    api.list(query).subscribe();
    expect(list).toHaveBeenCalledExactlyOnceWith(9, query);
    http.expectOne(req => req.url === '/api/v1/equipments').flush({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
    api.getById(12).subscribe(); expect(detail).toHaveBeenCalledExactlyOnceWith(12);
    http.expectOne('/api/v1/equipments/12').flush(EQUIPMENT);
  });
  it('passes exact combined filters and pagination without leaking company or unknown parameters', () => {
    const query = { site_id: 9, page: 2, page_size: 100, search: ' Pompe & énergie_% ',
      status: 'maintenance' as const, criticality: 'critical' as const, company_id: 7, equipment_type: 'not a filter' };
    let received: Page<EquipmentRead> | undefined;
    api.list(query).subscribe(value => received = value);
    const req = http.expectOne(req => req.url === '/api/v1/equipments');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys().sort()).toEqual(['criticality', 'page', 'page_size', 'search', 'site_id', 'status']);
    for (const key of ['site_id', 'page', 'page_size', 'search', 'status', 'criticality'] as const)
      expect(req.request.params.get(key)).toBe(String(query[key]));
    expect(new URL(req.request.urlWithParams, 'https://test.invalid').searchParams.get('search')).toBe(query.search);
    const response = { items: [EQUIPMENT], total: 101, page: 2, page_size: 100, pages: 2 };
    req.flush(response); expect(received).toEqual(response); expect(query.company_id).toBe(7);
  });
  it.each<Partial<EquipmentListQuery>>([{}, { search: '' }, { status: undefined, criticality: undefined }])
    ('omits absent filters and keeps backend pagination defaults: %j', query => {
      api.list({ site_id: 9, ...query }).subscribe();
      const req = http.expectOne('/api/v1/equipments?site_id=9');
      expect(req.request.params.keys()).toEqual(['site_id']);
      req.flush({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
    });
  it.each([1, 100])('transmits page_size %s and a 100-character search without transformation', size => {
    api.list({ site_id: 9, page: 3, page_size: size, search: 'x'.repeat(100) }).subscribe();
    const req = http.expectOne(req => req.url === '/api/v1/equipments');
    expect(req.request.params.get('page')).toBe('3'); expect(req.request.params.get('page_size')).toBe(String(size));
    expect(req.request.params.get('search')).toHaveLength(100);
    req.flush({ items: [], total: 2, page: 3, page_size: size, pages: 2 });
  });
  it('returns detail unchanged including null, enums and timestamps, without a scope query', () => {
    let received: EquipmentRead | undefined;
    api.getById(12).subscribe(value => received = value);
    const req = http.expectOne('/api/v1/equipments/12');
    expect(req.request.method).toBe('GET'); expect(req.request.params.keys()).toEqual([]);
    req.flush(EQUIPMENT); expect(received).toEqual(EQUIPMENT);
  });

  it.each<EquipmentCreate>([CREATE, { ...CREATE, description: undefined }, { ...CREATE, description: null },
    { ...CREATE, description: '' }, { ...CREATE, name: ' Usine 日本 🏭 ', code: ' Code-mixte ',
      equipment_type: ' Type libre ', description: '  Ligne 1\nLigne 2  ', status: 'out_of_service', criticality: 'critical' },
    { ...CREATE, name: 'N'.repeat(150), code: 'C'.repeat(100), equipment_type: 'T'.repeat(100) }])
    ('serializes POST %j without normalization or injecting defaults', body => {
      let received: EquipmentRead | undefined;
      api.create(body).subscribe(value => received = value);
      const req = http.expectOne('/api/v1/equipments'); expect(req.request.method).toBe('POST');
      expect(JSON.parse(req.request.serializeBody() as string)).toEqual(JSON.parse(JSON.stringify(body)));
      if (body.status === undefined) expect(Object.hasOwn(req.request.body, 'status')).toBe(false);
      if (body.criticality === undefined) expect(Object.hasOwn(req.request.body, 'criticality')).toBe(false);
      req.flush(EQUIPMENT, { status: 201, statusText: 'Created' }); expect(received).toEqual(EQUIPMENT);
    });
  it.each<EquipmentUpdate>([{ name: ' Nom avec espaces ' }, { code: 'Code-Mixte' }, { equipment_type: ' type libre ' },
    { status: 'maintenance' }, { criticality: 'high' }, { description: '' }, { description: null },
    { description: undefined }, {}])('sends supplied PATCH fields without calculating differences: %j', body => {
      let received: EquipmentRead | undefined;
      api.update(12, body).subscribe(value => received = value);
      const req = http.expectOne('/api/v1/equipments/12'); expect(req.request.method).toBe('PATCH');
      expect(JSON.parse(req.request.serializeBody() as string)).toEqual(JSON.parse(JSON.stringify(body)));
      if (body.description === undefined) expect(Object.hasOwn(req.request.body, 'description')).toBe(false);
      req.flush(EQUIPMENT); expect(received).toEqual(EQUIPMENT);
    });
  it.each(['create', 'update'] as const)('strips unknown properties and administrative data from %s without mutating input', operation => {
    const body = { ...EQUIPMENT, site_id: 99, company_id: 7, sensors: [{ id: 5 }], extra: 'not writable' };
    const original = structuredClone(body);
    (operation === 'create' ? api.create(body) : api.update(12, body)).subscribe();
    const req = http.expectOne(operation === 'create' ? '/api/v1/equipments' : '/api/v1/equipments/12');
    expect(req.request.body).toEqual({ name: body.name, code: body.code, equipment_type: body.equipment_type,
      description: null, status: body.status, criticality: body.criticality, ...(operation === 'create' ? { site_id: 99 } : {}) });
    expect(body).toEqual(original); req.flush(EQUIPMENT);
  });
  it.each(['name', 'code', 'equipment_type', 'status', 'criticality'] as const)
    ('rejects unsafe null %s locally in POST and PATCH without issuing HTTP', field => {
      for (const operation of ['create', 'update'] as const) {
        let error: unknown;
        const body = { ...CREATE, [field]: null };
        (operation === 'create' ? api.create(body as unknown as EquipmentCreate)
          : api.update(12, body as unknown as EquipmentUpdate)).subscribe({ error: value => error = value });
        expect(error).toBeInstanceOf(TypeError); http.expectNone(() => true);
      }
    });
  it.each(['site_id', 'name', 'code', 'equipment_type'] as const)('rejects missing creation field %s without HTTP', field => {
    const body = { ...CREATE }; delete (body as Partial<EquipmentCreate>)[field];
    let error: unknown; api.create(body).subscribe({ error: value => error = value });
    expect(error).toBeInstanceOf(TypeError); http.expectNone(() => true);
  });
  it('rejects null site on creation and ignores a forbidden null site in PATCH', () => {
    let error: unknown;
    const body = { ...CREATE, site_id: null };
    api.create(body as unknown as EquipmentCreate).subscribe({ error: value => error = value });
    expect(error).toBeInstanceOf(TypeError); http.expectNone(() => true);
    api.update(12, { ...body, name: 'Autre' }).subscribe();
    const req = http.expectOne('/api/v1/equipments/12'); expect(Object.hasOwn(req.request.body, 'site_id')).toBe(false);
    req.flush(EQUIPMENT);
  });
  it.each(OPERATIONS)('propagates HTTP errors for %s without interpreting or retrying', operation => {
    for (const [status, body] of [[403, { detail: 'Forbidden' }], [404, { detail: 'Equipment not found' }],
      [409, { detail: "Site with id '9' does not exist." }], [409, { detail: "Equipment with code 'P-12' already exists." }],
      [409, { detail: 'Unspecified conflict' }], [422, { detail: [{ loc: ['body', 'status'], type: 'enum' }] }],
      [500, 'Internal Server Error']] as const) {
      let error: HttpErrorResponse | undefined; let emitted = false;
      request(operation).subscribe({ next: () => emitted = true, error: value => error = value });
      pending(operation).flush(body, { status, statusText: 'Error' });
      expect(error).toBeInstanceOf(HttpErrorResponse); expect(error?.status).toBe(status);
      expect(error?.error).toEqual(body); expect(emitted).toBe(false); http.expectNone(() => true);
    }
  });
  it.each(OPERATIONS)('propagates network failure for %s without retry', operation => {
    let error: HttpErrorResponse | undefined; const event = new ProgressEvent('error');
    request(operation).subscribe({ error: value => error = value }); pending(operation).error(event);
    expect(error?.status).toBe(0); expect(error?.error).toBe(event); http.expectNone(() => true);
  });
});
