import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { CompaniesListFacade } from './companies-list.facade';

describe('CompaniesListFacade', () => {
  let facade: CompaniesListFacade;
  let http: HttpTestingController;
  const query = { page: 1, page_size: 20 };
  const empty = { items: [], total: 0, page: 1, page_size: 20, pages: 0 };

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), CompaniesListFacade] });
    facade = TestBed.inject(CompaniesListFacade);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('starts idle and does not request data before the page applies its URL', () => {
    expect(facade.state().status).toBe('idle');
    facade.retry();
    http.expectNone(() => true);
  });

  it('keeps an immutable snapshot and exposes loading then empty', () => {
    const applied = { ...query, search: 'Test' };
    facade.load(applied);
    applied.search = 'Edited';
    expect(facade.state()).toEqual({ status: 'loading', query: { ...query, search: 'Test' } });
    expect(Object.isFrozen(facade.query())).toBe(true);
    http.expectOne(request => request.params.get('search') === 'Test').flush(empty);
    expect(facade.state().status).toBe('empty');
  });

  it('does not mistake an out-of-range page for an empty database', () => {
    facade.load({ ...query, page: 8 });
    http.expectOne(request => request.params.get('page') === '8')
      .flush({ ...empty, page: 8, total: 21, pages: 2 });
    expect(facade.state().status).toBe('success');
  });

  it('cancels obsolete reads and only exposes the most recent response', () => {
    facade.load({ ...query, search: 'Old' });
    const old = http.expectOne(request => request.params.get('search') === 'Old');
    facade.load({ ...query, search: 'New' });
    expect(old.cancelled).toBe(true);
    http.expectOne(request => request.params.get('search') === 'New').flush(empty);
    expect(facade.state()).toEqual({ status: 'empty', query: { ...query, search: 'New' }, data: empty });
  });

  it.each([422, 404, 500])('exposes HTTP %s as an error instead of an empty result', status => {
    facade.load(query);
    http.expectOne(request => request.url === '/api/v1/companies')
      .flush({ detail: 'Error' }, { status, statusText: 'Error' });
    const state = facade.state();
    expect(state.status).toBe('error');
    if (state.status !== 'error') throw Error('Expected error state');
    expect(state.error.retryable).toBe(status === 500);
    facade.retry();
    if (status === 500) http.expectOne(request => request.url === '/api/v1/companies').flush(empty);
    else http.expectNone(() => true);
  });

  it('retries the applied query after a network failure and permits later successful loads', () => {
    facade.load({ ...query, search: 'Applied' });
    http.expectOne(request => request.url === '/api/v1/companies').error(new ProgressEvent('error'));
    facade.retry();
    http.expectOne(request => request.params.get('search') === 'Applied').flush(empty);
    expect(facade.state().status).toBe('empty');
    facade.load(query);
    http.expectOne(request => request.url === '/api/v1/companies').flush(empty);
    expect(facade.query()).toEqual(query);
  });

  it('cancels an outstanding read when its local provider is destroyed', () => {
    facade.load(query);
    const pending = http.expectOne(request => request.url === '/api/v1/companies');
    TestBed.resetTestingModule();
    expect(pending.cancelled).toBe(true);
  });
});
