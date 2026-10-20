import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { defer, Observable } from 'rxjs';
import { API_PREFIX } from '../../../core/http/api-config';
import { SensorPage, SensorRead } from '../models/sensor.model';
import { SensorPageQuery } from '../models/sensor-page-query.model';
import { SensorCreate, SensorPatch } from '../models/sensor-write.model';

@Injectable({ providedIn: 'root' })
export class SensorsApiService {
  private readonly http = inject(HttpClient);

  list(query: SensorPageQuery): Observable<SensorPage> {
    return defer(() => {
      this.requireId(query?.equipment_id);
      this.requireStatus(query.status);
      let params = new HttpParams().set('equipment_id', query.equipment_id);
      if (query.page != null) params = params.set('page', query.page);
      if (query.page_size != null) params = params.set('page_size', query.page_size);
      if (query.search) params = params.set('search', query.search);
      if (query.status !== undefined) params = params.set('status', query.status);
      return this.http.get<SensorPage>(`${API_PREFIX}/sensors`, { params });
    });
  }

  getById(id: number): Observable<SensorRead> {
    return defer(() => {
      this.requireId(id);
      return this.http.get<SensorRead>(`${API_PREFIX}/sensors/${id}`);
    });
  }

  create(body: SensorCreate): Observable<SensorRead> {
    return defer(() => {
      for (const field of ['equipment_id', 'name', 'code', 'sensor_type', 'unit'] as const) {
        if (!Object.hasOwn(body, field) || body[field] == null) {
          throw new TypeError(`Sensor ${field} is required and cannot be null.`);
        }
      }
      this.requireId(body.equipment_id);
      const payload: SensorCreate = { ...this.editableBody(body), equipment_id: body.equipment_id,
        name: body.name, code: body.code, sensor_type: body.sensor_type, unit: body.unit };
      return this.http.post<SensorRead>(`${API_PREFIX}/sensors`, payload);
    });
  }

  patch(id: number, body: SensorPatch): Observable<SensorRead> {
    return defer(() => {
      this.requireId(id);
      // Difference calculation belongs to the future editor, not the transport.
      return this.http.patch<SensorRead>(`${API_PREFIX}/sensors/${id}`, this.editableBody(body));
    });
  }

  private editableBody(body: SensorPatch): SensorPatch {
    const payload: SensorPatch = {};
    const copy = <K extends keyof SensorPatch>(field: K) => {
      const value = body[field];
      if (!Object.hasOwn(body, field) || value === undefined) return;
      if (value === null && field !== 'description') {
        throw new TypeError(`Sensor ${field} cannot be null.`);
      }
      if (field === 'status') this.requireStatus(value);
      payload[field] = value;
    };
    for (const field of ['name', 'code', 'status', 'description'] as const) copy(field);
    return payload;
  }

  private requireId(id: number): void {
    if (!Number.isSafeInteger(id) || id < 1) throw new TypeError('Sensor reference must be a positive safe integer.');
  }

  private requireStatus(value: unknown): void {
    if (value !== undefined && value !== 'active' && value !== 'inactive') {
      throw new TypeError('Sensor status must be active or inactive.');
    }
  }
}
