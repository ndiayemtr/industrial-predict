import { provideHttpClient } from '@angular/common/http';
import { ApplicationConfig, importProvidersFrom, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { provideAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { NbGlobalPhysicalPosition, NbSidebarModule, NbThemeModule, NbToastrModule } from '@nebular/theme';

import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(),
    // Nebular 17 still requires Angular's legacy animation providers.
    provideAnimations(),
    importProvidersFrom(
      NbThemeModule.forRoot(
        { name: 'industrial-predict' },
        [{ name: 'industrial-predict', base: 'default', variables: {} }]
      ),
      NbSidebarModule.forRoot(),
      NbToastrModule.forRoot({
        position: NbGlobalPhysicalPosition.TOP_RIGHT,
        duration: 5000,
        hasIcon: false,
        // Nebular 17 derives icon visibility from icon.icon, ignoring hasIcon alone.
        icon: { icon: '' },
        destroyByClick: false
      })
    )
  ]
};
