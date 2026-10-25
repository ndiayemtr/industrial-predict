import { Location } from '@angular/common';
import { provideLocationMocks } from '@angular/common/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { NavigationEnd, provideRouter, Router } from '@angular/router';
import { filter, firstValueFrom, take } from 'rxjs';
import { RouterTestingHarness } from '@angular/router/testing';
import { EQUIPMENT_ROUTES } from '../../equipments.routes';
import { PREDICTION_ROUTES } from '../../../predictions/predictions.routes';
import { PredictionsListComponent } from '../../../predictions/pages/predictions-list/predictions-list.component';
import { predictionNavigationParams } from '../../../predictions/utils/prediction-navigation';

// Synthetic in-memory HTTP fixtures, never PostgreSQL DEV records.
const company = { id: 7, name: 'Entreprise fixture', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, name: 'Site fixture', company_id: 7 };
const equipment = { ...company, id: 12, name: 'Pompe fixture', site_id: 9, equipment_type: 'pump', status: 'operational', criticality: 'high' };
const fresh = '/predictions?company_id=7&site_id=9&equipment_id=12&page=1&page_size=20';
const equipmentFilters = '?company_id=99&site_id=88&search=Pompe&status=maintenance&criticality=critical&page=4&page_size=50&returnUrl=https://example.com';
const applied = { company_id: 7, site_id: 9, equipment_id: 12, page: 2, page_size: 1, prediction_type: 'rul' as const,
  level: '  libre  ', is_alert: false, start_time: '2026-10-23T17:30:00.123456+05:30', end_time: '2026-10-23T12:00:00.123456Z' };

describe('Predictions and Equipment bidirectional navigation', () => {
  let http: HttpTestingController, harness: RouterTestingHarness;
  const root = () => harness.routeNativeElement!;
  const read = (path: string) => http.expectOne(req => req.method === 'GET' && req.url === '/api/v1/' + path);
  const catalog = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 50, pages: 1 });
  const router = () => TestBed.inject(Router);
  const detailUrl = (params: Record<string, unknown>) => router().serializeUrl(router().createUrlTree(['/equipments', 12], { queryParams: params }));
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), provideLocationMocks(),
      provideRouter([{ path: 'equipments', children: EQUIPMENT_ROUTES }, { path: 'predictions', children: PREDICTION_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { try { http.expectNone(req => req.method !== 'GET'); http.verify(); } finally { TestBed.resetTestingModule(); } });
  async function settle() {
    harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges();
    expect(root().querySelectorAll('.equipment-predictions,.predictions-return').length).toBeLessThanOrEqual(1);
  }
  async function open(url: string) { harness = await RouterTestingHarness.create(url); await settle(); }
  function parents() { read('equipments/12').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company); }
  async function loadedEquipment(url = '/equipments/12') { await open(url); parents(); await settle(); }
  async function finishList() {
    read('companies').flush(catalog([company]));
    http.expectNone(req => req.url.endsWith('/predictions'));
    read('equipments/12').flush(equipment); http.expectNone(req => req.url.endsWith('/predictions'));
    read('sites/9').flush(site); http.expectNone(req => req.url.endsWith('/predictions'));
    read('companies/7').flush(company); await settle();
    read('sites').flush(catalog([site])); read('equipments').flush(catalog([equipment]));
    const history = read('equipments/12/predictions');
    history.flush({ items: [], total: 0, page: Number(history.request.params.get('page')), page_size: Number(history.request.params.get('page_size')), pages: 0 });
    await settle(); return history.request;
  }
  it('waits for every real parent and emits fresh scope without Equipment filters', async () => {
    await open('/equipments/12' + equipmentFilters); expect(root().querySelector('.equipment-predictions')).toBeNull();
    read('equipments/12').flush(equipment); await settle(); expect(root().querySelector('.equipment-predictions')).toBeNull();
    read('sites/9').flush(site); await settle(); expect(root().querySelector('.equipment-predictions')).toBeNull();
    read('companies/7').flush(company); await settle();
    const action = root().querySelector<HTMLAnchorElement>('.equipment-predictions')!;
    expect(action.textContent).toBe('Voir les prédictions'); expect(action.getAttribute('href')).toBe(fresh);
    expect(action.hasAttribute('title')).toBe(false); action.focus(); expect(document.activeElement).toBe(action);
    action.click(); await settle(); expect(router().url).toBe(fresh);
    const request = await finishList(); expect(request.params.keys().sort()).toEqual(['page', 'page_size']);
    expect(root().textContent).toContain('Aucune prédiction enregistrée');
  });
  it.each(['site', 'company'] as const)('hides the fresh action when %s is inconsistent', async scope => {
    await open('/equipments/12'); read('equipments/12').flush(equipment);
    if (scope === 'site') read('sites/9').flush({ ...site, id: 88 });
    else { read('sites/9').flush(site); read('companies/7').flush({ ...company, id: 99 }); }
    await settle(); expect(root().querySelector('.equipment-predictions')).toBeNull(); http.expectNone(() => true);
  });
  it.each([403, 404, 500])('hides the fresh action on parent HTTP %s', async status => {
    await open('/equipments/12'); read('equipments/12').flush(equipment); read('sites/9').flush(site);
    read('companies/7').flush({}, { status, statusText: 'Unavailable' }); await settle();
    expect(root().querySelector('.equipment-predictions')).toBeNull(); http.expectNone(() => true);
  });
  it('preserves applied filters on the round trip and never exports an unsubmitted draft', async () => {
    const original = router().serializeUrl(router().createUrlTree(['/predictions'], { queryParams: applied }));
    await open(original); await finishList();
    const component = harness.routeDebugElement!.componentInstance as PredictionsListComponent;
    component.level.setValue('draft'); await settle();
    const inverse = root().querySelector<HTMLAnchorElement>('.predictions-equipment')!;
    const destination = router().parseUrl(inverse.getAttribute('href')!);
    expect(destination.queryParams).toMatchObject({ from: 'predictions', pre_level: '  libre  ', pre_is_alert: 'false', pre_page: '2', pre_page_size: '1', pre_start_time: applied.start_time, pre_end_time: applied.end_time });
    expect(destination.queryParams['level']).toBeUndefined(); expect(destination.queryParams['returnUrl']).toBeUndefined();
    inverse.click(); await settle(); parents(); await settle();
    expect(root().querySelector('.equipment-predictions')).toBeNull();
    expect(root().querySelectorAll('app-page-header a')).toHaveLength(5);
    expect(root().querySelector('.equipment-back')?.getAttribute('href')).toBe('/equipments?page=1&page_size=20');
    for (const selector of ['.equipment-sensors', '.equipment-maintenance', '.equipment-edit']) {
      const link = root().querySelector(selector)!.getAttribute('href')!; expect(link).not.toContain('pre_'); expect(link).not.toContain('from=');
    }
    root().querySelector<HTMLAnchorElement>('.predictions-return')!.click(); await settle();
    expect(router().parseUrl(router().url).queryParams).toEqual(router().parseUrl(original).queryParams);
    const request = await finishList(); expect(request.params.get('start_time')).toBe(applied.start_time); expect(request.params.get('is_alert')).toBe('false');
    expect(root().querySelector<HTMLInputElement>('#predictions-level')!.value).toBe('  libre  ');
    expect(root().textContent).not.toContain('Brouillon de filtres');
  });
  it.each([
    { pre_page: 0 }, { pre_equipment_id: 13 }, { pre_site_id: ['9', '9'] }, { from: ['predictions', 'predictions'] }, { pre_start_time: 'invalid' }
  ])('offers only fresh verified scope for invalid return context %j', async patch => {
    await loadedEquipment(detailUrl({ ...predictionNavigationParams(applied), ...patch, returnUrl: '//example.com' }));
    expect(root().querySelector('.predictions-return')).toBeNull();
    expect(root().querySelector('.equipment-predictions')?.getAttribute('href')).toBe(fresh);
    root().querySelector<HTMLAnchorElement>('.equipment-predictions')!.click(); await settle();
    expect(router().url).toBe(fresh); const request = await finishList();
    expect(request.params.keys().sort()).toEqual(['page', 'page_size']); http.expectNone(() => true);
  });
  it('keeps direct links without origin free of Predictions return context', async () => {
    await loadedEquipment('/equipments/12?returnUrl=https://example.com&pre_page=2');
    expect(root().querySelector('.predictions-return')).toBeNull(); expect(root().querySelector('.equipment-predictions')?.getAttribute('href')).toBe(fresh);
  });
  it('restores a valid return URL on direct Equipment load and on query-only changes', async () => {
    await loadedEquipment(detailUrl(predictionNavigationParams(applied)));
    expect(router().parseUrl(root().querySelector('.predictions-return')!.getAttribute('href')!).queryParams).toEqual(router().parseUrl(router().serializeUrl(router().createUrlTree(['/predictions'], { queryParams: applied }))).queryParams);
    await harness.navigateByUrl(detailUrl({ ...predictionNavigationParams(applied), pre_is_alert: true })); await settle();
    expect(root().querySelector('.predictions-return')!.getAttribute('href')).toContain('is_alert=true'); http.expectNone(() => true);
  });
  it('keeps a validated return available while Equipment is unresolved or fails, without fresh scope', async () => {
    await open(detailUrl(predictionNavigationParams(applied)));
    const action = root().querySelector<HTMLAnchorElement>('.predictions-return')!;
    expect(action.getAttribute('href')).toContain('page=2&page_size=1');
    expect(root().querySelector('.equipment-predictions')).toBeNull();
    action.focus(); expect(document.activeElement).toBe(action);
    read('equipments/12').flush({}, { status: 404, statusText: 'Missing' }); await settle();
    expect(root().querySelector('.predictions-return')).not.toBeNull();
    expect(root().querySelector('.equipment-predictions')).toBeNull(); http.expectNone(() => true);
  });
  it.each([{}, { ...predictionNavigationParams(applied), pre_page: '0' }])('has neither action without valid context until Equipment and its parents resolve: %j', async params => {
    await open(detailUrl(params));
    expect(root().querySelector('.predictions-return,.equipment-predictions')).toBeNull();
    read('equipments/12').flush(equipment); await settle();
    expect(root().querySelector('.predictions-return,.equipment-predictions')).toBeNull();
    read('sites/9').flush(site); await settle();
    expect(root().querySelector('.predictions-return,.equipment-predictions')).toBeNull();
    read('companies/7').flush(company); await settle();
    expect(root().querySelector('.predictions-return')).toBeNull();
    expect(root().querySelector('.equipment-predictions')?.getAttribute('href')).toBe(fresh);
  });
  it('switches the sole action on query-only context changes while keeping all other actions', async () => {
    await loadedEquipment();
    const labels = () => [...root().querySelectorAll('app-page-header a')].map(element => element.textContent);
    expect(labels()).toEqual(['Retour à la liste des équipements', 'Voir les capteurs', 'Voir les interventions', 'Voir les prédictions', 'Modifier']);
    await harness.navigateByUrl(detailUrl(predictionNavigationParams(applied))); await settle();
    expect(labels()).toEqual(['Retour à la liste des équipements', 'Voir les capteurs', 'Voir les interventions', 'Retour aux prédictions', 'Modifier']);
    const action = root().querySelector<HTMLAnchorElement>('.predictions-return')!;
    expect(action.hasAttribute('title')).toBe(false); action.focus(); expect(document.activeElement).toBe(action);
    await harness.navigateByUrl(detailUrl({ ...predictionNavigationParams(applied), pre_page_size: '101' })); await settle();
    expect(labels()).toEqual(['Retour à la liste des équipements', 'Voir les capteurs', 'Voir les interventions', 'Voir les prédictions', 'Modifier']);
    http.expectNone(() => true);
  });
  it('revalidates parent changes instead of reading history for stale return scope', async () => {
    await loadedEquipment(detailUrl(predictionNavigationParams(applied)));
    root().querySelector<HTMLAnchorElement>('.predictions-return')!.click(); await settle();
    read('companies').flush(catalog([company])); read('equipments/12').flush({ ...equipment, site_id: 88 }); await settle();
    expect(root().querySelector('.predictions-equipment')).toBeNull(); expect(root().textContent).toContain('ne correspond pas au site');
    http.expectNone(req => req.url.endsWith('/predictions')); http.expectNone(req => req.url.endsWith('/sites/88'));
  });
  it('restores the applied context using browser history back/forward with fresh reference validation', async () => {
    await open(fresh); await finishList();
    root().querySelector<HTMLAnchorElement>('.predictions-equipment')!.click(); await settle(); parents(); await settle();
    // Harness.navigateByUrl does not perform application initialNavigation.
    router().setUpLocationChangeListener();
    const back = firstValueFrom(router().events.pipe(filter(event => event instanceof NavigationEnd), take(1)));
    TestBed.inject(Location).back(); await back; await settle(); expect(router().url).toBe(fresh); await finishList();
    const forward = firstValueFrom(router().events.pipe(filter(event => event instanceof NavigationEnd), take(1)));
    TestBed.inject(Location).forward(); await forward; await settle(); expect(router().url).toContain('/equipments/12?from=predictions'); parents(); await settle();
    expect(root().querySelector('.predictions-return')?.getAttribute('href')).toBe(fresh);
    expect(root().querySelector('.equipment-predictions')).toBeNull();
  });
});
