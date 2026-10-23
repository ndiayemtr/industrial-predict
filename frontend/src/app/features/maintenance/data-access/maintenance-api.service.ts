import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { defer, map, Observable } from 'rxjs';
import { API_PREFIX } from '../../../core/http/api-config';
// Pure precision helpers only; no dependency on Measurements HTTP or state.
import { measurementInstant, validateMeasurementPeriod } from '../../measurements/utils/measurement-time';
import { MaintenancePageQuery } from '../models/maintenance-page-query.model';
import { MaintenancePage, MaintenanceRead } from '../models/maintenance.model';

const types = ['preventive', 'corrective', 'predictive'] as const;
const statuses = ['planned', 'in_progress', 'completed', 'cancelled'] as const;
const priorities = ['low', 'medium', 'high', 'critical'] as const;

@Injectable({ providedIn: 'root' })
export class MaintenanceApiService {
  private readonly http = inject(HttpClient);

  list(query: MaintenancePageQuery): Observable<MaintenancePage> {
    return defer(() => {
      const equipmentId = query?.equipment_id;
      this.integer(equipmentId, 1);
      if (query.page !== undefined) this.integer(query.page, 1);
      if (query.page_size !== undefined) this.integer(query.page_size, 1, 100);
      if (query.maintenance_type !== undefined) this.enumValue(query.maintenance_type, types);
      if (query.status !== undefined) this.enumValue(query.status, statuses);
      if (query.priority !== undefined) this.enumValue(query.priority, priorities);
      if (query.search !== undefined && (typeof query.search !== 'string'
        || Array.from(query.search).length < 1 || Array.from(query.search).length > 100)) {
        throw new TypeError('Invalid Maintenance search length or type.');
      }
      validateMeasurementPeriod(query.start_time, query.end_time);
      let params = new HttpParams().set('equipment_id', equipmentId);
      for (const key of ['page', 'page_size', 'maintenance_type', 'status', 'priority', 'search', 'start_time', 'end_time'] as const) {
        const value = query[key];
        if (value !== undefined) params = params.set(key, value);
      }
      return this.http.get<MaintenancePage>(`${API_PREFIX}/maintenance`, { params }).pipe(map(page => {
        if (!page || !Array.isArray(page.items)) throw new TypeError('Invalid Maintenance page.');
        this.integer(page.total, 0); this.integer(page.pages, 0);
        this.integer(page.page, 1); this.integer(page.page_size, 1, 100);
        if (page.pages !== Math.ceil(page.total / page.page_size) || page.items.length > page.page_size) {
          throw new TypeError('Inconsistent Maintenance pagination.');
        }
        for (const item of page.items) {
          this.record(item);
          if (item.equipment_id !== equipmentId) throw new TypeError('Maintenance belongs to another equipment.');
        }
        return page;
      }));
    });
  }

  getById(id: number): Observable<MaintenanceRead> {
    return defer(() => {
      this.integer(id, 1);
      return this.http.get<MaintenanceRead>(`${API_PREFIX}/maintenance/${id}`).pipe(map(item => {
        this.record(item);
        if (item.id !== id) throw new TypeError('Maintenance response does not match the requested id.');
        return item;
      }));
    });
  }

  private integer(value: unknown, minimum: number, maximum = Number.MAX_SAFE_INTEGER): void {
    if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum || value > maximum) {
      throw new TypeError('Maintenance identifiers and integers must be safe and within bounds.');
    }
  }

  private enumValue(value: unknown, allowed: readonly string[]): void {
    if (typeof value !== 'string' || !allowed.includes(value)) throw new TypeError('Invalid Maintenance enum.');
  }

  private record(item: MaintenanceRead): void {
    if (!item || typeof item !== 'object' || Array.isArray(item)) throw new TypeError('Invalid Maintenance record.');
    this.integer(item.id, 1); this.integer(item.equipment_id, 1);
    this.enumValue(item.maintenance_type, types); this.enumValue(item.status, statuses); this.enumValue(item.priority, priorities);
    if (typeof item.title !== 'string') throw new TypeError('Maintenance title must be a string.');
    for (const key of ['description', 'failure_code', 'root_cause', 'action_taken', 'technician'] as const) {
      if (item[key] !== null && typeof item[key] !== 'string') throw new TypeError('Invalid Maintenance text.');
    }
    for (const key of ['planned_at', 'started_at', 'completed_at'] as const) {
      if (item[key] !== null) measurementInstant(item[key]);
    }
    if (item.started_at !== null && item.completed_at !== null
      && measurementInstant(item.started_at) > measurementInstant(item.completed_at)) {
      throw new TypeError('Maintenance start must not follow completion.');
    }
    if (item.cost !== null && (typeof item.cost !== 'number' || !Number.isFinite(item.cost) || item.cost < 0)) {
      throw new TypeError('Maintenance cost must be finite and nonnegative, or null.');
    }
    if (item.downtime_minutes !== null) this.integer(item.downtime_minutes, 0);
    this.administrativeTime(item.created_at); this.administrativeTime(item.updated_at);
  }

  private administrativeTime(value: unknown): void {
    if (typeof value !== 'string') throw new TypeError('Invalid Maintenance administrative timestamp.');
    if (/(Z|[+-]\d{2}:\d{2})$/.test(value)) { measurementInstant(value); return; }
    // Validate naive calendar components only. Never append Z or infer an instant.
    const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?$/.exec(value);
    if (!parts || parts[0] !== value) throw new TypeError('Invalid naive Maintenance timestamp.');
    const [, y, m, d, h, min, sec = '0'] = parts;
    const year = Number(y), month = Number(m), day = Number(d);
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    if (year < 1 || month < 1 || month > 12 || day < 1 || day > days[month - 1]
      || Number(h) > 23 || Number(min) > 59 || Number(sec) > 59) {
      throw new TypeError('Invalid naive Maintenance calendar components.');
    }
  }
}
