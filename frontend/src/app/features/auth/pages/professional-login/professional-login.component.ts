import { ChangeDetectionStrategy, Component } from '@angular/core';
import { NbCardModule } from '@nebular/theme';
import { IconComponent } from '../../../../shared/ui/icon/icon.component';
import { PROFESSIONAL_CONNECTION_PREPARATION } from '../../professional-connection.model';

@Component({
  selector: 'app-professional-login',
  standalone: true,
  imports: [NbCardModule, IconComponent],
  templateUrl: './professional-login.component.html',
  styleUrl: './professional-login.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfessionalLoginComponent {
  readonly preparation = PROFESSIONAL_CONNECTION_PREPARATION;
}
