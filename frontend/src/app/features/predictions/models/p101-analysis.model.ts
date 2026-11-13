import { PredictionRead } from './prediction.model';
import { P101SimulationOutcome } from './p101-simulation.model';

// UI contracts only. A future secure API must validate and map its own response.
// A successful analysis does not by itself assert durable persistence.
export type P101AnalysisResult =
  | { readonly source: 'simulation'; readonly result: P101SimulationOutcome }
  | { readonly source: 'real'; readonly prediction: PredictionRead };

export type P101RealAnalysisState =
  | { readonly status: 'unavailable'; readonly message: string }
  | { readonly status: 'idle'; readonly equipmentId: number }
  | { readonly status: 'loading'; readonly equipmentId: number }
  | { readonly status: 'success'; readonly equipmentId: number;
      readonly result: Extract<P101AnalysisResult, { source: 'real' }> }
  | { readonly status: 'insufficient-data'; readonly equipmentId: number; readonly message: string }
  | { readonly status: 'unauthorized'; readonly equipmentId: number }
  | { readonly status: 'error'; readonly equipmentId: number; readonly message: string };

// There is no runtime enable switch or HTTP action in this delivery.
export const P101_REAL_ANALYSIS_UNAVAILABLE = Object.freeze({
  status: 'unavailable' as const,
  message: 'L’analyse réelle reste indisponible tant que l’API sécurisée n’est pas opérationnelle.',
}) satisfies P101RealAnalysisState;
