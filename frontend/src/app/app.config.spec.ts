import { HttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { appConfig } from './app.config';

describe('Application HTTP configuration', () => {
  it('initializes the application providers with HttpClient and no automatic request', () => {
    TestBed.configureTestingModule({
      providers: [...appConfig.providers, provideHttpClientTesting()]
    });
    expect(TestBed.inject(HttpClient)).toBeTruthy();
    const http = TestBed.inject(HttpTestingController);
    http.expectNone(() => true);
    http.verify();
  });
});
