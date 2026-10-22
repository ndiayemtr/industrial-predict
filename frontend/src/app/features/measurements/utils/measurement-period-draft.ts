import { measurementInstant, measurementUtcParts } from './measurement-time';

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
