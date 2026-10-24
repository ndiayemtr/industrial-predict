import { PREDICTION_ROUTES } from './predictions.routes';
import { routes } from '../../app.routes';

describe('Predictions internal lazy route', () => {
  it('declares only the full-match lazy list with its title', () => {
    expect(PREDICTION_ROUTES).toHaveLength(1);
    expect(PREDICTION_ROUTES[0]).toMatchObject({ path: '', pathMatch: 'full', title: 'Prédictions | Industrial Predict AI', data: { pageTitle: 'Prédictions' } });
    expect(typeof PREDICTION_ROUTES[0].loadComponent).toBe('function');
  });
  it('leaves the global placeholder in place until UI 9.5', () => {
    const global = routes[0].children?.find(route => route.path === 'predictions');
    expect(global?.loadChildren).toBeUndefined(); expect(typeof global?.loadComponent).toBe('function');
  });
});
