import { businessReferenceLabel } from './business-reference-label';

describe('Business reference label', () => {
  it.each([
    ['PETROSEN', 'PETROSEN', 'PETROSEN'],
    ['PETROSEN', 'PTR-001', 'PETROSEN - PTR-001'],
    [' PETROSEN ', ' PETROSEN ', 'PETROSEN'],
    ['', 'PTR-001', 'PTR-001'],
    ['Entreprise', '', 'Entreprise'],
    ['', '', 'Référence indisponible']
  ])('formats name %s and code %s without identifiers or duplication', (name, code, expected) => {
    expect(businessReferenceLabel({ name, code })).toBe(expected);
  });
});
