import { PREDICTION_ROUTES } from './predictions.routes';
import { routes } from '../../app.routes';

describe('Predictions lazy route', () => {
  it('declares only the full-match lazy list with its title', () => {
    expect(PREDICTION_ROUTES).toHaveLength(1);
    expect(PREDICTION_ROUTES[0]).toMatchObject({ path: '', pathMatch: 'full', title: 'Prédictions | Industrial Predict AI', data: { pageTitle: 'Prédictions' } });
    expect(typeof PREDICTION_ROUTES[0].loadComponent).toBe('function');
  });
  it('connects the global lazy route to the real list without a detail route', () => {
    const global = routes[0].children?.find(route => route.path === 'predictions');
    expect(typeof global?.loadChildren).toBe('function'); expect(global?.loadComponent).toBeUndefined();
  });
});
