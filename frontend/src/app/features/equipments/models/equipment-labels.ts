import { EquipmentCriticality, EquipmentStatus } from '../../../core/models/reference-data.model';

export function equipmentStatusLabels(): Readonly<Record<EquipmentStatus, string>> {
  return { operational: 'Opérationnel', maintenance: 'En maintenance', out_of_service: 'Hors service' };
}
export function equipmentCriticalityLabels(): Readonly<Record<EquipmentCriticality, string>> {
  return { low: 'Faible', medium: 'Moyenne', high: 'Élevée', critical: 'Critique' };
}
