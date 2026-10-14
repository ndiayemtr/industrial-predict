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
