import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

// Local, decorative SVGs: one coordinate system and stroke weight, no icon font.
const ICON_PATHS = {
  dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  companies: 'M5 21V3h14v18 M3 21h18 M9 7h1 M14 7h1 M9 11h1 M14 11h1 M10 21v-6h4v6',
  sites: 'M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
  equipments: 'M4 21V10l6 3V8l6 3V3h4v18H4Z M8 17h1 M13 17h1 M18 17h1',
  sensors: 'M10 19a2 2 0 1 0 4 0 2 2 0 0 0-4 0 M8 13a6 6 0 0 1 8 0 M5 9a10 10 0 0 1 14 0 M2 5a15 15 0 0 1 20 0',
  measurements: 'M3 3v18h18 M6 15l4-5 4 3 6-8',
  maintenance: 'M14 6a5 5 0 0 0-6 6L3 17a3 3 0 0 0 4 4l5-5a5 5 0 0 0 6-6l-3 3-4-4 3-3Z',
  predictions: 'M3 20V4 M3 20h18 M6 16l5-6 4 2 6-8 M16 4h5v5',
  recommendations: 'M9 18h6 M9 21h6 M8 14a7 7 0 1 1 8 0l-1 4H9l-1-4Z',
  reports: 'M14 3H5v18h14V8l-5-5Z M14 3v5h5 M8 12h8 M8 16h6',
  administration: 'M4 3v5 M4 12v9 M12 3v10 M12 17v4 M20 3v2 M20 9v12 M1 8h6v4H1z M9 13h6v4H9z M17 5h6v4h-6z',
  notifications: 'M6 9a6 6 0 0 1 12 0v5l2 3H4l2-3V9Z M9 20a3 3 0 0 0 6 0',
  profile: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z M4 21v-2a8 8 0 0 1 16 0v2',
} as const;

export type LocalIconName = keyof typeof ICON_PATHS;

@Component({
  selector: 'app-icon',
  standalone: true,
  template: `<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false"
    fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">
    <path [attr.d]="path()" />
  </svg>`,
  styles: ':host { display: inline-flex; flex: 0 0 auto; } svg { display: block; }',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class IconComponent {
  readonly name = input.required<LocalIconName>();
  readonly path = computed(() => ICON_PATHS[this.name()]);
}
