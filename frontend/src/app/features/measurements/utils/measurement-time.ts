// Compare instants at microsecond precision without Date's millisecond rounding.
// The result is validation-only: the original ISO string remains the HTTP value.
export function measurementInstant(value: unknown): bigint {
  const match = typeof value === 'string'
    ? /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,6}))?)?(Z|[+-]\d{2}:\d{2})$/.exec(value) : null;
  if (!match || match[0] !== value) throw new TypeError('Measurement time must be ISO with an offset and at most six fractional digits.');
  const [, y, m, d, h, min, sec = '0', fraction = '', zone] = match;
  const year = Number(y), month = Number(m), day = Number(d), hour = Number(h), minute = Number(min), second = Number(sec);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const monthDays = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const offsetHours = zone === 'Z' ? 0 : Number(zone.slice(1, 3));
  const offsetMinutes = zone === 'Z' ? 0 : Number(zone.slice(4, 6));
  if (year < 1 || month < 1 || month > 12 || day < 1 || day > monthDays[month - 1]
    || hour > 23 || minute > 59 || second > 59 || offsetHours > 23 || offsetMinutes > 59) {
    throw new TypeError('Measurement time contains invalid calendar or offset components.');
  }
  const previousYear = year - 1;
  const days = 365 * previousYear + Math.floor(previousYear / 4) - Math.floor(previousYear / 100)
    + Math.floor(previousYear / 400) + monthDays.slice(0, month - 1).reduce((sum, count) => sum + count, 0) + day - 1;
  const offset = (zone.startsWith('-') ? -1 : 1) * (offsetHours * 60 + offsetMinutes);
  return BigInt(((days * 24 + hour) * 60 + minute) * 60 + second - offset * 60) * 1_000_000n
    + BigInt(fraction.padEnd(6, '0'));
}

export function validateMeasurementPeriod(start?: string, end?: string): void {
  const lower = start === undefined ? undefined : measurementInstant(start);
  const upper = end === undefined ? undefined : measurementInstant(end);
  if (lower !== undefined && upper !== undefined && lower >= upper) throw new TypeError('Invalid Measurement period.');
}

// Offset conversion changes calendar components only; fractional digits stay intact.
export function measurementUtcParts(value: string): { date: string; time: string; fraction: string } {
  measurementInstant(value);
  const parts = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})$/.exec(value)!;
  let year = Number(parts[1]), month = Number(parts[2]), day = Number(parts[3]);
  const zone = parts[8], offset = zone === 'Z' ? 0 : (zone[0] === '-' ? -1 : 1) * (Number(zone.slice(1,3)) * 60 + Number(zone.slice(4,6)));
  let minutes = Number(parts[4]) * 60 + Number(parts[5]) - offset;
  const daysInMonth = (y: number, m: number) => [31, y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0) ? 29 : 28,31,30,31,30,31,31,30,31,30,31][m-1];
  if (minutes < 0) { minutes += 1440; day--; if (!day) { month--; if (!month) { month=12; year--; } day=daysInMonth(year,month); } }
  if (minutes >= 1440) { minutes -= 1440; day++; if (day > daysInMonth(year,month)) { day=1; month++; if (month===13) { month=1; year++; } } }
  const pad = (n: number, length=2) => String(n).padStart(length,'0');
  return { date: `${pad(year,4)}-${pad(month)}-${pad(day)}`,
    time: `${pad(Math.floor(minutes/60))}:${pad(minutes%60)}:${parts[6] ?? '00'}`, fraction: (parts[7] ?? '').slice(1) };
}

export function formatMeasurementUtc(value: string): string {
  try {
    const { date, time, fraction } = measurementUtcParts(value);
    const [year, month, day] = date.split('-');
    return `${day}/${month}/${year} à ${time}${fraction ? '.' + fraction : ''} UTC`;
  } catch { return 'Horodatage invalide'; }
}
