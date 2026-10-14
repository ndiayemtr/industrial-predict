import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { API_PREFIX } from '../../../core/http/api-config';
import { DashboardFilters } from '../models/dashboard-filters.model';
import { DashboardRead } from '../models/dashboard.model';

@Injectable({ providedIn: 'root' })
export class DashboardApiService {
  private readonly http = inject(HttpClient);

  getDashboard(filters: DashboardFilters): Observable<DashboardRead> {
    let params = new HttpParams()
      .set('company_id', filters.company_id)
      .set('start_time', filters.start_time)
      .set('end_time', filters.end_time);

    if (filters.site_id != null) {
      params = params.set('site_id', filters.site_id);
    }
    if (filters.equipment_id != null) {
      params = params.set('equipment_id', filters.equipment_id);
    }

    return this.http.get<DashboardRead>(`${API_PREFIX}/dashboard`, { params });
  }
}
