import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { expectTypeOf } from 'vitest';
import { Page } from '../../../core/models/page.model';
import { PredictionPageQuery } from '../models/prediction-page-query.model';
import { JsonObject, JsonValue, PredictionPage, PredictionRead, PredictionType } from '../models/prediction.model';
import { PredictionsApiService } from './predictions-api.service';

const ENDPOINT = '/api/v1/equipments/9/predictions';
const ROW: PredictionRead = {
  id: 12, equipment_id: 9, sensor_id: null, measurement_id: null,
  prediction_type: 'anomaly', score: 0.85, level: null, is_alert: false,
  model_name: 'unified', model_version: null, horizon_hours: null,
  details: { reason: 'Écart déclaré', nested: [true, false, null, 0, { label: '日本' }] },
  predicted_at: '2026-10-23T17:30:00.123456+05:30', created_at: '2026-10-23T12:00:01.654321Z'
};
const page = (items: PredictionRead[] = [ROW]): PredictionPage => ({
  items, total: items.length, page: 1, page_size: 20, pages: items.length ? 1 : 0
});
const TYPES: PredictionType[] = ['anomaly', 'failure_risk', 'health_score', 'rul'];
const NULLABLE = ['sensor_id', 'measurement_id', 'level', 'is_alert', 'model_name', 'model_version', 'horizon_hours', 'details'] as const;

describe('PredictionsApiService GET-only contract', () => {
  let api: PredictionsApiService;
  let http: HttpTestingController;
  const request = () => http.expectOne(req => req.url === ENDPOINT && req.method === 'GET');
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    api = TestBed.inject(PredictionsApiService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.expectNone(req => req.method !== 'GET' || /\/(rul|health-score|recommendations)(?:\?|$)/.test(req.url));
    http.verify();
  });

  function invalidQuery(query: unknown): void {
    let failure: unknown;
    expect(() => api.list(query as PredictionPageQuery).subscribe({ error: error => failure = error })).not.toThrow();
    expect(failure).toBeInstanceOf(TypeError);
    http.expectNone(() => true);
  }

  function invalidPage(response: unknown): void {
    let failure: unknown;
    let emitted = false;
    api.list({ equipment_id: 9 }).subscribe({ next: () => emitted = true, error: error => failure = error });
    const req = request();
    req.flush(response as Parameters<typeof req.flush>[0]);
    expect(failure).toBeInstanceOf(TypeError);
    expect(emitted).toBe(false);
    http.expectNone(() => true);
  }

  function invalidRecord(item: unknown): void { invalidPage({ ...page(), items: [item] }); }

  it('defines exactly fourteen fields, four types, recursive JSON, nullable keys, Page and one public method', () => {
    expectTypeOf<keyof PredictionRead>().toEqualTypeOf<'id' | 'equipment_id' | 'sensor_id' | 'measurement_id' | 'prediction_type'
      | 'score' | 'level' | 'is_alert' | 'model_name' | 'model_version' | 'horizon_hours' | 'details' | 'predicted_at' | 'created_at'>();
    expectTypeOf<PredictionType>().toEqualTypeOf<'anomaly' | 'failure_risk' | 'health_score' | 'rul'>();
    expectTypeOf<PredictionRead['details']>().toEqualTypeOf<JsonObject | null>();
    expectTypeOf<JsonValue>().toEqualTypeOf<string | number | boolean | null | JsonValue[] | JsonObject>();
    expectTypeOf<PredictionRead['is_alert']>().toEqualTypeOf<boolean | null>();
    expectTypeOf<PredictionRead['sensor_id']>().toEqualTypeOf<number | null>();
    expectTypeOf<PredictionRead['measurement_id']>().toEqualTypeOf<number | null>();
    expectTypeOf<PredictionRead['horizon_hours']>().toEqualTypeOf<number | null>();
    expectTypeOf<PredictionRead['level']>().toEqualTypeOf<string | null>();
    expectTypeOf<PredictionRead['model_name']>().toEqualTypeOf<string | null>();
    expectTypeOf<PredictionRead['model_version']>().toEqualTypeOf<string | null>();
    expectTypeOf<PredictionRead['predicted_at']>().toEqualTypeOf<string>();
    expectTypeOf<PredictionRead['created_at']>().toEqualTypeOf<string>();
    expectTypeOf<PredictionPage>().toEqualTypeOf<Page<PredictionRead>>();
    expectTypeOf<PredictionPageQuery['equipment_id']>().toEqualTypeOf<number>();
    expectTypeOf<keyof PredictionPageQuery>().toEqualTypeOf<'equipment_id' | 'page' | 'page_size' | 'prediction_type'
      | 'level' | 'is_alert' | 'start_time' | 'end_time'>();
    expectTypeOf<keyof PredictionsApiService>().toEqualTypeOf<'list'>();
    expect(Object.keys(ROW)).toHaveLength(14);
    for (const method of ['getById', 'getAll', 'create', 'update', 'delete', 'predict', 'calculate', 'post', 'put', 'patch']) {
      expect(method in api).toBe(false);
    }
  });

  it('is cold and sends one GET without a body or fabricated defaults', () => {
    const source = api.list({ equipment_id: 9 });
    http.expectNone(() => true);
    let received: PredictionPage | undefined;
    source.subscribe(value => received = value);
    const req = http.expectOne(ENDPOINT);
    expect(req.request.method).toBe('GET'); expect(req.request.body).toBeNull();
    expect(req.request.params.keys()).toEqual([]);
    req.flush(page()); expect(received).toEqual(page());
    http.expectNone(() => true);
  });

  it('whitelists seven query parameters and preserves false, whitespace, offsets and microseconds', () => {
    const query = Object.freeze({ equipment_id: 9, page: 2, page_size: 100, prediction_type: 'failure_risk' as const,
      level: '  Niveau_日本_%  ', is_alert: false,
      start_time: '2026-10-23T17:30:00.123456+05:30', end_time: '2026-10-23T12:00:00.123457Z',
      company_id: 7, site_id: 8, sensor_id: 10, sort: 'score', search: 'ignored' });
    const original = structuredClone(query);
    api.list(query).subscribe();
    const req = request();
    const keys = ['page', 'page_size', 'prediction_type', 'level', 'is_alert', 'start_time', 'end_time'] as const;
    expect(req.request.params.keys().sort()).toEqual([...keys].sort());
    for (const key of keys) expect(req.request.params.get(key)).toBe(String(query[key]));
    expect(new URL(req.request.urlWithParams, 'https://test.invalid').searchParams.get('start_time')).toBe(query.start_time);
    req.flush({ items: [], total: 1, page: 2, page_size: 100, pages: 1 });
    expect(query).toEqual(original);
  });

  it.each([
    { page: 1 }, { page_size: 100 }, { prediction_type: 'rul' as const }, { level: 'custom' },
    { is_alert: true }, { is_alert: false }, { start_time: ROW.predicted_at }, { end_time: ROW.predicted_at }
  ])('sends a single filter or pagination parameter %j', filter => {
    api.list({ equipment_id: 9, ...filter }).subscribe(); const req = request();
    expect(req.request.params.keys()).toEqual(Object.keys(filter));
    for (const [key, value] of Object.entries(filter)) expect(req.request.params.get(key)).toBe(String(value));
    req.flush({ ...page([]), page_size: 'page_size' in filter ? filter.page_size : 20 });
  });

  it('omits every optional undefined value', () => {
    api.list({ equipment_id: 9, page: undefined, page_size: undefined, prediction_type: undefined,
      level: undefined, is_alert: undefined, start_time: undefined, end_time: undefined }).subscribe();
    const req = http.expectOne(ENDPOINT); expect(req.request.params.keys()).toEqual([]); req.flush(page([]));
  });

  it.each(TYPES)('reads type %s without inventing its scale, level or details', prediction_type => {
    const item = { ...ROW, prediction_type, score: prediction_type === 'rul' ? 0 : 125.123456789,
      level: 'unknown-producer-level', details: { arbitrary: ['<script>untrusted</script>', -3] } };
    let received: PredictionPage | undefined;
    api.list({ equipment_id: 9, prediction_type }).subscribe(value => received = value);
    const req = request(); expect(req.request.params.get('prediction_type')).toBe(prediction_type);
    req.flush(page([item])); expect(received?.items[0]).toEqual(item);
  });

  it.each([true, false, null])('preserves nullable is_alert=%s without coercion', is_alert => {
    let received: PredictionPage | undefined;
    api.list({ equipment_id: 9 }).subscribe(value => received = value);
    request().flush(page([{ ...ROW, is_alert }])); expect(received?.items[0].is_alert).toBe(is_alert);
  });

  it('preserves all nullable keys as null and all fourteen fields', () => {
    const item = { ...ROW };
    for (const key of NULLABLE) item[key] = null;
    api.list({ equipment_id: 9 }).subscribe(value => {
      expect(value.items[0]).toEqual(item); expect(Object.keys(value.items[0])).toHaveLength(14);
    });
    request().flush(page([item]));
  });

  it.each(['', 'unfamiliar', '😀'.repeat(51)])('accepts free response level %j without reclassifying the score', level => {
    api.list({ equipment_id: 9 }).subscribe(value => expect(value.items[0].level).toBe(level));
    request().flush(page([{ ...ROW, level }]));
  });

  it.each([' ', '日本', '😀'.repeat(50)])('preserves valid free filter level %s', level => {
    api.list({ equipment_id: 9, level }).subscribe();
    const req = request(); expect(req.request.params.get('level')).toBe(level); req.flush(page([]));
  });

  it.each([0, -0, -1, Number.MIN_VALUE, Number.MAX_VALUE, 123.45678901234567])('preserves finite score %s without range assumptions or rounding', score => {
    api.list({ equipment_id: 9 }).subscribe(value => expect(Object.is(value.items[0].score, score)).toBe(true));
    request().flush(page([{ ...ROW, score }]));
  });

  it('keeps valid positive optional IDs and horizon unchanged', () => {
    const item = { ...ROW, sensor_id: 3, measurement_id: 4, horizon_hours: 0.000001, model_version: 'v1' };
    api.list({ equipment_id: 9 }).subscribe(value => expect(value.items[0]).toEqual(item)); request().flush(page([item]));
  });

  it.each([1, 100])('allows empty history and out-of-range empty pages at size %s', page_size => {
    api.list({ equipment_id: 9, page_size }).subscribe(value => expect(value.total).toBe(0));
    request().flush({ ...page([]), page_size });
    api.list({ equipment_id: 9, page: 3, page_size }).subscribe(value => {
      expect(value.items).toEqual([]); expect(value.total).toBe(1); expect(value.page).toBe(3);
    });
    request().flush({ items: [], total: 1, page: 3, page_size, pages: 1 });
  });

  it('preserves a multipage response, server order and equal prediction timestamps', () => {
    const response = { items: [{ ...ROW, id: 11 }], total: 2, page: 2, page_size: 1, pages: 2 };
    api.list({ equipment_id: 9, page: 2, page_size: 1 }).subscribe(value => expect(value).toEqual(response));
    request().flush(response);
    const ordered = page([ROW, { ...ROW, id: 11 }]);
    api.list({ equipment_id: 9 }).subscribe(value => expect(value.items.map(item => item.id)).toEqual([12, 11]));
    request().flush(ordered);
  });

  it('captures equipment and pagination at subscription without mutating frozen responses', () => {
    const query = { equipment_id: 9, page: 1, page_size: 20 };
    const response = Object.freeze({ ...page(), items: Object.freeze([Object.freeze({ ...ROW })]) });
    let received: PredictionPage | undefined;
    api.list(query).subscribe(value => received = value);
    const req = request(); query.equipment_id = 10; query.page = 4; query.page_size = 1;
    req.flush(response); expect(received).toBe(response);
  });

  it.each([
    ['2026-10-23T17:30:00.123456+05:30', '2026-10-23T12:00:00.123456Z'],
    ['2026-10-23T12:00:00Z', '2026-10-23T12:00:00Z'],
    ['2026-10-23T12:00:00.123456Z', '2026-10-23T12:00:00.123457Z']
  ])('preserves inclusive or equal bounds verbatim %s / %s', (start_time, end_time) => {
    api.list({ equipment_id: 9, start_time, end_time }).subscribe(); const req = request();
    expect(req.request.params.get('start_time')).toBe(start_time);
    expect(req.request.params.get('end_time')).toBe(end_time);
    req.flush(page([]));
  });

  it.each([undefined, null, [], {}, { equipment_id: undefined }])('rejects missing scope %j before HTTP', invalidQuery);
  it.each([null, 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, NaN, Infinity, '9', true])('rejects invalid equipment id %s', equipment_id => invalidQuery({ equipment_id }));
  it.each([null, 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1, NaN, Infinity, '1', true])('rejects invalid page %s', page => invalidQuery({ equipment_id: 9, page }));
  it.each([null, 0, -1, 101, 1.5, NaN, Infinity, '20', true])('rejects invalid size %s', page_size => invalidQuery({ equipment_id: 9, page_size }));
  it.each([null, '', 'x'.repeat(51), '😀'.repeat(51), 0, false])('rejects invalid filter level %s', level => invalidQuery({ equipment_id: 9, level }));
  it.each([null, 'true', 'false', 0, 1, ''])('rejects invalid alert filter %s', is_alert => invalidQuery({ equipment_id: 9, is_alert }));
  it.each([null, '', 'ANOMALY', 'unknown', 1, false])('rejects invalid type filter %s', prediction_type => invalidQuery({ equipment_id: 9, prediction_type }));
  it.each([null, '', 0, '2026-10-23', '2026-10-23T12:00:00', '2026-02-29T12:00:00Z',
    '2026-10-23T12:00:00Z\n', '2026-10-23T12:00:00.1234567Z', '2026-10-23T12:00:00+24:00'])('blocks invalid bounds %s before HTTP', value => {
    invalidQuery({ equipment_id: 9, start_time: value }); invalidQuery({ equipment_id: 9, end_time: value });
  });
  it('rejects reversed microsecond instants before HTTP', () => {
    invalidQuery({ equipment_id: 9, start_time: '2026-10-23T12:00:00.123457Z', end_time: '2026-10-23T17:30:00.123456+05:30' });
  });

  it.each(Object.keys(ROW))('requires response field %s even if nullable', key => {
    const item: Record<string, unknown> = { ...ROW }; delete item[key]; invalidRecord(item);
  });
  it.each([null, [], {}, { ...ROW, equipment_id: 10 }, { ...ROW, prediction_type: 'unknown' },
    { ...ROW, prediction_type: 'ANOMALY' }])('rejects invalid record shape/type/scope %j', invalidRecord);
  it.each(['id', 'equipment_id', 'sensor_id', 'measurement_id'] as const)('rejects invalid response identifier %s', key => {
    for (const value of [0, -1, 1.5, '9', true, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) invalidRecord({ ...ROW, [key]: value });
  });
  it.each([null, undefined, '0.5', true, NaN, Infinity, -Infinity])('rejects non-finite or nonnumeric score %s', score => invalidRecord({ ...ROW, score }));
  it.each([undefined, 0, -1, '24', true, NaN, Infinity, -Infinity])('rejects invalid horizon %s', horizon_hours => invalidRecord({ ...ROW, horizon_hours }));
  it.each(['level', 'model_name', 'model_version'] as const)('rejects nonstring response text %s', key => {
    for (const value of [undefined, 0, false, [], {}]) invalidRecord({ ...ROW, [key]: value });
  });
  it.each([undefined, 'false', 0, 1, []])('rejects malformed alert %s, distinguishing null/false/absence', is_alert => invalidRecord({ ...ROW, is_alert }));
  it.each(['predicted_at', 'created_at'] as const)('requires offset and real calendar in %s', key => {
    for (const value of [null, undefined, '', 0, '2026-10-23T12:00:00', '2026-02-30T12:00:00Z',
      '2026-10-23T12:00:00.1234567Z', '2026-10-23T12:00:00Z\n']) invalidRecord({ ...ROW, [key]: value });
  });

  it.each([
    null, [], {}, { ...page(), items: null }, { ...page(), items: {} }, { ...page(), total: -1 },
    { ...page(), total: '1' }, { ...page(), total: Number.MAX_SAFE_INTEGER + 1 }, { ...page(), total: Infinity },
    { ...page(), page: 0 }, { ...page(), page: 2 }, { ...page(), pages: -1 }, { ...page(), pages: 2 },
    { ...page(), pages: NaN }, { ...page(), page_size: 0 }, { ...page(), page_size: 101 }, { ...page(), page_size: 1 },
    { ...page(), total: 0, pages: 0 }, { ...page(), items: Array.from({ length: 21 }, () => ROW), total: 21, pages: 2 }
  ])('rejects inconsistent Page metadata or structure %j', invalidPage);
  it.each(['items', 'total', 'page', 'page_size', 'pages'])('requires Page field %s', key => {
    const response: Record<string, unknown> = { ...page() }; delete response[key]; invalidPage(response);
  });

  it.each([[], 'text', 1, false, undefined, { missing: undefined }, { nested: [NaN] }, { nested: Infinity },
    { nested: 1n }, { nested: () => 1 }, { nested: Symbol('bad') }, { nested: new Date() }])('rejects non-JSON or non-object details case %#', details => invalidRecord({ ...ROW, details }));
  it('rejects cyclic and sparse JSON rather than overflowing or filling missing values', () => {
    const cycle: Record<string, unknown> = {}; cycle['self'] = cycle;
    invalidRecord({ ...ROW, details: cycle }); invalidRecord({ ...ROW, details: { sparse: new Array(2) } });
  });
  it('accepts generic empty, shared, deep and large JSON without applying presentation caps', () => {
    const shared: JsonObject = { source: 'producer', empty: {} };
    let nested: JsonObject = { text: 'x'.repeat(10_001), flags: [true, false, null] };
    for (let level = 0; level < 20; level++) nested = { nested };
    const details: JsonObject = { first: shared, second: shared, nested };
    api.list({ equipment_id: 9 }).subscribe(value => expect(value.items[0].details).toEqual(details));
    request().flush(page([{ ...ROW, details }]));
    api.list({ equipment_id: 9 }).subscribe(value => expect(value.items[0].details).toEqual({}));
    request().flush(page([{ ...ROW, details: {} }]));
  });

  it.each([401, 403, 404, 422, 500, 503])('propagates HTTP %s and the original body without retry or empty fallback', status => {
    let failure: unknown; let emitted = false;
    api.list({ equipment_id: 9 }).subscribe({ next: () => emitted = true, error: error => failure = error });
    const body = status === 422 ? { detail: [{ loc: ['query', 'level'], msg: 'original' }] } : { detail: 'original' };
    request().flush(body, { status, statusText: 'Failure' });
    expect(failure).toBeInstanceOf(HttpErrorResponse);
    expect((failure as HttpErrorResponse).status).toBe(status);
    expect((failure as HttpErrorResponse).error).toEqual(body); expect(emitted).toBe(false);
    http.expectNone(() => true);
  });
  it('propagates network failure without a fallback', () => {
    let failure: unknown;
    api.list({ equipment_id: 9 }).subscribe({ error: error => failure = error });
    request().error(new ProgressEvent('error')); expect((failure as HttpErrorResponse).status).toBe(0);
    http.expectNone(() => true);
  });
  it('cancels an unsubscribed GET without issuing another request', () => {
    const subscription = api.list({ equipment_id: 9 }).subscribe(); const req = request();
    subscription.unsubscribe(); expect(req.cancelled).toBe(true); http.expectNone(() => true);
  });
});
