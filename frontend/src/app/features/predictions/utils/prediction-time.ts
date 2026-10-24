// Reuse only the pure instant parser, never Measurements' exclusive-end period.
import { measurementInstant } from '../../measurements/utils/measurement-time';

// Validation only: preserve the caller's ISO strings, offsets and fractions.
// Predictions uses [start, end], so equivalent instants are valid bounds.
export function validatePredictionPeriod(start?: string, end?: string): void {
  const lower = start === undefined ? undefined : measurementInstant(start);
  const upper = end === undefined ? undefined : measurementInstant(end);
  if (lower !== undefined && upper !== undefined && lower > upper) {
    throw new TypeError('Prediction start must not follow end (both bounds inclusive).');
  }
}
