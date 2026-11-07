import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Subject } from 'rxjs';
import { vi } from 'vitest';
import { P101SimulationOutcome, P101SimulationScenario, SimulationEquipment } from '../../models/p101-simulation.model';
import { P101_SIMULATION_RUNNER, simulationFixture } from '../../simulation/p101-simulation.fixtures';
import { P101SimulationComponent } from './p101-simulation.component';

const equipment: SimulationEquipment = { companyId: 7, siteId: 9, id: 12, label: 'Pompe test (POMPE)' };

describe('P101 explicitly local simulation', () => {
  let fixture: ComponentFixture<P101SimulationComponent>;
  let sources: Subject<P101SimulationOutcome>[];
  const runner = vi.fn((_: P101SimulationScenario) => {
    const source = new Subject<P101SimulationOutcome>(); sources.push(source); return source.asObservable();
  });
  const root = () => fixture.nativeElement as HTMLElement;
  const button = () => root().querySelector<HTMLButtonElement>('button')!;
  const state = () => fixture.componentInstance.state();
  async function render(selected: SimulationEquipment | null = equipment) {
    fixture = TestBed.createComponent(P101SimulationComponent);
    fixture.componentRef.setInput('equipment', selected);
    fixture.detectChanges(); await fixture.whenStable(); fixture.detectChanges();
  }
  function tick() { fixture.detectChanges(); TestBed.tick(); fixture.detectChanges(); }
  function start(scenario: P101SimulationScenario = 'anomaly') {
    fixture.componentInstance.scenario.setValue(scenario); tick(); button().click(); tick();
  }
  beforeEach(() => {
    sources = []; runner.mockClear();
    runner.mockImplementation(() => {
      const source = new Subject<P101SimulationOutcome>(); sources.push(source); return source.asObservable();
    });
    TestBed.configureTestingModule({ imports: [P101SimulationComponent], providers: [{ provide: P101_SIMULATION_RUNNER, useValue: runner }] });
  });
  afterEach(() => { TestBed.resetTestingModule(); runner.mockReset(); });

  it('requires a selected equipment and permanently labels fictional data', async () => {
    await render(null);
    expect(button().disabled).toBe(true);
    fixture.componentInstance.simulate();
    expect(runner).not.toHaveBeenCalled();
    expect(root().textContent).toContain('Simulation - données fictives');
    expect(root().textContent).toContain('Sélectionnez une entreprise');
    expect(state().status).toBe('idle');
  });

  it('rejects invalid selection IDs without creating a simulation', async () => {
    await render({ ...equipment, id: 0 });
    expect(button().disabled).toBe(true);
    fixture.componentInstance.simulate(); expect(runner).not.toHaveBeenCalled();
  });

  it('shows running state, prevents duplicate launches and disables the scenario control', async () => {
    await render(); start();
    expect(state().status).toBe('running');
    expect(root().textContent).toContain('Simulation en cours');
    expect(root().querySelector('section')?.getAttribute('aria-busy')).toBe('true');
    expect(button().disabled).toBe(true);
    expect(root().querySelector<HTMLSelectElement>('select')!.disabled).toBe(true);
    fixture.componentInstance.simulate(); expect(runner).toHaveBeenCalledTimes(1);
    expect(root().textContent).toContain(equipment.label);
  });

  it.each(['anomaly', 'normal'] as const)('renders %s as a binary example with explicit statistics', async scenario => {
    await render(); start(scenario); sources[0].next(simulationFixture(scenario)); tick();
    const positive = scenario === 'anomaly';
    expect(root().querySelector('h3')?.textContent).toContain(positive ? 'Anomalie détectée' : 'Aucune anomalie');
    const metrics = [...root().querySelectorAll('.metrics dd')].map(node => node.textContent?.trim());
    expect(metrics).toEqual([positive ? '70 °C' : '65 °C', '65 °C', '3 °C', positive ? '5 °C' : '0 °C', positive ? '1' : '0', positive ? 'Oui' : 'Non']);
    expect(root().querySelector('.metrics')?.textContent).not.toContain('%');
    expect(root().textContent).toContain('ne représente pas une probabilité de panne');
    expect(root().textContent).toContain('Provenance fictive');
    expect(root().textContent).toContain('sans lecture de mesures DEV');
    expect(root().textContent).toContain('Simulation - données fictives');
    expect(root().textContent).not.toContain('\u2014');
    expect(button().disabled).toBe(false);
    expect(sources[0].observed).toBe(false);
  });

  it.each(['abstained', 'rejected'] as const)('renders %s without inventing a score or statistics', async scenario => {
    await render(); start(scenario); sources[0].next(simulationFixture(scenario)); tick();
    expect(root().querySelector('h3')?.textContent).toContain(scenario === 'abstained' ? 'Abstention (Abstained)' : 'Rejet (Rejected)');
    expect(root().querySelector('.binary-score')).toBeNull();
    expect(root().querySelector('.metrics')?.textContent).toContain('Non produit');
    expect(root().querySelectorAll('.metrics dd').length).toBe(5);
    expect(root().textContent).toContain('Non disponible');
    expect(root().textContent).toContain(simulationFixture(scenario).reason);
    expect(root().textContent).not.toContain('\u2014');
  });

  it('renders the error scenario without exposing an exception as a real API failure', async () => {
    await render(); start('error'); sources[0].error(new Error('PRIVATE')); tick();
    expect(state().status).toBe('error');
    expect(root().querySelector('[role="alert"]')?.textContent).toContain('simulation locale');
    expect(root().textContent).not.toContain('PRIVATE');
    expect(root().textContent).toContain('Simulation - données fictives');
    expect(button().disabled).toBe(false);
    expect(() => simulationFixture('error')).toThrow('LOCAL_SIMULATION_ERROR');
  });

  it.each(['companyId', 'siteId', 'id', 'label'] as const)('cancels stale output when %s changes', async field => {
    await render(); start();
    fixture.componentRef.setInput('equipment', { ...equipment, [field]: field === 'label' ? 'Nouvelle pompe' : 99 }); tick();
    expect(state().status).toBe('idle');
    expect(sources[0].observed).toBe(false);
    sources[0].next(simulationFixture('anomaly')); tick();
    expect(root().querySelector('h3')).toBeNull();
  });

  it('clears completed examples when equipment is cleared or a different scenario is chosen', async () => {
    await render(); start(); sources[0].next(simulationFixture('anomaly')); tick();
    fixture.componentInstance.scenario.setValue('normal'); tick();
    expect(state().status).toBe('idle'); expect(root().querySelector('h3')).toBeNull();
    start('normal'); sources[1].next(simulationFixture('normal')); tick();
    fixture.componentRef.setInput('equipment', null); tick();
    expect(state().status).toBe('idle'); expect(button().disabled).toBe(true);
    expect(root().querySelector('.binary-score')).toBeNull();
  });

  it('unsubscribes on destruction and handles sources that fail synchronously or emit nothing', async () => {
    await render();
    runner.mockImplementationOnce(() => { throw new Error('PRIVATE'); });
    start(); expect(state().status).toBe('error'); expect(root().textContent).not.toContain('PRIVATE');
    start(); sources[0].complete(); tick(); expect(state().status).toBe('error');
    start(); expect(sources[1].observed).toBe(true);
    fixture.destroy(); expect(sources[1].observed).toBe(false);
  });
});
