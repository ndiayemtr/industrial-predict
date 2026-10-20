import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Observable } from 'rxjs';
import { expectTypeOf } from 'vitest';
import { Page } from '../../../core/models/page.model';
import { SensorPage, SensorRead, SensorStatus } from '../models/sensor.model';
import { SensorPageQuery } from '../models/sensor-page-query.model';
import { SensorCreate, SensorPatch } from '../models/sensor-write.model';
import { SensorsApiService } from './sensors-api.service';

const SENSOR: SensorRead = { id: 12, equipment_id: 9, name: 'Température 日本', code: 'T-12',
  sensor_type: 'temperature', unit: '°C', description: null, status: 'active',
  created_at: '2026-10-01T12:34:56.123456', updated_at: '2026-10-02T08:00:00.987654+02:00' };
const CREATE: SensorCreate = { equipment_id: 9, name: 'Température 日本', code: 'T-12',
  sensor_type: 'temperature', unit: '°C' };
const OPERATIONS = ['list', 'detail', 'create', 'patch'] as const;
type Operation = typeof OPERATIONS[number];

describe('SensorsApiService', () => {
  let api: SensorsApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(SensorsApiService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.expectNone(req => req.method === 'DELETE');
    http.verify();
  });

  function request(operation: Operation): Observable<unknown> {
    switch (operation) {
      case 'list': return api.list({ equipment_id: 9 });
      case 'detail': return api.getById(12);
      case 'create': return api.create(CREATE);
      case 'patch': return api.patch(12, { name: 'Autre nom' });
    }
  }
  const pending = (operation: Operation) => http.expectOne(operation === 'list'
    ? '/api/v1/sensors?equipment_id=9' : operation === 'create' ? '/api/v1/sensors' : '/api/v1/sensors/12');

  it('defines the exact read, write, query and pagination contracts', () => {
    expectTypeOf<keyof SensorRead>().toEqualTypeOf<'id' | 'name' | 'code' | 'sensor_type' | 'unit'
      | 'description' | 'status' | 'equipment_id' | 'created_at' | 'updated_at'>();
    expectTypeOf<SensorStatus>().toEqualTypeOf<'active' | 'inactive'>();
    expectTypeOf<SensorRead['description']>().toEqualTypeOf<string | null>();
    expectTypeOf<SensorRead['created_at']>().toEqualTypeOf<string>();
    expectTypeOf<SensorPage>().toEqualTypeOf<Page<SensorRead>>();
    expectTypeOf<keyof SensorPage>().toEqualTypeOf<'items' | 'total' | 'page' | 'page_size' | 'pages'>();
    expectTypeOf<Pick<SensorCreate, 'name' | 'code' | 'sensor_type' | 'unit' | 'equipment_id'>>()
      .toEqualTypeOf<{ name: string; code: string; sensor_type: string; unit: string; equipment_id: number }>();
    expectTypeOf<keyof SensorCreate>().toEqualTypeOf<'name' | 'code' | 'sensor_type' | 'unit'
      | 'equipment_id' | 'description' | 'status'>();
    expectTypeOf<SensorCreate['status']>().toEqualTypeOf<SensorStatus | undefined>();
    expectTypeOf<keyof SensorPatch>().toEqualTypeOf<'name' | 'code' | 'status' | 'description'>();
    expectTypeOf<SensorPatch['name']>().toEqualTypeOf<string | undefined>();
    expectTypeOf<SensorPatch['code']>().toEqualTypeOf<string | undefined>();
    expectTypeOf<SensorPatch['status']>().toEqualTypeOf<SensorStatus | undefined>();
    expectTypeOf<SensorPatch['description']>().toEqualTypeOf<string | null | undefined>();
    expectTypeOf<SensorPageQuery['equipment_id']>().toEqualTypeOf<number>();
    expectTypeOf<keyof SensorPageQuery>().toEqualTypeOf<'equipment_id' | 'status' | 'search' | 'page' | 'page_size'>();
    expectTypeOf<keyof SensorsApiService>().toEqualTypeOf<'list' | 'getById' | 'create' | 'patch'>();
  });

  it('keeps requests cold and exposes no deletion, transfer or global list method', () => {
    for (const operation of OPERATIONS) request(operation);
    expect('delete' in api).toBe(false);
    expect('transfer' in api).toBe(false);
    expect('getAll' in api).toBe(false);
    http.expectNone(() => true);
  });

  it('transmits only the five recognized list parameters with encoded search preserved', () => {
    const query = { equipment_id: 9, page: 2, page_size: 100, search: ' °C & 日本_% ',
      status: 'inactive' as const, company_id: 7, site_id: 8, sensor_type: 'not a filter', unit: 'not a filter', extra: 1 };
    const original = structuredClone(query);
    let received: SensorPage | undefined;
    api.list(query).subscribe(value => received = value);
    const req = http.expectOne(req => req.url === '/api/v1/sensors');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys().sort()).toEqual(['equipment_id', 'page', 'page_size', 'search', 'status']);
    for (const key of ['equipment_id', 'page', 'page_size', 'search', 'status'] as const)
      expect(req.request.params.get(key)).toBe(String(query[key]));
    expect(new URL(req.request.urlWithParams, 'https://test.invalid').searchParams.get('search')).toBe(query.search);
    const response: SensorPage = { items: [SENSOR], total: 101, page: 2, page_size: 100, pages: 2 };
    req.flush(response);
    expect(received).toEqual(response);
    expect(query).toEqual(original);
  });

  it.each<Partial<SensorPageQuery>>([{}, { search: '' }, { page: undefined, page_size: undefined, status: undefined }])
    ('omits absent filters and pagination defaults: %j', query => {
      api.list({ equipment_id: 9, ...query }).subscribe();
      const req = http.expectOne('/api/v1/sensors?equipment_id=9');
      expect(req.request.params.keys()).toEqual(['equipment_id']);
      req.flush({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
    });

  it.each([1, 100])('preserves page_size %s, a 100-character search and an empty out-of-range page', size => {
    let received: SensorPage | undefined;
    api.list({ equipment_id: 9, page: 3, page_size: size, search: 'x'.repeat(100) }).subscribe(value => received = value);
    const req = http.expectOne(req => req.url === '/api/v1/sensors');
    expect(req.request.params.get('page')).toBe('3');
    expect(req.request.params.get('page_size')).toBe(String(size));
    expect(req.request.params.get('search')).toHaveLength(100);
    const response: SensorPage = { items: [], total: 1, page: 3, page_size: size, pages: 1 };
    req.flush(response);
    expect(received).toEqual(response);
  });

  it.each<SensorStatus>(['active', 'inactive'])('sends the exact status %s for list, POST and PATCH', status => {
    api.list({ equipment_id: 9, status }).subscribe();
    const list = http.expectOne(req => req.url === '/api/v1/sensors');
    expect(list.request.params.get('status')).toBe(status);
    list.flush({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
    api.create({ ...CREATE, status }).subscribe();
    const create = http.expectOne('/api/v1/sensors');
    expect(create.request.body.status).toBe(status);
    create.flush({ ...SENSOR, status }, { status: 201, statusText: 'Created' });
    api.patch(12, { status }).subscribe();
    const patch = http.expectOne('/api/v1/sensors/12');
    expect(patch.request.body).toEqual({ status });
    patch.flush({ ...SENSOR, status });
  });

  it('returns the ten detail fields unchanged without adding parent context or parsing dates', () => {
    let received: SensorRead | undefined;
    api.getById(12).subscribe(value => received = value);
    const req = http.expectOne('/api/v1/sensors/12');
    expect(req.request.method).toBe('GET');
    expect(req.request.params.keys()).toEqual([]);
    req.flush(SENSOR);
    expect(received).toEqual(SENSOR);
    expect(Object.keys(received!)).toHaveLength(10);
  });

  it.each<SensorCreate>([CREATE, { ...CREATE, description: undefined }, { ...CREATE, description: null },
    { ...CREATE, description: '' }, { ...CREATE, name: ' Nom 日本 🏭 ', code: ' Code-Mixte ',
      sensor_type: ' Type libre ', unit: ' mm/s ', description: '  Ligne 1\nLigne 2  ', status: 'inactive' },
    { ...CREATE, name: 'N'.repeat(150), code: 'C'.repeat(100), sensor_type: 'T'.repeat(100), unit: 'U'.repeat(30) }])
    ('serializes POST without normalization or defaults: %j', body => {
      let received: SensorRead | undefined;
      api.create(body).subscribe(value => received = value);
      const req = http.expectOne('/api/v1/sensors');
      expect(req.request.method).toBe('POST');
      expect(JSON.parse(req.request.serializeBody() as string)).toEqual(JSON.parse(JSON.stringify(body)));
      if (body.status === undefined) expect(Object.hasOwn(req.request.body, 'status')).toBe(false);
      if (body.description === undefined) expect(Object.hasOwn(req.request.body, 'description')).toBe(false);
      req.flush(SENSOR, { status: 201, statusText: 'Created' });
      expect(received).toEqual(SENSOR);
    });

  it.each<SensorPatch>([{ name: ' Nom avec espaces ' }, { code: 'Code-Mixte' }, { status: 'inactive' },
    { description: '' }, { description: null }, { description: undefined }, {}])
    ('serializes only supplied PATCH differences without transforming them: %j', body => {
      let received: SensorRead | undefined;
      api.patch(12, body).subscribe(value => received = value);
      const req = http.expectOne('/api/v1/sensors/12');
      expect(req.request.method).toBe('PATCH');
      expect(JSON.parse(req.request.serializeBody() as string)).toEqual(JSON.parse(JSON.stringify(body)));
      if (body.description === undefined) expect(Object.hasOwn(req.request.body, 'description')).toBe(false);
      req.flush(SENSOR);
      expect(received).toEqual(SENSOR);
    });

  it.each(['create', 'patch'] as const)('whitelists %s even when passed a full read object with extra fields', operation => {
    const body = { ...SENSOR, company_id: 7, site_id: 8, measurements: [{ id: 5 }], extra: 'not writable' };
    const original = structuredClone(body);
    (operation === 'create' ? api.create(body) : api.patch(12, body)).subscribe();
    const req = http.expectOne(operation === 'create' ? '/api/v1/sensors' : '/api/v1/sensors/12');
    expect(req.request.body).toEqual({ name: body.name, code: body.code, status: body.status, description: null,
      ...(operation === 'create' ? { equipment_id: 9, sensor_type: 'temperature', unit: '°C' } : {}) });
    expect(req.request.params.keys()).toEqual([]);
    expect(body).toEqual(original);
    req.flush(SENSOR);
  });

  it('drops forbidden PATCH fields even when null, and never copies inherited fields', () => {
    api.patch(12, { name: 'Autre', equipment_id: null, sensor_type: null, unit: null,
      company_id: 7, site_id: 8 } as SensorPatch).subscribe();
    const req = http.expectOne('/api/v1/sensors/12');
    expect(req.request.body).toEqual({ name: 'Autre' });
    req.flush(SENSOR);
    const inherited = Object.assign(Object.create({ name: 'Inherited', code: 'Inherited', status: 'inactive', description: 'Inherited' }),
      { description: null }) as SensorPatch;
    api.patch(12, inherited).subscribe();
    const second = http.expectOne('/api/v1/sensors/12');
    expect(second.request.body).toEqual({ description: null });
    second.flush(SENSOR);
  });

  it.each(['equipment_id', 'name', 'code', 'sensor_type', 'unit'] as const)
    ('rejects missing or null creation field %s without HTTP', field => {
      for (const invalid of [undefined, null]) {
        const body = { ...CREATE, [field]: invalid };
        let error: unknown;
        api.create(body as unknown as SensorCreate).subscribe({ error: value => error = value });
        expect(error).toBeInstanceOf(TypeError);
        http.expectNone(() => true);
      }
    });

  it.each(['name', 'code', 'status'] as const)('rejects unsafe null PATCH field %s', field => {
    let error: unknown;
    api.patch(12, { [field]: null } as SensorPatch).subscribe({ error: value => error = value });
    expect(error).toBeInstanceOf(TypeError);
    http.expectNone(() => true);
  });

  it.each([undefined, null, 0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER + 1, '9'])
    ('rejects invalid equipment %s rather than issuing an unscoped request', equipmentId => {
      for (const operation of ['list', 'create'] as const) {
        let error: unknown;
        const id = equipmentId as number;
        const call: Observable<unknown> = operation === 'list' ? api.list({ equipment_id: id })
          : api.create({ ...CREATE, equipment_id: id });
        call.subscribe({ error: value => error = value });
        expect(error).toBeInstanceOf(TypeError);
        http.expectNone(() => true);
      }
    });

  it.each([undefined, null, 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, '12'])
    ('rejects invalid detail/PATCH id %s without HTTP', id => {
      for (const operation of ['detail', 'patch'] as const) {
        let error: unknown;
        (operation === 'detail' ? api.getById(id as number) : api.patch(id as number, { name: 'N' }))
          .subscribe({ error: value => error = value });
        expect(error).toBeInstanceOf(TypeError);
        http.expectNone(() => true);
      }
    });

  it.each([null, 'ACTIVE', ' active', 'Actif', 'operational', ''])('rejects invalid status %s without HTTP', status => {
    const value = status as SensorStatus;
    for (const operation of ['list', 'create', 'patch'] as const) {
      let error: unknown;
      const call: Observable<unknown> = operation === 'list' ? api.list({ equipment_id: 9, status: value })
        : operation === 'create' ? api.create({ ...CREATE, status: value }) : api.patch(12, { status: value });
      call.subscribe({ error: value => error = value });
      expect(error).toBeInstanceOf(TypeError);
      http.expectNone(() => true);
    }
  });

  it.each(OPERATIONS)('propagates HTTP errors for %s without interpreting or retrying', operation => {
    for (const [status, body] of [[401, { detail: 'Unauthorized' }], [403, { detail: 'Forbidden' }],
      [404, { detail: 'Sensor not found' }], [409, { detail: "Equipment with id '9' does not exist." }],
      [409, { detail: "Sensor with code 'T-12' already exists." }], [409, { detail: 'Unspecified conflict' }],
      [422, { detail: [{ loc: ['body', 'unit'], type: 'string_too_short' }] }],
      [500, 'Internal Server Error']] as const) {
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

  it.each(OPERATIONS)('propagates network failure for %s without retry', operation => {
    let error: HttpErrorResponse | undefined;
    const event = new ProgressEvent('error');
    request(operation).subscribe({ error: value => error = value });
    pending(operation).error(event);
    expect(error?.status).toBe(0);
    expect(error?.error).toBe(event);
    http.expectNone(() => true);
  });
});
