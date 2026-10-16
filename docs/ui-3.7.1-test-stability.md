# UI 3.7.1 - Diagnostic de stabilité 404 et Sidebar

Date : 16 octobre 2026 (UTC).

## Périmètre et décision

Branche contrôlée : `feature/frontend-companies`.
HEAD contrôlé : `ab9955174086afc1e9e836795adc0477fa2a06ed`.
État initial : `git status --short` vide.

Le défaut signalé (neuf liens Sidebar attendus, zéro obtenu dans les tests
404 pendant un build concurrent) n'est pas reproduit. Deux scénarios concurrents
ont produit respectivement deux puis un dépassement du timeout Vitest
de 5 000 ms dans les suites Sidebar et Shell responsive. Ces dépassements sont
distincts de l'assertion signalée et ne prouvent pas sa cause.

Aucune correction des tests, helpers, configurations ou composants n'est
appliquée. Toutes les assertions sont conservées, dont les neuf liens réels.
Ce document est le seul ajout destiné au suivi Git. Les journaux et builds de
diagnostic restent dans `frontend/tmp/ui-3.7.1/`, répertoire ignoré par Git.

## Signalement de départ

Informations fournies par l'utilisateur pendant ce diagnostic :

- UI 3.7 : 342 tests réussis et six échecs dans `not-found.component.spec.ts`.
- Parmi les assertions : neuf liens Sidebar attendus, zéro obtenu.
- Build et tests lancés simultanément.
- Six tests 404 réussis ensuite isolément, puis suite complète réussie sans build
  concurrent (348 tests).
- Commande exacte et sortie complète de la première exécution indisponibles.

## Environnement et examen du code

Windows, Node.js 24.21.0, Angular core 21.2.25, CLI/build 21.2.26,
Nebular 17.0.0, Vitest 4.1.11, jsdom 28.1.0, Dart Sass 1.97.3.
La machine expose huit processeurs logiques et environ 15,82 Gio de RAM.
Un relevé ponctuel pendant le premier scénario concurrent indiquait environ
1,34 Gio libres ; il ne constitue pas une mesure continue de la pression mémoire.

Fichiers examinés : tests 404, routing, Shell, focus, responsive, Header et
Sidebar ; composants et templates correspondants ; configuration de navigation ;
helper Dashboard ; `app.config.ts`, `angular.json`, `tsconfig.spec.json`,
`package.json` ; implémentations installées du harness Angular, de TestBed,
du builder Angular/Vitest et des composants Nebular.

Constats :

- `NAVIGATION_ITEMS` contient neuf destinations disponibles et deux entrées
  désactivées (Rapports et Administration). Le template rend les premières en
  ancres et les secondes en spans. L'attente de neuf liens est correcte.
- La Sidebar utilise une boucle synchrone `@for`, sans chargement réseau des
  entrées. `isNotFound` et `RouterLinkActive` règlent la sélection active, sans
  retirer les liens.
- Le Shell et les pages sont chargés par les imports dynamiques du Router.
  Aucun bloc Angular `@defer` n'est présent dans le Shell ou la Sidebar.
- `RouterTestingHarness.create(url)` attend `navigateByUrl`. Le harness attend
  la navigation et déclenche une détection. Le helper 404 ajoute déjà
  `fixture.detectChanges()`, `await fixture.whenStable()` et une détection finale.
- Les navigations ultérieures de la suite 404 attendent aussi `whenStable()`
  puis déclenchent une détection. Le retour Dashboard conserve l'instance du Shell.
- Les helpers des suites routing, focus et responsive appellent en plus
  `TestBed.tick()`. Cette API synchronise l'application Angular et ses vues de
  test ; ce n'est pas le `tick()` temporel de `fakeAsync`. La différence seule
  ne démontre pas que la suite 404 manque une phase de rendu.
- Les callbacks `afterNextRender` du Shell concernent le focus. Leur présence
  ne prouve pas une création différée des neuf liens.
- Le builder `@angular/build:unit-test` utilise Vitest et jsdom, les polyfills
  Zone.js hérités du build et le nettoyage TestBed avant/après les tests. Le
  plugin Angular configure `isolate: false` par défaut. Aucune configuration
  Vitest personnalisée n'est activée dans le dépôt. Une éventuelle interaction
  entre suites reste une piste, sans preuve observée de fuite de leur état.
- Les tests sont compilés en mémoire par le builder. Les builds concurrents
  ci-dessous ont des sorties temporaires distinctes ; aucune collision sur
  `dist/` n'est recherchée ni provoquée.

## Reproductions et résultats

Toutes les commandes sont lancées depuis `frontend/`, avec le CLI installé :

```powershell
node node_modules/@angular/cli/bin/ng.js test --watch=false --include=src/app/shared/pages/not-found/not-found.component.spec.ts
node node_modules/@angular/cli/bin/ng.js test --watch=false
node node_modules/@angular/cli/bin/ng.js build --configuration=production --output-path=tmp/ui-3.7.1/baseline-production
```

Chaque répétition est un nouveau processus CLI. Aucun retry automatique,
timeout augmenté, `skip`, `only`, `flaky` ou délai ajouté.
Les trois passages complets séquentiels sont réalisés sans build concurrent,
avec les mêmes tests et la configuration du HEAD de référence.

| Essai | Résultat | Durée Vitest | Journal dans `frontend/tmp/ui-3.7.1/` |
| --- | --- | --- | --- |
| 404 isolé 1 | 6/6 | 13,05 s | Sortie terminal, premier lancement hors bac à sable |
| 404 isolé 2 | 6/6 | 11,16 s | `baseline-isolated-2.log` |
| 404 isolé 3 | 6/6 | 9,24 s | `baseline-isolated-3.log` |
| Suite complète séquentielle 1 | 348/348, 31 fichiers | 26,62 s | `baseline-full.log` |
| Suite complète séquentielle 2 | 348/348, 31 fichiers | 27,65 s | `baseline-full-2.log` |
| Suite complète séquentielle 3 | 348/348, 31 fichiers | 25,69 s | `baseline-full-3.log` |
| Suite complète + build production simultanés | 346/348 ; 404 : 6/6 ; build réussi | 44,40 s | `baseline-concurrent-tests.log`, `baseline-concurrent-build.log` |
| 404 isolé + build production simultanés | 6/6 ; build réussi | 9,76 s | `concurrent-404.log`, `concurrent-404-build.log` |
| Suite complète + build lancé au signal Vitest RUN | 347/348 ; 404 : 6/6 ; build réussi | 37,83 s | `runtime-concurrent-tests.log`, `runtime-concurrent-build.log` |

Premier scénario concurrent : les deux processus sont lancés ensemble. Le build
termine à 10:27:39 UTC ; Vitest débute à 10:27:41 UTC après la compilation des
tests. Le chevauchement vérifié porte donc sur les phases de compilation et
de préparation, sans preuve d'un chevauchement du build avec les assertions
elles-mêmes. L'échec des tests survient après cette contention initiale.

Les deux échecs sont exactement :

- Sidebar : `should render all eleven entries in order inside a single Nebular
  sidebar`, durée rapportée 5 872 ms, erreur `Test timed out in 5000ms`.
- Shell responsive : initialisation à 1440 px, durée rapportée 5 333 ms,
  même erreur de timeout.

Aucune erreur « neuf liens attendus, zéro reçu » dans ce lancement.
Le deuxième scénario termine la compilation des tests à 10:31:25 UTC, démarre
Vitest à 10:31:26 UTC et termine le build à 10:31:27 UTC. Il vérifie un bref
chevauchement du build avec le démarrage de Vitest, sans erreur 404.

Troisième scénario : le script temporaire `runtime-concurrency.mjs` lance la
suite complète, détecte son message `RUN v4...` et démarre alors le build.
Le déclenchement repose sur cette sortie du processus, sans temporisation ni
modification des tests. Commande :

```powershell
node tmp/ui-3.7.1/runtime-concurrency.mjs
```

Les événements sont conservés dans `runtime-concurrent-events.json` : build
lancé à 10:33:10.954 UTC, tests terminés à 10:33:49.260 UTC, build terminé à
10:33:53.463 UTC. Le chevauchement couvre bien la phase Vitest (début rapporté
à 10:33:11 UTC). La suite Sidebar présente un timeout sur le même premier test
(5 515 ms). Toutes les autres suites passent, dont les six tests 404. Cette
reproduction renforce le constat de sensibilité à la charge, sans reproduire
une Sidebar contenant zéro lien.

Au total, les six tests 404 passent dans neuf lancements exploitables, soit
54 exécutions de cas réussies. Ces répétitions de diagnostic sont explicites,
sans mécanisme de relance automatique dans la suite.

Les trois suites complètes séquentielles réussies incluent les 12 tests Sidebar,
les deux tests Shell routing, les tests focus/responsive et les autres suites
de routing, Dashboard et Companies.

Deux premiers essais dans le bac à sable Windows ont échoué avant toute
exécution de test : `EPERM` lors du renommage d'un fichier temporaire de cache
Vitest. Ils ne sont pas comptés comme des exécutions des six tests 404.
Les validations exploitables utilisent les mêmes commandes hors du bac à sable,
sans modification du dépôt pour contourner cette limitation d'environnement.

## Contrôles complémentaires

- `node --test scripts/apply-nebular-sass-fix.test.mjs` : 5/5 réussis.
- Inspection non mutante du patch installé : deux fichiers et quatre expressions
  conformes ; aucun changement nécessaire dans `node_modules`.
- `node scripts/verify-nebular-breakpoints.mjs` : quatre expressions, huit
  breakpoints, media queries et thème unique validés.
- Premier build production temporaire : réussi, initial 600,89 kB,
  transfert estimé 153,15 kB ; Dashboard différé 45,38 kB.
- Warning existant : budget initial 500 kB dépassé de 100,89 kB. Budgets
  inchangés ; aucune nouvelle dépréciation Sass observée dans ce build.
- Build production final isolé : réussi, mêmes tailles et seul warning de
  budget initial. Commande :

```powershell
node node_modules/@angular/cli/bin/ng.js build --configuration=production --output-path=tmp/ui-3.7.1/final-production
```

Comparaison SHA-256 de tous les fichiers, chemins relatifs et tailles compris :
les 26 fichiers de `baseline-production/` et `final-production/` sont identiques,
pour 750 618 octets au total. Le manifeste est conservé dans
`bundle-comparison.json`. Aucun accroissement du bundle ni changement des
artefacts applicatifs. Les sorties préexistantes dans `frontend/dist/` n'ont
été ciblées par aucune commande de build de ce diagnostic.

`git diff --check` réussit. Le nouveau rapport, non suivi, est également vérifié
par `git diff --no-index --check -- NUL docs/ui-3.7.1-test-stability.md` depuis
la racine du dépôt. Aucun tiret cadratin dans le rapport. Aucun fichier suivi
préexistant n'est modifié.

## Recommandation et limites

Conserver les tests actuels. Pour les validations de livraison sur cette
machine, exécuter les tests puis le build séquentiellement, sans changer la
configuration ou la couverture des tests. La contention est une explication
vérifiée des timeouts reproduits, et seulement une piste pour le défaut 404
rapporté.

Avant une correction, obtenir une nouvelle trace du défaut précis : commande,
versions, tests précédents, assertions, état DOM du Shell et de la Sidebar,
état de stabilité Angular et éventuelles erreurs de cycle de vie. Si cette trace
établit une phase Angular manquante, évaluer alors un helper local de
synchronisation avec les API Angular standard et comparer avant/après dans les
mêmes conditions. Ne pas ajouter `TestBed.tick()` sur la seule différence avec
les autres helpers, ni augmenter les délais pour masquer la contention.

Les succès répétés ne garantissent pas l'absence de défaut intermittent. Le
contexte exact de l'échec UI 3.7 et l'ordre d'exécution de ses suites ne sont pas
connus. Aucun correctif ni garantie de stabilisation du défaut « zéro lien »
n'est revendiqué. Aucun changement backend, PostgreSQL, Dashboard ou Companies,
aucun package ajouté, aucun commit, push ou merge ; UI 3.8 non commencée.

La validation utilisateur est attendue avant toute correction.

## État Git final

Branche et HEAD inchangés. `git status --short` :

```text
?? docs/ui-3.7.1-test-stability.md
```

Seul fichier ajouté : ce rapport. Aucun test, helper ou fichier applicatif
modifié. Les scripts, journaux et builds sous `frontend/tmp/` restent ignorés.
