import { ChangeDetectionStrategy, Component, effect, inject, untracked } from '@angular/core';
import { DashboardFiltersComponent } from '../../components/dashboard-filters/dashboard-filters.component';
import { DashboardFacade } from '../../dashboard.facade';
import { DashboardReferenceCatalog, DashboardReferences } from '../../dashboard-references';
import { DashboardFilters } from '../../models/dashboard-filters.model';
import { DashboardKpiCardComponent } from '../../components/dashboard-kpi-card/dashboard-kpi-card.component';
import { EquipmentSummaryComponent } from '../../components/equipment-summary/equipment-summary.component';
import { SensorSummaryComponent } from '../../components/sensor-summary/sensor-summary.component';
import { MeasurementSummaryComponent } from '../../components/measurement-summary/measurement-summary.component';
import { MaintenanceSummaryComponent } from '../../components/maintenance-summary/maintenance-summary.component';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { formatUtcDateTime } from '../../../../shared/utils/datetime-display';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [PageHeaderComponent, DashboardFiltersComponent, LoadingStateComponent, EmptyStateComponent, ErrorStateComponent,
    DashboardKpiCardComponent, EquipmentSummaryComponent, SensorSummaryComponent, MeasurementSummaryComponent, MaintenanceSummaryComponent],
  providers: [DashboardFacade, DashboardReferences],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DashboardComponent {
  readonly formatDateTime = formatUtcDateTime;
  readonly facade = inject(DashboardFacade);
  readonly references = inject(DashboardReferences);

  constructor() {
    effect(() => {
      const state = this.facade.state();
      if (state.status === 'success') untracked(() => this.references.loadReadings(
        state.filters, state.data.measurements.last_measurements.map(reading => reading.equipment_id)
      ));
    });
  }

  applyFilters(filters: DashboardFilters, catalog: DashboardReferenceCatalog): void {
    const previous = this.facade.appliedFilters();
    this.facade.applyFilters(filters);
    const applied = this.facade.appliedFilters();
    if (applied && applied !== previous) this.references.capture(applied, catalog);
  }
}
