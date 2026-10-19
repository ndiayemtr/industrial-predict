import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { API_PREFIX } from '../http/api-config';
import { Page, ReferencePageQuery } from '../models/page.model';
import { CompanyRead, EquipmentRead, SiteRead } from '../models/reference-data.model';
import { EquipmentPageQuery } from '../models/equipment-page-query.model';

@Injectable({ providedIn: 'root' })
export class ReferenceDataApiService {
  private readonly http = inject(HttpClient);

  getCompanies(query: ReferencePageQuery = {}): Observable<Page<CompanyRead>> {
    return this.http.get<Page<CompanyRead>>(`${API_PREFIX}/companies`, { params: this.params(query) });
  }

  getCompanyById(id: number): Observable<CompanyRead> {
    return this.http.get<CompanyRead>(`${API_PREFIX}/companies/${id}`);
  }

  getSites(companyId: number, query: ReferencePageQuery = {}): Observable<Page<SiteRead>> {
    return this.http.get<Page<SiteRead>>(`${API_PREFIX}/sites`, {
      params: this.params(query).set('company_id', companyId)
    });
  }

  getSiteById(id: number): Observable<SiteRead> {
    return this.http.get<SiteRead>(`${API_PREFIX}/sites/${id}`);
  }

  getEquipmentById(id: number): Observable<EquipmentRead> {
    return this.http.get<EquipmentRead>(`${API_PREFIX}/equipments/${id}`);
  }

  getEquipments(siteId: number, query: EquipmentPageQuery = {}): Observable<Page<EquipmentRead>> {
    let params = this.params(query).set('site_id', siteId);
    if (query.status != null) params = params.set('status', query.status);
    if (query.criticality != null) params = params.set('criticality', query.criticality);
    return this.http.get<Page<EquipmentRead>>(`${API_PREFIX}/equipments`, {
      params
    });
  }

  private params(query: ReferencePageQuery): HttpParams {
    let params = new HttpParams();
    if (query.page != null) params = params.set('page', query.page);
    if (query.page_size != null) params = params.set('page_size', query.page_size);
    if (query.search) params = params.set('search', query.search);
    return params;
  }
}
