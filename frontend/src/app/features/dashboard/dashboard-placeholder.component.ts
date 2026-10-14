import { Component } from '@angular/core';
import { NbCardModule } from '@nebular/theme';

@Component({
  selector: 'app-dashboard-placeholder',
  standalone: true,
  imports: [NbCardModule],
  templateUrl: './dashboard-placeholder.component.html',
  styleUrl: './dashboard-placeholder.component.scss'
})
export class DashboardPlaceholderComponent {}
