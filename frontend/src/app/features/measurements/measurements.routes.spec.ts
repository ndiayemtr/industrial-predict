import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { Title } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarModule, NbThemeModule } from '@nebular/theme';
import { routes } from '../../app.routes';
import { MEASUREMENT_ROUTES } from './measurements.routes';

describe('Measurements lazy routing in Shell',()=>{
  beforeEach(()=>{vi.spyOn(window,'scrollTo').mockImplementation(()=>{});TestBed.configureTestingModule({providers:[provideRouter(routes),provideHttpClient(),provideHttpClientTesting(),provideNoopAnimations(),importProvidersFrom(NbThemeModule.forRoot({name:'industrial-predict'},[{name:'industrial-predict',base:'default',variables:{}}]),NbSidebarModule.forRoot())]});});
  afterEach(()=>{try{TestBed.inject(HttpTestingController).verify();}finally{TestBed.resetTestingModule();vi.restoreAllMocks();}});
  it('only declares a full-match lazy list',()=>{expect(MEASUREMENT_ROUTES.map(r=>r.path)).toEqual(['']);expect(MEASUREMENT_ROUTES[0].pathMatch).toBe('full');expect(typeof MEASUREMENT_ROUTES[0].loadComponent).toBe('function');expect(typeof routes[0].children?.find(r=>r.path==='measurements')?.loadChildren).toBe('function');});
  it('replaces the placeholder and retains title, Shell and active navigation',async()=>{
    const h=await RouterTestingHarness.create('/measurements');h.fixture.detectChanges();TestBed.tick();await h.fixture.whenStable();h.fixture.detectChanges();
    const http=TestBed.inject(HttpTestingController);http.expectOne(req=>req.url==='/api/v1/companies').flush({items:[],total:0,page:1,page_size:50,pages:0});h.fixture.detectChanges();
    expect(h.routeNativeElement!.querySelector('app-measurements-list')).not.toBeNull();expect(h.routeNativeElement!.querySelector('app-feature-placeholder')).toBeNull();
    expect(h.routeNativeElement!.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/measurements');expect(TestBed.inject(Title).getTitle()).toBe('Mesures | Industrial Predict AI');http.expectNone(()=>true);
  });
  it.each(['/measurements/23','/measurements/new','/measurements/23/edit'])('leaves future path %s to the global 404 without reads',async path=>{
    const h=await RouterTestingHarness.create(path);h.fixture.detectChanges();await h.fixture.whenStable();expect(h.routeNativeElement!.querySelector('app-measurements-list')).toBeNull();expect(TestBed.inject(Title).getTitle()).toBe('Page introuvable | Industrial Predict AI');TestBed.inject(HttpTestingController).expectNone(()=>true);
  });
});
