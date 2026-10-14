import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { of } from 'rxjs';
import { ReferenceDataApiService } from '../../../core/api/reference-data-api.service';
import { DashboardRead } from '../models/dashboard.model';

// Routing suites exercise layout/focus, not reference loading. No real network calls.
export function provideDashboardTesting() {
  return [provideHttpClient(), provideHttpClientTesting(), {
    provide: ReferenceDataApiService,
    useValue: { getCompanies: () => of({ items: [], total: 0, page: 1, page_size: 50, pages: 0 }) }
  }];
}

export function emptyDashboardResponse(): DashboardRead {
  const ratio = () => ({ numerator: 0, denominator: 0, percentage: null });
  const coverage = () => ({ valid_values: 0, eligible_records: 0, ratio: ratio() });
  return {
    scope: { company_id: 7, site_id: null, equipment_id: null },
    period: { start_time: '2026-10-01T00:00:00Z', end_time: '2026-10-08T00:00:00Z', calculated_at: '2026-10-14T00:00:00Z' },
    assets: { sites: 0, equipments: 0, sensors: 0 },
    equipment_status: { total: 0, operational: 0, maintenance: 0, out_of_service: 0, other: 0, distribution: [], operational_ratio: ratio() },
    equipment_criticality: { total: 0, low: 0, medium: 0, high: 0, critical: 0, other: 0, distribution: [], high_or_critical: 0, high_or_critical_unavailable: 0 },
    sensor_coverage: { equipments_total: 0, equipments_with_active_sensor: 0, coverage: ratio() },
    sensor_status: { total: 0, active: 0, inactive: 0, other: 0, distribution: [], active_ratio: ratio() },
    measurements: {
      activity: { measurements_total: 0, active_sensors_total: 0, active_sensors_with_measurement: 0, active_sensors_reporting_ratio: ratio() },
      quality: { total: 0, good: 0, suspect: 0, bad: 0, missing: 0, estimated: 0, other: 0, distribution: [], good_ratio: ratio() },
      daily_volume: [{ date: '2026-10-01', count: 0 }], last_measurements: []
    },
    maintenance: {
      open: { total: 0, planned: 0, in_progress: 0, other: 0,
        priorities: { total: 0, low: 0, medium: 0, high: 0, critical: 0, other: 0, distribution: [] } },
      overdue: { overdue: 0, planned_without_planned_at: 0 },
      completed: { total: 0, completed_without_completed_at: 0,
        types: { total: 0, preventive: 0, corrective: 0, predictive: 0, other: 0, distribution: [] } },
      corrective: { corrective_completed: 0, completed_total: 0, ratio: ratio() },
      downtime: { total_minutes: 0, total_hours: 0, coverage: coverage() },
      cost: { total_cost: 0, currency: null, coverage: coverage() }
    }
  };
}
