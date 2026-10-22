import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { defer, map, Observable } from 'rxjs';
import { API_PREFIX } from '../../../core/http/api-config';
import { measurementInstant, validateMeasurementPeriod } from '../utils/measurement-time';
import { MeasurementPageQuery } from '../models/measurement-page-query.model';
import { MeasurementPage, MeasurementQuality, MeasurementRead } from '../models/measurement.model';

const qualities: readonly MeasurementQuality[] = ['good', 'suspect', 'bad', 'missing', 'estimated'];

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
      validateMeasurementPeriod(query.start_time, query.end_time);
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
    measurementInstant(item.timestamp); this.quality(item.quality);
    if (typeof item.value !== 'number' || !Number.isFinite(item.value)) {
      throw new TypeError('Measurement value must be a finite number; no coercion is applied.');
    }
  }
}
