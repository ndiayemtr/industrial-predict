import { measurementInstant, measurementUtcParts, validateMeasurementPeriod } from './measurement-time';

export interface MeasurementBoundParts { date: string; time: string; fraction: string }
export interface MeasurementBoundBaseline { raw: string | undefined; parts: MeasurementBoundParts }
const empty = (): MeasurementBoundParts => ({ date: '', time: '', fraction: '' });

// Keep the URL string independently from the UTC controls, including its original offset.
export function restoreMeasurementBound(raw?: string): MeasurementBoundBaseline {
  try { return { raw, parts: raw === undefined ? empty() : measurementUtcParts(raw) }; }
  catch { return { raw, parts: empty() }; } // An invalid URL remains invalid until explicitly repaired or cleared.
}

export function serializeMeasurementBound(parts: MeasurementBoundParts, baseline: MeasurementBoundBaseline): string | undefined {
  const time = /^\d{2}:\d{2}$/.test(parts.time) ? parts.time + ':00' : parts.time;
  if (parts.date === baseline.parts.date && time === baseline.parts.time && parts.fraction === baseline.parts.fraction) return baseline.raw;
  if (!parts.date && !time && !parts.fraction) return undefined;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(parts.date) || !/^\d{2}:\d{2}:\d{2}$/.test(time)
    || !/^\d{0,6}$/.test(parts.fraction)) throw new TypeError('Incomplete or invalid UTC bound.');
  const value = `${parts.date}T${time}${parts.fraction ? '.' + parts.fraction : ''}Z`;
  measurementInstant(value);
  return value;
}


export interface MeasurementPeriodDraftValidation {
  period: { start_time: string | undefined; end_time: string | undefined } | null;
  fieldErrors: Readonly<Record<string, string>>;
  message: string;
}

// Both lists use the same validation. Native badInput may hide a partially typed value.
export function validateMeasurementPeriodDraft(
  start: MeasurementBoundParts, startBaseline: MeasurementBoundBaseline,
  end: MeasurementBoundParts, endBaseline: MeasurementBoundBaseline,
  invalidFields: readonly string[] = [],
): MeasurementPeriodDraftValidation {
  const errors: Record<string, string> = {};
  const read = (key: 'start' | 'end', parts: MeasurementBoundParts, baseline: MeasurementBoundBaseline): string | undefined => {
    for (const field of ['date', 'time', 'fraction'] as const) {
      if (invalidFields.includes(key + '-' + field)) errors[key + '-' + field] = 'Valeur incomplète ou invalide.';
    }
    if (parts.date && !parts.time) errors[key + '-time'] = 'Renseignez l’heure UTC avec la date, sans heure par défaut.';
    if ((parts.time || parts.fraction) && !parts.date) errors[key + '-date'] = 'Renseignez la date de cette borne.';
    if (parts.fraction && !parts.time) errors[key + '-time'] = 'Renseignez l’heure UTC de cette fraction.';
    if (!/^\d{0,6}$/.test(parts.fraction)) errors[key + '-fraction'] = 'Utilisez de 0 à 6 chiffres pour la fraction.';
    if (parts.time && !/^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(parts.time)) errors[key + '-time'] = 'Heure UTC invalide : heures, minutes et secondes valides requises.';
    if (Object.keys(errors).some(field => field.startsWith(key + '-'))) return undefined;
    try {
      const value = serializeMeasurementBound(parts, baseline);
      validateMeasurementPeriod(value, undefined);
      return value;
    } catch { errors[key + '-date'] = 'Borne invalide : date réelle et horodatage avec offset requis, sans fuseau supposé.'; return undefined; }
  };
  const start_time = read('start', start, startBaseline), end_time = read('end', end, endBaseline);
  let message = Object.keys(errors).length ? 'Période invalide : corrigez les champs indiqués.' : '';
  if (!message) {
    try { validateMeasurementPeriod(start_time, end_time); }
    catch {
      message = 'Période invalide : le début doit être strictement antérieur à la fin (début inclus, fin exclue).';
      errors['end-date'] = 'La fin doit être strictement postérieure au début.';
    }
  }
  return { period: message ? null : { start_time, end_time }, fieldErrors: errors, message };
}
