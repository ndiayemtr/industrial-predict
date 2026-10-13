import { Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { NbCardModule } from '@nebular/theme';

@Component({
  selector: 'app-feature-placeholder',
  standalone: true,
  imports: [NbCardModule],
  templateUrl: './feature-placeholder.component.html',
  styleUrl: './feature-placeholder.component.scss'
})
export class FeaturePlaceholderComponent {
  readonly title = inject(ActivatedRoute).snapshot.data['pageTitle'] as string;
}
