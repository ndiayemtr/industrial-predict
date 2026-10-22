# UI 7.4 - Fiche détail Measurements

22 octobre 2026. Branche feature/frontend-measurements, HEAD de départ bbd18d6.
Dépôt propre au démarrage. Implémentation selon les décisions MES-01 à MES-12
validées dans [UI 7.1](etape-ui-7.1-measurements.md), le contrat
[UI 7.2](ui-7.2-measurements-data-access.md) et la
[liste UI 7.3 / UI 7.3.1](ui-7.3-measurements-list.md).

Fiche strictement en lecture seule. Aucun backend, SQL, migration, Docker,
package, budget ou donnée PostgreSQL modifié. Aucun commit, push ou merge.
UI 7.5 non commencée.

## 1. Périmètre et fichiers

Douze fichiers concernés, six existants modifiés et six nouveaux :

| Fichier | Intervention |
| --- | --- |
| [Routes](../frontend/src/app/features/measurements/measurements.routes.ts) | Ajout lazy de :measurementId après la liste, deux routes en full-match |
| [Tests des routes](../frontend/src/app/features/measurements/measurements.routes.spec.ts) | Shell, titre, navigation active, détail, id invalide et chemins non livrés |
| [Liste TypeScript](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.ts) | RouterLink et présentation partagée des valeurs et qualités |
| [Liste HTML](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.html) | Références devenues de vrais liens, retrait de la notice de fiche future |
| [Liste SCSS](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.scss) | Lien accessible et focus ; regroupement des grilles équivalentes |
| [Tests de liste](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.spec.ts) | Liens actifs et aller-retour réel au sein du RouterTestingHarness |
| [Détail TypeScript](../frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.ts) | Nouveau composant, chargement et références séparées, annulation et navigation |
| [Détail HTML](../frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.html) | Cinq champs, chaîne industrielle, unité actuelle et erreurs |
| [Détail SCSS](../frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.scss) | Actions harmonisées, grille responsive, retour à la ligne et focus |
| [Tests de détail](../frontend/src/app/features/measurements/pages/measurement-detail/measurement-detail.component.spec.ts) | 56 scénarios de lecture, références, données et erreurs |
| [Présentation Measurements](../frontend/src/app/features/measurements/utils/measurement-display.ts) | Libellés typés des cinq qualités et format numérique commun liste/détail |
| Le présent rapport | Conception réalisée, preuves, résultats et limites |

MeasurementsApiService, modèles Read/query, utilitaires temporels et façade de
liste inchangés. Aucun composant shared, style global ou module Sensors/Equipments
modifié. Le regroupement SCSS de liste conserve les pistes minmax(0, 1fr) et retire
des min-width redondants, sans déplacer les styles pour contourner leur budget.

## 2. Route et données affichées

- /measurements reste la liste lazy ; /measurements/:measurementId charge le
  détail lazy, titre Détail mesure et navigation Mesures active dans le Shell.
- Pas de route de création ou d'édition. /measurements/new est traité comme id
  invalide, sans HTTP ni formulaire ; /measurements/23/edit reste en 404 globale.
- Un id doit être un entier positif sûr, en notation décimale. Valeur nulle,
  négative, décimale, scientifique, alphabétique ou hors précision sûre refusée
  avant HTTP. Un accès direct par id est permis par le contrat validé.
- Seul GET /api/v1/measurements/{id} lit la mesure, sans query de contexte.
  Aucun endpoint spécialisé par Sensor, aucune lecture globale ou écriture.

La section Informations de la mesure contient exactement les cinq champs réels :
id, sensor_id, timestamp, value, quality, avec leurs libellés français.
Pas de nom, code, description, auteur, dates administratives, provenance ou
métadonnées de mesure inventés. Les références industrielles sont dans une section
séparée et proviennent de leurs propres réponses API.

L'horodatage est affiché explicitement en UTC via formatMeasurementUtc, avec
secondes et chiffres fractionnaires conservés jusqu'à six décimales. Le même champ
est également présenté comme chaîne ISO source, offset original compris ;
time.datetime conserve cette chaîne. Exemple de recette :
2026-10-22T17:30:00.999991+05:30 et 22/10/2026 à 12:00:00.999991 UTC.
Aucun Date, DatePipe, conversion locale implicite, ajout de Z ou arrondi.
L'offset reçu ne prouve pas le fuseau IANA d'acquisition.

La valeur utilise String sur le nombre reçu et une virgule d'affichage française,
sans toFixed, arrondi métier, conversion d'unité ou substitution de zéro. Zéro,
moins zéro, négatifs, très petits et grands nombres restent distincts ; une
notation scientifique peut apparaître. La précision lexicale déjà perdue par le
float backend ou JSON/JavaScript Number ne peut pas être reconstituée.
Le service existant bloque null, booléen, chaîne numérique, NaN et Infinity,
ainsi que les id, timestamp et qualités hors contrat, avant toute référence.

Libellés communs à la liste : good Bonne, suspect Suspecte, bad Mauvaise,
missing Manquante, estimated Estimée. La fiche précise qu'il s'agit d'une qualité
déclarée, sans certification physique. missing ne signifie pas une valeur zéro
ou une mesure absente. La valeur zéro vue dans les captures est fournie par la
fixture ; les réponses invalides sont refusées, jamais remplacées par zéro.

## 3. Références réelles et tolérance aux erreurs

Chaîne séquentielle Measurement.sensor_id -> Sensor.equipment_id ->
Equipment.site_id -> Site.company_id -> Company, via les services existants.
Chaque identifiant demandé est positif et sûr ; l'id reçu doit correspondre à
celui demandé. Les FK suivantes sont validées avant leur requête. Aucun parent
n'est déduit de l'URL, d'un catalogue, d'un premier résultat ou du type de capteur.

Dès le GET Measurement réussi, les cinq champs restent visibles pendant la
résolution. Chaque parent possède un état attente, chargement, succès ou erreur.
Un échec conserve la mesure et les parents déjà vérifiés ; les descendants
restent explicitement non résolus. Erreur de référence affichée séparément de
l'erreur de chargement Measurement. Aucune incohérence n'est corrigée côté client.

Le lien vers /sensors/{id} n'existe qu'après lecture de la référence Sensor réelle.
Son nom/code et type sont issus de cette réponse. L'unité actuelle provient
uniquement de Sensor.unit. Si le Sensor est indisponible ou l'unité vide, un texte
indique son indisponibilité ; aucune déduction par sensor_type. La réserve
« ne constitue pas une unité historique garantie » est toujours affichée.

404 Measurement : fiche introuvable distincte. 404 parent : données de mesure
conservées. 400/422, 401/403, réseau/5xx et contrat de réponse invalide sont
traités sans afficher du HTML serveur. Relance manuelle proposée uniquement pour
réseau/5xx, sans retry automatique. Une relance de référence recommence sa chaîne
à Sensor et ne relit pas Measurement. Elle peut donc relire des ancêtres déjà
résolus ; ce choix minimal est documenté, sans cache global ni polling.

switchMap et toSignal annulent les anciens chargements lors d'un changement
d'id ou de destruction. Le passage à un autre id retire immédiatement les données
précédentes. Un changement de seuls paramètres de retour ne relance pas les GET.

## 4. Navigation et contexte

Les liens de liste utilisent les paramètres URL appliqués avec preserve et
preserveFragment. Un brouillon temporel non appliqué ne passe pas au détail.
Retour à la liste conserve les parents, qualité, bornes exactes, page, page_size,
paramètres distincts return_sensor_*, paramètres inconnus/répétés et fragment.
Les valeurs ne sont ni normalisées ni utilisées comme preuves de rattachement.
Un contexte contradictoire déclenche une notice ; le retour reste inchangé.
Même un filtre de retour invalide est conservé : la liste le validera et bloquera
si nécessaire, au lieu de lancer silencieusement une lecture élargie.

Vers le Sensor, le contexte Sensors est séparé : snapshot return_sensor_*
whitelisté et borné (ids, pagination, search <=100 caractères et status autorisé),
s'il est complet et valide. Sinon, parents réellement résolus avec page=1 et
page_size=20. Sans chaîne complète, lien par id Sensor réel sans fabriquer des
parents. Aucun filtre quality ou période Measurements recyclé dans Sensors.
Un returnUrl arbitraire n'est jamais suivi. L'action Sensor -> Measurements
n'est pas ajoutée à cette étape ; UI 7.5 reste hors périmètre.

## 5. Tests et build réellement exécutés

Depuis frontend, runner local ignoré à deux workers, sans nouveau package,
timeout relevé, exclusion ou test backend/SQL :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-7.4/vitest.config.mjs --include=src/app/features/measurements/**/*.spec.ts --include=src/app/app.routes.spec.ts --include=src/app/layout/sidebar/sidebar.component.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-7.4/vitest.config.mjs
npm.cmd run build -- --configuration production --stats-json
```

| Contrôle final | Résultat |
| --- | --- |
| Ciblage Measurements, routage et Sidebar | 310 tests réussis, 9 fichiers |
| Suite Angular complète | 1 456 tests réussis, 65 fichiers, Vitest 48,74 s |
| Build production | Réussi, 21,670 s |
| git diff --check et contrôles de contenu | Réussis |

58 tests nets ajoutés par rapport aux 1 398 de UI 7.3.1 : 56 cas de détail,
un aller-retour de liste et une évolution nette des routes. Couverture des cinq
champs/qualités, UTC/source ISO, nombres finis et invalides, ids invalides,
404/réseau/serveur, quatre niveaux de référence absents/incohérents, FK invalides,
relances sans relecture de mesure et annulation des requêtes obsolètes.
Les 126 tests du service UI 7.2 sont inclus, leur source et leur contrat inchangés.
Tests HTTP Angular simulés, sans FastAPI ni PostgreSQL.

Bundle initial : 605 340 octets, soit 605,34 kB, inchangé depuis bbd18d6.
Nouveau chunk lazy détail : 15 020 octets. Chunk de liste : 39 908 octets contre
43 791, en partie grâce aux fonctions désormais partagées entre les deux pages.
Cela ne signifie pas une diminution totale : ensemble JS/CSS émis 1 036 068 octets
contre 1 020 764, soit +15 304 octets. Les deux pages restent lazy.
Avertissement initial existant à 500 kB maintenu, dépassement de 105,34 kB.
Aucun avertissement de style sur le build final. Budgets initial et composants
inchangés, aucun fractionnement artificiel des styles.

## 6. Recette navigateur et responsive

Build production servi sur 127.0.0.1:8099 avec fixtures synthétiques locales
GET uniquement, sans proxy, API DEV, connexion SQL ou donnée industrielle réelle.
Ces fixtures sont uniquement dans frontend/tmp/ui-7.4, ignoré par Git.
Aucun appel n'a été fait à PostgreSQL ou aux services métier réels.

Parcours exécuté : liste du capteur 17, parents 7/9/12, qualité missing, intervalle
avec +05:30 et six décimales, page=2, page_size=1 et fragment history. Lien Mesure
#992, détail, puis retour à la liste : Page 2 sur 8 et tous les paramètres conservés.
Le lien Sensor utilise /sensors/17 avec les parents réels et page=1/page_size=20.

Fixture de mesure 2001 avec référence Sensor indisponible : cinq champs conservés,
message Capteur indisponible, unité indisponible et aucun faux lien Sensor.
GET détail inexistant : Mesure introuvable (404). Id abc : Identifiant invalide,
sans GET de mesure. Les erreurs réseau, réponses tardives et références incohérentes
supplémentaires sont couvertes par les tests simulés, pas revendiquées comme une
recette FastAPI. Trace navigateur : 45 GET, dont cinq GET détail sans query.
Aucun POST, PATCH ou DELETE. Aucun warning/erreur console relevé en fin de recette.

| Cible CSS | Mesurée | Colonnes des champs | Débordement global |
| --- | ---: | --- | --- |
| 1440 | 1440 | 2, timestamp pleine largeur | Aucun |
| 1024 | 1024 | 2, timestamp pleine largeur | Aucun |
| 1023 | 1023 | 2, timestamp pleine largeur | Aucun |
| 768 | 768 | 2, timestamp pleine largeur | Aucun |
| 390 | 389 et 391 | 1 | Aucun |
| 320 | 320 | 1 | Aucun |

scrollWidth égale clientWidth aux sept mesures. Cinq champs et timestamp complet
présents à chaque largeur. Retour et lien Sensor font 44 px de haut. Focus clavier
visible confirmé à 320 px par Maj+Tab de Sensor vers Retour. Les labels, dl/dt/dd,
time, sections nommées, états de chargement et alertes réutilisent les conventions
existantes. Pas d'audit exhaustif de lecteur d'écran ou de tous les navigateurs.

Réserve identique à UI 7.3.1 : zoom outil 0,75 et dimensions physiques entières ;
390 CSS demanderait 292,5 physiques. Contrôle encadrant à 389 et 391, sans annoncer
390 exact. Captures brutes non recomposées ; elles peuvent inclure la zone vide
du canevas du navigateur. La liste a aussi été recontrôlée aux sept largeurs après
le regroupement de son SCSS : périodes et liens conservés, aucun débordement global.

Pièces locales de recette, non destinées au commit :

- [Desktop 1440](../frontend/tmp/ui-7.4/screenshots/measurement-detail-1440.png),
  [1024](../frontend/tmp/ui-7.4/screenshots/measurement-detail-1024.png),
  [1023](../frontend/tmp/ui-7.4/screenshots/measurement-detail-1023.png).
- [Tablette 768](../frontend/tmp/ui-7.4/screenshots/measurement-detail-768.png),
  [mobile 389](../frontend/tmp/ui-7.4/screenshots/measurement-detail-390-near-389.png),
  [mobile 391](../frontend/tmp/ui-7.4/screenshots/measurement-detail-390-near-391.png),
  [mobile 320](../frontend/tmp/ui-7.4/screenshots/measurement-detail-320.png).
- [Focus clavier](../frontend/tmp/ui-7.4/screenshots/measurement-detail-keyboard-320.png),
  [référence indisponible](../frontend/tmp/ui-7.4/screenshots/measurement-parent-missing-320.png).
- [Mesures responsive](../frontend/tmp/ui-7.4/responsive.json),
  [non-régression visuelle liste](../frontend/tmp/ui-7.4/list-regression-responsive.json),
  [synthèse navigateur](../frontend/tmp/ui-7.4/browser-summary.json),
  [trace HTTP synthétique](../frontend/tmp/ui-7.4/http-audit.json),
  [bundle avant](../frontend/tmp/ui-7.4/bundle-before.json) et
  [après](../frontend/tmp/ui-7.4/bundle-after.json).

Serveur synthétique arrêté, override de viewport retiré et onglet de recette fermé.

## 7. Limites et état Git

B-MES-01 à B-MES-07 et B-SEN-02/03 restent ouverts, sans correction backend.
L'unité actuelle n'est pas un snapshot historique. Pas d'authentification,
d'autorisation de ressource ou d'isolation multi-tenant ajoutée par ces contrôles
de rattachement. Pas de recette FastAPI/PostgreSQL ni de test de charge réel.
Les risques de précision float, de données non finies côté serveur et de mutation
historique du Sensor restent explicitement documentés en UI 7.1.

HEAD bbd18d6 inchangé, branche feature/frontend-measurements, index vide et douze
fichiers du seul périmètre UI 7.4. Rapports antérieurs préservés. Runners, fixtures,
traces, captures et bundles de recette ignorés par Git. Aucun secret détecté par
les motifs ciblés et la revue du périmètre. Aucun backend, SQL, migration, Docker,
package ou budget modifié. Aucun commit, push ou merge. UI 7.5 non commencée.
Validation attendue avant tout commit.
