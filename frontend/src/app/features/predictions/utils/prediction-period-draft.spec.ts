import { restoreMeasurementBound } from '../../measurements/utils/measurement-period-draft';
import { predictionPeriodDraft } from './prediction-period-draft';

describe('Prediction period drafts', () => {
  const blank = restoreMeasurementBound();
  it('preserves original offsets, trailing fractions and equal instants when unchanged', () => {
    const start = restoreMeasurementBound('2026-10-23T17:30:00.123400+05:30'), end = restoreMeasurementBound('2026-10-23T12:00:00.123400Z');
    expect(predictionPeriodDraft(start.parts, start, end.parts, end).period).toEqual({ start_time: start.raw, end_time: end.raw });
  });
  it('serializes an intentional UTC edit without inventing a second bound', () => {
    expect(predictionPeriodDraft({ date: '2026-10-23', time: '12:34:56', fraction: '000001' }, blank, blank.parts, blank).period)
      .toEqual({ start_time: '2026-10-23T12:34:56.000001Z', end_time: undefined });
  });
  it.each([
    [{ date: '2026-10-23', time: '', fraction: '' }, 'start-time'],
    [{ date: '', time: '12:00:00', fraction: '' }, 'start-date'],
    [{ date: '2026-10-23', time: '24:00:00', fraction: '' }, 'start-time'],
    [{ date: '2026-10-23', time: '12:00:00', fraction: '1234567' }, 'start-fraction'],
    [{ date: '2026-02-30', time: '12:00:00', fraction: '' }, 'start-date']
  ] as const)('rejects invalid draft %j with an associated field', (parts, field) => {
    const result = predictionPeriodDraft(parts, blank, blank.parts, blank); expect(result.period).toBeNull(); expect(result.errors[field]).toBeTruthy();
  });
  it('keeps an invalid URL invalid until explicitly corrected or cleared', () => {
    const invalid = restoreMeasurementBound('broken');
    expect(predictionPeriodDraft(invalid.parts, invalid, blank.parts, blank).period).toBeNull();
    expect(predictionPeriodDraft(blank.parts, blank, blank.parts, blank).period).toEqual({ start_time: undefined, end_time: undefined });
  });
  it('honors native badInput and rejects inverted microseconds', () => {
    expect(predictionPeriodDraft(blank.parts, blank, blank.parts, blank, ['start-time']).errors['start-time']).toBeTruthy();
    const start = restoreMeasurementBound('2026-10-23T12:00:00.000002Z'), end = restoreMeasurementBound('2026-10-23T12:00:00.000001Z');
    expect(predictionPeriodDraft(start.parts, start, end.parts, end).errors['end-date']).toContain('égale');
  });
});
