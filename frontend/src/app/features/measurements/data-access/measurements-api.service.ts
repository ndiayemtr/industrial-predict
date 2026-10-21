import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { defer, map, Observable } from 'rxjs';
import { API_PREFIX } from '../../../core/http/api-config';
import { MeasurementPageQuery } from '../models/measurement-page-query.model';
import { MeasurementPage, MeasurementQuality, MeasurementRead } from '../models/measurement.model';

const qualities: readonly MeasurementQuality[] = ['good', 'suspect', 'bad', 'missing', 'estimated'];

// Compare instants at microsecond precision without Date's millisecond rounding.
// The result is validation-only: the original ISO string remains the HTTP value.
function instant(value: unknown): bigint {
  const match = typeof value === 'string'
    ? /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?(Z|[+-]\d{2}:\d{2})$/.exec(value) : null;
  if (!match || match[0] !== value) throw new TypeError('Measurement time must be ISO with an offset and at most six fractional digits.');
  const [, y, m, d, h, min, sec = '0', fraction = '', zone] = match;
  const year = Number(y), month = Number(m), day = Number(d), hour = Number(h), minute = Number(min), second = Number(sec);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const monthDays = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const offsetHours = zone === 'Z' ? 0 : Number(zone.slice(1, 3));
  const offsetMinutes = zone === 'Z' ? 0 : Number(zone.slice(4, 6));
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > monthDays[month - 1]
    || hour > 23 || minute > 59 || second > 59 || offsetHours > 23 || offsetMinutes > 59) {
    throw new TypeError('Measurement time contains invalid calendar or offset components.');
  }
  const previousYear = year - 1;
  const days = 365 * previousYear + Math.floor(previousYear / 4) - Math.floor(previousYear / 100)
    + Math.floor(previousYear / 400) + monthDays.slice(0, month - 1).reduce((sum, count) => sum + count, 0) + day - 1;
  const offset = (zone.startsWith('-') ? -1 : 1) * (offsetHours * 60 + offsetMinutes);
  return BigInt(((days * 24 + hour) * 60 + minute) * 60 + second - offset * 60) * 1_000_000n
    + BigInt(fraction.padEnd(6, '0'));
}

@Injectable({ providedIn: 'root' })
export class MeasurementsApiService {
  private readonly http = inject(HttpClient);

  list(query: MeasurementPageQuery): Observable<MeasurementPage> {
    return defer(() => {
      const sensorId = query?.sensor_id;
      this.integer(sensorId, 1);
      if (query.page !== undefined) this.integer(query.page, 1);
      if (query.page_size !== undefined) this.integer(query.page_size, 1, 100);
      if (query.quality !== undefined) this.quality(query.quality);
      const start = query.start_time === undefined ? undefined : instant(query.start_time);
      const end = query.end_time === undefined ? undefined : instant(query.end_time);
      if (start !== undefined && end !== undefined && start >= end) {
        throw new TypeError('Measurement start_time must be before exclusive end_time.');
      }
      let params = new HttpParams().set('sensor_id', sensorId);
      for (const key of ['page', 'page_size', 'quality', 'start_time', 'end_time'] as const) {
        const value = query[key];
        if (value !== undefined) params = params.set(key, value);
      }
      return this.http.get<MeasurementPage>(`${API_PREFIX}/measurements`, { params }).pipe(map(page => {
        if (!page || !Array.isArray(page.items)) throw new TypeError('Invalid Measurement page.');
        this.integer(page.total, 0); this.integer(page.pages, 0);
        this.integer(page.page, 1); this.integer(page.page_size, 1);
        for (const item of page.items) {
          this.measurement(item);
          if (item.sensor_id !== sensorId) throw new TypeError('Measurement belongs to another sensor.');
        }
        return page;
      }));
    });
  }

  getById(id: number): Observable<MeasurementRead> {
    return defer(() => {
      this.integer(id, 1);
      return this.http.get<MeasurementRead>(`${API_PREFIX}/measurements/${id}`).pipe(map(item => {
        this.measurement(item);
        if (item.id !== id) throw new TypeError('Measurement response does not match the requested id.');
        return item;
      }));
    });
  }

  private integer(value: unknown, minimum: number, maximum = Number.MAX_SAFE_INTEGER): void {
    if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum || value > maximum) {
      throw new TypeError('Measurement identifiers and pagination must be safe integers within their bounds.');
    }
  }

  private quality(value: unknown): void {
    if (!qualities.includes(value as MeasurementQuality)) throw new TypeError('Invalid Measurement quality.');
  }

  private measurement(item: MeasurementRead): void {
    if (!item || typeof item !== 'object') throw new TypeError('Invalid Measurement response.');
    this.integer(item.id, 1); this.integer(item.sensor_id, 1);
    instant(item.timestamp); this.quality(item.quality);
    if (typeof item.value !== 'number' || !Number.isFinite(item.value)) {
      throw new TypeError('Measurement value must be a finite number; no coercion is applied.');
    }
  }
}
