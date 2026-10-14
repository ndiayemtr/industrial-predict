import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { IconComponent, LocalIconName } from '../../ui/icon/icon.component';

@Component({
  selector: 'app-empty-state',
  standalone: true,
  imports: [IconComponent],
  templateUrl: './empty-state.component.html',
  styleUrl: './empty-state.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class EmptyStateComponent {
  readonly title = input.required<string>();
  readonly message = input.required<string>();
  readonly icon = input<LocalIconName>();
}
