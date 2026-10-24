import { JsonObject, PredictionRead, PredictionType } from '../models/prediction.model';

const levels: Record<PredictionType, Readonly<Record<string, string>>> = {
  anomaly: {},
  failure_risk: { low: 'Faible', medium: 'Moyen', high: 'Élevé', critical: 'Critique' },
  health_score: { healthy: 'Sain', good: 'Bon', degraded: 'Dégradé', poor: 'Mauvais', critical: 'Critique' },
  rul: { critical: 'Critique', warning: 'Avertissement', watch: 'À surveiller', healthy: 'Sain' }
};
export const healthComponents = [
  { key: 'failure_health', label: 'Santé liée au risque de panne' },
  { key: 'anomaly_health', label: 'Santé liée aux anomalies' },
  { key: 'data_quality_health', label: 'Santé liée à la qualité des données' },
  { key: 'maintenance_health', label: 'Santé liée à la maintenance' }
] as const;

export function finiteNumber(value: unknown): value is number { return typeof value === 'number' && Number.isFinite(value); }
export function jsonRecord(value: unknown): value is JsonObject { return value !== null && typeof value === 'object' && !Array.isArray(value); }
export function validProbability(value: unknown): value is number { return finiteNumber(value) && value >= 0 && value <= 1; }

export function readHealthComponents(value: unknown): { label: string; value: number }[] | null {
  if (!jsonRecord(value)) return null;
  const components = healthComponents.map(({ key, label }) => ({ label, value: value[key] }));
  if (!components.every(component => finiteNumber(component.value) && component.value >= 0 && component.value <= 100)) return null;
  return components.map(component => ({ label: component.label, value: component.value as number }));
}

// Match the persisted profile audited in UI 9.1, not a numeric range alone.
// Unknown names/versions or missing/malformed components do not establish a scale.
// These are declared producer metadata, not authenticated provenance.
export function knownHealthProducer(item: PredictionRead): boolean {
  return item.prediction_type === 'health_score' && item.model_name === 'health_score'
    && item.model_version === null && readHealthComponents(item.details?.['components']) !== null;
}

export function predictionPresentation(item: PredictionRead) {
  const labels: Record<PredictionType, string> = { anomaly: 'Indice d’anomalie', failure_risk: 'Score de risque déclaré',
    health_score: 'Indice de santé', rul: 'Durée de vie utile restante' };
  const warnings: string[] = [];
  let suffix = '';
  if (item.prediction_type === 'health_score') {
    if (knownHealthProducer(item)) {
      if (finiteNumber(item.score) && item.score >= 0 && item.score <= 100) suffix = ' / 100';
      else warnings.push('Valeur hors de l’échelle santé [0, 100] du producteur déclaré. Donnée conservée.');
    } else warnings.push('Échelle de santé non confirmée pour ce producteur ; valeur déclarée conservée.');
  }
  if (item.prediction_type === 'rul') {
    suffix = ' h';
    if (item.score < 0) warnings.push('Durée déclarée négative, incompatible avec une RUL en heures. Donnée conservée.');
    const detail = item.details?.['rul_hours'];
    if (finiteNumber(detail) && detail !== item.score) warnings.push('Incohérence : la durée fournie dans les détails diffère du score. Aucune valeur corrigée.');
  }
  const level = item.level === null ? 'Non renseigné' : item.level === '' ? 'Niveau vide'
    : Object.hasOwn(levels[item.prediction_type], item.level) ? levels[item.prediction_type][item.level] : item.level;
  return { label: labels[item.prediction_type], value: finiteNumber(item.score) ? String(item.score) + suffix : 'Valeur non disponible',
    level, alert: item.is_alert === null ? 'Non renseignée' : item.is_alert ? 'Oui' : 'Non', warnings };
}

export function predictionDetails(item: PredictionRead) {
  const details = item.details;
  const notices: string[] = [];
  const reason = typeof details?.['reason'] === 'string' ? details['reason'] : null;
  if (details && Object.hasOwn(details, 'reason') && reason === null) notices.push('Le motif fourni n’est pas une chaîne de texte. Consultez les données JSON.');
  const probability = item.prediction_type === 'failure_risk' && validProbability(details?.['failure_probability']) ? details!['failure_probability'] as number : null;
  if (item.prediction_type === 'failure_risk' && details && Object.hasOwn(details, 'failure_probability') && probability === null) {
    notices.push('Probabilité de panne fournie invalide : nombre fini entre 0 et 1 requis. Aucune probabilité déduite du score.');
  }
  const components = item.prediction_type === 'health_score' ? readHealthComponents(details?.['components']) : null;
  if (item.prediction_type === 'health_score' && details && Object.hasOwn(details, 'components') && components === null) notices.push('Composantes santé non interprétables : quatre nombres finis entre 0 et 100 requis.');
  const rul = item.prediction_type === 'rul' && finiteNumber(details?.['rul_hours']) ? details!['rul_hours'] as number : null;
  if (item.prediction_type === 'rul' && details && Object.hasOwn(details, 'rul_hours') && (rul === null || rul < 0)) notices.push('Durée RUL des détails invalide ou négative. Donnée d’origine conservée dans le JSON.');
  return { reason, probability, components, componentScaleConfirmed: knownHealthProducer(item), rul, notices };
}
