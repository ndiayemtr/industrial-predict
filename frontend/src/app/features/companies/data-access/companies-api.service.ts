import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { ReferenceDataApiService } from '../../../core/api/reference-data-api.service';
import { API_PREFIX } from '../../../core/http/api-config';
import { Page, ReferencePageQuery } from '../../../core/models/page.model';
import { CompanyRead } from '../../../core/models/reference-data.model';
import { CompanyCreate, CompanyUpdate } from '../models/company-write.model';

@Injectable({ providedIn: 'root' })
export class CompaniesApiService {
  private readonly http = inject(HttpClient);
  private readonly references = inject(ReferenceDataApiService);

  // Reuse the paginated transport; omitted parameters keep the backend defaults.
  list(query: ReferencePageQuery = {}): Observable<Page<CompanyRead>> {
    return this.references.getCompanies(query);
  }

  getById(id: number): Observable<CompanyRead> {
    return this.http.get<CompanyRead>(`${API_PREFIX}/companies/${id}`);
  }

  create(body: CompanyCreate): Observable<CompanyRead> {
    return this.http.post<CompanyRead>(`${API_PREFIX}/companies`, body);
  }

  update(id: number, body: CompanyUpdate): Observable<CompanyRead> {
    return this.http.patch<CompanyRead>(`${API_PREFIX}/companies/${id}`, body);
  }
}
