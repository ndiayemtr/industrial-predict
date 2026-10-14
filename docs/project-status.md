# Industrial Predict AI - Project Status

## État général

Projet en développement actif.

## Branche actuelle

`feature/frontend-shared-components`

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

## Frontend — finalisation UI 1.8.4 du 14 octobre 2026

La fondation UI 1.1 à UI 1.6 est terminée et fusionnée dans `main`.
Historique : `82fc073` a fusionné `feature/frontend-ui-foundation`, incluant
le commit final `8c7bd9f`. Le HEAD actuel est `e3a2a2c`
(`feat(frontend): add reusable shared UI components`) ; UI 1.7 est terminée
et commitée. Les corrections UI 1.8.2 restent non commitées.

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
| UI 1.8.2 | Corrections responsive validées ; sept fichiers modifiés et un test ajouté, non commités |
| UI 1.8.3 | Validation approfondie validée, complétée par le zoom réel contrôlé par l'utilisateur |
| UI 1.8.4 | Documentation, validation finale et préparation du commit en finalisation ; validation du livrable attendue |

Les neuf destinations de navigation accessibles et le détail équipement sont
encore des placeholders. Rapports et Administration restent « À venir » et
sans route dédiée. Le frontend n'appelle pas encore les APIs backend et
n'implémente pas l'authentification ni les écrans métier définitifs.

Versions vérifiées dans les manifests, le lockfile et les paquets installés :
Angular 21.2.25, CLI/build 21.2.26, Nebular 17.0.0, CDK 21.0.6,
TypeScript 5.9.3, RxJS 7.8.2, Zone.js 0.16.3 et Dart Sass 1.97.3.
Environnement constaté : Node.js 24.21.0 et npm 11.19.0.

Les résultats backend ci-dessus constituent l'historique de leurs validations
respectives ; aucune suite backend n'est relancée dans UI 1.8.4.

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

Les commandes frontend sont relancées pour la validation finale UI 1.8.4 ;
les résultats sont également fournis dans le rapport de livraison.

## Travail actuel

UI 1.8.4 en finalisation sur `feature/frontend-shared-components` : documents
synchronisés et contrôles finaux avant validation du commit responsive.

## Prochaine action

Faire valider le livrable UI 1.8.4 avant tout commit ou push.
La prochaine phase est la conception puis l'implémentation du Dashboard frontend
et de son intégration API. Elle n'est pas commencée et nécessite une mission distincte.
