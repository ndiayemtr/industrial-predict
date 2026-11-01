import { formatReadingAge } from './reading-age';

describe('formatReadingAge', () => {
  it.each([
    [0, '0 seconde'], [1, '1 seconde'], [45, '45 secondes'], [720, '12 minutes'],
    [12000, '3 heures et 20 minutes'], [1393200, '16 jours et 3 heures'],
    [0.5, '0,5 seconde'], [123.456, '≈ 2 minutes et 3 secondes'], [86401, '1 jour et 1 seconde']
  ])('presents API age %s as %s without a current-clock calculation', (seconds, expected) => {
    expect(formatReadingAge(seconds)).toBe(expected);
  });
  it.each([null, undefined])('preserves absent ages (%s)', value => {
    expect(formatReadingAge(value)).toBe('Non renseigné');
  });
  it.each([-1, NaN, Infinity, '45', {}, Number.MAX_SAFE_INTEGER + 1])('does not invent an age for %s', value => {
    expect(formatReadingAge(value)).toBe('Âge indisponible');
  });
});
