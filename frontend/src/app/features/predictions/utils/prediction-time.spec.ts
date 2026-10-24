import { validatePredictionPeriod } from './prediction-time';

describe('Prediction inclusive period', () => {
  it('allows missing or single bounds without adding a date', () => {
    expect(() => validatePredictionPeriod()).not.toThrow();
    expect(() => validatePredictionPeriod('2099-01-01T00:00:00.123456-03:30')).not.toThrow();
    expect(() => validatePredictionPeriod(undefined, '0001-01-01T00:00:00+00:00')).not.toThrow();
  });

  it.each([
    ['2026-10-23T12:00:00Z', '2026-10-23T12:00:00Z'],
    ['2026-10-23T17:30:00.123456+05:30', '2026-10-23T12:00:00.123456Z'],
    ['2026-01-01T00:00:00+01:00', '2025-12-31T23:00:00Z'],
    ['2000-02-29T23:59:59.999999Z', '2000-03-01T00:00:00Z'],
    ['2026-10-23T12:00:00.123456Z', '2026-10-23T12:00:00.123457Z']
  ])('accepts inclusive equal or ordered instants %s / %s', (start, end) => {
    expect(() => validatePredictionPeriod(start, end)).not.toThrow();
  });

  it.each([
    ['2026-10-23T12:00:00.123457Z', '2026-10-23T17:30:00.123456+05:30'],
    ['2026-01-01T00:00:00-01:00', '2026-01-01T00:59:59.999999Z']
  ])('rejects reversed instants without millisecond rounding %s / %s', (start, end) => {
    expect(() => validatePredictionPeriod(start, end)).toThrow(TypeError);
  });

  it.each([
    '', '2026-10-23', '2026-10-23T12:00:00', '2026-10-23T12:00:00Z\n',
    '2026-10-23T12:00:00Z ', '0000-01-01T00:00:00Z', '2026-13-01T00:00:00Z',
    '2026-04-31T00:00:00Z', '1900-02-29T00:00:00Z', '2026-01-01T24:00:00Z',
    '2026-01-01T00:60:00Z', '2026-01-01T00:00:60Z', '2026-01-01T00:00:00+24:00',
    '2026-01-01T00:00:00-01:60', '2026-01-01T00:00:00.1234567Z'
  ])('rejects invalid or offset-free bound %s', value => {
    expect(() => validatePredictionPeriod(value)).toThrow(TypeError);
    expect(() => validatePredictionPeriod(undefined, value)).toThrow(TypeError);
  });
});
