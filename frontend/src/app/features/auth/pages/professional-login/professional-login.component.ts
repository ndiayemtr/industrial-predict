import { ChangeDetectionStrategy, Component, computed, inject, OnDestroy, OnInit } from '@angular/core';
import { NbCardModule } from '@nebular/theme';
import { IconComponent } from '../../../../shared/ui/icon/icon.component';
import { ProfessionalAuthService } from '../../professional-auth.service';

@Component({
  selector: 'app-professional-login',
  standalone: true,
  imports: [NbCardModule, IconComponent],
  templateUrl: './professional-login.component.html',
  styleUrl: './professional-login.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfessionalLoginComponent implements OnInit, OnDestroy {
  readonly auth = inject(ProfessionalAuthService);
  readonly availabilityLabel = computed(() => {
    const state = this.auth.state();
    if (state.status === 'unavailable' && state.reason === 'service') return 'Service indisponible';
    return this.auth.authenticated() ? 'Session professionnelle'
      : this.auth.busy() ? 'Connexion sécurisée' : this.auth.backendReady() ? 'Connexion disponible' : 'Bientôt disponible';
  });

  ngOnInit(): void { this.auth.initialize(); }
  ngOnDestroy(): void { this.auth.cancelLogin(); }
}
