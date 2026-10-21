import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Observable } from 'rxjs';
import { expectTypeOf } from 'vitest';
import { Page } from '../../../core/models/page.model';
import { MeasurementPageQuery } from '../models/measurement-page-query.model';
import { MeasurementPage, MeasurementQuality, MeasurementRead } from '../models/measurement.model';
import { MeasurementsApiService } from './measurements-api.service';

const ROW: MeasurementRead = { id: 12, sensor_id: 9, timestamp: '2026-10-21T17:30:00.123456+05:30', value: -12.3456789012345, quality: 'suspect' };
const page = (items: MeasurementRead[] = [ROW]): MeasurementPage => ({ items, total: items.length, page: 1, page_size: 20, pages: items.length ? 1 : 0 });
const QUALITIES: MeasurementQuality[] = ['good', 'suspect', 'bad', 'missing', 'estimated'];

describe('MeasurementsApiService read-only contract', () => {
  let api: MeasurementsApiService, http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(MeasurementsApiService); http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.expectNone(req => req.method !== 'GET'); http.verify(); });
  const listRequest = () => http.expectOne(req => req.url === '/api/v1/measurements');
  function localError(query: unknown): void {
    let error: unknown;
    expect(() => api.list(query as MeasurementPageQuery).subscribe({ error: value => error = value })).not.toThrow();
    expect(error).toBeInstanceOf(TypeError); http.expectNone(() => true);
  }

  it('defines exactly five read fields, five qualities, a scoped query and two public methods', () => {
    expectTypeOf<keyof MeasurementRead>().toEqualTypeOf<'id' | 'sensor_id' | 'timestamp' | 'value' | 'quality'>();
    expectTypeOf<MeasurementRead['timestamp']>().toEqualTypeOf<string>();
    expectTypeOf<MeasurementRead['value']>().toEqualTypeOf<number>();
    expectTypeOf<MeasurementQuality>().toEqualTypeOf<'good' | 'suspect' | 'bad' | 'missing' | 'estimated'>();
    expectTypeOf<MeasurementPage>().toEqualTypeOf<Page<MeasurementRead>>();
    expectTypeOf<keyof MeasurementPageQuery>().toEqualTypeOf<'sensor_id' | 'page' | 'page_size' | 'quality' | 'start_time' | 'end_time'>();
    expectTypeOf<MeasurementPageQuery['sensor_id']>().toEqualTypeOf<number>();
    expectTypeOf<keyof MeasurementsApiService>().toEqualTypeOf<'list' | 'getById'>();
    for (const method of ['create', 'post', 'patch', 'update', 'delete', 'remove', 'transfer', 'getAll', 'getBySensor', 'getByPeriod']) expect(method in api).toBe(false);
  });

  it('is cold and never calls a non-paginated specialized endpoint', () => {
    api.list({ sensor_id: 9 }); api.getById(12); http.expectNone(() => true);
    api.list({ sensor_id: 9 }).subscribe(); listRequest().flush(page());
    api.getById(12).subscribe(); http.expectOne('/api/v1/measurements/12').flush(ROW);
  });

  it('whitelists parameters, preserves offset/microseconds and never mutates the query', () => {
    const query = { sensor_id: 9, page: 2, page_size: 100, quality: 'estimated' as const,
      start_time: '2026-10-21T17:30:00.123456+05:30', end_time: '2026-10-21T12:00:00.123457Z',
      company_id: 1, site_id: 2, equipment_id: 3, unit: '°C', search: 'ignored', status: 'active', sort: 'value', extra: 1 };
    const original = structuredClone(query); let received: MeasurementPage | undefined;
    api.list(query).subscribe(value => received = value);
    const req = listRequest(); expect(req.request.method).toBe('GET'); expect(req.request.body).toBeNull();
    expect(req.request.params.keys().sort()).toEqual(['sensor_id', 'page', 'page_size', 'quality', 'start_time', 'end_time'].sort());
    for (const key of ['sensor_id', 'page', 'page_size', 'quality', 'start_time', 'end_time'] as const)
      expect(req.request.params.get(key)).toBe(String(query[key]));
    expect(new URL(req.request.urlWithParams, 'https://test.invalid').searchParams.get('start_time')).toBe(query.start_time);
    const response = { items: [{ ...ROW, quality: 'estimated' as const }], total: 101, page: 2, page_size: 100, pages: 2 };
    req.flush(response); expect(received).toEqual(response); expect(query).toEqual(original);
  });

  it('keeps the subscribed sensor scope if the caller later changes its query object', () => {
    const query = { sensor_id: 9 }; let received: MeasurementPage | undefined;
    api.list(query).subscribe(value => received = value); const req = listRequest(); query.sensor_id = 10;
    req.flush(page()); expect(received?.items[0].sensor_id).toBe(9);
  });

  it.each([{}, { page: undefined, page_size: undefined, quality: undefined, start_time: undefined, end_time: undefined }])
    ('omits defaults and absent filters: %j', query => {
      api.list({ sensor_id: 9, ...query }).subscribe(); const req = http.expectOne('/api/v1/measurements?sensor_id=9');
      expect(req.request.params.keys()).toEqual(['sensor_id']); req.flush(page([]));
    });

  it.each([1, 100])('preserves valid size %s and an out-of-range empty page', size => {
    let received: MeasurementPage | undefined;
    api.list({ sensor_id: 9, page: 3, page_size: size }).subscribe(value => received = value);
    const req = listRequest(); expect(req.request.params.get('page')).toBe('3'); expect(req.request.params.get('page_size')).toBe(String(size));
    const response = { items: [], total: 1, page: 3, page_size: size, pages: 1 }; req.flush(response); expect(received).toEqual(response);
  });

  it.each(QUALITIES)('keeps quality %s distinct in queries and responses', quality => {
    let received: MeasurementPage | undefined;
    api.list({ sensor_id: 9, quality }).subscribe(value => received = value);
    const req = listRequest(); expect(req.request.params.get('quality')).toBe(quality);
    req.flush(page([{ ...ROW, quality, value: -7.125 }])); expect(received?.items[0]).toEqual({ ...ROW, quality, value: -7.125 });
  });

  it.each([0, -0, -99.25, Number.MIN_VALUE, Number.MAX_VALUE, 1.2345678901234567])('preserves finite value %s including missing-quality rows', value => {
    let received: MeasurementRead | undefined;
    api.getById(12).subscribe(item => received = item); http.expectOne('/api/v1/measurements/12').flush({ ...ROW, quality: 'missing', value });
    expect(Object.is(received?.value, value)).toBe(true); expect(received?.quality).toBe('missing'); expect(received?.timestamp).toBe(ROW.timestamp);
  });

  it('preserves response order and distinct ids at the same instant without deduplication', () => {
    let received: MeasurementPage | undefined;
    api.list({ sensor_id: 9 }).subscribe(value => received = value);
    listRequest().flush(page([ROW, { ...ROW, id: 11 }])); expect(received?.items.map(item => item.id)).toEqual([12, 11]);
  });

  it.each([undefined, null, 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, NaN, Infinity, '9', true])
    ('rejects invalid ids %s before any HTTP in both reads', id => {
      localError({ sensor_id: id }); let error: unknown;
      expect(() => api.getById(id as number).subscribe({ error: value => error = value })).not.toThrow();
      expect(error).toBeInstanceOf(TypeError); http.expectNone(() => true);
    });
  it.each([undefined, null, {}])('refuses missing query/scope %s', query => localError(query));
  it.each([null, 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, '2', NaN, Infinity])('rejects invalid page %s', value => localError({ sensor_id: 9, page: value }));
  it.each([null, 0, -1, 101, 1.5, '20', NaN, Infinity])('rejects invalid page_size %s', value => localError({ sensor_id: 9, page_size: value }));
  it.each([null, '', 'GOOD', ' good', 'unknown', true, 1])('rejects invalid quality %s', quality => localError({ sensor_id: 9, quality }));

  const invalidTimes = [null, 0, new Date(0), '', '2026-10-21T12:00:00', '2026-10-21',
    '2026-10-21T12:00:00Z ', '2026-10-21T12:00:00Z\n', '0000-01-01T00:00:00Z', '2026-00-01T00:00:00Z', '2026-13-01T00:00:00Z',
    '2026-01-00T00:00:00Z', '2026-04-31T00:00:00Z', '1900-02-29T00:00:00Z', '2026-02-29T00:00:00Z',
    '2026-01-01T24:00:00Z', '2026-01-01T00:60:00Z', '2026-01-01T00:00:60Z',
    '2026-01-01T00:00:00+24:00', '2026-01-01T00:00:00-01:60', '2026-01-01T00:00:00.1234567Z'];
  it.each(invalidTimes)('rejects invalid temporal filters without trimming, guessing or truncating: %s', value => {
    localError({ sensor_id: 9, start_time: value }); localError({ sensor_id: 9, end_time: value });
  });

  it.each([
    ['2026-10-21T12:00:00Z', '2026-10-21T12:00:00Z'],
    ['2026-10-21T17:30:00.123456+05:30', '2026-10-21T12:00:00.123456Z'],
    ['2026-10-21T12:00:00.123457Z', '2026-10-21T12:00:00.123456Z'],
    ['2026-01-01T10:00:00-03:00', '2026-01-01T12:00:00Z'],
    ['2026-01-01T00:00:00-01:00', '2025-12-31T23:59:59.999999Z']
  ])('rejects equal/reversed instants %s / %s at microsecond precision', (start_time, end_time) => localError({ sensor_id: 9, start_time, end_time }));

  it.each([
    ['2026-10-21T12:00:00.123456Z', '2026-10-21T12:00:00.123457Z'],
    ['2026-10-21T17:30:00.123456+05:30', '2026-10-21T12:00:00.123457Z'],
    ['2026-01-01T13:00:00+02:00', '2026-01-01T12:00:00Z'],
    ['2026-01-01T00:00:00+01:00', '2025-12-31T23:00:00.000001Z'],
    ['2000-02-29T23:59:59.999999Z', '2000-03-01T00:00:00Z'],
    ['2026-01-01T00:00:00.1Z', '2026-01-01T00:00:00.100001Z'],
    ['0001-01-01T00:00:00Z', '9999-12-31T23:59:59.999999Z']
  ])('validates real instants without rewriting %s / %s', (start_time, end_time) => {
    api.list({ sensor_id: 9, start_time, end_time }).subscribe(); const req = listRequest();
    expect(req.request.params.get('start_time')).toBe(start_time); expect(req.request.params.get('end_time')).toBe(end_time); req.flush(page());
  });

  it.each(['start_time', 'end_time'] as const)('allows a single future %s unchanged without imposing Dashboard rules', key => {
    const value = '2099-01-01T00:00:00.654321-03:30'; api.list({ sensor_id: 9, [key]: value }).subscribe();
    const req = listRequest(); expect(req.request.params.get(key)).toBe(value);
    expect(req.request.params.keys().sort()).toEqual(['sensor_id', key].sort()); req.flush(page());
  });
  it('accepts minute precision and detail timestamps with their original offset', () => {
    api.list({ sensor_id: 9, start_time: '2026-01-01T12:00Z', end_time: '2026-01-01T12:01Z' }).subscribe(); listRequest().flush(page());
    let received: MeasurementRead | undefined; api.getById(12).subscribe(item => received = item);
    const req = http.expectOne('/api/v1/measurements/12'); expect(req.request.params.keys()).toEqual([]); req.flush(ROW); expect(received).toEqual(ROW);
  });

  it.each(['list', 'detail'] as const)('rejects invalid numbers in %s responses rather than coercing them', operation => {
    for (const value of [null, undefined, true, '12.5', NaN, Infinity, -Infinity]) {
      let error: unknown;
      const response: Observable<unknown> = operation === 'list' ? api.list({ sensor_id: 9 }) : api.getById(12);
      response.subscribe({ error: reason => error = reason });
      const req = operation === 'list' ? listRequest() : http.expectOne('/api/v1/measurements/12');
      const item = { ...ROW, value }; req.flush(operation === 'list' ? { ...page(), items: [item] } : item); expect(error).toBeInstanceOf(TypeError);
    }
  });
  it.each([null, { ...ROW, id: 13 }, { ...ROW, sensor_id: 0 }, { ...ROW, quality: 'GOOD' }, { ...ROW, timestamp: '2026-01-01T00:00:00' }])
    ('rejects invalid detail shape, identity, quality or timestamp: %j', item => {
      let error: unknown; api.getById(12).subscribe({ error: reason => error = reason }); http.expectOne('/api/v1/measurements/12').flush(item);
      expect(error).toBeInstanceOf(TypeError);
    });
  it.each([null, {}, { ...page(), total: -1 }, { ...page(), pages: -1 }, { ...page(), page: 0 }, { ...page(), page_size: 0 },
    { ...page(), items: [{ ...ROW, sensor_id: 10 }] }])('rejects invalid page or foreign sensor without widening the request: %j', response => {
      let error: unknown; api.list({ sensor_id: 9 }).subscribe({ error: reason => error = reason }); listRequest().flush(response);
      expect(error).toBeInstanceOf(TypeError); http.expectNone(() => true);
    });

  describe.each(['list', 'detail'] as const)('%s HTTP failures', operation => {
    it.each([400, 401, 403, 404, 409, 422, 500, 503])('propagates HTTP %s without retry or fabricated fallback', status => {
      let error: unknown; const source: Observable<unknown> = operation === 'list' ? api.list({ sensor_id: 9 }) : api.getById(12);
      source.subscribe({ error: reason => error = reason }); const req = operation === 'list' ? listRequest() : http.expectOne('/api/v1/measurements/12');
      const body = { detail: [{ loc: ['query', 'start_time'], msg: 'original error' }] }; req.flush(body, { status, statusText: 'Failure' });
      expect(error).toBeInstanceOf(HttpErrorResponse); expect((error as HttpErrorResponse).status).toBe(status);
      expect((error as HttpErrorResponse).error).toEqual(body); http.expectNone(() => true);
    });
    it('propagates a network error without retry', () => {
      let error: unknown; const source: Observable<unknown> = operation === 'list' ? api.list({ sensor_id: 9 }) : api.getById(12);
      source.subscribe({ error: reason => error = reason }); const req = operation === 'list' ? listRequest() : http.expectOne('/api/v1/measurements/12');
      req.error(new ProgressEvent('error')); expect(error).toBeInstanceOf(HttpErrorResponse); expect((error as HttpErrorResponse).status).toBe(0); http.expectNone(() => true);
    });
    it('cancels an obsolete read on unsubscribe', () => {
      const source: Observable<unknown> = operation === 'list' ? api.list({ sensor_id: 9 }) : api.getById(12);
      const subscription = source.subscribe();
      const req = operation === 'list' ? listRequest() : http.expectOne('/api/v1/measurements/12'); subscription.unsubscribe(); expect(req.cancelled).toBe(true);
    });
  });
});
