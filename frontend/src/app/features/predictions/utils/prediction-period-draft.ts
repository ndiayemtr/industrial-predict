import { MeasurementBoundBaseline, MeasurementBoundParts, serializeMeasurementBound } from '../../measurements/utils/measurement-period-draft';
import { validatePredictionPeriod } from './prediction-time';

// Bound serialization is shared; the exclusive Measurements period validator is not.
export function predictionPeriodDraft(start: MeasurementBoundParts, startBaseline: MeasurementBoundBaseline,
  end: MeasurementBoundParts, endBaseline: MeasurementBoundBaseline, invalidFields: readonly string[] = []) {
  const errors: Record<string, string> = {};
  const read = (name: 'start' | 'end', parts: MeasurementBoundParts, baseline: MeasurementBoundBaseline) => {
    for (const field of ['date', 'time', 'fraction'] as const) {
      if (invalidFields.includes(name + '-' + field)) errors[name + '-' + field] = 'Valeur incomplète ou invalide.';
    }
    if (parts.date && !parts.time) errors[name + '-time'] = 'Renseignez l’heure UTC avec la date, sans heure par défaut.';
    if ((parts.time || parts.fraction) && !parts.date) errors[name + '-date'] = 'Renseignez la date de cette borne.';
    if (parts.fraction && !parts.time) errors[name + '-time'] = 'Renseignez l’heure UTC de cette fraction.';
    if (!/^\d{0,6}$/.test(parts.fraction)) errors[name + '-fraction'] = 'Utilisez de 0 à 6 chiffres.';
    if (parts.time && !/^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(parts.time)) errors[name + '-time'] = 'Heure UTC invalide.';
    if (Object.keys(errors).some(key => key.startsWith(name + '-'))) return undefined;
    try {
      const value = serializeMeasurementBound(parts, baseline);
      validatePredictionPeriod(value);
      return value;
    } catch { errors[name + '-date'] = 'Date réelle et offset explicite requis, sans fuseau supposé.'; return undefined; }
  };
  const start_time = read('start', start, startBaseline), end_time = read('end', end, endBaseline);
  if (Object.keys(errors).length === 0) {
    try { validatePredictionPeriod(start_time, end_time); }
    catch { errors['end-date'] = 'La fin incluse doit être postérieure ou égale au début inclus.'; }
  }
  return { period: Object.keys(errors).length ? null : { start_time, end_time }, errors };
}
