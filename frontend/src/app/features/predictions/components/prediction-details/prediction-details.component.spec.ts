import { TestBed } from '@angular/core/testing';
import { JsonObject, PredictionRead } from '../../models/prediction.model';
import { PredictionDetailsComponent } from './prediction-details.component';

const base: PredictionRead = { id: 17, equipment_id: 12, sensor_id: null, measurement_id: null,
  prediction_type: 'anomaly', score: 0, level: null, is_alert: null, model_name: null, model_version: null,
  horizon_hours: null, details: null, predicted_at: '2026-10-23T17:30:00.123456+05:30', created_at: '2026-10-23T12:00:01.654321Z' };

describe('Prediction inline details', () => {
  async function render(patch: Partial<PredictionRead> = {}) {
    const fixture = TestBed.createComponent(PredictionDetailsComponent);
    fixture.componentRef.setInput('prediction', { ...base, ...patch }); fixture.detectChanges(); await fixture.whenStable();
    return fixture.nativeElement as HTMLElement;
  }
  beforeEach(() => TestBed.configureTestingModule({ imports: [PredictionDetailsComponent] }));
  afterEach(() => TestBed.resetTestingModule());
  it('renders nullable metadata explicitly without inventing values or links', async () => {
    const root = await render();
    expect(root.querySelectorAll('.metadata dd')).toHaveLength(6);
    expect(root.querySelectorAll('a')).toHaveLength(0); expect(root.textContent).toContain('Non renseigné');
    expect(root.textContent).toContain('Aucun détail JSON fourni'); expect(root.querySelector('pre')).toBeNull();
  });
  it('preserves created timestamp and offset independently of prediction timestamp', async () => {
    const root = await render({ model_name: 'producer', model_version: 'v3', sensor_id: 3, measurement_id: 4, horizon_hours: .5 });
    expect(root.querySelector('time')?.textContent).toBe(base.created_at);
    expect(root.querySelector('time')?.getAttribute('datetime')).toBe(base.created_at);
    expect(root.textContent).not.toContain(base.predicted_at);
    expect(root.textContent).toContain('0.5 h'); expect(root.textContent).toContain('producer'); expect(root.textContent).toContain('v3');
  });
  it('keeps empty names/versions/reasons distinct from null', async () => {
    const root = await render({ model_name: '', model_version: '', details: { reason: '' } });
    expect(root.textContent).toContain('Nom vide'); expect(root.textContent).toContain('Version vide'); expect(root.textContent).toContain('Motif vide');
  });
  it('escapes metadata, reasons, unknown JSON keys and values containing HTML', async () => {
    const html = '<img src=x onerror="alert(1)"><script>bad()</script>';
    const root = await render({ model_name: html, model_version: html, details: { reason: html, [html]: html } });
    expect(root.querySelector('img,script')).toBeNull(); expect(root.querySelector('.reason')?.textContent).toBe(html);
    expect(root.querySelector('pre')?.textContent).toContain('<img'); expect(root.querySelector('pre')?.innerHTML).toContain('&lt;img');
    expect(root.querySelector('.metadata')?.textContent).toContain(html);
  });
  it.each<JsonObject>([{}, { extras: [0, false, null, { nested: 'value' }] }])('displays empty or nested JSON without losing null/false/zero: %j', async details => {
    const root = await render({ details }); expect(JSON.parse(root.querySelector('pre')!.textContent!)).toEqual(details);
    expect(root.querySelector('.json-warning')).toBeNull();
  });
  it('shows explicit zero probability independently of risk score', async () => {
    const root = await render({ prediction_type: 'failure_risk', score: 75, details: { failure_probability: 0 } });
    expect(root.querySelector('.probability')?.textContent).toContain(': 0 (échelle 0 à 1)'); expect(root.textContent).not.toContain('%');
  });
  it('displays invalid declared fields only as raw JSON with a notice', async () => {
    const root = await render({ prediction_type: 'failure_risk', details: { failure_probability: '0.5', reason: false } });
    expect(root.querySelector('.probability,.reason')).toBeNull(); expect(root.querySelectorAll('.notice')).toHaveLength(2);
    expect(root.querySelector('pre')?.textContent).toContain('"0.5"');
  });
  it('shows valid producer components including zero and generic extras', async () => {
    const root = await render({ prediction_type: 'health_score', model_name: 'health_score', details: { components: {
      failure_health: 0, anomaly_health: 100, data_quality_health: 80, maintenance_health: 90 }, extra: 'kept' } });
    expect(root.querySelectorAll('.components dd')).toHaveLength(4); expect(root.querySelector('.components')?.textContent).toContain('0 / 100');
    expect(root.querySelector('pre')?.textContent).toContain('kept');
  });
  it('shows RUL zero and never extrapolates a failure date', async () => {
    const root = await render({ prediction_type: 'rul', details: { rul_hours: 0 } });
    expect(root.querySelector('.rul-detail')?.textContent).toContain(': 0 h'); expect(root.querySelectorAll('time')).toHaveLength(1);
  });
  it('warns about large/deep JSON, with keyboard focus on the bounded text region', async () => {
    const root = await render({ details: { large: 'x'.repeat(20000) } });
    expect(root.querySelector('pre')!.textContent!.length).toBeLessThanOrEqual(10000);
    expect(root.querySelector('pre')?.getAttribute('tabindex')).toBe('0');
    expect(root.querySelector('.json-warning')?.textContent).toContain('ni le volume réseau');
    expect(root.querySelector('.json-warning')?.textContent).toContain('six niveaux');
  });
});
