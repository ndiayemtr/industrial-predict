import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { defer, map, Observable } from 'rxjs';
import { API_PREFIX } from '../../../core/http/api-config';
import { measurementInstant } from '../../measurements/utils/measurement-time';
import { PredictionPageQuery } from '../models/prediction-page-query.model';
import { PredictionPage } from '../models/prediction.model';
import { validatePredictionPeriod } from '../utils/prediction-time';

const predictionTypes = ['anomaly', 'failure_risk', 'health_score', 'rul'] as const;

function integer(value: unknown, minimum: number, maximum = Number.MAX_SAFE_INTEGER): asserts value is number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum || value > maximum) {
    throw new TypeError('Prediction integer is outside its allowed bounds.');
  }
}

function finite(value: unknown): asserts value is number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new TypeError('Expected a finite Prediction number.');
}

function object(value: unknown): asserts value is Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)
    || (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null)) {
    throw new TypeError('Expected a Prediction JSON object.');
  }
}

function predictionType(value: unknown): void {
  if (typeof value !== 'string' || !predictionTypes.some(type => type === value)) {
    throw new TypeError('Invalid Prediction type.');
  }
}

// Iterative traversal avoids a call-stack limit. No UI preview size/depth cap
// belongs in the transport contract. Reject cycles, but allow shared subobjects.
function jsonObject(value: unknown): void {
  object(value);
  const active = new WeakSet<object>();
  const pending: { value: unknown; exit?: boolean }[] = [{ value }];
  while (pending.length) {
    const entry = pending.pop()!;
    const current = entry.value;
    if (current === null || typeof current === 'string' || typeof current === 'boolean') continue;
    if (typeof current === 'number') { finite(current); continue; }
    if (typeof current !== 'object') throw new TypeError('Invalid Prediction JSON value.');
    if (entry.exit) { active.delete(current); continue; }
    if (active.has(current)) throw new TypeError('Cyclic Prediction JSON value.');
    if (!Array.isArray(current)) object(current);
    if (Object.getOwnPropertySymbols(current).length) throw new TypeError('Invalid Prediction JSON keys.');
    active.add(current);
    pending.push({ value: current, exit: true });
    const children: unknown[] = Array.isArray(current) ? current : Object.values(current);
    for (const child of children) pending.push({ value: child });
  }
}

function record(value: unknown, equipmentId: number): void {
  object(value);
  integer(value['id'], 1);
  integer(value['equipment_id'], 1);
  if (value['equipment_id'] !== equipmentId) throw new TypeError('Prediction belongs to another equipment.');
  for (const key of ['sensor_id', 'measurement_id'] as const) {
    if (value[key] !== null) integer(value[key], 1);
  }
  predictionType(value['prediction_type']);
  finite(value['score']);
  for (const key of ['level', 'model_name', 'model_version'] as const) {
    if (value[key] !== null && typeof value[key] !== 'string') throw new TypeError('Invalid nullable Prediction text.');
  }
  if (value['is_alert'] !== null && typeof value['is_alert'] !== 'boolean') throw new TypeError('Invalid Prediction alert.');
  if (value['horizon_hours'] !== null) {
    finite(value['horizon_hours']);
    if (value['horizon_hours'] <= 0) throw new TypeError('Prediction horizon must be positive.');
  }
  if (value['details'] !== null) jsonObject(value['details']);
  measurementInstant(value['predicted_at']);
  measurementInstant(value['created_at']);
}

function page(value: unknown, equipmentId: number, requestedPage: number, requestedSize: number): asserts value is PredictionPage {
  object(value);
  if (!Array.isArray(value['items'])) throw new TypeError('Invalid Prediction items.');
  integer(value['total'], 0);
  integer(value['pages'], 0);
  integer(value['page'], 1);
  integer(value['page_size'], 1, 100);
  if (value['page'] !== requestedPage || value['page_size'] !== requestedSize
    || value['pages'] !== Math.ceil(value['total'] / value['page_size'])
    || value['items'].length > value['page_size'] || value['items'].length > value['total']
    || (value['page'] > value['pages'] && value['items'].length !== 0)) {
    throw new TypeError('Inconsistent Prediction pagination.');
  }
  for (const item of value['items']) record(item, equipmentId);
}

@Injectable({ providedIn: 'root' })
export class PredictionsApiService {
  private readonly http = inject(HttpClient);

  list(query: PredictionPageQuery): Observable<PredictionPage> {
    return defer(() => {
      object(query);
      const equipmentId = query.equipment_id;
      integer(equipmentId, 1);
      if (query.page !== undefined) integer(query.page, 1);
      if (query.page_size !== undefined) integer(query.page_size, 1, 100);
      if (query.prediction_type !== undefined) predictionType(query.prediction_type);
      if (query.level !== undefined && (typeof query.level !== 'string'
        || Array.from(query.level).length < 1 || Array.from(query.level).length > 50)) {
        throw new TypeError('Prediction level must contain 1 to 50 characters.');
      }
      if (query.is_alert !== undefined && typeof query.is_alert !== 'boolean') throw new TypeError('Invalid Prediction alert filter.');
      validatePredictionPeriod(query.start_time, query.end_time);
      const requestedPage = query.page ?? 1;
      const requestedSize = query.page_size ?? 20;
      let params = new HttpParams();
      for (const key of ['page', 'page_size', 'prediction_type', 'level', 'is_alert', 'start_time', 'end_time'] as const) {
        const value = query[key];
        if (value !== undefined) params = params.set(key, value);
      }
      return this.http.get<unknown>(`${API_PREFIX}/equipments/${equipmentId}/predictions`, { params }).pipe(map(response => {
        page(response, equipmentId, requestedPage, requestedSize);
        return response;
      }));
    });
  }
}
