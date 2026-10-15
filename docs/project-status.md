# Industrial Predict AI - Project Status

## État général

Projet en développement actif.

## Branche actuelle

`feature/frontend-dashboard`

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

Dashboard V1 est opérationnel via FastAPI/PostgreSQL. Les huit autres destinations
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

## Travail actuel

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

Faire valider cette synchronisation avant tout commit documentaire. La prochaine
phase est UI 3 - Gestion des entreprises (Companies), en commençant par UI 3.1 :
analyse fonctionnelle et technique des contrats CRUD, de la pagination, des états
UI et de l’accessibilité. Cette analyse et son implémentation ne sont pas commencées.
Aucun commit, push, merge ou développement UI 3 dans la présente intervention.
