import { formatAdministrativeDateTime, formatUtcDateTime } from './datetime-display';

describe('Date/time display without transport changes', () => {
  it.each([
    ['2026-10-16T11:51:15.910577Z', '16/10/2026 à 11:51:15 UTC'],
    ['2026-01-01T00:15:09.999999+02:30', '31/12/2025 à 21:45:09 UTC'],
    ['2026-12-31T23:45:59.999999-01:00', '01/01/2027 à 00:45:59 UTC'],
    ['2024-02-29T12:30:00+00:00', '29/02/2024 à 12:30:00 UTC']
  ])('formats explicit UTC/offset %s without rounding fractions', (value, expected) => {
    expect(formatUtcDateTime(value)).toBe(expected);
    expect(formatAdministrativeDateTime(value)).toBe(expected.replace(/:\d{2} UTC$/, ' UTC'));
  });

  it.each([
    ['2026-08-31T14:58:20.179290', '31/08/2026 à 14:58'],
    ['2026-03-29T02:30:59.999999', '29/03/2026 à 02:30'],
    ['2026-10-25T02:30:00', '25/10/2026 à 02:30'],
    ['2026-01-01T00:00', '01/01/2026 à 00:00']
  ])('preserves timezone-free components of %s, including DST transition times', (value, expected) => {
    expect(formatAdministrativeDateTime(value)).toBe(expected);
    expect(formatUtcDateTime(value)).toBe('Non disponible');
  });

  it.each([null, undefined, '', 'invalid', '2026-02-29T12:00:00', '2026-04-31T12:00:00Z',
    '2026-00-01T00:00:00', '2026-13-01T00:00:00', '2026-01-00T00:00:00',
    '2026-01-01T24:00:00Z', '2026-01-01T12:60:00Z', '2026-01-01T12:00:60Z',
    '2026-01-01T12:00:00+24:00', '2026-01-01T12:00:00+01:60', '2026-01-01',
    '2026-01-01T12:00:00.', '2026-01-01T12:00:00Zextra'])('rejects missing/invalid value %s', value => {
    expect(formatAdministrativeDateTime(value)).toBe('Non disponible');
    expect(formatUtcDateTime(value)).toBe('Non disponible');
  });
});
