const secondsFormat = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 20 });

/** Presentation of API seconds only; no wall-clock recalculation or freshness threshold. */
export function formatReadingAge(value: unknown): string {
  if (value == null) return 'Non renseigné';
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > Number.MAX_SAFE_INTEGER) return 'Âge indisponible';
  if (value < 60) return `${secondsFormat.format(value)} ${value <= 1 ? 'seconde' : 'secondes'}`;
  const units = [{ size: 86400, name: 'jour' }, { size: 3600, name: 'heure' }, { size: 60, name: 'minute' }, { size: 1, name: 'seconde' }];
  let remainder = value;
  const parts: string[] = [];
  for (const unit of units) {
    const amount = Math.floor(remainder / unit.size);
    remainder %= unit.size;
    if (amount) parts.push(`${amount} ${unit.name}${amount > 1 ? 's' : ''}`);
    if (parts.length === 2) break;
  }
  // Lower units may be omitted for compactness; exact API seconds remain in details.
  return (remainder > 0 ? '≈ ' : '') + parts.join(' et ');
}
