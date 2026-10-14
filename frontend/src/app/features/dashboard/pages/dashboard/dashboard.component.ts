import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { DashboardFiltersComponent } from '../../components/dashboard-filters/dashboard-filters.component';
import { DashboardFacade } from '../../dashboard.facade';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [PageHeaderComponent, DashboardFiltersComponent, LoadingStateComponent, EmptyStateComponent, ErrorStateComponent],
  providers: [DashboardFacade],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DashboardComponent {
  readonly facade = inject(DashboardFacade);
}
