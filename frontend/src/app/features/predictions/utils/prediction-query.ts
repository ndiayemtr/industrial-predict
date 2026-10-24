import { ParamMap } from '@angular/router';
import { PredictionsQuery } from '../models/predictions-state.model';
import { PredictionType } from '../models/prediction.model';
import { validatePredictionPeriod } from './prediction-time';

export const predictionTypes: readonly PredictionType[] = ['anomaly', 'failure_risk', 'health_score', 'rul'];
export const predictionQueryKeys = ['company_id', 'site_id', 'equipment_id', 'page', 'page_size',
  'prediction_type', 'level', 'is_alert', 'start_time', 'end_time'] as const;
export const positiveId = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0;

export function readPredictionQuery(params: ParamMap): PredictionsQuery {
  for (const key of predictionQueryKeys) {
    if (params.getAll(key).length > 1) throw new TypeError('Un paramètre de l’URL est répété. Corrigez le contexte ou réinitialisez la sélection.');
  }
  const integer = (key: string, fallback?: number, max = Number.MAX_SAFE_INTEGER): number | undefined => {
    if (!params.has(key)) return fallback;
    const raw = params.get(key)!;
    if (!/^\d+$/.test(raw) || !positiveId(Number(raw)) || Number(raw) > max) {
      throw new TypeError('Le contexte ou la pagination de l’URL est invalide.');
    }
    return Number(raw);
  };
  const type = params.get('prediction_type');
  if (type !== null && !predictionTypes.some(value => value === type)) throw new TypeError('Le type de prédiction de l’URL est invalide.');
  const alert = params.get('is_alert');
  if (alert !== null && alert !== 'true' && alert !== 'false') throw new TypeError('Le filtre d’alerte de l’URL est invalide. Utilisez Tous, Oui ou Non.');
  const level = params.get('level') ?? undefined;
  if (level !== undefined && (Array.from(level).length < 1 || Array.from(level).length > 50)) throw new TypeError('Le niveau de l’URL doit comporter 1 à 50 caractères bruts.');
  const start_time = params.get('start_time') ?? undefined, end_time = params.get('end_time') ?? undefined;
  try { validatePredictionPeriod(start_time, end_time); }
  catch { throw new TypeError('La période de l’URL est invalide : offsets explicites requis, début inférieur ou égal à la fin.'); }
  return { company_id: integer('company_id'), site_id: integer('site_id'), equipment_id: integer('equipment_id'),
    page: integer('page', 1)!, page_size: integer('page_size', 20, 100)!,
    prediction_type: type === null ? undefined : type as PredictionType, level,
    is_alert: alert === null ? undefined : alert === 'true', start_time, end_time };
}
