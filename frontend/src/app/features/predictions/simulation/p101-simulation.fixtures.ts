import { InjectionToken } from '@angular/core';
import { Observable, map, timer } from 'rxjs';
import { P101SimulationOutcome, P101SimulationScenario } from '../models/p101-simulation.model';

export const SIMULATION_PROVENANCE = 'Jeu fictif local P101 : températures fictives, sans lecture de mesures DEV.';
export const SIMULATION_SCENARIOS: readonly Readonly<{ id: P101SimulationScenario; label: string }>[] = Object.freeze([
  { id: 'anomaly', label: 'Anomalie détectée - indice 1' },
  { id: 'normal', label: 'Aucune anomalie - indice 0' },
  { id: 'abstained', label: 'Abstention - historique insuffisant' },
  { id: 'rejected', label: 'Rejet - entrée fictive invalide' },
  { id: 'error', label: 'Erreur de simulation' },
]);

// Presentation examples only: no backend response, statistical engine or dataset access.
export function simulationFixture(scenario: P101SimulationScenario): P101SimulationOutcome {
  const base = { synthetic: true as const, provenance: SIMULATION_PROVENANCE };
  switch (scenario) {
    case 'anomaly':
      return { ...base, status: 'computed', target: { value: 70, unit: '°C' }, score: 1, is_alert: true,
        statistics: { mean: 65, sample_std: 1, threshold: 3, absolute_deviation: 5 },
        reason: 'Exemple fictif : l’écart de 5 °C dépasse strictement le seuil de 3 °C.' };
    case 'normal':
      return { ...base, status: 'computed', target: { value: 65, unit: '°C' }, score: 0, is_alert: false,
        statistics: { mean: 65, sample_std: 1, threshold: 3, absolute_deviation: 0 },
        reason: 'Exemple fictif : la température cible égale la moyenne historique.' };
    case 'abstained':
      return { ...base, status: 'abstained', target: { value: 65, unit: '°C' }, statistics: null,
        code: 'INSUFFICIENT_HISTORY', reference_count: 3,
        reason: 'Historique fictif insuffisant : 3 références disponibles sur les 10 requises. Aucun indice produit.' };
    case 'rejected':
      return { ...base, status: 'rejected', target: { value: 65, unit: '°C' }, statistics: null,
        code: 'INVALID_PROVENANCE', reason: 'Provenance fictive incomplète : déclaration de source volontairement absente. Aucun calcul ni indice produit.' };
    case 'error': throw new Error('LOCAL_SIMULATION_ERROR');
  }
}

export type P101SimulationRunner = (scenario: P101SimulationScenario) => Observable<P101SimulationOutcome>;
export const P101_SIMULATION_RUNNER = new InjectionToken<P101SimulationRunner>('P101 local simulation', {
  providedIn: 'root', factory: () => scenario => timer(450).pipe(map(() => simulationFixture(scenario))),
});
