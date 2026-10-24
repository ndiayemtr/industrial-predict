export interface PredictionJsonPreview { text: string; truncated: boolean }

// Bounds apply only to rendered text, never to HTTP data or backend acceptance.
// Build incrementally: never stringify the entire (possibly huge/deep) object first.
export function predictionJsonPreview(value: unknown): PredictionJsonPreview {
  const limit = 10_000;
  let text = '';
  let truncated = false;
  const active = new WeakSet<object>();
  const append = (part: string): void => {
    const remaining = limit - text.length;
    if (part.length > remaining) truncated = true;
    text += part.slice(0, remaining);
  };
  const quote = (value: string): void => {
    append('"');
    // Escape incrementally so a huge string/key cannot allocate a full JSON copy.
    for (const char of value) {
      if (text.length >= limit) { truncated = true; return; }
      append(JSON.stringify(char).slice(1, -1));
    }
    append('"');
  };
  const visit = (current: unknown, depth: number): void => {
    if (text.length >= limit) { truncated = true; return; }
    if (current === null) { append('null'); return; }
    if (typeof current === 'string') { quote(current); return; }
    if (typeof current === 'boolean' || (typeof current === 'number' && Number.isFinite(current))) { append(String(current)); return; }
    if (typeof current !== 'object') { quote('[Valeur non JSON]'); return; }
    if (depth >= 6) { truncated = true; quote('[Profondeur limitée à six niveaux]'); return; }
    if (active.has(current)) { truncated = true; quote('[Référence circulaire]'); return; }
    active.add(current);
    const array = Array.isArray(current);
    append(array ? '[' : '{');
    let first = true;
    // Lazy enumeration; do not allocate Object.entries for an unbounded object.
    const entry = (key: string, child: unknown): void => {
      if (!first) append(', ');
      first = false;
      if (!array) { quote(key); append(': '); }
      visit(child, depth + 1);
    };
    if (array) {
      for (let index = 0; index < current.length; index++) {
        if (text.length >= limit) { truncated = true; break; }
        entry(String(index), current[index]);
      }
    } else {
      for (const key in current) {
        if (!Object.hasOwn(current, key)) continue;
        if (text.length >= limit) { truncated = true; break; }
        entry(key, (current as Record<string, unknown>)[key]);
      }
    }
    append(array ? ']' : '}');
    active.delete(current);
  };
  visit(value, 0);
  return { text, truncated };
}
