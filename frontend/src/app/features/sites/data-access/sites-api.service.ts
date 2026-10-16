import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { ReferenceDataApiService } from '../../../core/api/reference-data-api.service';
import { API_PREFIX } from '../../../core/http/api-config';
import { Page } from '../../../core/models/page.model';
import { SiteRead } from '../../../core/models/reference-data.model';
import { SiteListQuery } from '../models/site-list-query.model';
import { SiteCreate, SiteUpdate } from '../models/site-write.model';

@Injectable({ providedIn: 'root' })
export class SitesApiService {
  private readonly http = inject(HttpClient);
  private readonly references = inject(ReferenceDataApiService);

  list(query: SiteListQuery): Observable<Page<SiteRead>> {
    return this.references.getSites(query.company_id, query);
  }

  getById(id: number): Observable<SiteRead> {
    return this.http.get<SiteRead>(`${API_PREFIX}/sites/${id}`);
  }

  create(body: SiteCreate): Observable<SiteRead> {
    return this.http.post<SiteRead>(`${API_PREFIX}/sites`, body);
  }

  update(id: number, body: SiteUpdate): Observable<SiteRead> {
    // TypeScript also accepts variables with extra properties. Keep the MVP
    // write boundary explicit so passing a SiteRead cannot transfer its company.
    const patch: SiteUpdate = {};
    for (const field of ['name', 'code', 'description'] as const) {
      if (Object.prototype.hasOwnProperty.call(body, field)) patch[field] = body[field];
    }
    return this.http.patch<SiteRead>(`${API_PREFIX}/sites/${id}`, patch);
  }
}
