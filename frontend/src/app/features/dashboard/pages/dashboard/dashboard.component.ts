import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DashboardFiltersComponent } from '../../components/dashboard-filters/dashboard-filters.component';
import { DashboardFacade } from '../../dashboard.facade';
import { DashboardKpiCardComponent } from '../../components/dashboard-kpi-card/dashboard-kpi-card.component';
import { EquipmentSummaryComponent } from '../../components/equipment-summary/equipment-summary.component';
import { SensorSummaryComponent } from '../../components/sensor-summary/sensor-summary.component';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [PageHeaderComponent, DashboardFiltersComponent, LoadingStateComponent, EmptyStateComponent, ErrorStateComponent,
    DashboardKpiCardComponent, EquipmentSummaryComponent, SensorSummaryComponent],
  providers: [DashboardFacade],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DashboardComponent {
  readonly facade = inject(DashboardFacade);
}
