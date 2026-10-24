import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { PredictionRead } from '../../models/prediction.model';
import { predictionDetails } from '../../utils/prediction-display';
import { predictionJsonPreview } from '../../utils/prediction-json-preview';

@Component({
  selector: 'app-prediction-details', standalone: true, changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './prediction-details.component.html', styleUrl: './prediction-details.component.scss'
})
export class PredictionDetailsComponent {
  readonly prediction = input.required<PredictionRead>();
  readonly view = computed(() => predictionDetails(this.prediction()));
  readonly preview = computed(() => predictionJsonPreview(this.prediction().details));
}
