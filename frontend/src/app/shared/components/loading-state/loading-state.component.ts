import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

const DEFAULT_MESSAGE = 'Chargement des données…';

@Component({
  selector: 'app-loading-state',
  standalone: true,
  templateUrl: './loading-state.component.html',
  styleUrl: './loading-state.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class LoadingStateComponent {
  readonly message = input(DEFAULT_MESSAGE);
  readonly announcement = computed(() => this.message().trim() || DEFAULT_MESSAGE);
}
