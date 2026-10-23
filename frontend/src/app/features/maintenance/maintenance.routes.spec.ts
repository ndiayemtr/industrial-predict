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
import { MAINTENANCE_ROUTES } from './maintenance.routes';

describe('Maintenance lazy routing in Shell',()=>{
  beforeEach(()=>{vi.spyOn(window,'scrollTo').mockImplementation(()=>{});TestBed.configureTestingModule({providers:[provideRouter(routes),provideHttpClient(),provideHttpClientTesting(),provideNoopAnimations(),importProvidersFrom(NbThemeModule.forRoot({name:'industrial-predict'},[{name:'industrial-predict',base:'default',variables:{}}]),NbSidebarModule.forRoot())]});});
  afterEach(()=>{try{TestBed.inject(HttpTestingController).verify();}finally{TestBed.resetTestingModule();vi.restoreAllMocks();}});
  it('declares ordered full-match lazy list and detail',()=>{expect(MAINTENANCE_ROUTES.map(r=>r.path)).toEqual(['']);expect(MAINTENANCE_ROUTES[0].pathMatch).toBe('full');expect(typeof MAINTENANCE_ROUTES[0].loadComponent).toBe('function');expect(typeof routes[0].children?.find(r=>r.path==='maintenance')?.loadChildren).toBe('function');});
  it('replaces the placeholder and retains title, Shell and active navigation',async()=>{
    const h=await RouterTestingHarness.create('/maintenance');h.fixture.detectChanges();TestBed.tick();await h.fixture.whenStable();h.fixture.detectChanges();
    const http=TestBed.inject(HttpTestingController);http.expectOne(req=>req.url==='/api/v1/companies').flush({items:[],total:0,page:1,page_size:50,pages:0});h.fixture.detectChanges();
    expect(h.routeNativeElement!.querySelector('app-maintenance-list')).not.toBeNull();expect(h.routeNativeElement!.querySelector('app-feature-placeholder')).toBeNull();
    expect(h.routeNativeElement!.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/maintenance');expect(TestBed.inject(Title).getTitle()).toBe('Maintenance | Industrial Predict AI');http.expectNone(()=>true);
  });
  it.each(['/maintenance/23','/maintenance/new','/maintenance/23/edit','/maintenance/23/unknown'])('leaves future path %s to the global 404 without reads',async path=>{
    const h=await RouterTestingHarness.create(path);h.fixture.detectChanges();await h.fixture.whenStable();expect(h.routeNativeElement!.querySelector('app-maintenance-list')).toBeNull();expect(TestBed.inject(Title).getTitle()).toBe('Page introuvable | Industrial Predict AI');TestBed.inject(HttpTestingController).expectNone(()=>true);
  });
});
