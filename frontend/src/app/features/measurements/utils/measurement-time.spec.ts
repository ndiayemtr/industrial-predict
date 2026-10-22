import { formatMeasurementUtc, measurementInstant, validateMeasurementPeriod } from './measurement-time';

describe('Measurement UTC precision without Date', () => {
  it.each([
    ['2026-10-22T17:30:00.123456+05:30', '22/10/2026 à 12:00:00.123456 UTC'],
    ['2026-01-01T00:30:00.000001+01:00', '31/12/2025 à 23:30:00.000001 UTC'],
    ['2025-12-31T23:30:59.999999-01:00', '01/01/2026 à 00:30:59.999999 UTC'],
    ['2000-03-01T00:00:00+01:00', '29/02/2000 à 23:00:00 UTC'],
    ['1900-03-01T00:00:00+01:00', '28/02/1900 à 23:00:00 UTC'],
    ['2026-10-22T12:34Z', '22/10/2026 à 12:34:00 UTC'],
    ['2026-10-22T12:34:56.000000Z', '22/10/2026 à 12:34:56.000000 UTC']
  ])('formats %s as UTC without dropping fractional digits', (raw, expected) => expect(formatMeasurementUtc(raw)).toBe(expected));
  it('compares equivalent offsets exactly and a one-microsecond difference', () => {
    const start = '2026-10-22T17:30:00.123456+05:30', same = '2026-10-22T12:00:00.123456Z';
    expect(measurementInstant(start)).toBe(measurementInstant(same));
    expect(() => validateMeasurementPeriod(start,same)).toThrow(TypeError);
    expect(() => validateMeasurementPeriod(start,'2026-10-22T12:00:00.123457Z')).not.toThrow();
  });
  it.each(['2026-01-01T00:00:00','2026-02-30T00:00Z','2026-01-01T00:00:00.1234567Z'])('never invents a timezone or normalizes %s', raw => {
    expect(() => validateMeasurementPeriod(raw)).toThrow(TypeError); expect(formatMeasurementUtc(raw)).toBe('Horodatage invalide');
  });
});
