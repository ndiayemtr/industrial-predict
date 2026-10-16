import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { Page } from '../../../../core/models/page.model';
import { CompanyRead, EquipmentRead, SiteRead } from '../../../../core/models/reference-data.model';
import { DashboardFiltersComponent } from './dashboard-filters.component';

const NOW = Date.parse('2026-10-14T12:34:56.789Z');
const company = (id: number): CompanyRead => ({ id, name: `Test company ${id}`, code: `C-${id}`,
  description: null, created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00' });
const site = (id: number, companyId = 1): SiteRead => ({ ...company(id), company_id: companyId });
const equipment = (id: number, siteId = 10): EquipmentRead => ({ ...company(id), site_id: siteId,
  equipment_type: 'pump', status: 'operational', criticality: 'medium' });
const page = <T>(items: T[], total = items.length, current = 1, pages = total ? 1 : 0): Page<T> =>
  ({ items, total, page: current, page_size: 50, pages });

describe('DashboardFiltersComponent', () => {
  let fixture: ComponentFixture<DashboardFiltersComponent>;
  let component: DashboardFiltersComponent;
  let http: HttpTestingController;
  beforeEach(async () => {
    vi.spyOn(Date, 'now').mockReturnValue(NOW);
    await TestBed.configureTestingModule({ imports: [DashboardFiltersComponent],
      providers: [provideHttpClient(), provideHttpClientTesting()] }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(DashboardFiltersComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });
  afterEach(() => { http.verify(); vi.restoreAllMocks(); });

  function companiesReady(): void {
    http.expectOne(req => req.url === '/api/v1/companies').flush(page([company(1), company(2)]));
    fixture.detectChanges();
  }
  function selectCompany(id = 1): void {
    component.form.controls.company_id.setValue(id);
    http.expectOne(req => req.url === '/api/v1/sites' && req.params.get('company_id') === String(id))
      .flush(page([site(10, id), site(11, id)]));
    fixture.detectChanges();
  }
  function selectSite(id = 10): void {
    component.form.controls.site_id.setValue(id);
    http.expectOne(req => req.url === '/api/v1/equipments' && req.params.get('site_id') === String(id))
      .flush(page([equipment(20, id), equipment(21, id)]));
    fixture.detectChanges();
  }

  function precision(checked: boolean): void {
    const checkbox = fixture.nativeElement.querySelector('#dashboard-precision') as HTMLInputElement;
    checkbox.checked = checked;
    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
    fixture.detectChanges();
  }

  it('loads only companies initially, without a default selection, output or Dashboard call', () => {
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted);
    expect(component.form.controls.company_id.value).toBeNull();
    expect(component.form.controls.site_id.disabled).toBe(true);
    expect(component.form.controls.equipment_id.disabled).toBe(true);
    expect(component.canApply()).toBe(false);
    expect(fixture.nativeElement.querySelector('[role="status"]')).not.toBeNull();
    companiesReady();
    http.expectNone(req => req.url.includes('/dashboard') || req.url.includes('/sites') || req.url.includes('/equipments'));
    expect(emitted).not.toHaveBeenCalled();
  });

  it('initializes precisely seven UTC days and finalizes the untouched preset at application', () => {
    expect(component.form.controls.start_time.value).toBe('2026-10-07T12:34');
    expect(component.form.controls.end_time.value).toBe('2026-10-14T12:34');
    expect(component.advancedPrecision()).toBe(false);
    for (const input of fixture.nativeElement.querySelectorAll('input[type="datetime-local"]') as NodeListOf<HTMLInputElement>) {
      expect(input.step).toBe('60');
      expect(input.value).toHaveLength(16);
    }
    expect(fixture.nativeElement.querySelector('.datetime-preview')).toBeNull();
    companiesReady(); selectCompany();
    vi.mocked(Date.now).mockReturnValue(NOW + 10_000);
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted);
    component.applyFilters();
    expect(emitted).toHaveBeenCalledExactlyOnceWith({ company_id: 1,
      start_time: '2026-10-07T12:35:00.000Z', end_time: '2026-10-14T12:35:00.000Z' });
    expect(Date.parse(emitted.mock.calls[0][0].end_time) - Date.parse(emitted.mock.calls[0][0].start_time)).toBe(168 * 60 * 60 * 1000);
    http.expectNone(req => req.url.includes('/dashboard'));
  });

  it('emits only on a valid submit and omits optional selections', () => {
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted);
    component.applyFilters(); expect(emitted).not.toHaveBeenCalled();
    companiesReady(); selectCompany();
    expect(emitted).not.toHaveBeenCalled();
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    expect(emitted).toHaveBeenCalledTimes(1);
    expect(emitted.mock.calls[0][0]).toEqual({ company_id: 1,
      start_time: '2026-10-07T12:34:00.000Z', end_time: '2026-10-14T12:34:00.000Z' });
    http.expectNone(req => req.url.includes('/dashboard'));
  });

  it('includes valid site/equipment, clears descendants on changes and supports all sites/equipments', () => {
    companiesReady(); selectCompany(); selectSite();
    component.form.controls.equipment_id.setValue(20);
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted);
    component.applyFilters(); expect(emitted.mock.calls[0][0]).toMatchObject({ company_id: 1, site_id: 10, equipment_id: 20 });
    selectSite(11); expect(component.form.controls.equipment_id.value).toBeNull();
    component.form.controls.site_id.setValue(null);
    expect(component.form.controls.equipment_id.disabled).toBe(true);
    component.applyFilters(); expect(emitted.mock.calls[1][0].site_id).toBeUndefined();
    selectSite(); component.form.controls.equipment_id.setValue(20);
    component.form.controls.company_id.setValue(2);
    expect(component.form.controls.site_id.value).toBeNull();
    expect(component.form.controls.equipment_id.value).toBeNull();
    expect(component.canApply()).toBe(false);
    http.expectOne(req => req.url === '/api/v1/sites').flush(page([site(12, 2)]));
  });

  it.each(['companies', 'sites', 'equipments'] as const)('keeps %s pagination metadata and loads later options', kind => {
    if (kind !== 'companies') companiesReady();
    if (kind === 'equipments') selectCompany();
    if (kind === 'sites') component.form.controls.company_id.setValue(1);
    if (kind === 'equipments') component.form.controls.site_id.setValue(10);
    const firstItems = Array.from({ length: 50 }, (_, index) => kind === 'companies' ? company(index + 1)
      : kind === 'sites' ? site(index + 1) : equipment(index + 1));
    http.expectOne(req => req.url === `/api/v1/${kind}`).flush(page(firstItems, 51, 1, 2));
    fixture.detectChanges();
    const state = component[kind];
    expect(state().items).toHaveLength(50);
    expect(state().total).toBe(51); expect(state().pages).toBe(2);
    const loader = kind === 'companies' ? () => component.loadCompanies(2)
      : kind === 'sites' ? () => component.loadSites(2) : () => component.loadEquipments(2);
    loader();
    const req = http.expectOne(request => request.url === `/api/v1/${kind}`);
    expect(req.request.params.get('page')).toBe('2'); expect(req.request.params.get('page_size')).toBe('50');
    req.flush(page([kind === 'companies' ? company(51) : kind === 'sites' ? site(51) : equipment(51)], 51, 2, 2));
    fixture.detectChanges();
    expect(state().items).toHaveLength(51); expect(state().page).toBe(2);
  });

  it('cancels obsolete company/site requests and ignores their results', () => {
    companiesReady();
    component.form.controls.company_id.setValue(1);
    const oldSites = http.expectOne(req => req.url === '/api/v1/sites');
    component.form.controls.company_id.setValue(2);
    expect(oldSites.cancelled).toBe(true);
    http.expectOne(req => req.url === '/api/v1/sites').flush(page([site(11, 2), site(12, 2)]));
    component.form.controls.site_id.setValue(11);
    const oldEquipment = http.expectOne(req => req.url === '/api/v1/equipments');
    component.form.controls.site_id.setValue(12);
    expect(oldEquipment.cancelled).toBe(true);
    http.expectOne(req => req.url === '/api/v1/equipments').flush(page([equipment(22, 12)]));
    expect(component.sites().items.map(item => item.id)).toEqual([11, 12]);
    expect(component.equipments().items.map(item => item.id)).toEqual([22]);
  });

  it('preserves loaded options after a later-page failure and retries the failed page without duplicates', () => {
    const first = Array.from({ length: 50 }, (_, index) => company(index + 1));
    http.expectOne(req => req.url === '/api/v1/companies').flush(page(first, 51, 1, 2));
    component.loadCompanies(2);
    http.expectOne(req => req.url === '/api/v1/companies').flush({ detail: 'Unavailable' }, { status: 500, statusText: 'Error' });
    expect(component.companies().items).toHaveLength(50);
    expect(component.companies().page).toBe(1);
    expect(component.companies().requestedPage).toBe(2);
    fixture.detectChanges();
    fixture.nativeElement.querySelector('app-error-state button').click();
    const req = http.expectOne(request => request.url === '/api/v1/companies');
    expect(req.request.params.get('page')).toBe('2');
    req.flush(page([company(50), company(51)], 51, 2, 2));
    expect(component.companies().items).toHaveLength(51);
    expect(component.companies().status).toBe('ready');
  });

  it.each([
    ['not-a-date', '2026-10-14T12:00', 'invalidDate'],
    ['2026-02-30T12:00', '2026-10-14T12:00', 'invalidDate'],
    ['2026-10-14T12:00', '2026-10-14T12:00', 'invalidPeriod'],
    ['2026-10-14T12:00', '2026-10-13T12:00', 'invalidPeriod'],
    ['2026-10-13T12:00', '2026-10-15T12:00', 'futureEnd'],
    ['', '', 'invalidDate']
  ])('rejects dates %s / %s with %s', (start, end, error) => {
    companiesReady(); selectCompany();
    component.form.patchValue({ start_time: start, end_time: end });
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted);
    component.applyFilters();
    expect(component.form.hasError(error)).toBe(true);
    expect(component.canApply()).toBe(false); expect(emitted).not.toHaveBeenCalled();
  });

  it('preserves custom dates, including UTC milliseconds and an exclusive end', () => {
    companiesReady(); selectCompany();
    component.form.patchValue({ start_time: '2026-10-01T08:00', end_time: '2026-10-02T00:00:00.123' });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('#dashboard-end').step).toBe('0.001');
    expect(fixture.nativeElement.querySelector('#dashboard-end').value).toBe('2026-10-02T00:00:00.123');
    expect(component.advancedPrecision()).toBe(true);
    expect(fixture.nativeElement.querySelector('#dashboard-precision').checked).toBe(true);
    expect(fixture.nativeElement.querySelector('#end-help').textContent).toBe('Fin exclue');
    expect(component.form.controls.end_time.value).toBe('2026-10-02T00:00:00.123');
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted);
    component.applyFilters();
    expect(emitted.mock.calls[0][0]).toMatchObject({ start_time: '2026-10-01T08:00:00.000Z', end_time: '2026-10-02T00:00:00.123Z' });
  });

  it('allows lossless mode changes for whole-minute dates and retains the precise preset behavior', () => {
    companiesReady(); selectCompany();
    const original = component.form.getRawValue();
    precision(true);
    expect(component.form.getRawValue()).toEqual(original);
    expect(fixture.nativeElement.querySelector('#dashboard-start').step).toBe('0.001');
    precision(false);
    expect(component.form.getRawValue()).toEqual(original);
    expect(component.precisionConversionPending()).toBe(false);
    precision(true);
    vi.mocked(Date.now).mockReturnValue(NOW + 1000);
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted);
    component.applyFilters();
    expect(emitted).toHaveBeenCalledExactlyOnceWith({ company_id: 1,
      start_time: '2026-10-07T12:34:57.789Z', end_time: '2026-10-14T12:34:57.789Z' });
    expect(Date.parse(emitted.mock.calls[0][0].end_time) - Date.parse(emitted.mock.calls[0][0].start_time)).toBe(168 * 60 * 60 * 1000);
  });

  it.each(['2026-10-02T00:00:01', '2026-10-02T00:00:00.001', '2026-10-02T00:00:59.999'])
    ('automatically selects and retains advanced precision for existing value %s', end => {
      companiesReady();
      component.form.patchValue({ start_time: '2026-10-01T00:00', end_time: end });
      fixture.detectChanges();
      expect(component.advancedPrecision()).toBe(true);
      expect(fixture.nativeElement.querySelector('#dashboard-precision').checked).toBe(true);
      expect(fixture.nativeElement.querySelector('#dashboard-end').step).toBe('0.001');
      expect(component.form.controls.end_time.value).toBe(end);
      component.form.controls.end_time.setValue('2026-10-02T00:00');
      expect(component.advancedPrecision()).toBe(true);
    });

  it('does not request advanced precision for zero seconds/fractions and normalizes them losslessly on mode change', () => {
    companiesReady();
    component.form.patchValue({ start_time: '2026-10-01T08:00:00.000', end_time: '2026-10-02T00:00:00' });
    fixture.detectChanges();
    expect(component.advancedPrecision()).toBe(false);
    precision(true); precision(false);
    expect(component.form.controls.start_time.value).toBe('2026-10-01T08:00');
    expect(component.form.controls.end_time.value).toBe('2026-10-02T00:00');
    expect(component.precisionConversionPending()).toBe(false);
  });

  it('requires explicit conversion, preserves precise dates on cancellation and emits only the confirmed minute bounds', () => {
    companiesReady(); selectCompany();
    const dates = { start_time: '2026-10-01T08:00:12.987', end_time: '2026-10-02T00:00:59.123' };
    component.form.patchValue(dates); fixture.detectChanges();
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted);
    precision(false);
    expect(component.advancedPrecision()).toBe(true);
    expect(fixture.nativeElement.querySelector('#dashboard-precision').checked).toBe(true);
    expect(component.precisionConversionPending()).toBe(true);
    expect(fixture.nativeElement.querySelector('.precision-confirmation [role="status"]').textContent).toContain('Aucune date n’a encore été modifiée');
    expect(component.form.getRawValue()).toMatchObject(dates);
    component.applyFilters(); expect(emitted).not.toHaveBeenCalled();
    component.keepAdvancedPrecision(); fixture.detectChanges();
    expect(component.form.getRawValue()).toMatchObject(dates);
    expect(component.precisionConversionPending()).toBe(false);
    precision(false);
    fixture.nativeElement.querySelector('.precision-confirmation button').click(); fixture.detectChanges();
    expect(component.form.getRawValue()).toMatchObject({ start_time: '2026-10-01T08:00', end_time: '2026-10-02T00:00' });
    expect(component.form.controls.start_time.dirty).toBe(true);
    expect(component.form.controls.end_time.dirty).toBe(true);
    expect(component.advancedPrecision()).toBe(false);
    expect(fixture.nativeElement.querySelector('#precision-notice').textContent).toContain('minute inférieure');
    component.applyFilters();
    expect(emitted).toHaveBeenCalledExactlyOnceWith({ company_id: 1,
      start_time: '2026-10-01T08:00:00.000Z', end_time: '2026-10-02T00:00:00.000Z' });
  });

  it('does not expand the exclusive end if a confirmed conversion collapses the interval', () => {
    companiesReady(); selectCompany();
    component.form.patchValue({ start_time: '2026-10-01T08:00:00.100', end_time: '2026-10-01T08:00:00.200' });
    fixture.detectChanges(); precision(false); component.confirmMinutePrecision(); fixture.detectChanges();
    expect(component.form.hasError('invalidPeriod')).toBe(true);
    expect(component.canApply()).toBe(false);
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted); component.applyFilters();
    expect(emitted).not.toHaveBeenCalled();
  });

  it('keeps invalid precise values intact and prevents their conversion', () => {
    companiesReady();
    const invalid = '2026-02-30T12:00:01.123';
    component.form.patchValue({ start_time: invalid, end_time: '2026-10-01T08:00' });
    fixture.detectChanges(); precision(false);
    expect(fixture.nativeElement.querySelector('.precision-confirmation button').disabled).toBe(true);
    component.confirmMinutePrecision();
    expect(component.form.controls.start_time.value).toBe(invalid);
    expect(component.advancedPrecision()).toBe(true);
    expect(component.form.hasError('invalidDate')).toBe(true);
  });

  it('keeps future/invalid-period validation in advanced mode and exposes a keyboard-operable checkbox', () => {
    companiesReady(); selectCompany();
    const checkbox = fixture.nativeElement.querySelector('#dashboard-precision') as HTMLInputElement;
    checkbox.focus(); expect(document.activeElement).toBe(checkbox);
    expect(checkbox.tabIndex).toBe(0);
    precision(true);
    component.form.patchValue({ start_time: '2026-10-13T12:00:00.001', end_time: '2026-10-15T12:00:00.001' });
    expect(component.form.hasError('futureEnd')).toBe(true);
    component.form.controls.end_time.setValue(component.form.controls.start_time.value);
    expect(component.form.hasError('invalidPeriod')).toBe(true);
    component.form.controls.end_time.setValue('2026-10-12T12:00:00.001');
    expect(component.form.hasError('invalidPeriod')).toBe(true);
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted); component.applyFilters();
    expect(emitted).not.toHaveBeenCalled();
  });

  it.each(['companies', 'sites', 'equipments'] as const)('blocks application on %s errors and allows explicit retry', kind => {
    if (kind !== 'companies') companiesReady();
    if (kind === 'equipments') selectCompany();
    if (kind === 'sites') component.form.controls.company_id.setValue(1);
    if (kind === 'equipments') component.form.controls.site_id.setValue(10);
    http.expectOne(req => req.url === `/api/v1/${kind}`).flush({ detail: 'Unavailable' }, { status: 500, statusText: 'Error' });
    fixture.detectChanges();
    expect(component.canApply()).toBe(false);
    expect(fixture.nativeElement.querySelector('[role="alert"]')).not.toBeNull();
    fixture.nativeElement.querySelector('app-error-state button').click();
    http.expectOne(req => req.url === `/api/v1/${kind}`).flush(page([]));
    expect(component[kind]().status).toBe('ready');
  });

  it('rejects unknown selections and parent mismatches', () => {
    companiesReady(); selectCompany(); selectSite();
    component.form.controls.equipment_id.setValue(999);
    component.applyFilters(); expect(component.canApply()).toBe(false);
    component.form.controls.equipment_id.setValue(20);
    component.equipments.update(state => ({ ...state, items: [equipment(20, 99)] }));
    component.applyFilters(); expect(component.canApply()).toBe(false);
  });

  it('has labelled native fields, UTC help, a submit button and no navigation or KPI markup', () => {
    companiesReady(); fixture.detectChanges();
    const root: HTMLElement = fixture.nativeElement;
    for (const control of root.querySelectorAll('input, select')) {
      expect(root.querySelector(`label[for="${control.id}"]`)?.textContent?.trim()).toBeTruthy();
      expect(control.getAttribute('aria-describedby')).toBeTruthy();
    }
    expect(root.querySelectorAll('input[type="datetime-local"]')).toHaveLength(2);
    expect(root.querySelector('#period-help')?.textContent).toContain('fin exclue');
    expect(root.querySelector('button[type="submit"]')?.textContent).toBe('Appliquer les filtres');
    expect(root.querySelector('h1, nb-layout, router-outlet, a')).toBeNull();
  });

  it('cancels pending reference requests when destroyed', () => {
    const req = http.expectOne(request => request.url === '/api/v1/companies');
    fixture.destroy(); expect(req.cancelled).toBe(true);
  });

  it('provides a focusable native submit action and emits once on activation', () => {
    companiesReady(); selectCompany(); fixture.detectChanges();
    const button = fixture.nativeElement.querySelector('button[type="submit"]') as HTMLButtonElement;
    const emitted = vi.fn(); component.filtersApplied.subscribe(emitted);
    expect(button.disabled).toBe(false); expect(button.tabIndex).toBe(0);
    button.focus(); expect(document.activeElement).toBe(button);
    button.click(); expect(emitted).toHaveBeenCalledTimes(1);
  });
});
