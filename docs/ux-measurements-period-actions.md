# Finition UX Measurements - Actions de période

Branche `feature/frontend-maintenance`, HEAD initial `d74a3e6`, dépôt initial
propre. Modification de présentation uniquement sur `/measurements`.

## Périmètre

- [Template](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.html) : les deux boutons sont regroupés dans une ligne dédiée immédiatement après les deux fieldsets temporels.
- [SCSS local](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.scss) : la ligne d’actions occupe toute la largeur de la grille, avec alignement naturel à gauche, espacement existant et repli flex sur petit écran ; la grille desktop contient les deux groupes de champs seuls.
- [Test du composant](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.spec.ts) : ordre des deux groupes et de la ligne d’actions, six inputs, libellés et sémantique submit/bouton, primaire/secondaire.
- Présent rapport dédié. Aucun rapport historique modifié.

Les groupes Début inclus (UTC) et Fin exclue (UTC) sont conservés. Sur desktop,
leurs six champs occupent leur ligne, les deux actions la suivante. Tablette et
mobile conservent le repli des groupes ; les boutons se placent côte à côte si
la place suffit, sinon se replient sans dépasser la largeur disponible.

Les handlers applyPeriod et clearFilters sont inchangés, tout comme le TypeScript
du composant, la façade, les utilitaires temporels, les services API et les modèles.
Aucun changement de brouillon, filtres appliqués, microsecondes, offsets,
pagination, contexte URL, contrat GET ou décision MES-01 à MES-12. Effacer les
critères conserve sa portée existante ; aucune logique Maintenance transposée.

Aucun changement du module Maintenance, des styles partagés ou globaux. Aucun
backend, package, migration, SQL, PostgreSQL ou Docker. Aucun formulaire métier,
écriture ou route détail ajoutés. UI 8.4 non commencée.

## Validation

- **37 tests ciblés du composant réussis**, dont un nouveau test structurel.
  Commande : `npx ng test --watch=false --include='src/app/features/measurements/pages/measurements-list/measurements-list.component.spec.ts' --runner-config=tmp/ux-measurements-time-actions/vitest.config.mjs`.
- **1 804 tests Angular réussis sur 70 fichiers**, suite complète exécutée une
  seule fois après stabilisation : `npx ng test --watch=false --runner-config=tmp/ux-measurements-time-actions/vitest.config.mjs`.
- **Build production réussi, une seule exécution** :
  `npx ng build --configuration production`. Aucun budget modifié.
- Initial inchangé : **605 752 octets, 605,75 kB**. Chunk Measurements List :
  **39 459 octets, 39,46 kB**, hausse de 51 octets. Total JS/CSS émis :
  1 085 916 octets, hausse de 51 octets par rapport au build précédent.
- CSS local compilé/minifié Sass/esbuild : **3 987 octets** (contre 3 972),
  sous le seuil de 4 000. **Aucun nouvel avertissement**, aucun dépassement SCSS
  au build. Seul subsiste l’avertissement initial existant : +105,75 kB au budget
  de 500 kB. Aucun package ajouté pour les mesures.

Recette sur build production et fixtures locales GET, port 8098, sans proxy
FastAPI ni PostgreSQL ; serveur arrêté après contrôle. Mesures DOM, styles
calculés et captures réellement réalisés :

| Cible CSS | Obtenue | Actions sous les 6 champs | Disposition des boutons | Débordement global |
| --- | --- | --- | --- | --- |
| 1440 | 1440 | Oui | Même ligne, à gauche | Aucun |
| 1024 | 1024 | Oui | Même ligne, à gauche | Aucun |
| 1023 | 1023 | Oui | Même ligne, à gauche | Aucun |
| 768 | 768 | Oui | Même ligne, à gauche | Aucun |
| 390 | **389 et 391** | Oui | Repli sur deux lignes, à gauche | Aucun |
| 320 | 320 | Oui | Repli sur deux lignes, à gauche | Aucun |

Hauteur des boutons : 44 px ; fond primaire #2563eb et secondaire blanc
conservés. Aucun contrôle hors largeur. À 320, les conteneurs du Shell, main,
la page et le panneau de filtres ont également scrollWidth = clientWidth ;
seul le tableau défile localement. Tab depuis Fraction de fin atteint Appliquer,
puis Effacer ; focus-visible avec contour solid sur les deux boutons.

Captures locales, ignorées par Git :
[desktop 1440 CSS](../frontend/tmp/ux-measurements-time-actions/screenshots/measurements-actions-1440.jpg),
[mobile 320 CSS avec focus](../frontend/tmp/ux-measurements-time-actions/screenshots/measurements-actions-320.jpg).
Elles sont disponibles cette fois, sans réécrire les réserves des rapports
historiques. Réserve maintenue : 390 exact non obtenu à cause de l’arrondi du
zoom ; 389 et 391 sont vérifiés. Pas de recette DEV ni d’audit lecteur d’écran
complet revendiqués. Journaux et mesures dans frontend/tmp/ux-measurements-time-actions.


## État Git

Quatre fichiers attendus : template, SCSS et test Measurements existants, plus
ce rapport. Liens locaux et `git diff --check` contrôlés ; aucun secret ni artefact
dans le périmètre versionnable. HEAD `d74a3e6` inchangé. Index vide ; aucun commit, push, merge ou rebase. Validation attendue.
