import { ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Subscription, take } from 'rxjs';
import { P101SimulationScenario, P101SimulationState, SimulationEquipment } from '../../models/p101-simulation.model';
import { P101_SIMULATION_RUNNER, SIMULATION_PROVENANCE, SIMULATION_SCENARIOS } from '../../simulation/p101-simulation.fixtures';

function contextKey(equipment: SimulationEquipment | null): string | null {
  return equipment && [equipment.companyId, equipment.siteId, equipment.id].every(id => Number.isSafeInteger(id) && id > 0)
    && typeof equipment.label === 'string' && equipment.label.trim()
    ? JSON.stringify([equipment.companyId, equipment.siteId, equipment.id, equipment.label]) : null;
}

@Component({
  selector: 'app-p101-simulation', standalone: true, imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './p101-simulation.component.html', styleUrl: './p101-simulation.component.scss',
})
export class P101SimulationComponent {
  readonly equipment = input<SimulationEquipment | null>(null);
  readonly scenario = new FormControl<P101SimulationScenario>('anomaly', { nonNullable: true });
  readonly scenarios = SIMULATION_SCENARIOS;
  readonly provenance = SIMULATION_PROVENANCE;
  readonly state = signal<P101SimulationState>({ status: 'idle' });
  readonly canSimulate = computed(() => contextKey(this.equipment()) !== null && this.state().status !== 'running');
  private readonly runner = inject(P101_SIMULATION_RUNNER);
  private readonly destroy = inject(DestroyRef);
  private pending?: Subscription;
  private generation = 0;

  constructor() {
    let previous: string | null | undefined;
    effect(() => {
      const current = contextKey(this.equipment());
      if (current !== previous) { previous = current; this.reset(); }
    });
    effect(() => {
      if (this.state().status === 'running') this.scenario.disable({ emitEvent: false });
      else this.scenario.enable({ emitEvent: false });
    });
    this.scenario.valueChanges.pipe(takeUntilDestroyed(this.destroy)).subscribe(() => this.reset());
    this.destroy.onDestroy(() => { this.generation++; this.pending?.unsubscribe(); });
  }

  private reset(): void {
    this.generation++;
    this.pending?.unsubscribe();
    this.state.set({ status: 'idle' });
  }

  simulate(): void {
    if (!this.canSimulate()) return;
    const equipment = this.equipment()!;
    const key = contextKey(equipment);
    this.reset();
    const generation = this.generation;
    this.state.set({ status: 'running', equipment });
    const current = () => generation === this.generation && key === contextKey(this.equipment());
    try {
      this.pending = this.runner(this.scenario.value).pipe(take(1)).subscribe({
        next: result => { if (current()) this.state.set({ status: 'completed', equipment, result }); },
        error: () => { if (current()) this.state.set({ status: 'error', equipment }); },
        complete: () => { if (current() && this.state().status === 'running') this.state.set({ status: 'error', equipment }); },
      });
    } catch {
      if (current()) this.state.set({ status: 'error', equipment });
    }
  }
}
