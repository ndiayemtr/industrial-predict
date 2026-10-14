import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { DashboardFiltersComponent } from '../../components/dashboard-filters/dashboard-filters.component';
import { emptyDashboardResponse } from '../../testing/dashboard-testing';
import { DashboardComponent } from './dashboard.component';

const filters = { company_id: 7, start_time: '2026-10-01T00:00:00Z', end_time: '2026-10-08T00:00:00Z' };
describe('DashboardComponent', () => {
  let fixture: ComponentFixture<DashboardComponent>;
  let http: HttpTestingController;
  let form: DashboardFiltersComponent;
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [DashboardComponent], providers: [provideHttpClient(), provideHttpClientTesting()] }).compileComponents();
    http = TestBed.inject(HttpTestingController); fixture = TestBed.createComponent(DashboardComponent); fixture.detectChanges();
    form = fixture.debugElement.query(By.directive(DashboardFiltersComponent)).componentInstance;
    http.expectOne(req => req.url === '/api/v1/companies').flush({ items: [{ id: 7, name: 'Test company', code: 'TEST', description: null,
      created_at: '2026-01-01T00:00:00', updated_at: '2026-01-01T00:00:00' }], total: 1, page: 1, page_size: 50, pages: 1 });
    fixture.detectChanges();
  });
  afterEach(() => http.verify());
  const request = () => http.expectOne(req => req.url === '/api/v1/dashboard');
  function apply() { form.filtersApplied.emit(filters); fixture.detectChanges(); }

  it('shows one h1 and the initial invitation without a Dashboard request', () => {
    expect(fixture.nativeElement.querySelectorAll('h1')).toHaveLength(1);
    expect(fixture.nativeElement.textContent).toContain('Sélectionnez une entreprise');
    expect(fixture.nativeElement.querySelector('.refresh-button').getAttribute('aria-disabled')).toBe('true');
    http.expectNone(req => req.url === '/api/v1/dashboard');
  });
  it('keeps the same visible filters and focus through loading and success', () => {
    const field = fixture.nativeElement.querySelector('#dashboard-start') as HTMLInputElement;
    field.focus(); apply(); const req = request();
    expect(fixture.nativeElement.querySelector('.results').getAttribute('aria-busy')).toBe('true');
    expect(fixture.nativeElement.querySelector('.results [role="status"]')).not.toBeNull();
    expect(document.activeElement).toBe(field);
    const response = emptyDashboardResponse(); response.assets.sites = 1; req.flush(response); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.results').getAttribute('aria-busy')).toBe('false');
    expect(fixture.nativeElement.querySelector('.results-ready')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.result-metadata').textContent).toContain(response.period.calculated_at);
    expect(fixture.debugElement.query(By.directive(DashboardFiltersComponent)).componentInstance).toBe(form);
    expect(document.activeElement).toBe(field);
  });
  it('shows empty only for an asset-free response and retains scope/period metadata', () => {
    apply(); request().flush(emptyDashboardResponse()); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-empty-state')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.result-metadata').textContent).toContain('Tous les sites');
    expect(fixture.nativeElement.querySelector('app-equipment-summary, app-sensor-summary, .kpi-grid')).toBeNull();
  });
  it('renders the six actual KPI fields and summaries only on success, without another request', () => {
    expect(fixture.nativeElement.querySelector('.kpi-grid')).toBeNull();
    apply(); const req = request();
    expect(fixture.nativeElement.querySelector('.kpi-grid')).toBeNull();
    const response = emptyDashboardResponse();
    response.assets.equipments = 19; response.sensor_status.active = 13;
    response.sensor_coverage.coverage.percentage = 73.25;
    response.measurements.activity.measurements_total = 0;
    response.maintenance.open.total = 6; response.maintenance.overdue.overdue = 2;
    req.flush(response); fixture.detectChanges();
    const cards = fixture.nativeElement.querySelectorAll('.kpi-grid app-dashboard-kpi-card');
    expect(cards).toHaveLength(6);
    expect([...cards].map((el: Element) => el.querySelector('.kpi-value')!.textContent!.trim())).toEqual(['19', '13', '73,25 %', '0', '6', '2']);
    expect([...cards].map((el: Element) => el.querySelector('.temporal-scope')!.textContent)).toEqual(['État actuel', 'État actuel', 'État actuel', 'Sur la période', 'État actuel', 'Au calcul']);
    expect(fixture.nativeElement.querySelector('app-equipment-summary')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('app-sensor-summary')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('app-measurement-summary')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('app-maintenance-summary')).not.toBeNull();
    expect(fixture.nativeElement.querySelectorAll('h1')).toHaveLength(1);
    http.expectNone(() => true);
    apply(); const next = request();
    expect(fixture.nativeElement.querySelector('.kpi-grid')).toBeNull();
    next.flush({}, { status: 500, statusText: 'Error' }); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-equipment-summary, app-sensor-summary, app-measurement-summary, app-maintenance-summary, .kpi-grid')).toBeNull();
  });
  it('keeps measurements and maintenance absent in idle/loading/empty and reuses the exact success response', () => {
    const sections = () => fixture.nativeElement.querySelector('app-measurement-summary, app-maintenance-summary');
    expect(sections()).toBeNull(); apply(); expect(sections()).toBeNull();
    request().flush(emptyDashboardResponse()); fixture.detectChanges(); expect(sections()).toBeNull();
    const response = emptyDashboardResponse(); response.assets.sensors = 1;
    response.measurements.last_measurements = [{ sensor_id: 1, sensor_name: 'Relevé API', sensor_code: 'REAL-1', equipment_id: 42,
      timestamp: '2026-09-01T00:00:00Z', value: 0, unit: null, quality: null, age_seconds: 123 }];
    response.maintenance.completed.completed_without_completed_at = 9;
    apply(); request().flush(response); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-measurement-summary').textContent).toContain('2026-09-01T00:00:00Z');
    expect(fixture.nativeElement.querySelector('app-maintenance-summary').textContent).toContain('Terminées sans date de fin');
    expect(fixture.nativeElement.querySelectorAll('h1')).toHaveLength(1);
    expect(fixture.nativeElement.querySelectorAll('.kpi-grid app-dashboard-kpi-card')).toHaveLength(6);
    http.expectNone(() => true);
  });
  it.each([400, 422, 404, 500])('shows the appropriate HTTP %s state and keeps filters available', status => {
    apply(); request().flush({ detail: 'Test error' }, { status, statusText: 'Error' }); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.results [role="alert"]')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.results app-error-state button') !== null).toBe(status === 500);
    expect(fixture.debugElement.query(By.directive(DashboardFiltersComponent)).componentInstance).toBe(form);
    if (status === 500) { fixture.nativeElement.querySelector('.results app-error-state button').click(); request().flush(emptyDashboardResponse()); }
  });
  it('refreshes applied filters even while the form contains unsubmitted changes and retains button focus', () => {
    apply(); request().flush(emptyDashboardResponse()); fixture.detectChanges();
    form.form.controls.start_time.setValue('2026-09-01T00:00');
    const button = fixture.nativeElement.querySelector('.refresh-button') as HTMLButtonElement;
    button.focus(); button.click(); fixture.detectChanges();
    const req = request(); expect(req.request.params.get('start_time')).toBe(filters.start_time);
    expect(document.activeElement).toBe(button); req.flush(emptyDashboardResponse()); fixture.detectChanges();
    expect(document.activeElement).toBe(button);
  });
  it('isolates facade state between two page instances', () => {
    const other = TestBed.createComponent(DashboardComponent); other.detectChanges();
    http.expectOne(req => req.url === '/api/v1/companies').flush({ items: [], total: 0, page: 1, page_size: 50, pages: 0 });
    expect(other.componentInstance.facade).not.toBe(fixture.componentInstance.facade);
    apply(); request().flush(emptyDashboardResponse()); expect(other.componentInstance.facade.state().status).toBe('idle'); other.destroy();
  });
});
