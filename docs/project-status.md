# Industrial Predict AI - Project Status

## État général

Projet en développement actif.

## Branche actuelle

`feature/frontend-sites`. Point de départ de la série : `e8702b0`.
La création Site UI 4.5 et ses finitions sont commitées. La
[modification UI 4.6](ui-4.6-site-edit.md) est validée, sans transfert
d'entreprise ni suppression. Les parcours HTTP restent testés par simulation.
La [sécurisation UI 4.6.2](ui-4.6.2-site-code-simulation.md) est validée, avec
un simulateur local en mémoire sans connexion FastAPI/PostgreSQL.
L'[environnement permanent DEV](ui-4.7.2.1-development-environment.md) est validé :
`industrial_predict_dev` sur 5434, FastAPI 8001, Angular 4201, rôles séparés
et aucune cible de repli sur l'API historique. Les deux bases historiques sont préservées.
Le [seed UI 4.7.3](ui-4.7.3-development-data.md) est validé : 36 lignes fictives
créées exclusivement dans DEV, deuxième application sans écriture. Ces insertions
SQL réelles ne valident pas le parcours POST/PATCH du navigateur.

À mettre à jour à chaque changement de branche.

## Backend

FastAPI + PostgreSQL opérationnels.

CRUD terminés pour :

- Company
- Site
- Equipment
- Sensor
- Measurement
- MaintenanceRecord

## Dashboard

Étape 1.4.16 terminée.

Fonctionnalités principales :

- inventaire des actifs
- statut des équipements
- criticité
- couverture capteurs
- qualité des mesures
- activité des mesures
- maintenance
- downtime
- coûts
- filtres company/site/equipment/date

Tests Dashboard :

- 50 tests passés
- 0 échec
- 1 test PostgreSQL ignoré selon l'environnement

## Machine Learning

### 2.4 - Anomaly Detection

Statut : terminée et testée.

Fonctionnalités principales :

- détection statistique des anomalies
- Z-score classique et robuste
- Isolation Forest
- score d'anomalie unifié
- orchestration par capteur et équipement
- explication des anomalies

### 2.5 - Failure Risk Model

Statut : terminée et testée.

Fonctionnalités principales :

- génération des labels de panne
- préparation du dataset supervisé
- baseline classifier
- Random Forest
- évaluation du modèle
- score de risque
- niveaux de risque
- explication des prédictions

### 2.6 - Health Score

Statut : terminée et testée.

Fonctionnalités principales :

- Failure Health
- Anomaly Health
- Data Quality Health
- Maintenance Health
- agrégation pondérée
- classification du niveau de santé
- API Health Score par équipement

### 2.7 - Predictions Persistence

Statut : terminée et testée.

Fonctionnalités principales :

- enum PredictionType
- modèle SQLAlchemy PredictionRecord
- migration Alembic prediction_records
- schémas Pydantic
- PredictionRepository
- PredictionService
- persistance des anomalies
- persistance du Failure Risk
- persistance du Health Score
- historique des prédictions par équipement
- filtres par type, niveau, alerte et période
- pagination des prédictions

API :

- GET /api/v1/equipments/{equipment_id}/predictions

Tests Predictions Persistence :

- 44 tests passés
- 0 échec
- 1 test PostgreSQL ignoré selon l'environnement

Suite backend complète :

- 538 tests passés
- 0 échec
- 4 tests ignorés
- compileall app : OK

### 2.8 - Remaining Useful Life (RUL)

Statut : terminée et testée.

La fonctionnalité Remaining Useful Life est terminée.

### Fonctionnalités implémentées

- Définition métier du RUL :
  - nombre d'heures jusqu'à la prochaine maintenance corrective connue ;
  - calcul par équipement ;
  - les observations sans panne future connue sont considérées comme censurées et exclues de l'entraînement.

- Pipeline de données :
  - `RULLabeler`
  - `RULDatasetBuilder`
  - `RULPreparer`
  - split temporel réutilisant `TemporalDatasetSplitter`

- Modèles ML :
  - baseline `DummyRegressor` avec stratégie médiane ;
  - modèle principal `RandomForestRegressor` ;
  - sauvegarde et chargement des modèles avec `joblib`.

- Évaluation :
  - MAE ;
  - RMSE ;
  - R².

- Classification RUL :
  - critical : <= 24 h
  - warning : <= 72 h
  - watch : <= 168 h
  - healthy : > 168 h

- Explicabilité :
  - classement des feature importances ;
  - résumé des variables les plus influentes.

- API :
  - `POST /api/v1/equipments/{equipment_id}/rul`
  - validation des features attendues ;
  - gestion des équipements inexistants ;
  - gestion d'un modèle RUL indisponible.

- Persistance :
  - nouveau type de prédiction `rul` ;
  - enregistrement automatique dans `prediction_records` ;
  - `score` = RUL en heures ;
  - `level` = niveau RUL ;
  - `details.rul_hours` = valeur RUL.

### Validation

Tests RUL :

- 118 passed
- 0 failed
- 0 skipped

Suite backend complète :

- 656 passed
- 0 failed
- 4 skipped

Les tests ignorés nécessitent PostgreSQL.

### 2.9 - Predictive Maintenance Recommendations

Statut : terminée et testée.

Fonctionnalités principales :

- moteur de recommandations basé sur :
  - Anomaly Detection
  - Failure Risk
  - Health Score
  - Remaining Useful Life (RUL)

- priorités :
  - critical
  - high
  - medium
  - low

- types de recommandations :
  - urgent_maintenance
  - inspection
  - planned_maintenance
  - monitoring
  - no_action

- résolution de priorité centralisée
- génération d'explications métier
- combinaison de plusieurs signaux
- récupération automatique des dernières prédictions persistées
- persistance des recommandations dans `maintenance_recommendations`
- historique paginé
- filtres par :
  - priority
  - recommendation_type
  - start_time
  - end_time

API :

- POST /api/v1/equipments/{equipment_id}/recommendations
- GET /api/v1/equipments/{equipment_id}/recommendations

Tests Predictive Maintenance Recommendations :

- 216 tests passés
- 0 échec
- 0 skipped

Suite backend complète :

- 872 tests passés
- 0 échec
- 4 tests ignorés

Les tests ignorés nécessitent PostgreSQL.

## Historique de transition backend

Étape 2.9 - Predictive Maintenance Recommendations terminée et validée.

### Action prévue à l'issue de l'étape 2.9 (historique)

Merger la branche `feature/2.9-predictive-maintenance-recommendations` vers `main`, puis démarrer l'étape suivante du projet.

## Frontend - socle UI 1.1 à UI 1.8 terminé

La fondation UI 1.1 à UI 1.6 est terminée et fusionnée dans `main`.
Historique : `82fc073` a fusionné `feature/frontend-ui-foundation`, incluant
le commit final `8c7bd9f`. UI 1.7 est livrée dans `e3a2a2c`
(`feat(frontend): add reusable shared UI components`). UI 1.8 est terminée
et commitée dans `12a18c3` (`feat(frontend): finalize responsive shell and accessibility`).
Le HEAD de référence au début d'UI 2.1.1 est `acd872b`, fusion de
`feature/frontend-shared-components` dans `main` ; le socle UI 1.1 à UI 1.8
est fusionné. L'état Git initial de la branche Dashboard est propre.

| Étape | État et périmètre livré |
| --- | --- |
| UI 1.1 | Audit et architecture de la fondation frontend terminés |
| UI 1.2 | Initialisation Angular standalone, routing, SCSS et mode strict terminée |
| UI 1.3 | Thème clair personnalisé, tokens et Shell terminés ; compatibilité CDK corrigée |
| UI 1.4 | Sidebar, navigation centralisée et icônes terminées ; correction Sass reproductible |
| UI 1.5 | Header global, titre dynamique et commande Sidebar terminés ; finitions visuelles validées |
| UI 1.6 | Routing consolidé, 404 lazy, titres, lien d'évitement et gestion du focus terminés |
| UI 1.7.0 | Synchronisation documentaire validée et commitée |
| UI 1.7.1 | Conception et contrats des quatre composants partagés validés |
| UI 1.7.2 | PageHeader standalone implémenté et validé |
| UI 1.7.3 | LoadingState standalone implémenté et validé |
| UI 1.7.4 | EmptyState standalone implémenté et validé |
| UI 1.7.5 | ErrorState standalone implémenté et validé |
| UI 1.7.6 | Validation globale et visuelle terminée ; démonstration temporaire retirée |
| UI 1.8.1 | Audit responsive validé |
| UI 1.8.2 | Corrections responsive validées ; sept fichiers modifiés et un test ajouté, livrés dans le commit UI 1.8 |
| UI 1.8.3 | Validation approfondie validée, complétée par le zoom réel contrôlé par l'utilisateur |
| UI 1.8.4 | Documentation et validation finale terminées ; commit `12a18c3`, fusion `acd872b` |
| UI 2.1 | Audit du contrat Dashboard et architecture frontend validés |
| UI 2.1.1 | Synchronisation documentaire validée et commitée dans `e819393` |
| UI 2.2 | DTO, HttpClient, DashboardApiService et proxy développement livrés |
| UI 2.3 | Références paginées et filtres UTC/cascade livrés |
| UI 2.4 | Page Dashboard lazy, façade locale et cinq états UI livrés (`4f4f77f`) |
| UI 2.4.1 | Diagnostic du bundle validé ; lazy loading conservé, coût Forms partagé identifié |
| UI 2.5 | KPI, équipements et capteurs livrés (`b666d7d`) |
| UI 2.6 | Mesures et maintenance livrées (`2a6116d`) |
| UI 2.7 | Validation intégrée terminée ; observations réelles et cas simulés distingués |
| UI 2.7.1 | Formulation neutre de couverture corrigée et commitée (`956a0b4`) |
| UI 2.8 | Documentation et validation finale terminées (`9ce0cac`) ; Dashboard fusionné dans `main` (`f3f6f2c`) et publié sur GitHub |
| UI 3.1 | Conception Companies validée (`d6d31ec`) |
| UI 3.2 | DTO et service API Companies livrés (`07d2bc3`) |
| UI 3.3 | Liste, recherche serveur et pagination (`84f7f18`) |
| UI 3.4 | Détail entreprise (`a1e332e`) |
| UI 3.5 | Création et formulaire partagé (`d8e6c48`) |
| UI 3.6 / UI 3.6.1 | Modification et notifications CRUD Nebular (`ab99551`) |
| UI 3.7 | Validation intégrée terminée ; lectures réelles et écritures simulées distinguées |
| UI 3.7.1 | Diagnostic de stabilité validé et commité (`ac2dc3a`), sans correctif spéculatif |
| UI 3.8 | Documentation finale terminée (`a495f90`) ; Companies fusionné dans `main` (`537822c`) et publié |

Dashboard V1 est opérationnel via FastAPI/PostgreSQL. Companies MVP est terminé,
fusionné dans `main` et publié. Les sept autres destinations
de navigation et le détail équipement restent des placeholders. Rapports et
Administration restent « À venir » et sans route dédiée. L'authentification
frontend n'est pas implémentée ; le Dashboard n'est pas déclaré prêt pour une
production SaaS multi-tenant faute d'autorisation multi-entreprises démontrée.

Versions vérifiées dans les manifests, le lockfile et les paquets installés :
Angular 21.2.25, CLI/build 21.2.26, Nebular 17.0.0, CDK 21.0.6,
TypeScript 5.9.3, RxJS 7.8.2, Zone.js 0.16.3 et Dart Sass 1.97.3.
Environnement constaté : Node.js 24.21.0 et npm 11.19.0.

Les résultats backend ci-dessus constituent l'historique de leurs validations
respectives ; aucune suite backend n'est relancée dans UI 2.1.1.

### Responsive livré et validations

- Desktop : largeur CSS **>= 1024 px**, Sidebar latérale ; 1024 px reste desktop.
- Mobile/tablette : largeur CSS **< 1024 px**, panneau superposé fermé initialement,
  sans compression du contenu, avec fond de fermeture, Échap et bouton de fermeture.
- Fermeture après navigation réussie, confinement du focus CDK, arrière-plan inert,
  restauration du focus et transitions de modes ; skip link et routing conservés.
- Validation navigateur UI 1.8.3 : 1440, 1024, 1023, 768, 390 et 320 px, hauteur
  900 px ; Dashboard, détail équipement et 404, menu ouvert/fermé ; six cycles
  répétés autour de 1024 px, sans état bloqué ni débordement horizontal observé.
- Build de production réussi ; **116 tests Angular** et **5 tests du correctif
  Sass** réussis. Contrôles des quatre expressions Sass, huit breakpoints et
  thème unique réussis ; aucune nouvelle dépréciation Sass.
- Bundle initial : **504,68 ko** contre budget d'avertissement **500 ko**,
  dépassement de **4,68 ko**. Seuil d'erreur 1 Mo et budgets inchangés.
- Zoom navigateur réel **100 %, 200 % et 400 % validé manuellement par
  l'utilisateur**, qui confirme les cinq vérifications OK dans la demande
  UI 1.8.4. Cette confirmation complète la limite du navigateur intégré
  rencontrée lors des tests de l'assistant ; ce n'est pas un test automatisé.
- **Aucun test de lecteur d'écran réel réalisé** : les contrôles clavier,
  de focus et d'attributs ARIA ne constituent pas une validation vocale complète.

Ces résultats sont l'historique de validation UI 1.8, pas une nouvelle exécution
en UI 2.1.1. Cette étape documentaire contrôle le contrat dans le code et les
tests existants, la cohérence des documents et le diff Git.

## Livraison UI 3 - Companies MVP et finition des dates

UI 3.1 à UI 3.8 sont terminées. Le rapport de stabilité
[UI 3.7.1](ui-3.7.1-test-stability.md) est commité dans `ac2dc3a`, puis la
documentation UI 3.8 dans `a495f90`. Companies MVP est fusionné dans `main`
via `537822c` et publié. La finition des dates est livrée dans `9c183e0`,
documentée dans `3e83b0b`, puis fusionnée et publiée via `2c49c4f`.
Cette publication du code ne constitue pas un déploiement de production.

Le [formatage Dashboard et Companies](frontend-datetime-display.md) est livré :
dates administratives à la minute, résultats Dashboard à la seconde, fractions
masquées uniquement à l'affichage et dates Companies sans fuseau conservées
sans conversion locale. Les [filtres Dashboard](dashboard-date-precision.md)
offrent un mode simple à la minute et une précision avancée à la milliseconde.
Le mode précis est automatique pour les valeurs précises existantes ; le retour
à la minute exige une confirmation en cas de perte de précision. UTC, intervalle
initial de 168 heures, début inclus et fin exclusive sont conservés.

Validation finale de livraison : **386 tests Angular réussis dans 32 fichiers**,
build production réussi et `npm audit` sans vulnérabilité signalée. Ces résultats
de livraison sont consignés à partir des rapports et du bilan communiqué par
l'utilisateur ; aucun test, build ou audit npm n'est relancé pour cette mise à
jour documentaire. Le bundle initial reste à **600,89 ko pour 500 ko** de budget.

Le MVP comprend liste, recherche serveur sur nom/code, pagination, détail,
création et modification. La liste conserve `page`, `page_size` et `search` dans
l'URL et les liens internes ; la modification part du détail. Le formulaire
partagé applique les validations locales nom/code, conserve Unicode et la casse,
ne soumet aucun PATCH inchangé et transmet seulement les champs modifiés.
Les confirmations de succès associent un toast Nebular et un texte persistant
sur le détail. Aucun DELETE dans l'UI ou le service Angular.
Voir [frontend-architecture.md](frontend-architecture.md#companies-mvp---architecture-implémentée-ui-3)
et [ui-design.md](ui-design.md#companies-mvp---présentation-et-parcours-livrés).

### Companies MVP - validation historique UI 3.7

Les résultats ci-dessous proviennent du rapport de validation intégrée UI 3.7
du 16 octobre 2026, sur `ab99551`, consulté dans le chat « Auditer le frontend
Angular » (identifiant `01a135fd-814d-7e51-89e3-249e2f655afb`). Le code et les tests
sont réexaminés en UI 3.8 ; ces observations ne sont pas de nouvelles exécutions.

| Périmètre | Nature et résultat de la validation UI 3.7 |
| --- | --- |
| Liste et détail | Navigateur et FastAPI réels, PETROSEN, champs et horodatages conformes ; aucune conversion UTC implicite. |
| Recherche | Backend réel : `petro`, recherche Unicode sans résultat, contexte conservé au retour. |
| Pagination | Réel sur une page ; pages 2/3 et 45 entreprises par simulation. Aucun grand volume réel démontré. |
| Création | POST simulé : accents, emoji, caractères japonais ; description intacte omise, description vide volontaire nullable. Aucune création PostgreSQL réelle. |
| Modification | PATCH simulé : code seul modifié, effacement `description: null`, aucun PATCH sans changement. Aucune modification PostgreSQL réelle. |
| Erreurs | 404 réelle sur le détail ; 422 réelle par GET direct invalide. 409/422/500 d'écriture et réseau validés par simulations, sans toast de succès. |
| Concurrence et soumissions | Réponses obsolètes écartées ; doubles clics POST/PATCH sans doublon dans les simulations et tests automatisés. |
| Notifications | Toast unique après succès simulé POST/PATCH, conservé après navigation puis fermeture automatique ; confirmation persistante indépendante. |
| Abandon | Guard local et refus/acceptation couverts par les tests ; dialogue natif non validé manuellement en navigateur. |
| Non-régression | Dashboard réel avec ses cinq sections, placeholder Sites, 404 globale, Shell et sélection Sidebar contrôlés. |

Responsive historique : quatre parcours (liste, détail, création, modification)
à 1440/1024/1023/768/390/320 px CSS, hauteur 900 px, soit 24 contrôles au zoom
nominal 100 %. Aucun débordement horizontal global observé, un h1 par page,
tableau avec caption/en-têtes, clavier/focus, skip link et menu mobile contrôlés.
Les zooms Companies réels 200 % et 400 % n'ont pas pu être validés ; les preuves
de zoom du socle/Dashboard ne s'étendent pas à Companies. Lecteur d'écran réel
non testé. Aucun test de charge à grande échelle ni certification d'accessibilité.

UI 3.7 : dernière suite complète 348 tests réussis dans 31 fichiers, build
production réussi, cinq tests du correctif Sass réussis, contrôles Sass conformes,
`npm ls --all` code 0 et `npm audit` sans vulnérabilité à cette date. Ces résultats
ne sont pas attribués à UI 3.8 et ne valent pas audit actuel des dépendances.

### Stabilité - bilan UI 3.7.1 validé

Sur `ab99551`, trois suites complètes sans build concurrent réussissent chacune
à 348/348. Les six tests 404 passent dans neuf lancements exploitables (54/54).
Le défaut initial « neuf liens attendus, zéro reçu » rapporté en UI 3.7 n'est pas
reproduit ; aucune cause de synchronisation Angular n'est établie et aucun test,
helper ou composant n'est corrigé. Les neuf liens attendus sont conservés.

Les scénarios concurrents produisent respectivement 346/348 puis 347/348 avec
timeouts de 5 secondes dans Sidebar et Shell responsive, tandis que les six tests
404 passent. L'essai 404 seul avec build passe également. Le troisième scénario
fait réellement chevaucher l'exécution Vitest et le build. La contention explique
les timeouts observés et reste une piste pour le défaut initial, sans prouver sa
cause. Recommandation validée : tests et build séquentiels, sans délai, retry
automatique ni assouplissement des assertions. Détails et limites dans le
[rapport UI 3.7.1](ui-3.7.1-test-stability.md), conservé comme historique de séance.

UI 3.7.1 a aussi validé le build production, les cinq tests Sass, les quatre
expressions corrigées, huit breakpoints et thème unique. Les 26 artefacts des
builds de référence/final sont identiques par SHA-256 ; aucune hausse liée au
diagnostic. Les limites EPERM du bac à sable sont documentées dans ce rapport.

### Bundle et limites de livraison Companies

| Élément, mesure historique UI 3.7 / UI 3.7.1 | Taille brute |
| --- | ---: |
| Initial | 600,89 ko |
| Budget initial d'avertissement | 500 ko |
| Dépassement | 100,89 ko |
| Surcoût après intégration NbToastrService | +32,48 ko |
| Liste Companies différée | 12,57 ko |
| Détail différé | 7,77 ko |
| Formulaire création/modification différé | 15,97 ko |
| Dashboard différé | 45,38 ko |

Le surcoût Toastr est inclus dans les 600,89 ko ; il ne s'ajoute pas à ce total.
Budgets et dépendances restent inchangés. Le chargement différé des pages reste
effectif ; aucun travail de réduction du bundle n'est réalisé dans UI 3.8.

DELETE est exclu du MVP à cause de la suppression définitive en cascade. L'API
backend existante conserve cette capacité ; masquer l'action ne la sécurise pas.
L'autorisation multi-entreprises n'est pas démontrée, ni sur Companies ni sur le
Dashboard ; aucun périmètre utilisateur/RBAC n'est prouvé. Les écritures réelles
POST/PATCH ne sont pas validées de bout en bout, les horodatages Company restent
sans garantie de fuseau et aucun verrou de version serveur n'est fourni.
**Le module n'est pas prêt pour une production SaaS multi-tenant.**

### Contrôles documentaires UI 3.8 - historique

Relecture du code et des tests, cohérence des documents, liens internes, tirets
simples, périmètre documentaire, `git diff --check` et état Git. Aucune suite
Angular/backend, aucun build, contrôle Sass, audit npm ou requête FastAPI relancé.
Si les validations applicatives sont relancées ultérieurement, les exécuter
séquentiellement et consigner séparément leur date, leur HEAD et leurs résultats.
Les résultats UI 3.7 / UI 3.7.1 ci-dessus restent historiques.

Contrôles documentaires UI 3.8 réussis : 39 liens internes, dont huit liens
avec ancre, `git diff --check`, absence de tiret cadratin dans les huit documents
modifiés et absence de changement hors documentation. Le contenu D001 à D014
est conservé intégralement ; le rapport UI 3.7.1 reste inchangé. Branche et HEAD
inchangés à l'issue des contrôles, avant le commit documentaire `a495f90`.

## Livraison Dashboard V1 - historique

Synchronisation documentaire après livraison, au 15 octobre 2026 : branche
`main`, HEAD `23e28e5`, identique à `origin/main`, répertoire de travail propre
avant intervention. UI 2.1 à UI 2.8 sont terminées ; Dashboard V1 est fusionné
dans `main` via `f3f6f2c` et son code est publié sur GitHub. Cela ne constitue
pas un déploiement de production. Le backend local sur **127.0.0.1:8000**
est consommé via le proxy Angular `/api/v1` de développement.

Le périmètre livré couvre synthèse, équipements, capteurs, mesures et maintenance,
uniquement à partir des agrégats de `GET /api/v1/dashboard`. Health Score,
RUL et prédictions de panne sont exclus de V1 ; l'affichage monétaire est différé.
Voir `frontend-architecture.md` pour le contrat, les états UI et les risques,
`ui-design.md` pour la présentation et `roadmap.md` pour l'état des étapes UI 2.

### Validation Dashboard V1 - UI 2.7 / UI 2.7.1

- 217 tests Angular en UI 2.7, puis **220 tests** après UI 2.7.1 ; build production
  réussi, **5 tests de correctif Sass**, contrôles Sass conformes, `npm ls --all`
  valide et `npm audit` sans vulnérabilité. UI 2.8 a relancé ces contrôles.
- Données existantes PETROSEN, sans écriture PostgreSQL : 2 équipements,
  2 capteurs actifs, couverture 50 %, aucune mesure sur les sept jours testés,
  aucune maintenance ouverte ni retard. Le compresseur sans capteurs reste en
  `success`, avec zéros et ratios non calculables distincts.
- Fin exclusive vérifiée dans FastAPI et l'interface : 3 mesures pour
  `[2026-09-01T10:00:00Z, 2026-09-01T10:03:00Z)`, 4 mesures en déplaçant
  la fin à `10:03:00.001Z`. Dernier relevé du 1er septembre visible hors période
  d'octobre ; capteur sans relevé et unité déclarée conservés.
- Réel navigateur : idle/success, cascade, options facultatives, 168 heures UTC,
  dates invalides bloquées, actualisation des filtres appliqués, clavier/focus,
  menu mobile, huit tableaux avec captions, un h1 et console sans erreur/warning.
- Simulé : empty (aucun périmètre réel sans actifs), loading Dashboard (réponse
  locale trop rapide pour une observation durable), UI error/retry réseau/500 et
  400/404/422, annulation des requêtes obsolètes, pagination multipage et couverture
  partielle. Les statuts backend 400/404/422 sont aussi reproduits par GET directs,
  sans les confondre avec un état erreur observé dans la page.
- Les références réelles tiennent sur une page ; les tests multipages sont simulés.
  L'absence de requêtes Dashboard automatiques/supplémentaires est vérifiée par
  les tests HTTP et le code, sans capture réseau navigateur exhaustive.
- Responsive : 1440/1024/1023/768/390/320 px CSS, hauteur 900 px, sans débordement
  horizontal détecté ; desktop à 1024, mobile à 1023. La confirmation historique
  utilisateur du zoom réel 100/200/400 % concerne UI 1.8. En UI 2.7, les raccourcis
  de zoom du navigateur intégré restent sans effet : le zoom réel Dashboard
  200/400 % n'est pas validé par l'assistant. En réponse à la clarification UI 2.8,
  **l'utilisateur confirme avoir effectué et validé les trois niveaux de zoom réel
  100 %, 200 % et 400 % sur le Dashboard V1**. Cette validation manuelle complète
  les essais automatisés ; elle n'est pas attribuée au navigateur de l'assistant.
- **Lecteur d'écran réel non testé**, malgré les contrôles clavier/DOM/ARIA.
- Dette bundle : initial **565,38 ko**, budget warning **500 ko** (écart 65,38 ko),
  seuil d'erreur 1 Mo inchangé. Angular Forms est partagé avec Nebular et émis
  dans un chunk initial commun ; la page Dashboard reste lazy. Référence différée
  UI 2.6 : **52,00 ko** ; après la formulation UI 2.7.1 : **51,98 ko**.

La validation intégrée est terminée avec ces limites explicites ; aucune validation
de charge à grande échelle ni garantie de sécurité multi-tenant n'est revendiquée.

### Contrôles finaux UI 2.8

Contrôles relancés sur HEAD `956a0b4` sans changement applicatif :
build production réussi ; **220 tests Angular** (23 fichiers) et **5 tests de
correctif Sass** réussis ; quatre expressions, huit breakpoints et thème unique
conformes ; `npm ls --all` code 0 ; `npm audit` : **0 vulnérabilité**.
Aucune nouvelle dépréciation Sass. Bundle final **565,38 ko initial**,
**51,98 ko Dashboard différé** (référence historique 52,00 ko en UI 2.6).
Warning de 65,38 ko conservé, aucun budget relevé.
Les modifications UI 2.8 concernaient uniquement les sept documents de contexte,
statut, roadmap, architectures, design et décisions ; historique backend conservé.

### Livraison et nettoyage typographique

La documentation UI 2.8 est commitée dans `9ce0cac`, puis fusionnée dans
`main` via `f3f6f2c`. Le commit publié `23e28e5` remplace exactement
**90 tirets cadratins dans 24 fichiers** par des tirets simples, sans changement
fonctionnel. Les 220 tests Angular et le build production ont réussi après ce
nettoyage ; le bundle initial reste à 565,38 ko. Ces validations sont historiques :
la présente synchronisation documentaire ne relance pas les tests applicatifs.

Les limites restent ouvertes : budget initial de 500 ko dépassé, lecteur d’écran
réel non testé et autorisation multi-entreprises à renforcer avant production.

## Prochaine action

Les travaux UI 4.6, UI 4.6.2, UI 4.7.2/UI 4.7.2.1 et UI 4.7.3 sont enregistrés
en quatre commits locaux. Voir le [bilan de préparation](pre-ui-4.7.4-commits.md).
Attendre validation avant UI 4.7.4, qui n'est pas commencée. Aucun push ni merge.
La conception UI 4.1 reste applicable : entreprise explicite, code unique
globalement, suppression et transfert exclus, aucun company_id dans PATCH
et aucune interprétation arbitraire des 409. L'absence d'autorisation
multi-entreprises reste une limite de sécurité.
