import { convertToParamMap } from '@angular/router';
import { PredictionsQuery } from '../models/predictions-state.model';
import { predictionNavigationParams, readPredictionNavigationContext } from './prediction-navigation';

const query: PredictionsQuery = { company_id: 7, site_id: 9, equipment_id: 12, page: 2, page_size: 1,
  prediction_type: 'rul', level: '  libre 日本  ', is_alert: false,
  start_time: '2026-10-23T17:30:00.123456+05:30', end_time: '2026-10-23T12:00:00.123456Z' };
const context = predictionNavigationParams(query);

describe('Typed Predictions return context', () => {
  it('round trips the complete whitelist, inclusive equal instants, precision and explicit false', () => {
    expect(readPredictionNavigationContext(convertToParamMap(context), 12)).toEqual({ from: 'predictions', query });
    expect(Object.keys(context).sort()).toEqual(['from', ...Object.keys(query).map(key => 'pre_' + key)].sort());
  });
  it('omits absent filters and never forwards Equipment filters, URLs or unknown prefixed parameters', () => {
    const params = predictionNavigationParams({ company_id: 7, site_id: 9, equipment_id: 12, page: 1, page_size: 20 });
    expect(params).toEqual({ from: 'predictions', pre_company_id: '7', pre_site_id: '9', pre_equipment_id: '12', pre_page: '1', pre_page_size: '20' });
    expect(readPredictionNavigationContext(convertToParamMap({ ...params, search: 'x', status: 'maintenance', returnUrl: 'https://example.com', pre_returnUrl: '//example.com', pre_search: 'x' }), 12)?.query).toEqual({
      company_id: 7, site_id: 9, equipment_id: 12, page: 1, page_size: 20,
      prediction_type: undefined, level: undefined, is_alert: undefined, start_time: undefined, end_time: undefined
    });
  });
  it.each([
    { from: undefined }, { from: 'equipment' }, { from: ['predictions', 'predictions'] },
    { pre_company_id: undefined }, { pre_site_id: undefined }, { pre_equipment_id: undefined },
    { pre_equipment_id: 13 }, { pre_company_id: '0' }, { pre_site_id: '1.5' }, { pre_page: 0 }, { pre_page_size: 101 },
    { pre_prediction_type: 'unknown' }, { pre_level: '' }, { pre_is_alert: '0' },
    { pre_start_time: '2026-10-23T12:00:00' }, { pre_start_time: '2026-10-23T12:00:00.123457Z' },
    { pre_end_time: '' }
  ])('rejects malformed, partial or contradictory context %j', patch => {
    const params: Record<string, unknown> = { ...context, ...patch };
    for (const key of Object.keys(params)) if (params[key] === undefined) delete params[key];
    expect(readPredictionNavigationContext(convertToParamMap(params), 12)).toBeNull();
  });
  it.each(['company_id', 'site_id', 'equipment_id', 'page', 'page_size', 'prediction_type', 'level', 'is_alert', 'start_time', 'end_time'])('rejects duplicate pre_%s', key => {
    expect(readPredictionNavigationContext(convertToParamMap({ ...context, ['pre_' + key]: ['1', '1'] }), 12)).toBeNull();
  });
  it('rejects context on an invalid detail id and refuses to emit incomplete context', () => {
    expect(readPredictionNavigationContext(convertToParamMap(context), undefined)).toBeNull();
    expect(() => predictionNavigationParams({ page: 1, page_size: 20 })).toThrow();
  });
});
