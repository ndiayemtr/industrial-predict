# IndustrialPredictUi

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 21.2.26.

## Development server

Le démarrage permanent utilise Angular sur `127.0.0.1:4201`, FastAPI sur
`127.0.0.1:8001` et PostgreSQL `industrial_predict_dev` sur `127.0.0.1:5434`.
Suivre le [guide DEV](../infra/development/README.md) pour le démarrage, le
contrôle d'identité et l'arrêt, avec la configuration privée existante hors Git.
Ne pas réinitialiser la base pour résoudre un problème de lancement.

`ng serve` / `npm start` sans le lanceur dédié utilisent encore le proxy
historique vers 8000 et le port Angular par défaut 4200. Ils ne constituent pas
la procédure DEV ci-dessus. Le lanceur permanent impose sa cible, vérifie
l'identité et ne possède aucun repli vers l'API historique.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Vitest](https://vitest.dev/) test runner, use the following command:

```bash
npm test -- --watch=false
```

## Running end-to-end tests

Aucune cible `ng e2e` n'est configurée. Les tests Angular emploient Vitest et
HttpTestingController ; le [simulateur Sites](../docs/ui-4.6.2-site-code-simulation.md)
permet des parcours locaux en mémoire sans connexion FastAPI/PostgreSQL.
La validation réelle et ses limites sont consignées séparément dans les rapports
[UI 4.7.4](../docs/ui-4.7.4-real-sites-crud.md) et
[UI 4.7.5](../docs/ui-4.7.5-sites-closure.md).

La référence actuelle Équipements est **864 tests Angular réussis dans 49 fichiers**
et un build production réussi (UI 5.6.1), initial **604,81 ko** pour un budget de
500 ko. [UI 5.7](../docs/ui-5.7-equipments-integration.md) distingue POST 201/PATCH
200 et persistance PostgreSQL réels des erreurs 409/422 d'écriture et doubles
soumissions simulées. Le dialogue natif d'abandon reste partiellement non validé.

Exécuter tests et build séquentiellement après modification exécutable ; aucune
relance pour UI 5.8 documentaire. Voir le [statut courant](../docs/project-status.md#équipements-mvp---livraison-préparée-ui-58)
et la [checklist de livraison](../docs/ui-5.8-equipments-delivery.md).
Les références Sites ci-dessus restent historiques et ne sont pas réécrites.

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.
