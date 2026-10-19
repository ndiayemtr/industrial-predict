import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { defer, Observable } from 'rxjs';
import { ReferenceDataApiService } from '../../../core/api/reference-data-api.service';
import { API_PREFIX } from '../../../core/http/api-config';
import { Page } from '../../../core/models/page.model';
import { EquipmentRead } from '../../../core/models/reference-data.model';
import { EquipmentListQuery } from '../models/equipment-list-query.model';
import { EquipmentCreate, EquipmentUpdate } from '../models/equipment-write.model';

@Injectable({ providedIn: 'root' })
export class EquipmentsApiService {
  private readonly http = inject(HttpClient);
  private readonly references = inject(ReferenceDataApiService);

  list(query: EquipmentListQuery): Observable<Page<EquipmentRead>> {
    return this.references.getEquipments(query.site_id, query);
  }

  getById(id: number): Observable<EquipmentRead> {
    return this.references.getEquipmentById(id);
  }

  create(body: EquipmentCreate): Observable<EquipmentRead> {
    return defer(() => {
      for (const field of ['site_id', 'name', 'code', 'equipment_type'] as const) {
        if (!Object.hasOwn(body, field) || body[field] == null) {
          throw new TypeError(`Equipment ${field} is required and cannot be null.`);
        }
      }
      const payload: EquipmentCreate = { ...this.editableBody(body), site_id: body.site_id,
        name: body.name, code: body.code, equipment_type: body.equipment_type };
      return this.http.post<EquipmentRead>(`${API_PREFIX}/equipments`, payload);
    });
  }

  update(id: number, body: EquipmentUpdate): Observable<EquipmentRead> {
    // Difference calculation belongs to UI 5.6. Even an unsafe structural object
    // cannot transfer a site, write administrative data or pass unknown fields.
    return defer(() => this.http.patch<EquipmentRead>(`${API_PREFIX}/equipments/${id}`, this.editableBody(body)));
  }

  private editableBody(body: EquipmentUpdate): EquipmentUpdate {
    const payload: EquipmentUpdate = {};
    const copy = <K extends keyof EquipmentUpdate>(field: K) => {
      const value = body[field];
      if (!Object.hasOwn(body, field) || value === undefined) return;
      if (value === null && field !== 'description') {
        throw new TypeError(`Equipment ${field} cannot be null.`);
      }
      payload[field] = value;
    };
    for (const field of ['name', 'code', 'equipment_type', 'description', 'status', 'criticality'] as const) copy(field);
    return payload;
  }
}
