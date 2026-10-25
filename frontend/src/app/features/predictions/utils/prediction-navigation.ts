import { convertToParamMap, ParamMap } from '@angular/router';
import { PredictionsQuery } from '../models/predictions-state.model';
import { positiveId, predictionQueryKeys, readPredictionQuery } from './prediction-query';

export interface PredictionNavigationContext {
  from: 'predictions';
  query: PredictionsQuery;
}

function complete(query: PredictionsQuery): boolean {
  return [query.company_id, query.site_id, query.equipment_id].every(positiveId);
}

// Only applied, validated query values cross the fixed Equipment destination.
export function predictionNavigationParams(query: Readonly<PredictionsQuery>): Record<string, string> {
  const entries = predictionQueryKeys.filter(key => query[key] !== undefined).map(key => [key, String(query[key])]);
  const validated = readPredictionQuery(convertToParamMap(Object.fromEntries(entries)));
  if (!complete(validated)) throw new TypeError('Contexte Prédictions incomplet.');
  return { from: 'predictions', ...Object.fromEntries(predictionQueryKeys
    .filter(key => validated[key] !== undefined).map(key => ['pre_' + key, String(validated[key])])) };
}

// Context is never an authorization or an arbitrary return URL. Invalid input
// returns no context; the caller may offer fresh scope only after parent checks.
export function readPredictionNavigationContext(params: ParamMap, equipmentId: number | undefined): PredictionNavigationContext | null {
  if (params.getAll('from').length !== 1 || params.get('from') !== 'predictions') return null;
  const entries: [string, string][] = [];
  for (const key of predictionQueryKeys) {
    const values = params.getAll('pre_' + key);
    if (values.length > 1) return null;
    if (values.length === 1) entries.push([key, values[0]]);
  }
  try {
    const query = readPredictionQuery(convertToParamMap(Object.fromEntries(entries)));
    return complete(query) && query.equipment_id === equipmentId ? { from: 'predictions', query } : null;
  } catch { return null; }
}
