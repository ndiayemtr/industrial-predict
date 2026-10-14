import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { DashboardFilters } from '../models/dashboard-filters.model';
import { DashboardRead } from '../models/dashboard.model';
import { DashboardApiService } from './dashboard-api.service';

const FILTERS: DashboardFilters = {
  company_id: 7,
  start_time: '2026-10-01T12:34:56.123Z',
  end_time: '2026-10-08T12:34:56.123Z'
};

// Test-only transport fixture; never imported by the application.
function dashboardResponse(): DashboardRead {
  return {
    scope: { company_id: 7, site_id: null, equipment_id: null },
    period: { start_time: FILTERS.start_time, end_time: FILTERS.end_time,
      calculated_at: '2026-10-08T12:35:00Z' },
    assets: { sites: 1, equipments: 2, sensors: 3 },
    equipment_status: { total: 2, operational: 1, maintenance: 0, out_of_service: 0,
      other: 1, distribution: [{ value: 'operational', count: 1 }, { value: 'custom', count: 1 }],
      operational_ratio: { numerator: 1, denominator: 2, percentage: 50 } },
    equipment_criticality: { total: 2, low: 1, medium: 0, high: 1, critical: 0, other: 0,
      distribution: [{ value: 'low', count: 1 }, { value: 'high', count: 1 }],
      high_or_critical: 1, high_or_critical_unavailable: 0 },
    sensor_coverage: { equipments_total: 2, equipments_with_active_sensor: 1,
      coverage: { numerator: 1, denominator: 2, percentage: 50 } },
    sensor_status: { total: 3, active: 2, inactive: 0, other: 1,
      distribution: [{ value: 'active', count: 2 }, { value: 'custom', count: 1 }],
      active_ratio: { numerator: 2, denominator: 3, percentage: 66.67 } },
    measurements: {
      activity: { measurements_total: 2, active_sensors_total: 2, active_sensors_with_measurement: 1,
        active_sensors_reporting_ratio: { numerator: 1, denominator: 2, percentage: 50 } },
      quality: { total: 2, good: 1, suspect: 0, bad: 0, missing: 0, estimated: 0, other: 1,
        distribution: [{ value: 'good', count: 1 }, { value: 'legacy-quality', count: 1 }],
        good_ratio: { numerator: 1, denominator: 2, percentage: 50 } },
      daily_volume: [{ date: '2026-10-01', count: 2 }, { date: '2026-10-02', count: 0 }],
      last_measurements: [
        { sensor_id: 3, sensor_name: 'Test sensor', sensor_code: 'TEST-3', equipment_id: 4,
          timestamp: '2026-09-30T00:00:00Z', value: 0, unit: 'C', quality: 'legacy-quality',
          age_seconds: 734100 },
        { sensor_id: 5, sensor_name: 'Unobserved sensor', sensor_code: 'TEST-5', equipment_id: 4,
          timestamp: null, value: null, unit: null, quality: null, age_seconds: null }
      ]
    },
    maintenance: {
      open: { total: 2, planned: 1, in_progress: 1, other: 0,
        priorities: { total: 2, low: 0, medium: 0, high: 1, critical: 0, other: 1,
          distribution: [{ value: 'high', count: 1 }, { value: 'custom', count: 1 }] } },
      overdue: { overdue: 1, planned_without_planned_at: 0 },
      completed: { total: 3, completed_without_completed_at: 1,
        types: { total: 3, preventive: 1, corrective: 1, predictive: 0, other: 1,
          distribution: [{ value: 'preventive', count: 1 }, { value: 'corrective', count: 1 },
            { value: 'custom', count: 1 }] } },
      corrective: { corrective_completed: 1, completed_total: 3,
        ratio: { numerator: 1, denominator: 3, percentage: 33.33 } },
      downtime: { total_minutes: null, total_hours: null,
        coverage: { valid_values: 0, eligible_records: 3,
          ratio: { numerator: 0, denominator: 3, percentage: 0 } } },
      cost: { total_cost: 100.5, currency: null,
        coverage: { valid_values: 2, eligible_records: 3,
          ratio: { numerator: 2, denominator: 3, percentage: 66.67 } } }
    }
  };
}

describe('DashboardApiService', () => {
  let service: DashboardApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    service = TestBed.inject(DashboardApiService);
  });

  afterEach(() => http.verify());

  it('does not request data on injection or before subscription', () => {
    http.expectNone(() => true);
    service.getDashboard(FILTERS);
    http.expectNone(() => true);
  });

  it('uses a relative GET with exactly the required parameters and no request body', () => {
    service.getDashboard(FILTERS).subscribe();
    const req = http.expectOne((request) => request.url === '/api/v1/dashboard');
    const request = req.request;
    expect(request.method).toBe('GET');
    expect(request.body).toBeNull();
    expect(request.params.keys().sort()).toEqual(['company_id', 'end_time', 'start_time']);
    expect(request.params.get('company_id')).toBe('7');
    expect(request.params.get('start_time')).toBe(FILTERS.start_time);
    expect(request.params.get('end_time')).toBe(FILTERS.end_time);
    req.flush(dashboardResponse());
  });

  it('includes both optional filters when provided without changing the input', () => {
    const filters = Object.freeze({ ...FILTERS, site_id: 2, equipment_id: 4 });
    service.getDashboard(filters).subscribe();
    const req = http.expectOne((request) => request.url === '/api/v1/dashboard');
    expect(req.request.params.get('site_id')).toBe('2');
    expect(req.request.params.get('equipment_id')).toBe('4');
    expect(filters).toEqual({ ...FILTERS, site_id: 2, equipment_id: 4 });
    req.flush(dashboardResponse());
  });

  it.each([null, undefined])('omits optional filters that are %s', (absent) => {
    service.getDashboard({ ...FILTERS, site_id: absent, equipment_id: absent }).subscribe();
    const req = http.expectOne((request) => request.url === '/api/v1/dashboard');
    expect(req.request.params.has('site_id')).toBe(false);
    expect(req.request.params.has('equipment_id')).toBe(false);
    req.flush(dashboardResponse());
  });

  it('accepts equipment_id without site_id', () => {
    service.getDashboard({ ...FILTERS, equipment_id: 4 }).subscribe();
    const req = http.expectOne((request) => request.url === '/api/v1/dashboard');
    expect(req.request.params.get('equipment_id')).toBe('4');
    expect(req.request.params.has('site_id')).toBe(false);
    req.flush(dashboardResponse());
  });

  it('preserves UTC dates, precision and the exclusive end without defaults', () => {
    service.getDashboard(FILTERS).subscribe();
    const req = http.expectOne((request) => request.url === '/api/v1/dashboard');
    const encoded = new URL(req.request.urlWithParams, 'https://test.invalid').searchParams;
    expect(encoded.get('start_time')).toBe(FILTERS.start_time);
    expect(encoded.get('end_time')).toBe(FILTERS.end_time);
    req.flush(dashboardResponse());
  });

  it('encodes an explicit timezone offset without losing its plus sign or shifting instants', () => {
    const filters = { ...FILTERS, start_time: '2026-10-01T14:34:56.123+02:00' };
    service.getDashboard(filters).subscribe();
    const req = http.expectOne((request) => request.url === '/api/v1/dashboard');
    expect(req.request.urlWithParams).toContain('%2B02:00');
    expect(new URL(req.request.urlWithParams, 'https://test.invalid').searchParams.get('start_time'))
      .toBe(filters.start_time);
    req.flush(dashboardResponse());
  });

  it('passes every response block through, including nulls, zero, unknown categories and partial coverage', () => {
    const response = dashboardResponse();
    response.sensor_coverage.coverage.percentage = null;
    let received: DashboardRead | undefined;
    service.getDashboard(FILTERS).subscribe((value) => received = value);
    http.expectOne((request) => request.url === '/api/v1/dashboard').flush(response);
    expect(received).toEqual(response);
    expect(received?.measurements.last_measurements[0].timestamp).toBe('2026-09-30T00:00:00Z');
    expect(received?.measurements.last_measurements[0].value).toBe(0);
    expect(received?.measurements.last_measurements[1].value).toBeNull();
    expect(received?.sensor_coverage.coverage.percentage).toBeNull();
    expect(received?.maintenance.cost.currency).toBeNull();
    expect(received?.maintenance.cost.coverage.ratio.percentage).toBe(66.67);
  });

  it.each([
    { status: 400, body: { detail: 'Site does not belong to company' } },
    { status: 404, body: { detail: 'Company not found' } },
    { status: 422, body: { detail: [{ loc: ['query', 'company_id'], msg: 'Invalid input', type: 'int_parsing' }] } },
    { status: 500, body: 'Internal Server Error' }
  ])('propagates HTTP $status and its error body without retrying', ({ status, body }) => {
    let received: HttpErrorResponse | undefined;
    service.getDashboard(FILTERS).subscribe({ error: (error: HttpErrorResponse) => received = error });
    http.expectOne((request) => request.url === '/api/v1/dashboard')
      .flush(body, { status, statusText: 'Test error' });
    expect(received).toBeInstanceOf(HttpErrorResponse);
    expect(received?.status).toBe(status);
    expect(received?.error).toEqual(body);
    http.expectNone(() => true);
  });

  it('propagates a network failure as status zero without automatically retrying', () => {
    const networkError = new ProgressEvent('error');
    let received: HttpErrorResponse | undefined;
    service.getDashboard(FILTERS).subscribe({ error: (error: HttpErrorResponse) => received = error });
    http.expectOne((request) => request.url === '/api/v1/dashboard').error(networkError);
    expect(received?.status).toBe(0);
    expect(received?.error).toBe(networkError);
    http.expectNone(() => true);
  });
});
