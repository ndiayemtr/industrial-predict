import { HttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { NB_TOASTR_CONFIG, NbGlobalPhysicalPosition, NbToastrService } from '@nebular/theme';

import { appConfig } from './app.config';
import { PROFESSIONAL_AUTH_BACKEND } from './features/auth/professional-auth.model';
import { FastApiProfessionalAuthBackend } from './features/auth/fastapi-professional-auth.service';

describe('Application HTTP configuration', () => {
  it('initializes the application providers with HttpClient and no automatic request', () => {
    TestBed.configureTestingModule({
      providers: [...appConfig.providers, provideHttpClientTesting()]
    });
    expect(TestBed.inject(HttpClient)).toBeTruthy();
    const auth = TestBed.inject(PROFESSIONAL_AUTH_BACKEND);
    expect(auth).toBe(TestBed.inject(FastApiProfessionalAuthBackend));
    expect(auth?.ready()).toBe(false);
    expect(auth?.availability?.()).toBe('closed');
    expect(TestBed.inject(NbToastrService)).toBeTruthy();
    expect(TestBed.inject(NB_TOASTR_CONFIG)).toEqual({
      position: NbGlobalPhysicalPosition.TOP_RIGHT,
      duration: 5000,
      hasIcon: false,
      icon: { icon: '' },
      destroyByClick: false
    });
    const http = TestBed.inject(HttpTestingController);
    http.expectNone(() => true);
    http.verify();
  });
});
