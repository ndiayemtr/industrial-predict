import { PredictionRead, PredictionType } from '../models/prediction.model';
import { knownHealthProducer, predictionDetails, predictionPresentation, readHealthComponents } from './prediction-display';

const base: PredictionRead = { id: 1, equipment_id: 12, sensor_id: null, measurement_id: null,
  prediction_type: 'anomaly', score: 0, level: null, is_alert: null, model_name: null,
  model_version: null, horizon_hours: null, details: null, predicted_at: '2026-10-24T00:00:00Z', created_at: '2026-10-24T00:00:01Z' };
const components = { failure_health: 0, anomaly_health: 100, data_quality_health: 50, maintenance_health: 75.5 };
const health: PredictionRead = { ...base, prediction_type: 'health_score', model_name: 'health_score', details: { components } };

describe('Prediction business presentation', () => {
  it.each([
    ['anomaly', 'Indice d’anomalie', '0'], ['failure_risk', 'Score de risque déclaré', '0'],
    ['health_score', 'Indice de santé', '0'], ['rul', 'Durée de vie utile restante', '0 h']
  ] as const)('presents %s without guessing a probability or failure date', (prediction_type, label, value) => {
    expect(predictionPresentation({ ...base, prediction_type })).toMatchObject({ label, value, level: 'Non renseigné' });
  });
  it.each([0, 1, 75, -1, 125, 0.123456789])('preserves risk score %s without percent or level inference', score => {
    expect(predictionPresentation({ ...base, prediction_type: 'failure_risk', score })).toMatchObject({ value: String(score), level: 'Non renseigné' });
  });
  it.each([0, 100, 99.123456])('uses the audited declared producer profile for health %s / 100', score => {
    expect(knownHealthProducer(health)).toBe(true);
    expect(predictionPresentation({ ...health, score })).toMatchObject({ value: `${score} / 100`, warnings: [] });
  });
  it.each([-1, 100.001])('flags incompatible health %s without clamping', score => {
    const view = predictionPresentation({ ...health, score });
    expect(view.value).toBe(String(score)); expect(view.warnings.join()).toContain('hors de l’échelle');
  });
  it.each([{ model_name: null }, { model_name: 'external' }, { model_version: 'v2' }, { details: null }, { details: { components: {} } }])(
    'does not infer health scale from numeric range for %j', patch => {
      const item = { ...health, score: 85, ...patch };
      expect(knownHealthProducer(item)).toBe(false); expect(predictionPresentation(item).value).toBe('85');
      expect(predictionPresentation(item).warnings.join()).toContain('non confirmée');
    });
  it.each([
    ['failure_risk', 'low', 'Faible'], ['failure_risk', 'medium', 'Moyen'], ['failure_risk', 'high', 'Élevé'], ['failure_risk', 'critical', 'Critique'],
    ['health_score', 'healthy', 'Sain'], ['health_score', 'good', 'Bon'], ['health_score', 'degraded', 'Dégradé'], ['health_score', 'poor', 'Mauvais'], ['health_score', 'critical', 'Critique'],
    ['rul', 'critical', 'Critique'], ['rul', 'warning', 'Avertissement'], ['rul', 'watch', 'À surveiller'], ['rul', 'healthy', 'Sain'],
    ['anomaly', 'high', 'high'], ['rul', 'high', 'high'], ['failure_risk', '__proto__', '__proto__'], ['health_score', 'unknown', 'unknown'], ['anomaly', '', 'Niveau vide']
  ] satisfies [PredictionType, string, string][])('translates only known %s level %s', (prediction_type, level, expected) => {
    expect(predictionPresentation({ ...base, prediction_type, level }).level).toBe(expected);
  });
  it.each([[true, 'Oui'], [false, 'Non'], [null, 'Non renseignée']] as const)('distinguishes alert %s', (is_alert, alert) => {
    expect(predictionPresentation({ ...base, is_alert }).alert).toBe(alert);
  });
  it.each([NaN, Infinity, -Infinity])('defensively hides nonfinite display value %s', score => {
    expect(predictionPresentation({ ...base, score }).value).toBe('Valeur non disponible');
  });
  it.each([0, 1, .123456])('shows explicit valid risk probability %s separately', failure_probability => {
    expect(predictionDetails({ ...base, prediction_type: 'failure_risk', details: { failure_probability } }).probability).toBe(failure_probability);
  });
  it.each([null, '0.5', false, {}, [], NaN, Infinity, -.01, 1.01])('rejects invalid probability %j without coercion', failure_probability => {
    const view = predictionDetails({ ...base, prediction_type: 'failure_risk', details: { failure_probability } });
    expect(view.probability).toBeNull(); expect(view.notices.join()).toContain('invalide');
  });
  it('does not invent missing or cross-type probabilities and preserves empty reasons', () => {
    expect(predictionDetails({ ...base, prediction_type: 'failure_risk', score: .7 }).probability).toBeNull();
    expect(predictionDetails({ ...base, details: { failure_probability: .7, reason: '' } })).toMatchObject({ probability: null, reason: '' });
    expect(predictionDetails({ ...base, details: { reason: false } }).notices.join()).toContain('n’est pas une chaîne');
  });
  it('validates four health components and preserves zero and precision', () => {
    expect(readHealthComponents(components)?.map(item => item.value)).toEqual([0, 100, 50, 75.5]);
    expect(predictionDetails(health).componentScaleConfirmed).toBe(true);
    expect(predictionDetails({ ...health, model_name: 'external' }).componentScaleConfirmed).toBe(false);
  });
  it.each([null, [], 0, {}, { ...components, failure_health: '0' }, { ...components, anomaly_health: 101 }, { ...components, maintenance_health: NaN }])('rejects malformed components %j', value => {
    expect(readHealthComponents(value)).toBeNull();
    expect(predictionDetails({ ...health, details: { components: value } }).notices).toHaveLength(1);
  });
  it('reports contradictory RUL while retaining both values including zero', () => {
    const item: PredictionRead = { ...base, prediction_type: 'rul', details: { rul_hours: 2 } };
    expect(predictionPresentation(item).value).toBe('0 h'); expect(predictionPresentation(item).warnings.join()).toContain('Incohérence');
    expect(predictionDetails(item).rul).toBe(2);
    expect(predictionPresentation({ ...item, details: { rul_hours: 0 } }).warnings).toEqual([]);
    expect(predictionDetails({ ...item, details: { rul_hours: 0 } }).rul).toBe(0);
  });
  it.each([null, '0', false, [], NaN, Infinity])('does not coerce invalid RUL %j', rul_hours => {
    const item: PredictionRead = { ...base, prediction_type: 'rul', details: { rul_hours } };
    expect(predictionDetails(item).rul).toBeNull(); expect(predictionDetails(item).notices).toHaveLength(1);
    expect(predictionPresentation(item).warnings).toEqual([]);
  });
  it('signals negative RUL without correcting it', () => {
    const item: PredictionRead = { ...base, prediction_type: 'rul', score: -1, details: { rul_hours: -1 } };
    expect(predictionPresentation(item).value).toBe('-1 h'); expect(predictionPresentation(item).warnings).toHaveLength(1);
    expect(predictionDetails(item).notices).toHaveLength(1);
  });
});
