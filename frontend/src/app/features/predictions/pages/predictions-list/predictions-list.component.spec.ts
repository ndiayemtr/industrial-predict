import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { PREDICTION_ROUTES } from '../../predictions.routes';
import { PredictionsListComponent } from './predictions-list.component';
import { PredictionRead } from '../../models/prediction.model';

const company = {
  id: 7,
  name: 'Entreprise test',
  code: 'ENT',
  description: null,
  created_at: '',
  updated_at: '',
};
const site = { ...company, id: 9, company_id: 7, name: 'Site test', code: 'SITE' };
const equipment = {
  ...company,
  id: 12,
  site_id: 9,
  name: 'Pompe test',
  code: 'POMPE',
  equipment_type: 'pump',
  status: 'operational',
  criticality: 'high',
};
const row: PredictionRead = {
  id: 17,
  equipment_id: 12,
  sensor_id: null,
  measurement_id: null,
  prediction_type: 'anomaly',
  score: 0.85,
  level: null,
  is_alert: null,
  model_name: null,
  model_version: null,
  horizon_hours: null,
  details: null,
  predicted_at: '2026-10-23T17:30:00.123456+05:30',
  created_at: '2026-10-23T12:00:01.654321Z',
};
const catalog = { items: [company], total: 1, page: 1, page_size: 50, pages: 1 };
const page = { items: [row], total: 21, page: 1, page_size: 20, pages: 2 };
const base = '/predictions?company_id=7&site_id=9&equipment_id=12';

describe('Predictions list with isolated routing and HTTP fixtures', () => {
  let http: HttpTestingController, h: RouterTestingHarness, c: PredictionsListComponent;
  const root = () => h.routeNativeElement!;
  const req = (name: string) => http.expectOne((r) => r.url === '/api/v1/' + name);
  const list = (id = 12) => req(`equipments/${id}/predictions`);
  const url = () => TestBed.inject(Router).parseUrl(TestBed.inject(Router).url).queryParams;
  async function settle() {
    h.fixture.detectChanges();
    TestBed.tick();
    await h.fixture.whenStable();
    h.fixture.detectChanges();
  }
  async function open(path = '/predictions') {
    h = await RouterTestingHarness.create();
    c = await h.navigateByUrl(path, PredictionsListComponent);
    await settle();
  }
  function parents(id = 12) {
    req(`equipments/${id}`).flush({ ...equipment, id });
    req('sites/9').flush(site);
    req('companies/7').flush(company);
  }
  function catalogs() {
    req('sites').flush({ ...catalog, items: [site] });
    req('equipments').flush({ ...catalog, items: [equipment] });
  }
  async function ready(path = base) {
    await open(path);
    req('companies').flush(catalog);
    parents();
    await settle();
    catalogs();
    list().flush({
      ...page,
      page: Number(url()['page'] ?? 1),
      page_size: Number(url()['page_size'] ?? 20),
      pages: Math.ceil(21 / Number(url()['page_size'] ?? 20)),
    });
    await settle();
  }
  async function reload() {
    parents();
    list().flush({
      ...page,
      page: Number(url()['page'] ?? 1),
      page_size: Number(url()['page_size'] ?? 20),
      pages: Math.ceil(21 / Number(url()['page_size'] ?? 20)),
    });
    await settle();
  }
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([{ path: 'predictions', children: PREDICTION_ROUTES }]),
      ],
    });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    try {
      http.expectNone(
        (r) => r.method !== 'GET' || /\/(rul|health-score|recommendations)$/.test(r.url),
      );
      http.verify();
    } finally {
      TestBed.resetTestingModule();
    }
  });

  it('never chooses a single available option and validates each explicit selection', async () => {
    await open();
    req('companies').flush(catalog);
    await settle();
    expect(c.company.value).toBeNull();
    expect(c.site.disabled).toBe(true);
    expect(c.equipment.disabled).toBe(true);
    http.expectNone(() => true);
    c.company.setValue(7);
    await settle();
    req('companies/7').flush(company);
    await settle();
    req('sites').flush({ ...catalog, items: [site] });
    await settle();
    expect(c.site.value).toBeNull();
    http.expectNone((r) => r.url.endsWith('/predictions'));
    c.site.setValue(9);
    await settle();
    req('sites/9').flush(site);
    req('companies/7').flush(company);
    await settle();
    req('equipments').flush({ ...catalog, items: [equipment] });
    await settle();
    expect(c.equipment.value).toBeNull();
    http.expectNone((r) => r.url.endsWith('/predictions'));
    c.equipment.setValue(12);
    await settle();
    parents();
    await settle();
    list().flush(page);
    await settle();
    expect(c.facade.state().status).toBe('success');
    expect(root().querySelector('.context')?.textContent).toContain('POMPE');
  });
  it('renders six accessible columns, precise source timestamp and declared values with details initially closed', async () => {
    await ready();
    expect(root().querySelectorAll('thead th[scope="col"]')).toHaveLength(6);
    expect(root().querySelector('table caption')?.textContent).toContain('Tri serveur');
    expect(root().querySelector('time')?.textContent).toBe(row.predicted_at);
    expect(root().querySelector('time')?.getAttribute('datetime')).toBe(row.predicted_at);
    expect(root().querySelector('tbody')?.textContent).toContain('0.85');
    expect(root().querySelector('tbody')?.textContent).toContain('Non renseignée');
    expect(root().querySelector('tbody')?.textContent).not.toMatch(/%|probabilité|\/100/);
    expect(root().querySelector('tbody details,tbody a,tbody pre')).toBeNull();
    expect(root().querySelectorAll('h1')).toHaveLength(1);
  });
  it('shares one selection hint and omits applied summaries for default filters', async () => {
    await ready();
    const help = root().querySelector('#predictions-context-help');
    expect(root().querySelectorAll('#predictions-context-help')).toHaveLength(1);
    expect(help?.textContent).toContain('rattachements sont vérifiés');
    for (const select of root().querySelectorAll('.parents select')) {
      expect(select.getAttribute('aria-describedby')).toBe(help?.id);
    }
    expect(root().querySelector('#predictions-level')?.getAttribute('aria-describedby')).toContain(
      'predictions-level-help',
    );
    expect(root().querySelector('#predictions-level-help')?.textContent).toBe(
      'Facultatif - saisissez un niveau exact pour filtrer.',
    );
    const reset = root().querySelector<HTMLButtonElement>('.reset-selection')!;
    expect(reset.type).toBe('button');
    expect(reset.textContent).toBe('Recommencer la sélection');
    expect(reset.previousElementSibling?.classList.contains('parents')).toBe(true);
    expect(root().querySelector('.scroll-help')?.textContent).toBe(
      'Faites défiler le tableau horizontalement.',
    );
    expect(root().querySelector('.anomaly-notice')).toBeNull();
    expect(root().querySelector('.filter-summary')).toBeNull();
    expect(root().querySelector('.draft-notice')).toBeNull();
    http.expectNone(() => true);
  });
  it('summarizes only applied filters, including false, raw spaces and precise dates', async () => {
    const start = '2026-10-23T17:30:00.123456+05:30',
      end = '2026-10-23T12:00:00.123456Z';
    await ready(
      base +
        '&prediction_type=anomaly&level=' +
        encodeURIComponent('  日本  ') +
        '&is_alert=false&start_time=' +
        encodeURIComponent(start) +
        '&end_time=' +
        encodeURIComponent(end),
    );
    const summary = root().querySelector('.filter-summary')!;
    expect(summary.getAttribute('role')).toBe('status');
    expect(summary.querySelectorAll('li')).toHaveLength(5);
    expect(summary.textContent).toContain('Type : Anomalie');
    expect(summary.textContent).toContain('Alerte : Non');
    expect(summary.querySelector('.filter-raw-value')?.textContent).toBe('«  日本  »');
    expect(summary.textContent).toContain(start);
    expect(summary.textContent).toContain(end);
    expect(summary.textContent).not.toMatch(/sans borne|tous/);
    c.level.setValue('unapplied');
    await settle();
    expect(root().querySelector('.draft-notice')).not.toBeNull();
    expect(summary.textContent).not.toContain('unapplied');
    http.expectNone(() => true);
    c.clearFilters();
    await settle();
    await reload();
    expect(root().querySelector('.filter-summary')).toBeNull();
    expect(root().querySelector('.draft-notice')).toBeNull();
  });
  it('opens and closes a labelled detail panel without HTTP, navigation or filter changes', async () => {
    await ready();
    c.level.setValue('unapplied');
    await settle();
    const beforeUrl = TestBed.inject(Router).url,
      query = c.facade.query(),
      state = c.facade.state();
    const button = root().querySelector<HTMLButtonElement>('#prediction-toggle-17')!;
    expect(button.type).toBe('button');
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(button.querySelector('.details-indicator')?.getAttribute('aria-hidden')).toBe('true');
    expect(button.querySelector('.details-indicator')?.textContent).toBe('+');
    button.focus();
    button.click();
    await settle();
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(button.getAttribute('aria-controls')).toBe('prediction-panel-17');
    expect(button.querySelector('.details-indicator')?.textContent).toBe('−');
    expect(root().querySelector('#prediction-panel-17')?.getAttribute('aria-labelledby')).toBe(
      button.id,
    );
    expect(root().querySelector('#prediction-panel-17 .anomaly-notice')?.textContent).toBe(
      'L’indice d’anomalie n’est pas une probabilité de panne.',
    );
    expect(root().querySelector('.detail-row td')?.getAttribute('colspan')).toBe('6');
    expect(document.activeElement).toBe(button);
    expect(root().querySelectorAll('tbody tr')).toHaveLength(2);
    button.click();
    await settle();
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(root().querySelector('#prediction-panel-17')).toBeNull();
    expect(document.activeElement).toBe(button);
    expect(TestBed.inject(Router).url).toBe(beforeUrl);
    expect(c.facade.query()).toBe(query);
    expect(c.facade.state()).toBe(state);
    expect(c.draft()).toBe(true);
    expect(c.level.value).toBe('unapplied');
    http.expectNone(() => true);
  });
  it('keeps independent panel states and clears them when leaving loaded results', async () => {
    await open(base);
    req('companies').flush(catalog);
    parents();
    await settle();
    catalogs();
    list().flush({ ...page, items: [row, { ...row, id: 18 }] });
    await settle();
    root().querySelector<HTMLButtonElement>('#prediction-toggle-17')!.click();
    root().querySelector<HTMLButtonElement>('#prediction-toggle-18')!.click();
    await settle();
    expect(root().querySelectorAll('app-prediction-details')).toHaveLength(2);
    http.expectNone(() => true);
    c.changePage(2);
    await settle();
    expect(root().querySelector('app-prediction-details')).toBeNull();
    await reload();
    expect(c.openDetails().size).toBe(0);
  });
  it('paginates all three catalogs, merges a selection outside page one and preserves arbitrary URL sizes', async () => {
    await open(base + '&page_size=37');
    req('companies').flush({ ...catalog, items: [], total: 51, pages: 2 });
    parents();
    await settle();
    req('sites').flush({ ...catalog, items: [], total: 51, pages: 2 });
    req('equipments').flush({ ...catalog, items: [], total: 51, pages: 2 });
    const read = list();
    expect(read.request.params.get('page_size')).toBe('37');
    read.flush({ ...page, page_size: 37, pages: 1 });
    await settle();
    expect(c.options('company_id', c.companies).map((item) => item.id)).toContain(7);
    expect(c.options('site_id', c.sites).map((item) => item.id)).toContain(9);
    expect(c.options('equipment_id', c.equipments).map((item) => item.id)).toContain(12);
    c.companies.more();
    c.sites.more();
    c.equipments.more();
    for (const name of ['companies', 'sites', 'equipments']) {
      const read = req(name);
      expect(read.request.params.get('page')).toBe('2');
      read.flush({ ...catalog, items: [], total: 51, page: 2, pages: 2 });
    }
    await settle();
    expect(c.sizes()).toEqual([20, 37, 50, 100]);
    http.expectNone(() => true);
  });
  it.each([
    ['predictionType', 'rul', 'prediction_type'],
    ['level', '  日本  ', 'level'],
    ['alert', 'false', 'is_alert'],
    ['alert', 'true', 'is_alert'],
  ] as const)(
    'applies %s only on explicit action and returns to page one',
    async (control, value, key) => {
      await ready(base + '&page=2');
      c[control].setValue(value);
      await settle();
      http.expectNone(() => true);
      expect(c.draft()).toBe(true);
      c.applyFilters();
      await settle();
      parents();
      const read = list();
      expect(read.request.params.get(key)).toBe(value);
      expect(read.request.params.get('page')).toBe('1');
      expect(read.request.params.has('company_id')).toBe(false);
      expect(read.request.params.has('site_id')).toBe(false);
      read.flush(page);
      await settle();
      expect(url()[key]).toBe(value);
      expect(c.draft()).toBe(false);
    },
  );
  it('combines all filters and equal inclusive instants without changing original offsets', async () => {
    const start = '2026-10-23T17:30:00.123456+05:30',
      end = '2026-10-23T12:00:00.123456Z';
    await ready(
      base + '&start_time=' + encodeURIComponent(start) + '&end_time=' + encodeURIComponent(end),
    );
    c.predictionType.setValue('health_score');
    c.alert.setValue('false');
    c.level.setValue('unknown');
    c.applyFilters();
    await settle();
    parents();
    const read = list();
    expect(read.request.params.get('start_time')).toBe(start);
    expect(read.request.params.get('end_time')).toBe(end);
    expect(read.request.params.get('is_alert')).toBe('false');
    expect(read.request.params.get('level')).toBe('unknown');
    expect(read.request.params.get('prediction_type')).toBe('health_score');
    read.flush(page);
    await settle();
    expect(root().querySelector('.applied-period')?.textContent).toContain(start);
    expect(root().textContent).toContain('égalité permise');
  });
  it('preserves unsubmitted drafts across page/size changes while requests retain applied source times', async () => {
    const start = '2026-10-23T17:30:00.123456+05:30';
    await ready(base + '&start_time=' + encodeURIComponent(start));
    c.start.controls.time.setValue('13:00:00');
    c.level.setValue('unapplied');
    await settle();
    http.expectNone(() => true);
    c.changePage(2);
    await settle();
    parents();
    let read = list();
    expect(read.request.params.get('start_time')).toBe(start);
    expect(read.request.params.has('level')).toBe(false);
    read.flush({ ...page, page: 2 });
    await settle();
    expect(c.start.controls.time.value).toBe('13:00:00');
    expect(c.draft()).toBe(true);
    c.size.setValue(50);
    await settle();
    parents();
    read = list();
    expect(read.request.params.get('page')).toBe('1');
    expect(read.request.params.get('page_size')).toBe('50');
    expect(read.request.params.get('start_time')).toBe(start);
    read.flush({ ...page, page_size: 50, pages: 1 });
    await settle();
    expect(c.level.value).toBe('unapplied');
  });
  it('does not turn form submission or Enter into implicit application', async () => {
    await ready();
    c.start.controls.date.setValue('2026-10-23');
    const event = new Event('submit', { bubbles: true, cancelable: true });
    root().querySelector('form')!.dispatchEvent(event);
    await settle();
    expect(event.defaultPrevented).toBe(true);
    http.expectNone(() => true);
    expect(root().querySelector('button[type="submit"]')).toBeNull();
  });
  it('focuses the error summary, preserves results on invalid drafts and allows correction', async () => {
    await ready();
    const previous = c.facade.state();
    c.start.controls.date.setValue('2026-10-23');
    c.applyFilters();
    await settle();
    expect(c.facade.state()).toBe(previous);
    expect(c.start.controls.time.value).toBe('');
    expect(c.feedback()).not.toBe('');
    expect(document.activeElement?.id).toBe('predictions-feedback');
    expect(root().querySelector('#predictions-start-time')?.getAttribute('aria-invalid')).toBe(
      'true',
    );
    http.expectNone(() => true);
    c.start.controls.time.setValue('12:34:56');
    c.start.controls.fraction.setValue('000001');
    await settle();
    expect(c.feedback()).toBe('');
    c.applyFilters();
    await settle();
    parents();
    const read = list();
    expect(read.request.params.get('start_time')).toBe('2026-10-23T12:34:56.000001Z');
    read.flush(page);
    await settle();
    expect(c.draft()).toBe(false);
  });
  it('rejects inverted instants, malformed fractions and oversized levels before any GET', async () => {
    await ready();
    c.start.setValue({ date: '2026-10-23', time: '12:00:00', fraction: '000002' });
    c.end.setValue({ date: '2026-10-23', time: '12:00:00', fraction: '000001' });
    c.applyFilters();
    await settle();
    expect(c.fieldErrors()['end-date']).toBeTruthy();
    http.expectNone(() => true);
    c.end.controls.fraction.setValue('1234567');
    c.level.setValue('😀'.repeat(51));
    c.applyFilters();
    await settle();
    expect(c.fieldErrors()['end-fraction']).toBeTruthy();
    expect(c.fieldErrors()['level']).toBeTruthy();
    http.expectNone(() => true);
  });
  it('clears only the applied period while retaining other valid filters', async () => {
    await ready(base + '&is_alert=false&start_time=2026-10-23T12:00:00Z');
    c.clearPeriod();
    await settle();
    parents();
    const read = list();
    expect(read.request.params.has('start_time')).toBe(false);
    expect(read.request.params.get('is_alert')).toBe('false');
    read.flush(page);
    await settle();
  });
  it.each([
    'prediction_type=bad',
    'is_alert=null',
    'level=',
    'page_size=101',
    'start_time=bad',
    'equipment_id=13',
  ])('blocks invalid or duplicate URL %s without dropping it', async (filter) => {
    await open(base + '&' + filter);
    req('companies').flush(catalog);
    await settle();
    expect(c.urlNotice()).not.toBe('');
    expect(c.facade.state()).toMatchObject({ status: 'error', retryable: false });
    http.expectNone(() => true);
  });
  it('repairs invalid URL filters explicitly, retaining the scope and no silent widening', async () => {
    await open(base + '&is_alert=null');
    req('companies').flush(catalog);
    c.alert.setValue('false');
    c.applyFilters();
    await settle();
    parents();
    await settle();
    catalogs();
    const read = list();
    expect(read.request.params.get('is_alert')).toBe('false');
    read.flush(page);
    await settle();
    expect(url()['is_alert']).toBe('false');
  });
  it('does not repair a contradictory scope when clearing filters', async () => {
    await open(base);
    req('companies').flush(catalog);
    req('equipments/12').flush({ ...equipment, site_id: 99 });
    await settle();
    expect(c.facade.state().status).toBe('error');
    http.expectNone(() => true);
    c.clearFilters();
    await settle();
    expect(url()['site_id']).toBe('9');
    http.expectNone(() => true);
  });
  it('requires complete URL ancestors before reading predictions', async () => {
    await open('/predictions?equipment_id=12');
    req('companies').flush(catalog);
    await settle();
    expect(c.facade.state()).toMatchObject({ status: 'error', retryable: false });
    http.expectNone(() => true);
  });
  it('clears old rows and descendants immediately on changing company and cancels pending catalogs', async () => {
    await open(base);
    const companies = req('companies');
    parents();
    await settle();
    const sites = req('sites'),
      equipments = req('equipments'),
      old = list();
    companies.flush(catalog);
    c.company.setValue(8);
    expect(c.site.value).toBeNull();
    expect(c.equipment.value).toBeNull();
    expect(old.cancelled).toBe(true);
    expect(sites.cancelled).toBe(true);
    expect(equipments.cancelled).toBe(true);
    expect(c.facade.state().status).toBe('loading');
    await settle();
    req('companies/8').flush({ ...company, id: 8 });
    await settle();
    req('sites').flush({ ...catalog, items: [] });
    await settle();
    expect(root().querySelector('tbody')).toBeNull();
    http.expectNone(() => true);
  });
  it('cancels a rapid equipment change and never displays old rows', async () => {
    await ready();
    c.refresh();
    const old = req('equipments/12');
    c.equipment.setValue(13);
    expect(old.cancelled).toBe(true);
    await settle();
    parents(13);
    await settle();
    list(13).flush({ ...page, items: [{ ...row, equipment_id: 13 }] });
    await settle();
    expect(c.facade.equipment()?.id).toBe(13);
    expect(root().querySelectorAll('tbody tr')).toHaveLength(1);
  });
  it('clears the equipment on site change without reloading unchanged catalogs', async () => {
    await ready();
    c.site.setValue(10);
    expect(c.equipment.value).toBeNull();
    await settle();
    req('sites/10').flush({ ...site, id: 10 });
    req('companies/7').flush(company);
    await settle();
    req('equipments').flush({ ...catalog, items: [] });
    await settle();
    expect(c.site.value).toBe(10);
    expect(c.equipment.value).toBeNull();
    http.expectNone(() => true);
  });
  it('rejects a foreign site catalog without exposing its options', async () => {
    await ready();
    c.company.setValue(8);
    await settle();
    req('companies/8').flush({ ...company, id: 8 });
    await settle();
    req('sites').flush({ ...catalog, items: [site] });
    await settle();
    expect(c.sites.state().status).toBe('error');
    expect(c.sites.state().items).toEqual([]);
    http.expectNone(() => true);
  });
  it('retains the failed next catalog page for a manual retry', async () => {
    await open();
    req('companies').flush({ ...catalog, total: 51, pages: 2 });
    await settle();
    c.companies.more();
    req('companies').error(new ProgressEvent('error'));
    await settle();
    expect(c.companies.state().items).toEqual([company]);
    c.companies.retry();
    const read = req('companies');
    expect(read.request.params.get('page')).toBe('2');
    read.flush({ ...catalog, items: [{ ...company, id: 8 }], total: 51, page: 2, pages: 2 });
    await settle();
    expect(c.companies.state().items.map((item) => item.id)).toEqual([7, 8]);
    expect(c.company.value).toBeNull();
  });
  it('recovers out-of-range pages explicitly to page one', async () => {
    await ready();
    c.changePage(3);
    await settle();
    parents();
    list().flush({ ...page, items: [], page: 3 });
    await settle();
    expect(root().textContent).toContain('Page hors plage');
    http.expectNone(() => true);
    c.recoverPage();
    await settle();
    await reload();
    expect(url()['page']).toBe('1');
  });
  it.each([false, true])(
    'distinguishes unfiltered/filtered empty %s, including false as an applied filter',
    async (filtered) => {
      await open(base + (filtered ? '&is_alert=false' : ''));
      req('companies').flush(catalog);
      parents();
      await settle();
      catalogs();
      list().flush({ ...page, items: [], total: 0, pages: 0 });
      await settle();
      expect(root().textContent).toContain(
        filtered ? 'Aucun résultat' : 'Aucune prédiction enregistrée',
      );
      expect(root().textContent).not.toContain('modèle absent');
    },
  );
  it.each([404, 422, 500, 0])(
    'renders HTTP error %s and offers retry only where applicable',
    async (status) => {
      await open(base);
      req('companies').flush(catalog);
      parents();
      await settle();
      catalogs();
      const read = list();
      expect(root().querySelector('.results')?.getAttribute('aria-busy')).toBe('true');
      if (status === 0) read.error(new ProgressEvent('error'));
      else read.flush({ detail: 'failure' }, { status, statusText: 'Failure' });
      await settle();
      expect(c.facade.state()).toMatchObject({
        status: 'error',
        retryable: status === 0 || status >= 500,
      });
      expect(root().querySelector('tbody')).toBeNull();
      http.expectNone(() => true);
    },
  );
  it('renders true, false and null alerts and arbitrary declared levels without color-only meaning', async () => {
    await open(base);
    req('companies').flush(catalog);
    parents();
    await settle();
    catalogs();
    list().flush({
      ...page,
      items: [
        row,
        { ...row, id: 18, is_alert: false, level: 'strange' },
        { ...row, id: 19, is_alert: true, score: 125 },
      ],
    });
    await settle();
    const rows = [...root().querySelectorAll('tbody tr')];
    expect(rows[0].textContent).toContain('Non renseignée');
    expect(rows[1].textContent).toContain('Non');
    expect(rows[2].textContent).toContain('Oui');
    expect(rows[0].querySelector('.alert-unknown')?.textContent).toBe('Non renseignée');
    expect(rows[1].querySelector('.alert-no')?.textContent).toBe('Non');
    expect(rows[2].querySelector('.alert-yes')?.textContent).toBe('Oui');
    expect(rows[1].textContent).toContain('strange');
    expect(rows[2].textContent).toContain('125');
  });
  it('keeps native keyboard controls, labelled inputs, focus and a keyboard-scrollable table', async () => {
    await ready();
    for (const label of root().querySelectorAll('label[for]'))
      expect(root().querySelector('#' + label.getAttribute('for'))).not.toBeNull();
    const input = root().querySelector<HTMLInputElement>('#predictions-level')!;
    input.focus();
    expect(document.activeElement).toBe(input);
    const region = root().querySelector<HTMLElement>('.table-scroll')!;
    region.focus();
    expect(document.activeElement).toBe(region);
    expect(region.getAttribute('tabindex')).toBe('0');
    expect(root().querySelector('button:not([type])')).toBeNull();
    expect(root().textContent).not.toMatch(/Supprimer|Modifier|Calculer|Générer/);
  });
  it('restarts a broken selection without preserving invalid URL parameters', async () => {
    await open(base + '&equipment_id=13');
    req('companies').flush(catalog);
    c.resetSelection();
    await settle();
    expect(url()).toEqual({ page: '1', page_size: '20' });
    expect(c.company.value).toBeNull();
    http.expectNone(() => true);
  });
});
