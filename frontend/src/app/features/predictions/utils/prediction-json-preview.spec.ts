import { predictionJsonPreview } from './prediction-json-preview';

describe('Prediction JSON presentation limits', () => {
  it.each([null, {}, [], { values: [0, false, null, 'é😀', { reason: '<script>"&</script>\n' }] }])('preserves JSON primitives and structures: %j', value => {
    const result = predictionJsonPreview(value);
    expect(result.truncated).toBe(false); expect(JSON.parse(result.text)).toEqual(value);
  });
  it('retains unknown keys as text including HTML and special property names', () => {
    const value = JSON.parse('{"__proto__":null,"<img onerror=bad>":[true,false]}');
    expect(JSON.parse(predictionJsonPreview(value).text)).toEqual(value);
  });
  it('allows exactly 10000 characters and warns only if longer', () => {
    expect(predictionJsonPreview('x'.repeat(9998))).toEqual({ text: '"' + 'x'.repeat(9998) + '"', truncated: false });
    const result = predictionJsonPreview('x'.repeat(9999)); expect(result.text.length).toBe(10000); expect(result.truncated).toBe(true);
  });
  it('bounds huge values, keys, arrays and objects without changing received data', () => {
    const value = { large: 'x'.repeat(100000), trailing: 7 }; const original = structuredClone(value);
    for (const item of [value, { ['k'.repeat(100000)]: 0 }, Array(20000).fill(false), Object.fromEntries(Array.from({ length: 10000 }, (_, i) => [i, i]))]) {
      expect(predictionJsonPreview(item).text.length).toBeLessThanOrEqual(10000); expect(predictionJsonPreview(item).truncated).toBe(true);
    }
    expect(value).toEqual(original);
  });
  it('permits six container levels with scalar leaves and truncates a seventh', () => {
    const six = { a: [{ b: [{ c: [0] }] }] }; expect(predictionJsonPreview(six).truncated).toBe(false);
    const seven = { a: [{ b: [{ c: [{ d: 0 }] }] }] };
    expect(predictionJsonPreview(seven).truncated).toBe(true); expect(predictionJsonPreview(seven).text).toContain('six niveaux');
  });
  it('handles very deep and circular unknown data without stack overflow or mutation', () => {
    const circular: Record<string, unknown> = {}; circular['self'] = circular;
    expect(predictionJsonPreview(circular)).toMatchObject({ truncated: true });
    let deep: unknown = 0; for (let i = 0; i < 20000; i++) deep = [deep];
    expect(predictionJsonPreview(deep).truncated).toBe(true);
    const child = { x: 1 }; expect(predictionJsonPreview([child, child]).truncated).toBe(false);
  });
  it.each([undefined, NaN, Infinity, () => 1])('handles unexpected non JSON value defensively', value => {
    expect(predictionJsonPreview(value).text).toBe('"[Valeur non JSON]"');
  });
});
