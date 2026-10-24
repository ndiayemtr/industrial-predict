import { convertToParamMap } from '@angular/router';
import { readPredictionQuery } from './prediction-query';

describe('Prediction URL contract', () => {
  it('defaults only absent pagination and keeps false, arbitrary size and source time strings', () => {
    expect(readPredictionQuery(convertToParamMap({}))).toMatchObject({ page: 1, page_size: 20 });
    const start_time = '2026-10-23T17:30:00.123456+05:30';
    expect(readPredictionQuery(convertToParamMap({ is_alert: 'false', page_size: '37', level: '  日本  ', start_time })))
      .toMatchObject({ is_alert: false, page_size: 37, level: '  日本  ', start_time });
  });
  it.each(['company_id', 'site_id', 'equipment_id', 'page', 'page_size', 'prediction_type', 'level', 'is_alert', 'start_time', 'end_time'])('rejects duplicate %s', key => {
    expect(() => readPredictionQuery(convertToParamMap({ [key]: ['1', '2'] }))).toThrow(TypeError);
  });
  it.each([{ company_id: '0' }, { page: '-1' }, { page_size: '101' }, { page_size: '' }, { level: '' }, { level: '😀'.repeat(51) },
    { prediction_type: 'unknown' }, { is_alert: 'null' }, { is_alert: '0' }, { start_time: '2026-01-01T00:00:00' },
    { start_time: '2026-01-01T00:00:00.000002Z', end_time: '2026-01-01T00:00:00.000001Z' }])('blocks malformed query without widening it %j', params => {
    expect(() => readPredictionQuery(convertToParamMap(params))).toThrow(TypeError);
  });
  it('keeps inclusive equality and ignores keys outside the contract', () => {
    const raw = '2026-01-01T00:00:00.000001Z';
    expect(readPredictionQuery(convertToParamMap({ start_time: raw, end_time: raw, search: 'ignored' }))).toMatchObject({ start_time: raw, end_time: raw });
  });
});
