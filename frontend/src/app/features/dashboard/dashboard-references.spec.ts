import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { DashboardReferenceCatalog, DashboardReferences } from './dashboard-references';

const company = { id: 7, name: 'PETROSEN', code: 'PETROSEN', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, name: 'Usine', code: 'SITE-9', company_id: 7 };
const equipment = { ...company, id: 12, name: 'Pompe', code: 'P12', site_id: 9,
  equipment_type: 'pump', status: 'operational' as const, criticality: 'high' as const };
const filters = { company_id: 7, site_id: 9, equipment_id: 12, start_time: '2026-10-01T00:00:00.123Z', end_time: '2026-10-02T00:00:00.124Z' };
const catalog = () => ({ companies: [{ ...company }], sites: [{ ...site }], equipments: [{ ...equipment }] });
const absent: DashboardReferenceCatalog = { companies: [], sites: [], equipments: [] };

describe('Applied Dashboard reference snapshot', () => {
  let references: DashboardReferences;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [DashboardReferences, provideHttpClient(), provideHttpClientTesting()] });
    references = TestBed.inject(DashboardReferences); http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.expectNone(req => req.method !== 'GET'); http.verify(); });

  it('copies all loaded business labels without requesting any detail or rewriting filters', () => {
    const loaded = catalog(); const before = { ...filters };
    references.capture(filters, loaded);
    expect(references.label('company', 7)).toBe('PETROSEN');
    expect(references.label('site', 9)).toBe('Usine - SITE-9');
    expect(references.label('equipment', 12)).toBe('Pompe - P12');
    loaded.companies[0].name = 'Draft'; loaded.sites.length = 0; loaded.equipments[0].code = 'Draft';
    expect(references.label('company', 7)).toBe('PETROSEN');
    expect(references.label('equipment', 12)).toBe('Pompe - P12');
    expect(filters).toEqual(before); http.expectNone(() => true);
  });

  it('shows all sites/equipments for optional unselected scopes without requests', () => {
    references.capture({ ...filters, site_id: null, equipment_id: undefined }, catalog());
    expect(references.label('site', null)).toBe('Tous les sites');
    expect(references.label('equipment', null)).toBe('Tous les équipements');
    http.expectNone(() => true);
  });

  it('resolves selections outside loaded pages with exactly one GET per missing reference', () => {
    references.capture(filters, absent);
    expect(references.label('company', 7)).toBe('Chargement de la référence...');
    http.expectOne('/api/v1/companies/7').flush(company);
    http.expectOne('/api/v1/sites/9').flush(site);
    http.expectOne('/api/v1/equipments/12').flush(equipment);
    expect(references.label('company', 7)).toBe('PETROSEN');
    expect(references.label('site', 9)).toBe('Usine - SITE-9');
    expect(references.label('equipment', 12)).toBe('Pompe - P12');
    http.expectNone(() => true);
  });

  it('requests only the missing reference and keeps already known labels visible', () => {
    references.capture(filters, { ...catalog(), sites: [] });
    expect(references.label('company', 7)).toBe('PETROSEN');
    expect(references.label('equipment', 12)).toBe('Pompe - P12');
    http.expectOne('/api/v1/sites/9').flush(site); http.expectNone(() => true);
  });

  it.each([0, 404, 500])('renders unavailable references for HTTP %s without numeric fallback or retry', status => {
    references.capture(filters, absent);
    for (const url of ['/api/v1/companies/7', '/api/v1/sites/9', '/api/v1/equipments/12']) {
      const request = http.expectOne(url);
      if (status === 0) request.error(new ProgressEvent('error'));
      else request.flush(null, { status, statusText: 'Error' });
    }
    expect(references.label('company', 7)).toBe('Référence indisponible');
    expect(references.label('site', 9)).toBe('Référence indisponible');
    expect(references.label('equipment', 12)).toBe('Référence indisponible');
    http.expectNone(() => true);
  });

  it('rejects wrong identifiers and parent relationships returned by detail endpoints', () => {
    references.capture(filters, absent);
    http.expectOne('/api/v1/companies/7').flush({ ...company, id: 8 });
    http.expectOne('/api/v1/sites/9').flush({ ...site, company_id: 8 });
    http.expectOne('/api/v1/equipments/12').flush({ ...equipment, site_id: 10 });
    for (const [kind, id] of [['company', 7], ['site', 9], ['equipment', 12]] as const) {
      expect(references.label(kind, id)).toBe('Référence indisponible');
    }
    expect(references.label('site', 10)).toBe('Référence indisponible');
  });

  it('does not reuse loaded children belonging to another parent', () => {
    references.capture(filters, { ...catalog(), sites: [{ ...site, company_id: 99 }], equipments: [{ ...equipment, site_id: 99 }] });
    http.expectOne('/api/v1/sites/9').flush(site); http.expectOne('/api/v1/equipments/12').flush(equipment);
    expect(references.label('site', 9)).toBe('Usine - SITE-9'); http.expectNone(() => true);
  });

  it('cancels obsolete resolutions even when the next selection is entirely loaded', () => {
    references.capture(filters, absent);
    const old = http.match(() => true); expect(old).toHaveLength(3);
    references.capture({ ...filters, company_id: 8, site_id: null, equipment_id: null },
      { ...absent, companies: [{ ...company, id: 8, name: 'Nouvelle entreprise', code: 'C8' }] });
    expect(old.every(req => req.cancelled)).toBe(true);
    expect(references.label('company', 8)).toBe('Nouvelle entreprise - C8');
    expect(references.label('company', 7)).toBe('Référence indisponible'); http.expectNone(() => true);
  });

  it('cancels pending reference requests on destruction', () => {
    references.capture(filters, absent); const pending = http.match(() => true);
    TestBed.resetTestingModule(); expect(pending.every(req => req.cancelled)).toBe(true);
  });

  it('reuses all loaded equipment pages and snapshots labels across draft catalog mutations', () => {
    const loaded = catalog(); loaded.equipments.push({ ...equipment, id: 13, name: 'Seconde page', code: 'E13' });
    references.capture(filters, loaded);
    loaded.equipments[1].name = 'Draft';
    references.loadReadings(filters, [12, 13, 13]);
    expect(references.equipmentLabels()).toEqual({ 12: 'Pompe - P12', 13: 'Seconde page - E13' });
    http.expectNone(() => true);
  });

  it('shares a pending selected-equipment GET with repeated readings and later refreshes', () => {
    references.capture(filters, { ...catalog(), equipments: [] });
    const selected = http.expectOne('/api/v1/equipments/12');
    references.loadReadings(filters, [12, 12, 12]); http.expectNone(() => true);
    selected.flush(equipment);
    references.loadReadings(filters, [12]); http.expectNone(() => true);
    expect(references.equipmentLabels()[12]).toBe('Pompe - P12');
  });

  it.each([0, 404, 500])('caches reading-reference failure %s without retrying each reading or refresh', status => {
    references.capture(filters, catalog());
    references.loadReadings(filters, [13, 13]);
    const req = http.expectOne('/api/v1/equipments/13');
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush(null, { status, statusText: 'Error' });
    expect(references.equipmentLabels()[13]).toBe('Référence indisponible');
    references.loadReadings(filters, [13, 13]); http.expectNone(() => true);
  });

  it('limits targeted missing-equipment reads to four simultaneous requests without loading the catalog', () => {
    references.capture(filters, catalog()); references.loadReadings(filters, [13, 14, 15, 16, 17, 18, 13]);
    const first = http.match(req => req.url.startsWith('/api/v1/equipments/'));
    expect(first).toHaveLength(4); http.expectNone(() => true);
    first[0].flush({ ...equipment, id: 13 });
    const fifth = http.expectOne('/api/v1/equipments/17');
    first[1].flush({ ...equipment, id: 14 });
    const sixth = http.expectOne('/api/v1/equipments/18');
    first[2].flush({ ...equipment, id: 15 }); first[3].flush({ ...equipment, id: 16 });
    fifth.flush({ ...equipment, id: 17 }); sixth.flush({ ...equipment, id: 18 });
    http.expectNone(() => true);
  });

  it('cancels old reading references and ignores readings from an obsolete applied snapshot', () => {
    references.capture(filters, catalog()); references.loadReadings(filters, [13]);
    const old = http.expectOne('/api/v1/equipments/13');
    references.capture({ ...filters, equipment_id: null }, catalog());
    expect(old.cancelled).toBe(true); expect(references.equipmentLabels()[13]).toBeUndefined();
    references.loadReadings(filters, [13]); http.expectNone(() => true);
  });

  it('rejects wrong equipment IDs or site relationships in reading references', () => {
    references.capture(filters, catalog()); references.loadReadings(filters, [13, 14]);
    http.expectOne('/api/v1/equipments/13').flush({ ...equipment, id: 999 });
    http.expectOne('/api/v1/equipments/14').flush({ ...equipment, id: 14, site_id: 999 });
    expect(references.equipmentLabels()[13]).toBe('Référence indisponible');
    expect(references.equipmentLabels()[14]).toBe('Référence indisponible');
  });
});
