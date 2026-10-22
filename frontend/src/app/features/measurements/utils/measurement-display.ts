import { MeasurementQuality } from '../models/measurement.model';

export function measurementQualityLabels(): Readonly<Record<MeasurementQuality, string>> {
  return { good: 'Bonne', suspect: 'Suspecte', bad: 'Mauvaise', missing: 'Manquante', estimated: 'Estimée' };
}

export function formatMeasurementValue(value: number): string {
  return (Object.is(value, -0) ? '-0' : String(value)).replace('.', ',');
}
