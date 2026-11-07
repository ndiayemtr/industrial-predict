export type P101SimulationScenario = 'anomaly' | 'normal' | 'abstained' | 'rejected' | 'error';

export interface SimulationEquipment {
  readonly companyId: number;
  readonly siteId: number;
  readonly id: number;
  readonly label: string;
}

interface FictionalResult {
  readonly synthetic: true;
  readonly target: Readonly<{ value: number; unit: '°C' }>;
  readonly reason: string;
  readonly provenance: string;
}

export type P101SimulationOutcome = FictionalResult & (
  | { readonly status: 'computed'; readonly score: 0 | 1; readonly is_alert: boolean;
      readonly statistics: Readonly<{ mean: number; sample_std: number; threshold: number; absolute_deviation: number }> }
  | { readonly status: 'abstained'; readonly code: 'INSUFFICIENT_HISTORY'; readonly reference_count: number; readonly statistics: null }
  | { readonly status: 'rejected'; readonly code: 'INVALID_PROVENANCE'; readonly statistics: null }
);

export type P101SimulationState =
  | { readonly status: 'idle' }
  | { readonly status: 'running'; readonly equipment: SimulationEquipment }
  | { readonly status: 'completed'; readonly equipment: SimulationEquipment; readonly result: P101SimulationOutcome }
  | { readonly status: 'error'; readonly equipment: SimulationEquipment };
