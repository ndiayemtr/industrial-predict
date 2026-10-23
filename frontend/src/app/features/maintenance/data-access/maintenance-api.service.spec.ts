import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Observable } from 'rxjs';
import { expectTypeOf } from 'vitest';
import { Page } from '../../../core/models/page.model';
import { MaintenancePageQuery } from '../models/maintenance-page-query.model';
import { MaintenancePage, MaintenancePriority, MaintenanceRead, MaintenanceStatus, MaintenanceType } from '../models/maintenance.model';
import { MaintenanceApiService } from './maintenance-api.service';

const ROW: MaintenanceRead = {
  id: 12, equipment_id: 9, maintenance_type: 'preventive', status: 'planned', priority: 'medium', title: 'Inspection 日本',
  description: '', failure_code: null, root_cause: 'Cause déclarée', action_taken: null, technician: 'Équipe A',
  planned_at: '2026-10-23T17:30:00.123456+05:30', started_at: null, completed_at: null,
  downtime_minutes: 0, cost: 12.3456789012345, created_at: '2026-10-23T10:00:00.654321', updated_at: '2026-10-23T12:00:00.123456Z'
};
const page = (items: MaintenanceRead[] = [ROW]): MaintenancePage => ({ items, total: items.length, page: 1, page_size: 20, pages: items.length ? 1 : 0 });
const TYPES: MaintenanceType[] = ['preventive', 'corrective', 'predictive'];
const STATUSES: MaintenanceStatus[] = ['planned', 'in_progress', 'completed', 'cancelled'];
const PRIORITIES: MaintenancePriority[] = ['low', 'medium', 'high', 'critical'];

describe('MaintenanceApiService read-only data contract', () => {
  let api: MaintenanceApiService, http: HttpTestingController;
  const listRequest = () => http.expectOne(req => req.url === '/api/v1/maintenance');
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(MaintenanceApiService); http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.expectNone(req => req.method !== 'GET'); http.verify(); });
  function localError(query: unknown): void {
    let error: unknown;
    expect(() => api.list(query as MaintenancePageQuery).subscribe({ error: reason => error = reason })).not.toThrow();
    expect(error).toBeInstanceOf(TypeError); http.expectNone(() => true);
  }
  function invalidRecord(item: unknown, operation: 'list' | 'detail' = 'detail'): void {
    let error: unknown;
    const source: Observable<unknown> = operation === 'list' ? api.list({ equipment_id: 9 }) : api.getById(12);
    source.subscribe({ error: reason => error = reason });
    const req = operation === 'list' ? listRequest() : http.expectOne('/api/v1/maintenance/12');
    req.flush((operation === 'list' ? { ...page(), items: [item] } : item) as Parameters<typeof req.flush>[0]);
    expect(error).toBeInstanceOf(TypeError); http.expectNone(() => true);
  }

  it('defines eighteen exact fields, nullable types, strict enums, Page and only two public operations', () => {
    expectTypeOf<keyof MaintenanceRead>().toEqualTypeOf<'id' | 'equipment_id' | 'maintenance_type' | 'status' | 'priority' | 'title'
      | 'description' | 'failure_code' | 'root_cause' | 'action_taken' | 'technician' | 'planned_at' | 'started_at' | 'completed_at'
      | 'downtime_minutes' | 'cost' | 'created_at' | 'updated_at'>();
    expectTypeOf<MaintenanceRead['planned_at']>().toEqualTypeOf<string | null>();
    expectTypeOf<MaintenanceRead['description']>().toEqualTypeOf<string | null>();
    expectTypeOf<MaintenanceRead['created_at']>().toEqualTypeOf<string>();
    expectTypeOf<MaintenanceRead['cost']>().toEqualTypeOf<number | null>();
    expectTypeOf<MaintenanceRead['downtime_minutes']>().toEqualTypeOf<number | null>();
    expectTypeOf<MaintenanceType>().toEqualTypeOf<'preventive' | 'corrective' | 'predictive'>();
    expectTypeOf<MaintenanceStatus>().toEqualTypeOf<'planned' | 'in_progress' | 'completed' | 'cancelled'>();
    expectTypeOf<MaintenancePriority>().toEqualTypeOf<'low' | 'medium' | 'high' | 'critical'>();
    expectTypeOf<MaintenancePage>().toEqualTypeOf<Page<MaintenanceRead>>();
    expectTypeOf<keyof MaintenancePageQuery>().toEqualTypeOf<'equipment_id' | 'page' | 'page_size' | 'maintenance_type' | 'status'
      | 'priority' | 'search' | 'start_time' | 'end_time'>();
    expectTypeOf<MaintenancePageQuery['equipment_id']>().toEqualTypeOf<number>();
    expectTypeOf<keyof MaintenanceApiService>().toEqualTypeOf<'list' | 'getById'>();
    for (const method of ['create', 'update', 'post', 'patch', 'put', 'delete', 'remove', 'transfer', 'start', 'complete', 'cancel', 'getAll', 'getByEquipment']) {
      expect(method in api).toBe(false);
    }
  });

  it('is cold and requests only the singular paginated endpoint and detail without query/body', () => {
    api.list({ equipment_id: 9 }); api.getById(12); http.expectNone(() => true);
    api.list({ equipment_id: 9 }).subscribe(); const list = http.expectOne('/api/v1/maintenance?equipment_id=9');
    expect(list.request.method).toBe('GET'); expect(list.request.body).toBeNull(); list.flush(page());
    let received: MaintenanceRead | undefined; api.getById(12).subscribe(item => received = item);
    const detail = http.expectOne('/api/v1/maintenance/12'); expect(detail.request.method).toBe('GET');
    expect(detail.request.params.keys()).toEqual([]); expect(detail.request.body).toBeNull(); detail.flush(ROW);
    expect(received).toEqual(ROW); expect(Object.keys(received!)).toHaveLength(18);
  });

  it('whitelists nine parameters with status alias, preserving raw search/offset/fraction and frozen data', () => {
    const query = Object.freeze({ equipment_id: 9, page: 2, page_size: 100, maintenance_type: 'corrective' as const,
      status: 'completed' as const, priority: 'critical' as const, search: '  Révision_% 日本  ',
      start_time: '2026-10-23T17:30:00.123456+05:30', end_time: '2026-10-23T12:00:00.123457Z',
      company_id: 7, site_id: 8, sensor_id: 10, unit: 'EUR', sort: 'cost', maintenance_status: 'cancelled', planned_at: 'ignored' });
    const original = structuredClone(query); let received: MaintenancePage | undefined;
    api.list(query).subscribe(value => received = value); const req = listRequest();
    const keys = ['equipment_id', 'page', 'page_size', 'maintenance_type', 'status', 'priority', 'search', 'start_time', 'end_time'] as const;
    expect(req.request.params.keys().sort()).toEqual([...keys].sort());
    for (const key of keys) expect(req.request.params.get(key)).toBe(String(query[key]));
    expect(new URL(req.request.urlWithParams, 'https://test.invalid').searchParams.get('start_time')).toBe(query.start_time);
    const response = Object.freeze({ items: Object.freeze([Object.freeze({ ...ROW })]), total: 101, page: 2, page_size: 100, pages: 2 });
    req.flush(response); expect(received).toEqual(response); expect(query).toEqual(original);
  });

  it('keeps the subscribed equipment scope when the caller changes its object later', () => {
    const query = { equipment_id: 9 }; let received: MaintenancePage | undefined;
    api.list(query).subscribe(value => received = value); const req = listRequest(); query.equipment_id = 10;
    req.flush(page()); expect(received?.items[0].equipment_id).toBe(9);
  });
  it('omits undefined filters and lets backend pagination defaults apply without sending fabricated values', () => {
    api.list({ equipment_id: 9, page: undefined, page_size: undefined, status: undefined, maintenance_type: undefined,
      priority: undefined, search: undefined, start_time: undefined, end_time: undefined }).subscribe();
    const req = http.expectOne('/api/v1/maintenance?equipment_id=9'); expect(req.request.params.keys()).toEqual(['equipment_id']); req.flush(page([]));
  });
  it.each([1, 100])('preserves a valid size %s and a nonempty total on an out-of-range empty page', page_size => {
    let result: MaintenancePage | undefined; api.list({ equipment_id: 9, page: 3, page_size }).subscribe(value => result = value);
    const response = { items: [], total: 1, page: 3, page_size, pages: 1 }; listRequest().flush(response); expect(result).toEqual(response);
  });
  it.each(TYPES)('preserves maintenance_type %s', maintenance_type => {
    api.list({ equipment_id: 9, maintenance_type }).subscribe(result => expect(result.items[0].maintenance_type).toBe(maintenance_type));
    const req = listRequest(); expect(req.request.params.get('maintenance_type')).toBe(maintenance_type); req.flush(page([{ ...ROW, maintenance_type }]));
  });
  it.each(STATUSES)('preserves status %s without inventing mandatory status dates or transitions', status => {
    api.list({ equipment_id: 9, status }).subscribe(result => expect(result.items[0].status).toBe(status));
    const req = listRequest(); expect(req.request.params.get('status')).toBe(status);
    req.flush(page([{ ...ROW, status, planned_at: null, started_at: null, completed_at: null }]));
  });
  it.each(PRIORITIES)('preserves priority %s', priority => {
    api.list({ equipment_id: 9, priority }).subscribe(result => expect(result.items[0].priority).toBe(priority));
    const req = listRequest(); expect(req.request.params.get('priority')).toBe(priority); req.flush(page([{ ...ROW, priority }]));
  });
  it.each([' ', '日本', '😀'.repeat(100)])('sends accepted raw search unchanged: %s', search => {
    api.list({ equipment_id: 9, search }).subscribe(); const req = listRequest(); expect(req.request.params.get('search')).toBe(search); req.flush(page());
  });
  it.each([undefined, null, {}, { equipment_id: undefined }])('rejects absent list scope %j', localError);
  it.each([null, 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, NaN, Infinity, '9', true, undefined])('rejects invalid list/detail id %s without HTTP', id => {
    localError({ equipment_id: id }); let error: unknown; api.getById(id as number).subscribe({ error: reason => error = reason });
    expect(error).toBeInstanceOf(TypeError); http.expectNone(() => true);
  });
  it.each([null, 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, NaN, Infinity, '1'])('rejects invalid page %s', page => localError({ equipment_id: 9, page }));
  it.each([null, 0, -1, 101, 1.5, NaN, Infinity, '20'])('rejects invalid page_size %s', page_size => localError({ equipment_id: 9, page_size }));
  it.each(['maintenance_type', 'status', 'priority'] as const)('rejects invalid %s before HTTP', key => {
    for (const value of [null, '', 'UNKNOWN', ' planned', 'ACTIVE', true, 1]) localError({ equipment_id: 9, [key]: value });
  });
  it.each([null, '', 'x'.repeat(101), '😀'.repeat(101), 123, true])('rejects invalid raw search %s', search => localError({ equipment_id: 9, search }));

  const invalidTimes = [null, '', 0, '2026-10-23T12:00:00', '2026-10-23', '2026-10-23T12:00:00Z\n',
    '2026-10-23T12:00:00Z ', '0000-01-01T00:00:00Z', '2026-13-01T00:00:00Z', '2026-04-31T00:00:00Z',
    '1900-02-29T00:00:00Z', '2026-01-01T24:00:00Z', '2026-01-01T00:60:00Z', '2026-01-01T00:00:60Z',
    '2026-01-01T00:00:00+24:00', '2026-01-01T00:00:00-01:60', '2026-01-01T00:00:00.1234567Z'];
  it.each(invalidTimes)('blocks an invalid period without dropping either bound: %s', value => {
    localError({ equipment_id: 9, start_time: value }); localError({ equipment_id: 9, end_time: value });
  });
  it.each([
    ['2026-10-23T12:00:00Z', '2026-10-23T12:00:00Z'],
    ['2026-10-23T17:30:00.123456+05:30', '2026-10-23T12:00:00.123456Z'],
    ['2026-10-23T12:00:00.123457Z', '2026-10-23T12:00:00.123456Z'],
    ['2026-01-01T00:00:00-01:00', '2025-12-31T23:59:59.999999Z']
  ])('blocks equal/reversed instants %s / %s', (start_time, end_time) => localError({ equipment_id: 9, start_time, end_time }));
  it.each([
    ['2026-10-23T17:30:00.123456+05:30', '2026-10-23T12:00:00.123457Z'],
    ['2000-02-29T23:59:59.999999Z', '2000-03-01T00:00:00Z'],
    ['2026-01-01T00:00:00+01:00', '2025-12-31T23:00:00.000001Z']
  ])('preserves an ordered precise period %s / %s', (start_time, end_time) => {
    api.list({ equipment_id: 9, start_time, end_time }).subscribe(); const req = listRequest();
    expect(req.request.params.get('start_time')).toBe(start_time); expect(req.request.params.get('end_time')).toBe(end_time); req.flush(page());
  });
  it.each(['start_time', 'end_time'] as const)('allows a single future %s unchanged', key => {
    const value = '2099-01-01T00:00:00.123456-03:30'; api.list({ equipment_id: 9, [key]: value }).subscribe();
    const req = listRequest(); expect(req.request.params.keys().sort()).toEqual(['equipment_id', key].sort()); expect(req.request.params.get(key)).toBe(value); req.flush(page());
  });

  describe.each(['list', 'detail'] as const)('%s response validation', operation => {
    it.each(Object.keys(ROW))('requires field %s even if nullable', key => {
      const item: Record<string, unknown> = { ...ROW }; delete item[key]; invalidRecord(item, operation);
    });
    it.each([
      null, [], {}, { ...ROW, equipment_id: 0 }, { ...ROW, maintenance_type: 'PREVENTIVE' }, { ...ROW, status: 'active' },
      { ...ROW, priority: 'urgent' }, { ...ROW, title: null }, { ...ROW, title: 123 },
      { ...ROW, description: false }, { ...ROW, failure_code: 0 }, { ...ROW, root_cause: [] }, { ...ROW, action_taken: {} }, { ...ROW, technician: true }
    ])('rejects invalid identity, text or enum: %j', item => invalidRecord(item, operation));
    it.each([undefined, true, '12.5', NaN, Infinity, -Infinity, -0.01])('rejects invalid cost %s without coercion', cost => invalidRecord({ ...ROW, cost }, operation));
    it.each([undefined, true, '30', -1, 1.5, Infinity, Number.MAX_SAFE_INTEGER + 1])('rejects invalid minutes %s without calculating duration', downtime_minutes => invalidRecord({ ...ROW, downtime_minutes }, operation));
    it.each(['planned_at', 'started_at', 'completed_at'] as const)('rejects naive or malformed business date %s', key => {
      for (const value of ['2026-10-23T12:00:00.123456', '2026-02-30T12:00:00Z', 0]) invalidRecord({ ...ROW, [key]: value }, operation);
    });
    it('rejects reversed business chronology rather than silently correcting it', () => {
      invalidRecord({ ...ROW, started_at: '2026-10-23T12:00:00.123457Z', completed_at: '2026-10-23T17:30:00.123456+05:30' }, operation);
    });
    it.each(['created_at', 'updated_at'] as const)('rejects invalid administrative date %s but never infers an offset', key => {
      for (const value of [null, undefined, '', 'broken', '2026-02-29T12:00:00', '0000-01-01T00:00:00', '2026-01-01T25:00:00',
        '2026-01-01T00:61:00', '2026-01-01T00:00:60', '2026-01-01T00:00:00.1234567', '2026-01-01T00:00:00\n', '2026-01-01T00:00:00+24:00']) {
        invalidRecord({ ...ROW, [key]: value }, operation);
      }
    });
  });

  it('preserves all nullable fields as null, without filling title, dates, cost or minutes', () => {
    const item = { ...ROW, title: '', description: null, failure_code: null, root_cause: null, action_taken: null,
      technician: null, planned_at: null, started_at: null, completed_at: null, downtime_minutes: null, cost: null };
    api.getById(12).subscribe(value => expect(value).toEqual(item)); http.expectOne('/api/v1/maintenance/12').flush(Object.freeze(item));
  });
  it.each([0, -0, Number.MIN_VALUE, Number.MAX_VALUE, 123.45678901234567])('preserves finite nonnegative cost %s without rounding/currency', cost => {
    api.getById(12).subscribe(value => { expect(Object.is(value.cost, cost)).toBe(true); expect(value.downtime_minutes).toBe(0); });
    http.expectOne('/api/v1/maintenance/12').flush({ ...ROW, cost });
  });
  it.each(['2026-10-23T12:00:00.123456', '2000-02-29T12:00', '2026-10-23T17:30:00.000000+05:30', '2026-10-23T12:00:00Z'])('preserves administrative ISO source %s exactly, including absent offset', value => {
    api.getById(12).subscribe(item => { expect(item.created_at).toBe(value); expect(item.updated_at).toBe(value); });
    http.expectOne('/api/v1/maintenance/12').flush({ ...ROW, created_at: value, updated_at: value });
  });
  it('allows equal business instants with distinct offsets, and does not equate downtime to elapsed duration', () => {
    const item = { ...ROW, started_at: '2026-10-23T12:00:00.123456Z', completed_at: '2026-10-23T17:30:00.123456+05:30', downtime_minutes: 30 };
    api.getById(12).subscribe(value => expect(value).toEqual(item)); http.expectOne('/api/v1/maintenance/12').flush(item);
  });
  it('rejects wrong detail id and foreign equipment page, without another broader request', () => {
    invalidRecord({ ...ROW, id: 13 }); invalidRecord({ ...ROW, equipment_id: 10 }, 'list');
  });
  it('keeps distinct records in server order without deduplication or response mutation', () => {
    const response = page([ROW, { ...ROW, id: 11 }]); const original = structuredClone(response);
    api.list({ equipment_id: 9 }).subscribe(value => { expect(value.items.map(item => item.id)).toEqual([12, 11]); expect(value).toEqual(original); });
    listRequest().flush(response); expect(response).toEqual(original);
  });
  it.each([null, {}, { ...page(), items: {} }, { ...page(), total: -1 }, { ...page(), total: '1' }, { ...page(), pages: -1 },
    { ...page(), pages: 2 }, { ...page(), page: 0 }, { ...page(), page_size: 0 }, { ...page(), page_size: 101 }, { ...page(), total: Number.MAX_SAFE_INTEGER + 1 },
    { ...page(), page_size: 1, total: 2, pages: 2, items: [ROW, ROW] }])('rejects invalid Page metadata/shape %j', response => {
    let error: unknown; api.list({ equipment_id: 9 }).subscribe({ error: reason => error = reason }); listRequest().flush(response); expect(error).toBeInstanceOf(TypeError);
  });

  describe.each(['list', 'detail'] as const)('%s transport errors', operation => {
    it.each([400, 401, 403, 404, 409, 422, 500, 503])('propagates HTTP %s and original body without retry/fallback', status => {
      let error: unknown; const source: Observable<unknown> = operation === 'list' ? api.list({ equipment_id: 9 }) : api.getById(12);
      source.subscribe({ error: reason => error = reason }); const req = operation === 'list' ? listRequest() : http.expectOne('/api/v1/maintenance/12');
      const body = { detail: [{ loc: ['query', 'status'], msg: 'original' }] }; req.flush(body, { status, statusText: 'Failure' });
      expect(error).toBeInstanceOf(HttpErrorResponse); expect((error as HttpErrorResponse).status).toBe(status); expect((error as HttpErrorResponse).error).toEqual(body); http.expectNone(() => true);
    });
    it('propagates network error without returning empty items', () => {
      let error: unknown; const source: Observable<unknown> = operation === 'list' ? api.list({ equipment_id: 9 }) : api.getById(12);
      source.subscribe({ error: reason => error = reason }); const req = operation === 'list' ? listRequest() : http.expectOne('/api/v1/maintenance/12');
      req.error(new ProgressEvent('error')); expect((error as HttpErrorResponse).status).toBe(0); http.expectNone(() => true);
    });
    it('cancels an obsolete request on unsubscribe', () => {
      const source: Observable<unknown> = operation === 'list' ? api.list({ equipment_id: 9 }) : api.getById(12);
      const subscription = source.subscribe(); const req = operation === 'list' ? listRequest() : http.expectOne('/api/v1/maintenance/12');
      subscription.unsubscribe(); expect(req.cancelled).toBe(true);
    });
  });
});
