import { restoreMeasurementBound, serializeMeasurementBound, validateMeasurementPeriodDraft } from './measurement-period-draft';
import { validateMeasurementPeriod } from './measurement-time';

describe('UTC period controls with exact original URL baseline',()=>{
  const baseline=restoreMeasurementBound();
  it.each(['','1','12','123','1234','12345','123456'])('serializes %s fractional digits without padding or rounding',fraction=>{
    expect(serializeMeasurementBound({date:'2026-10-22',time:'12:34:56',fraction},baseline)).toBe(`2026-10-22T12:34:56${fraction?'.'+fraction:''}Z`);
  });
  it.each(['2026-10-22T17:30:00.123456+05:30','2026-01-01T00:15:00.000001+01:00','2025-12-31T23:15:00.120000-02:00','2026-10-22T12:00Z'])('retains exact unchanged %s including offset, precision and rollovers',raw=>{
    const restored=restoreMeasurementBound(raw);expect(serializeMeasurementBound({...restored.parts},restored)).toBe(raw);
    expect(serializeMeasurementBound({...restored.parts,time:'23:59:59'},restored)).toMatch(/Z$/);
    expect(serializeMeasurementBound({...restored.parts},restored)).toBe(raw);
  });
  it('displays offset-bearing bounds as UTC components and normalizes only an edited bound',()=>{
    const original=restoreMeasurementBound('2026-01-01T00:15:00.000001+01:00');
    expect(original.parts).toEqual({date:'2025-12-31',time:'23:15:00',fraction:'000001'});
    expect(serializeMeasurementBound({...original.parts,fraction:'000002'},original)).toBe('2025-12-31T23:15:00.000002Z');
  });
  it('does not lose the original offset if the time picker omits zero seconds',()=>{
    const original=restoreMeasurementBound('2026-10-22T13:00:00+01:00');expect(serializeMeasurementBound({...original.parts,time:'12:00'},original)).toBe(original.raw);
  });
  it('allows either or both bounds absent and rejects a reversed interval by one microsecond',()=>{
    const empty={date:'',time:'',fraction:''};expect(serializeMeasurementBound(empty,baseline)).toBeUndefined();
    expect(()=>validateMeasurementPeriod(undefined,'2026-01-01T00:00:00Z')).not.toThrow();expect(()=>validateMeasurementPeriod('2026-01-01T00:00:00Z')).not.toThrow();
    expect(()=>validateMeasurementPeriod('2026-01-01T00:00:00.000002Z','2026-01-01T00:00:00.000001Z')).toThrow();
  });
  it('retains an invalid URL for validation rather than silently removing its bound',()=>{
    const invalid=restoreMeasurementBound('invalid');expect(serializeMeasurementBound(invalid.parts,invalid)).toBe('invalid');expect(()=>validateMeasurementPeriod('invalid')).toThrow();
  });
  it.each(['1234567','-1','1.2',' 1','1 ','a','١'])('rejects invalid fraction %s rather than truncating it',fraction=>{
    expect(()=>serializeMeasurementBound({date:'2026-01-01',time:'12:00:00',fraction},baseline)).toThrow();
  });
  it('shares field errors without completing an absent hour or widening invalid native input', () => {
    const result = validateMeasurementPeriodDraft({ date: '2026-10-24', time: '', fraction: '' }, baseline, baseline.parts, baseline);
    expect(result.period).toBeNull(); expect(Object.keys(result.fieldErrors)).toEqual(['start-time']);
    expect(result.fieldErrors['start-time']).toContain('heure UTC');
    const native = validateMeasurementPeriodDraft(baseline.parts, baseline, baseline.parts, baseline, ['end-date']);
    expect(native.period).toBeNull(); expect(native.fieldErrors['end-date']).toBeTruthy();
  });
  it('keeps the source offset while comparing and applying microsecond bounds', () => {
    const start = restoreMeasurementBound('2026-10-24T14:00:00.000001+02:00');
    const end = { date: '2026-10-24', time: '12:00:00', fraction: '000002' };
    expect(validateMeasurementPeriodDraft(start.parts, start, end, baseline).period).toEqual({ start_time: start.raw, end_time: '2026-10-24T12:00:00.000002Z' });
    expect(validateMeasurementPeriodDraft(start.parts, start, { ...end, fraction: '000001' }, baseline).period).toBeNull();
    const naive = restoreMeasurementBound('2026-10-24T12:00:00.000001');
    expect(validateMeasurementPeriodDraft(naive.parts, naive, baseline.parts, baseline).period).toBeNull();
  });

});
