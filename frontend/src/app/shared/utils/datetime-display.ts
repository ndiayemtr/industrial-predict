const unavailable = 'Non disponible';

// Parse ISO components before using Date: Date alone normalizes invalid dates
// and interprets timestamps without an offset in the browser's local timezone.
function format(value: string | null | undefined, seconds: boolean, requireOffset: boolean): string {
  const match = typeof value === 'string'
    ? /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?(Z|[+-]\d{2}:\d{2})?$/.exec(value)
    : null;
  if (!match) return unavailable;
  const [, year, month, day, hour, minute, second = '00', , offset] = match;
  if (requireOffset && !offset) return unavailable;
  const date = new Date(0);
  date.setUTCFullYear(Number(year), Number(month) - 1, Number(day));
  date.setUTCHours(Number(hour), Number(minute), Number(second), 0);
  if (date.getUTCFullYear() !== Number(year) || date.getUTCMonth() !== Number(month) - 1
    || date.getUTCDate() !== Number(day) || date.getUTCHours() !== Number(hour)
    || date.getUTCMinutes() !== Number(minute) || date.getUTCSeconds() !== Number(second)) return unavailable;
  if (offset && offset !== 'Z') {
    const hours = Number(offset.slice(1, 3)), minutes = Number(offset.slice(4, 6));
    if (hours > 23 || minutes > 59) return unavailable;
    const direction = offset[0] === '+' ? 1 : -1;
    date.setTime(date.getTime() - direction * (hours * 60 + minutes) * 60_000);
  }
  const pad = (part: number, length = 2) => String(part).padStart(length, '0');
  return `${pad(date.getUTCDate())}/${pad(date.getUTCMonth() + 1)}/${pad(date.getUTCFullYear(), 4)}`
    + ` à ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`
    + (seconds ? `:${pad(date.getUTCSeconds())}` : '') + (offset ? ' UTC' : '');
}

// Offset-free administrative timestamps retain the supplied wall-clock components.
export function formatAdministrativeDateTime(value: string | null | undefined): string {
  return format(value, false, false);
}

// Dashboard instants require an explicit offset; never invent UTC for an unknown timezone.
export function formatUtcDateTime(value: string | null | undefined): string {
  return format(value, true, true);
}
