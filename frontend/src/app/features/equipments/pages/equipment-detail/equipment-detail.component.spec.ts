import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { EquipmentRead } from '../../../../core/models/reference-data.model';
import { EQUIPMENT_ROUTES } from '../../equipments.routes';
import { EquipmentDetailComponent } from './equipment-detail.component';

const equipment: EquipmentRead = { id: 12, name: 'Pompe 日本', code: 'POMPE', equipment_type: 'Pompe haute pression',
  description: 'Circuit principal\nLigne secondaire', status: 'maintenance', criticality: 'critical', site_id: 9,
  created_at: '2026-08-31T14:58:20.179290', updated_at: '2026-10-16T13:51:15.910577+02:00' };
const site = { id: 9, name: 'Usine réelle', code: 'USINE', company_id: 7, description: null, created_at: '', updated_at: '' };
const company = { ...site, id: 7, name: 'Entreprise réelle', code: 'ENT' };

describe('Equipment read-only detail and real parent chain', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: EquipmentDetailComponent;
  const root = () => harness.routeNativeElement!;
  const read = (id = 12) => http.expectOne(`/api/v1/equipments/${id}`);
  const siteRead = () => http.expectOne('/api/v1/sites/9');
  const companyRead = () => http.expectOne('/api/v1/companies/7');
  const values = () => [...root().querySelectorAll('dl > div')].map(el => [el.querySelector('dt')!.textContent!, el.querySelector('dd')!.textContent!.trim()]);
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'equipments', children: EQUIPMENT_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    http.expectNone(req => req.method !== 'GET');
    http.expectNone(req => /health-score|rul|predictions|recommendations|sensors|measurements|maintenance/.test(req.url));
    http.verify();
  });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(url = '/equipments/12') {
    harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, EquipmentDetailComponent); await settle();
  }
  async function loaded(url = '/equipments/12') { await open(url); read().flush(equipment); siteRead().flush(site); companyRead().flush(company); await settle(); }

  it('loads equipment, then its actual site, then the actual company while retaining accessible data', async () => {
    await open('/equipments/12?company_id=99&site_id=88&status=operational&criticality=low&search=Pompe&page=3&page_size=50');
    expect(root().querySelector('.equipment-detail')?.getAttribute('aria-busy')).toBe('true');
    expect(root().textContent).toContain('Chargement de l’équipement'); http.expectNone(req => req.url.includes('/sites/'));
    const req = read(); expect(req.request.method).toBe('GET'); expect(req.request.params.keys()).toHaveLength(0); req.flush(equipment); await settle();
    expect(root().textContent).toContain(equipment.name); expect(root().textContent).toContain('Chargement du site réel');
    http.expectNone(req => req.url.includes('/companies/')); siteRead().flush(site); await settle();
    expect(root().querySelector('.site-reference')?.textContent).toBe('Usine réelle - USINE');
    expect(root().textContent).toContain('Chargement de l’entreprise réelle'); companyRead().flush(company); await settle();
    expect(root().querySelector('.company-reference')?.textContent).toBe('Entreprise réelle - ENT');
    expect(root().querySelector('.context-notice')?.textContent).toContain('conservé pour revenir à la liste');
    expect(root().querySelector('.site-reference')?.getAttribute('href')).toBe('/sites/9?company_id=7');
    expect(root().querySelector('.equipment-back')?.getAttribute('href')).toBe('/equipments?company_id=99&site_id=88&page=3&page_size=50&search=Pompe&status=operational&criticality=low');
    expect(root().querySelector('.equipment-edit')?.getAttribute('href')).toBe('/equipments/12/edit?company_id=99&site_id=88&page=3&page_size=50&search=Pompe&status=operational&criticality=low');
    expect(values()).toContainEqual(['Type d’équipement', equipment.equipment_type]);
    expect(values()).toContainEqual(['Statut', 'En maintenance']); expect(values()).toContainEqual(['Criticité', 'Critique']);
    expect(values()).toContainEqual(['Création', '31/08/2026 à 14:58']); expect(values()).toContainEqual(['Dernière modification', '16/10/2026 à 11:51 UTC']);
    expect(component.state()).toMatchObject({ status: 'success', data: equipment }); http.expectNone(() => true);
  });
  it('uses semantic read-only content, one h1 and keyboard-accessible business links without technical IDs or fake predictions', async () => {
    await loaded(); expect(root().querySelectorAll('h1')).toHaveLength(1);
    expect(values().map(([label]) => label)).toEqual(['Nom', 'Code métier', 'Type d’équipement', 'Statut', 'Criticité', 'Description', 'Site industriel', 'Entreprise de rattachement', 'Création', 'Dernière modification']);
    expect(values().map(([, value]) => value)).not.toContain('12'); expect(values().map(([, value]) => value)).not.toContain('9'); expect(values().map(([, value]) => value)).not.toContain('7');
    expect(root().querySelectorAll('form,input,select,button')).toHaveLength(0);
    expect(root().textContent).not.toMatch(/Supprimer|Health Score|RUL|maintenance prédi|Prédiction|Identifiant/);
    expect(root().querySelector('.equipment-edit')?.getAttribute('href')).toBe('/equipments/12/edit?page=1&page_size=20');
    const link = root().querySelector<HTMLAnchorElement>('.site-reference')!; link.focus(); expect(document.activeElement).toBe(link);
    expect(root().querySelector('.description dd')?.textContent).toBe(equipment.description);
    expect(root().querySelector('.context-notice')).toBeNull();
    expect(root().querySelector('.equipment-back')?.getAttribute('href')).toBe('/equipments?page=1&page_size=20');
  });
  it('does not accept URL query parameters as creation-success evidence', async () => {
    await loaded('/equipments/12?createdEquipmentId=12'); expect(component.creationConfirmed()).toBe(false);
    expect(root().querySelector('.creation-confirmation')).toBeNull();
  });
  it('does not accept URL query parameters as update-success evidence', async () => {
    await loaded('/equipments/12?updatedEquipmentId=12'); expect(component.updateConfirmed()).toBe(false);
    expect(root().querySelector('.update-confirmation')).toBeNull();
  });
  it('offers editing only once the Equipment GET has succeeded', async () => {
    await open(); expect(root().querySelector('.equipment-edit')).toBeNull();
    read().flush({}, { status: 404, statusText: 'Not found' }); await settle(); expect(root().querySelector('.equipment-edit')).toBeNull();
  });
  it.each(['0', '-1', 'abc', '1.5', '1e2', '9007199254740992'])('rejects identifier %s locally without any HTTP', async id => {
    await open(`/equipments/${id}`); expect(root().textContent).toContain('Identifiant invalide'); expect(root().querySelector('dl')).toBeNull(); http.expectNone(() => true);
  });
  it.each([0, 400, 401, 403, 404, 422, 500])('handles equipment error %s without parent calls and only retries transient reads', async status => {
    await open(); const req = read();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' });
    await settle(); expect(component.state()).toMatchObject({ status: 'error', retryable: status === 0 || status >= 500 });
    if (status === 404) expect(root().textContent).toContain('Équipement introuvable (404)');
    expect(root().querySelector('dl')).toBeNull(); component.retry();
    if (status === 0 || status >= 500) { read().flush(equipment); siteRead().flush(site); companyRead().flush(company); await settle(); expect(root().querySelector('dl')).not.toBeNull(); }
    http.expectNone(() => true);
  });
  it.each([0, 401, 403, 404, 422, 500])('retains equipment on site error %s without guessing the company from the URL', async status => {
    await open('/equipments/12?company_id=99&site_id=88'); read().flush(equipment); const req = siteRead();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' });
    await settle(); expect(root().textContent).toContain(equipment.name); expect(root().textContent).toContain('Site industriel indisponible');
    expect(root().querySelector('.site-reference')).toBeNull(); expect(root().querySelector('.company-reference')).toBeNull();
    expect(root().textContent).toContain('Entreprise non résolue'); component.retrySite();
    if (status === 0 || status >= 500) { siteRead().flush(site); companyRead().flush(company); await settle(); expect(root().querySelector('.company-reference')).not.toBeNull(); }
    http.expectNone(req => req.url === '/api/v1/equipments/12'); http.expectNone(() => true);
  });
  it.each([0, 401, 403, 404, 422, 500])('retains equipment and real site on company error %s with independent retry', async status => {
    await open(); read().flush(equipment); siteRead().flush(site); const req = companyRead();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' });
    await settle(); expect(root().textContent).toContain(equipment.name); expect(root().textContent).toContain('Entreprise indisponible');
    expect(root().querySelector('.site-reference')?.getAttribute('href')).toBe('/sites/9?company_id=7'); component.retryCompany();
    if (status === 0 || status >= 500) { companyRead().flush(company); await settle(); expect(root().querySelector('.company-reference')).not.toBeNull(); }
    http.expectNone(() => true);
  });
  it.each([
    ['2026-10-16T11:51:15.910577Z', '16/10/2026 à 11:51 UTC'],
    ['2026-10-16T13:51:15.910577+02:00', '16/10/2026 à 11:51 UTC'],
    ['2026-10-16T00:15:20.123-03:30', '16/10/2026 à 03:45 UTC'],
    ['2026-10-25T02:30:59.999999', '25/10/2026 à 02:30'],
    ['2024-02-29T12:00:00', '29/02/2024 à 12:00'],
    ['2026-02-30T12:00:00', 'Non disponible'], ['broken', 'Non disponible'], ['', 'Non disponible'],
    ['2026-10-16T25:00:00Z', 'Non disponible'], ['2026-10-16T12:00:00+25:00', 'Non disponible']
  ])('formats administrative timestamp %s without changing its transport value', async (timestamp, expected) => {
    await open(); read().flush({ ...equipment, created_at: timestamp, updated_at: timestamp }); siteRead().flush(site); companyRead().flush(company); await settle();
    expect(values()).toContainEqual(['Création', expected]); expect(values()).toContainEqual(['Dernière modification', expected]);
    expect(component.state()).toMatchObject({ status: 'success', data: { created_at: timestamp, updated_at: timestamp } });
  });
  it.each([null, '', '   '])('displays missing description %s without inventing equipment data', async description => {
    await open(); read().flush({ ...equipment, description, created_at: null, updated_at: undefined }); siteRead().flush(site); companyRead().flush(company); await settle();
    expect(values()).toContainEqual(['Description', 'Non renseignée']); expect(values()).toContainEqual(['Création', 'Non disponible']); expect(values()).toContainEqual(['Dernière modification', 'Non disponible']);
  });
  it('does not silently replace unexpected enum values or interpret business text as HTML', async () => {
    await open(); read().flush({ ...equipment, status: 'unknown', criticality: 'urgent', description: '<img src=x onerror=alert(1)>' }); siteRead().flush(site); companyRead().flush(company); await settle();
    expect(values()).toContainEqual(['Statut', 'Non disponible']); expect(values()).toContainEqual(['Criticité', 'Non disponible']);
    expect(root().querySelector('dl img')).toBeNull(); expect(root().textContent).toContain('<img src=x onerror=alert(1)>');
  });
  it.each(['equipment', 'site', 'company'])('cancels obsolete %s reads when the route identifier changes', async stage => {
    await open(); let obsolete = read();
    if (stage !== 'equipment') { obsolete.flush(equipment); obsolete = siteRead(); }
    if (stage === 'company') { obsolete.flush(site); obsolete = companyRead(); }
    const original = component; component = await harness.navigateByUrl('/equipments/13', EquipmentDetailComponent); await settle();
    expect(component).toBe(original); expect(obsolete.cancelled).toBe(true); expect(root().textContent).not.toContain(equipment.name);
    read(13).flush({ ...equipment, id: 13, name: 'Second équipement' }); siteRead().flush(site); companyRead().flush(company); await settle();
    expect(root().textContent).toContain('Second équipement'); expect(root().textContent).not.toContain(equipment.name);
  });
  it('cancels pending requests on invalid route navigation and destruction', async () => {
    await open(); const obsolete = read(); await harness.navigateByUrl('/equipments/abc'); await settle(); expect(obsolete.cancelled).toBe(true);
    component = await harness.navigateByUrl('/equipments/13', EquipmentDetailComponent); await settle(); const pending = read(13);
    harness.fixture.destroy(); expect(pending.cancelled).toBe(true);
  });
  it('changes only return context on query navigation without reloading real data', async () => {
    await loaded('/equipments/12?company_id=7&site_id=9&status=maintenance&criticality=critical&search=Pompe&page=2&page_size=1');
    expect(component.differentContext()).toBe(false);
    await harness.navigateByUrl('/equipments/12?company_id=99&site_id=88&status=out_of_service&criticality=low&search=Other&page=4&page_size=100'); await settle();
    http.expectNone(() => true); expect(component.differentContext()).toBe(true); expect(component.state()).toMatchObject({ status: 'success', data: equipment });
    expect(root().querySelector('.equipment-back')?.getAttribute('href')).toBe('/equipments?company_id=99&site_id=88&page=4&page_size=100&search=Other&status=out_of_service&criticality=low');
    expect(root().querySelector('.site-reference')?.getAttribute('href')).toBe('/sites/9?company_id=7');
  });
  it('sanitizes invalid return context without injecting the real parents as defaults', async () => {
    await loaded('/equipments/12?company_id=-1&site_id=abc&page=0&page_size=101&search=%20%20&status=invalid&criticality=urgent&returnUrl=https://example.com');
    expect(root().querySelector('.equipment-back')?.getAttribute('href')).toBe('/equipments?page=1&page_size=20');
    expect(root().querySelector('.context-notice')).toBeNull();
  });
  it('returns to the actual list preserving all seven applied filters', async () => {
    await loaded('/equipments/12?company_id=7&site_id=9&status=maintenance&criticality=critical&search=Pompe&page=2&page_size=50');
    root().querySelector<HTMLAnchorElement>('.equipment-back')!.click(); await settle();
    http.expectOne(req => req.url === '/api/v1/companies').flush({ items: [company], total: 1, page: 1, page_size: 50, pages: 1 });
    http.expectOne(req => req.url === '/api/v1/sites').flush({ items: [site], total: 1, page: 1, page_size: 50, pages: 1 });
    companyRead().flush(company); siteRead().flush(site);
    const req = http.expectOne(req => req.url === '/api/v1/equipments');
    expect(Object.fromEntries(req.request.params.keys().map(key => [key, req.request.params.get(key)]))).toEqual({
      site_id: '9', page: '2', page_size: '50', search: 'Pompe', status: 'maintenance', criticality: 'critical'
    });
    req.flush({ items: [equipment], total: 51, page: 2, page_size: 50, pages: 2 }); await settle();
    expect(root().querySelector('app-feature-placeholder')).toBeNull();
    expect(root().querySelector('tbody a')?.textContent).toBe(equipment.name);
    expect(TestBed.inject(Router).url).toBe('/equipments?company_id=7&site_id=9&page=2&page_size=50&search=Pompe&status=maintenance&criticality=critical');
  });
  it.each(['equipment', 'site', 'company'])('rejects a mismatched returned %s identity', async stage => {
    await open(); read().flush(stage === 'equipment' ? { ...equipment, id: 13 } : equipment);
    if (stage !== 'equipment') siteRead().flush(stage === 'site' ? { ...site, id: 10 } : site);
    if (stage === 'company') companyRead().flush({ ...company, id: 8 });
    await settle(); expect(root().textContent).toContain('ne correspond pas');
    expect(component.state().status).toBe(stage === 'equipment' ? 'error' : 'success'); http.expectNone(() => true);
  });
  it('keeps equipment data when its site identifier is invalid without a parent request', async () => {
    await open(); read().flush({ ...equipment, site_id: 0 }); await settle();
    expect(root().textContent).toContain(equipment.name); expect(root().textContent).toContain('référence du site'); http.expectNone(() => true);
  });
  it('keeps the real site when its company identifier is invalid without a company request', async () => {
    await open(); read().flush(equipment); siteRead().flush({ ...site, company_id: 0 }); await settle();
    expect(root().querySelector('.site-reference')?.getAttribute('href')).toBe('/sites/9'); expect(root().textContent).toContain('référence entreprise'); http.expectNone(() => true);
  });
  it('deduplicates identical business names and codes in parent labels', async () => {
    await open(); read().flush(equipment); siteRead().flush({ ...site, name: 'USINE' }); companyRead().flush({ ...company, name: 'ENT' }); await settle();
    expect(root().querySelector('.site-reference')?.textContent).toBe('USINE'); expect(root().querySelector('.company-reference')?.textContent).toBe('ENT');
  });
  it('keeps the visible title and keyboard actions without an inherited native title or tooltip component', async () => {
    await loaded(); const header = root().querySelector('app-page-header')!;
    expect(header.getAttribute('title')).toBeNull(); expect(header.querySelector('h1')?.textContent).toBe('Détail équipement');
    const actions = [...header.querySelectorAll<HTMLAnchorElement>('a')]; expect(actions).toHaveLength(5);
    for (const action of actions) {
      expect(action.closest('[title]')).toBeNull(); expect(action.hasAttribute('nbTooltip')).toBe(false);
      expect(action.getAttribute('href')).toBeTruthy(); action.focus(); expect(document.activeElement).toBe(action);
    }
    expect(root().querySelector('nb-tooltip,[role="tooltip"]')).toBeNull();
  });

});
