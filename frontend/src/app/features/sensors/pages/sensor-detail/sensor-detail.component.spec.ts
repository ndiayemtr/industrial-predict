import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { SensorRead } from '../../models/sensor.model';
import { SENSOR_ROUTES } from '../../sensors.routes';
import { SensorDetailComponent } from './sensor-detail.component';

const sensor: SensorRead = { id: 17, name: 'Température 日本', code: 'TEMP', sensor_type: 'temperature', unit: '°C',
  description: 'Palier principal\nLigne secondaire', status: 'active', equipment_id: 12,
  created_at: '2026-08-31T14:58:20.179290', updated_at: '2026-10-16T13:51:15.910577+02:00' };
const company = { id: 7, name: 'Entreprise réelle', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7, name: 'Site réel', code: 'SITE' };
const equipment = { ...company, id: 12, site_id: 9, name: 'Pompe réelle', code: 'POMPE', equipment_type: 'pump', status: 'operational', criticality: 'high' };
const context = 'company_id=7&site_id=9&equipment_id=12&page=3&page_size=50&search=TEMP&status=active';

describe('Sensor read-only detail and real parent chain', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: SensorDetailComponent;
  const root = () => harness.routeNativeElement!;
  const read = (path: string) => http.expectOne(req => req.url === `/api/v1/${path}`);
  const values = () => [...root().querySelectorAll('dl > div')].map(el => [el.querySelector('dt')!.textContent!, el.querySelector('dd')!.textContent!.trim()]);
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'sensors', children: SENSOR_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    try {
      http.expectNone(req => req.method !== 'GET');
      http.expectNone(req => /measurements|predictions|recommendations|health-score|rul/.test(req.url));
      http.verify();
    } finally { TestBed.resetTestingModule(); }
  });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(url = '/sensors/17') {
    harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, SensorDetailComponent); await settle();
  }
  function parents() { read('equipments/12').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company); }
  async function loaded(url = '/sensors/17') { await open(url); read('sensors/17').flush(sensor); parents(); await settle(); }

  it('loads each real parent sequentially, never from return context, and keeps sensor fields during resolution', async () => {
    await open('/sensors/17?company_id=99&site_id=88&equipment_id=77&page=3&page_size=50&search=TEMP&status=active');
    expect(root().querySelector('.sensor-detail')?.getAttribute('aria-busy')).toBe('true');
    http.expectNone(req => req.url.includes('/equipments/'));
    const req = read('sensors/17'); expect(req.request.params.keys()).toHaveLength(0); req.flush(sensor); await settle();
    expect(root().textContent).toContain(sensor.name); expect(root().textContent).toContain('Chargement de l’équipement réel');
    http.expectNone(req => req.url.includes('/sites/')); read('equipments/12').flush(equipment); await settle();
    expect(root().querySelector('.equipment-reference')?.getAttribute('href')).toBe('/equipments/12?site_id=9');
    http.expectNone(req => req.url.includes('/companies/')); read('sites/9').flush(site); await settle();
    expect(root().textContent).toContain('Chargement de l’entreprise réelle'); read('companies/7').flush(company); await settle();
    expect(root().querySelector('.equipment-reference')?.getAttribute('href')).toBe('/equipments/12?site_id=9&company_id=7');
    expect(root().querySelector('.site-reference')?.textContent).toBe('Site réel - SITE');
    expect(root().querySelector('.company-reference')?.textContent).toBe('Entreprise réelle - ENT');
    expect(root().querySelector('.context-notice')?.textContent).toContain('conservé pour revenir à la liste');
    expect(root().querySelector('.sensor-back')?.getAttribute('href')).toBe('/sensors?company_id=99&site_id=88&equipment_id=77&page=3&page_size=50&search=TEMP&status=active');
    expect(component.state()).toMatchObject({ status: 'success', data: sensor }); http.expectNone(() => true);
  });
  it('renders semantic read-only fields, French status, original text and administrative dates', async () => {
    await loaded();
    expect(root().querySelectorAll('h1')).toHaveLength(1);
    expect(values().map(([label]) => label)).toEqual(['Nom', 'Code métier', 'Type de capteur', 'Unité', 'Statut', 'Description', 'Équipement', 'Site industriel', 'Entreprise de rattachement', 'Création', 'Dernière modification']);
    expect(values()).toContainEqual(['Type de capteur', 'temperature']); expect(values()).toContainEqual(['Unité', '°C']);
    expect(values()).toContainEqual(['Statut', 'Actif']); expect(values()).toContainEqual(['Description', sensor.description]);
    expect(values()).toContainEqual(['Création', '31/08/2026 à 14:58']); expect(values()).toContainEqual(['Dernière modification', '16/10/2026 à 11:51 UTC']);
    expect(root().querySelectorAll('form,input,select,button')).toHaveLength(0);
    expect(root().textContent).not.toMatch(/Modifier|Supprimer|Mesures|Prédiction|Health Score|RUL/);
    const link = root().querySelector<HTMLAnchorElement>('.equipment-reference')!; link.focus(); expect(document.activeElement).toBe(link);
    expect(root().querySelector('.context-notice')).toBeNull();
  });
  it.each(['0', '-1', 'abc', '1.5', '1e2', '9007199254740992'])('rejects invalid ID %s without HTTP', async id => {
    await open(`/sensors/${id}`); expect(root().textContent).toContain('Identifiant invalide'); http.expectNone(() => true);
  });
  it.each([0, 400, 401, 403, 404, 422, 500])('handles Sensor HTTP %s separately and retries only transient errors', async status => {
    await open(); const req = read('sensors/17');
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' });
    await settle(); expect(component.state()).toMatchObject({ status: 'error', retryable: status === 0 || status >= 500 });
    expect(root().querySelector('dl')).toBeNull(); if (status === 404) expect(root().textContent).toContain('Capteur introuvable (404)');
    component.retry();
    if (status === 0 || status >= 500) { read('sensors/17').flush(sensor); parents(); await settle(); }
    http.expectNone(() => true);
  });
  describe.each(['equipment', 'site', 'company'] as const)('%s reference', stage => {
    function reach() {
      read('sensors/17').flush(sensor);
      if (stage !== 'equipment') read('equipments/12').flush(equipment);
      if (stage === 'company') read('sites/9').flush(site);
    }
    const target = () => stage === 'equipment' ? 'equipments/12' : stage === 'site' ? 'sites/9' : 'companies/7';
    it.each([0, 401, 403, 404, 422, 500])('retains Sensor on HTTP %s and retries only this parent and descendants', async status => {
      await open('/sensors/17?company_id=99&site_id=88&equipment_id=77'); reach(); const req = read(target());
      if (status === 0) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' });
      await settle(); expect(component.state()).toMatchObject({ status: 'success', data: sensor, [stage]: { status: 'error', retryable: status === 0 || status >= 500 } });
      expect(root().textContent).toContain(sensor.name); expect(root().textContent).not.toContain('Capteur introuvable');
      if (stage === 'equipment') expect(root().querySelector('.equipment-reference')).toBeNull();
      else expect(root().querySelector('.equipment-reference')).not.toBeNull();
      if (stage === 'equipment') component.retryEquipment(); else if (stage === 'site') component.retrySite(); else component.retryCompany();
      if (status === 0 || status >= 500) {
        if (stage === 'equipment') read('equipments/12').flush(equipment);
        if (stage !== 'company') read('sites/9').flush(site);
        read('companies/7').flush(company); await settle(); expect(root().querySelector('.company-reference')).not.toBeNull();
      }
      http.expectNone(() => true);
    });
    it('rejects a mismatched returned identity without losing Sensor', async () => {
      await open(); reach(); read(target()).flush(stage === 'equipment' ? { ...equipment, id: 13 } : stage === 'site' ? { ...site, id: 10 } : { ...company, id: 8 });
      await settle(); expect(component.state()).toMatchObject({ status: 'success', data: sensor, [stage]: { status: 'error', retryable: false } });
      expect(root().textContent).toContain('ne correspond pas'); http.expectNone(() => true);
    });
    it('rejects an invalid foreign key locally', async () => {
      await open(); read('sensors/17').flush(stage === 'equipment' ? { ...sensor, equipment_id: 0 } : sensor);
      if (stage !== 'equipment') read('equipments/12').flush(stage === 'site' ? { ...equipment, site_id: 0 } : equipment);
      if (stage === 'company') read('sites/9').flush({ ...site, company_id: 0 });
      await settle(); expect(component.state()).toMatchObject({ status: 'success', [stage]: { status: 'error', retryable: false } });
      expect(root().textContent).toContain(sensor.name); http.expectNone(() => true);
    });
  });
  it('rejects a Sensor response for another ID without any parent calls', async () => {
    await open(); read('sensors/17').flush({ ...sensor, id: 18 }); await settle();
    expect(component.state().status).toBe('error'); expect(root().textContent).toContain('ne correspond pas'); http.expectNone(() => true);
  });
  it.each(['sensor', 'equipment', 'site', 'company'])('cancels obsolete %s reads on ID navigation', async stage => {
    await open(); let obsolete = read('sensors/17');
    if (stage !== 'sensor') { obsolete.flush(sensor); obsolete = read('equipments/12'); }
    if (stage === 'site' || stage === 'company') { obsolete.flush(equipment); obsolete = read('sites/9'); }
    if (stage === 'company') { obsolete.flush(site); obsolete = read('companies/7'); }
    const original = component; component = await harness.navigateByUrl('/sensors/18', SensorDetailComponent); await settle();
    expect(component).toBe(original); expect(obsolete.cancelled).toBe(true); expect(root().textContent).not.toContain(sensor.name);
    read('sensors/18').flush({ ...sensor, id: 18, name: 'Autre capteur' }); parents(); await settle();
    expect(root().textContent).toContain('Autre capteur'); expect(root().textContent).not.toContain(sensor.name);
  });
  it('cancels requests on invalid ID navigation and destruction', async () => {
    await open(); const pending = read('sensors/17'); await harness.navigateByUrl('/sensors/abc'); await settle(); expect(pending.cancelled).toBe(true);
    await harness.navigateByUrl('/sensors/18'); await settle(); const next = read('sensors/18'); harness.fixture.destroy(); expect(next.cancelled).toBe(true);
  });
  it('updates only return context on query navigation and never borrows Sensor filters for Equipment', async () => {
    await loaded(`/sensors/17?${context}`); expect(component.differentContext()).toBe(false);
    await harness.navigateByUrl('/sensors/17?company_id=99&site_id=88&equipment_id=77&page=4&page_size=1&status=inactive&search=Other'); await settle();
    expect(component.differentContext()).toBe(true); http.expectNone(() => true);
    expect(root().querySelector('.sensor-back')?.getAttribute('href')).toBe('/sensors?company_id=99&site_id=88&equipment_id=77&page=4&page_size=1&search=Other&status=inactive');
    expect(root().querySelector('.equipment-reference')?.getAttribute('href')).toBe('/equipments/12?site_id=9&company_id=7');
  });
  it('does not treat query parameters as creation confirmation evidence', async () => {
    await loaded('/sensors/17?createdSensorId=17'); expect(component.creationConfirmed()).toBe(false); expect(root().querySelector('.creation-confirmation')).toBeNull();
  });
  it('sanitizes invalid return parameters and drops untrusted returnUrl', async () => {
    await loaded('/sensors/17?company_id=-1&site_id=abc&equipment_id=0&page=0&page_size=101&status=wrong&search=%20%20&returnUrl=https://example.com');
    expect(root().querySelector('.sensor-back')?.getAttribute('href')).toBe('/sensors?page=1&page_size=20');
  });
  it.each([null, '', '   '])('shows missing description %s and unavailable dates without modifying transport', async description => {
    await open(); read('sensors/17').flush({ ...sensor, description, created_at: 'broken', updated_at: '' }); parents(); await settle();
    expect(values()).toContainEqual(['Description', 'Non renseignée']); expect(values()).toContainEqual(['Création', 'Non disponible']);
    expect(component.state()).toMatchObject({ data: { description } });
  });
  it('escapes business text and does not disguise an unknown status as active', async () => {
    await open(); read('sensors/17').flush({ ...sensor, status: 'unknown', description: '<img src=x onerror=alert(1)>' }); parents(); await settle();
    expect(values()).toContainEqual(['Statut', 'Non disponible']); expect(root().querySelector('dl img')).toBeNull();
    expect(root().textContent).toContain('<img src=x onerror=alert(1)>');
  });
  it('returns to the list with the seven applied parameters and only equipment scope sent to Sensors', async () => {
    await loaded(`/sensors/17?${context}`); root().querySelector<HTMLAnchorElement>('.sensor-back')!.click(); await settle();
    read('companies').flush({ items: [company], total: 1, page: 1, page_size: 50, pages: 1 }); parents(); await settle();
    read('sites').flush({ items: [site], total: 1, page: 1, page_size: 50, pages: 1 });
    read('equipments').flush({ items: [equipment], total: 1, page: 1, page_size: 50, pages: 1 });
    const req = read('sensors'); expect(Object.fromEntries(req.request.params.keys().map(key => [key, req.request.params.get(key)]))).toEqual({ equipment_id: '12', page: '3', page_size: '50', search: 'TEMP', status: 'active' });
    req.flush({ items: [sensor], total: 101, page: 3, page_size: 50, pages: 3 }); await settle();
    expect(root().querySelector('tbody a')?.getAttribute('href')).toContain('/sensors/17?');
    expect(TestBed.inject(Router).url).toBe(`/sensors?${context}`);
  });
});
