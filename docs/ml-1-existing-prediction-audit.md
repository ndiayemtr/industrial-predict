# ML 1 — Audit de la chaîne prédictive existante

Date : 25 octobre 2026. Référence vérifiée : branche `main`, HEAD
`687389613d1cfc274cb0ee5fea8055fe3243c741`. Arbre de travail initial propre.

## 1. Périmètre et conclusion

Audit statique des sources, déclarations de dépendances, tests et documents du dépôt.
Aucun import applicatif, accès PostgreSQL, appel HTTP, chargement joblib,
entraînement, calcul ML, seed, migration, test ou build exécuté. Aucune modification
de code exécutable, aucun package ajouté, aucune opération commit/push/merge/rebase.
Seul ce rapport est créé. Les étapes proposées ci-dessous restent à valider ; ML 2
n'est pas commencé.

La base logicielle contient des algorithmes réels et des adaptateurs de persistance,
mais **pas une chaîne complète et validée mesures → quatre prédictions → historique**.
Une seule route RUL lance l'inférence et persiste automatiquement. Le Health Score
est une heuristique composite, calculée à partir de données déclarées par le client,
sans persistance dans sa route. Anomalie et risque de panne ont des composants
Python, sans route de calcul ni orchestration applicative complète identifiée.

La première intégration recommandée est une **détection statistique d'anomalie de
température sur une seule pompe, en environnement de démonstration isolé**. Ce sera
un signal de surveillance explicable, pas un modèle entraîné de prédiction de panne.
Les données DEV documentées sont trop limitées pour démontrer une performance
industrielle du risque de panne ou de la RUL.

Les mentions « présent », « implémenté » et « couvert par un test » désignent une
constatation dans les fichiers, sans certification de fonctionnement à l'exécution.
Les constats DEV proviennent des rapports antérieurs et du jeu JSON ; aucun état
actuel de la base n'est affirmé ou revérifié ici.

## 2. Inventaire technique et niveau de réalisation

| Domaine | Sources principales | Réalisation constatée | Écarts d'intégration |
| --- | --- | --- | --- |
| Extraction | `backend/app/data_pipeline/extractor.py`, `schemas.py`, `dataset_builder.py`, `pipeline.py` | Jointures Measurement → Sensor → Equipment → Site → Company ; filtres facultatifs ; DataFrame trié ; fenêtres de base | Pas de scénario orchestré complet ; extraction non bornée en volume ; filtres d'entreprise facultatifs et sans autorisation |
| Nettoyage | `quality_rules.py`, `quality_filter.py`, `duplicate_detector.py`, `cleaner.py`, `outlier_detector.py`, `gap_detector.py`, `silent_sensor_detector.py`, `cleaning_report.py` | Classification qualité, dédoublonnage, IQR, trous, silence, rapports | Le pipeline de base n'appelle pas automatiquement le cleaner ni les détecteurs de trous/silence ; pas de politique unique obligatoire |
| Features | `feature_pipeline.py`, `time_series.py`, `window_features.py`, `lag_features.py`, `trend_features.py`, `variability_features.py`, `rate_features.py`, `multiscale_features.py`, `quality_features.py`, `equipment_features.py` | Features temporelles et numériques implémentées | Pas de contrat versionné entraînement/inférence, d'imputation commune ou de contrôle de maturité de fenêtre |
| Anomalie | `backend/app/anomaly_detection/*.py` | Écart statistique, z-score classique et robuste, Isolation Forest, vote pondéré, synthèse équipement et explications | Aucun artefact sauvegardé ni route de calcul ; conversion DataFrame → AnomalyResult → persistance à orchestrer |
| Risque de panne | `data_pipeline/failure_labeler.py`, `supervised_dataset.py`, `ml/failure_risk_preparer.py`, `baseline_classifier.py`, `random_forest_classifier.py`, `risk_score.py`, `time_splitter.py`, `evaluator.py`, `prediction_explainer.py` | Régression logistique équilibrée ; RandomForestClassifier équilibré (200 arbres, seed 42, max_features sqrt, n_jobs -1) ; labels, séparation temporelle et métriques | Pas de service d'inférence applicatif dédié, route, store ou artefact de risque identifié ; pas de calibration ni validation industrielle |
| Santé | `ml/health_score/*.py`, `services/health_score_service.py`, `schemas/health_score.py` | Formule pondérée, pénalités et niveaux déterministes ; route de calcul | Heuristique fonctionnelle dans les sources, aucun apprentissage ; entrées agrégées reçues du client ; absence de récupération automatique des signaux et de persistance par cette route |
| RUL | `data_pipeline/rul_labeler.py`, `rul_dataset.py`, `ml/rul_*.py`, `services/rul_service.py`, `rul_prediction_service.py`, `schemas/rul.py` | Baseline médiane DummyRegressor ; RandomForestRegressor (200 arbres, seed 42, max_features sqrt, n_jobs -1), sortie bornée à zéro ; store joblib, niveaux, métriques, route persistante | Features libres fournies par client ; aucune extraction de mesures dans le service ; provenance et aptitude de l'artefact local inconnues |
| Historique | `models/prediction_record.py`, `schemas/prediction_record.py`, `repositories/prediction_repository.py`, `services/prediction_service.py` | Modèle SQLAlchemy, DTO, création, quatre adaptateurs persist_*, lecture/pagination/latest en Python | Validation métier partielle ; latest et détail non exposés en HTTP ; absence d'idempotence et de contrat de provenance obligatoire |
| API | `api/routes/equipment.py`, `main.py` | GET historique, POST Health Score, POST RUL sous `/api/v1/equipments` | Pas de POST anomalie/risque ; pas d'alimentation des quatre types par une tâche automatique identifiée |

Il n'y a pas de simple `pass` à remplacer dans les calculs centraux : le `pass` de
`PredictionRecordCreate` sert à hériter du schéma de base. La baseline RUL médiane
est un comparateur statistique volontaire, pas un placeholder de modèle de panne.
Les fonctionnalités manquantes sont surtout l'orchestration, les contrats et la
validation. Les fixtures et mocks des tests ne constituent pas des modèles déployés.

### Artefacts et dépendances

- Fichier local observé : `backend/artifacts/rul/rul_model.joblib`, 42 259 octets.
  Il est ignoré par Git (`*.joblib`) et absent des fichiers suivis. Sa présence
  locale ne garantit pas sa disponibilité depuis un clone du HEAD.
- Aucun manifeste, version, schéma de features ou rapport d'entraînement associé
  trouvé à cet emplacement. Aucun autre fichier dans `backend/artifacts` lors de
  l'inventaire. L'état entraîné, les colonnes, le jeu d'origine, les métriques et
  les versions internes du binaire restent **non vérifiés** : aucun chargement.
- `core/config.py` définit `artifacts/rul/rul_model.joblib`, chemin relatif au
  répertoire de lancement et surchargeable par configuration. Le fichier local
  sous `backend` ne prouve donc pas quel fichier serait chargé en service.
- `backend/requirements.txt` déclare notamment pandas 3.0.6 et scikit-learn 1.9.1,
  FastAPI 0.141.1, Pydantic 2.13.4, SQLAlchemy 2.0.52, psycopg 3.3.4 et Alembic
  1.19.1. NumPy et joblib sont importés directement mais non épinglés explicitement
  dans ce fichier ; leur présence est attendue transitivement via scikit-learn.
  `requirements.txt` à la racine est vide. Versions installées non inspectées.
- `RULModelStore.load` désérialise via `joblib.load` **avant** le contrôle de type.
  Ce contrôle ne sécurise pas un pickle malveillant et ne certifie pas un modèle
  entraîné, compatible ou validé. Gestion d'artefacts de confiance à concevoir.

## 3. Flux et sémantique des quatre types

### 3.1 Socle commun de données et caractéristiques

`MeasurementDataExtractor.extract` lit les valeurs, qualités, timestamps, identifiants,
codes, type/unité/statut du capteur, type/statut/criticité équipement et hiérarchie.
Bornes des mesures : début inclus, fin **exclue** ; ordre timestamp puis id.
`MeasurementDataPipeline.build` prépare la série et les fenêtres de base ; il
n'appelle pas le pipeline avancé de features ni le cleaner.

`MeasurementFeaturePipeline.build` ajoute par capteur, après tri timestamp/id :

| Feature | Convention actuelle |
| --- | --- |
| Fenêtres moyenne/min/max/std/count | 3 observations par défaut, point courant inclus ; moyenne dès 1 point, std échantillonnale dès 2 |
| Décalages | `value_lag_1/2/3` ; valeurs initiales manquantes |
| Pente | Différence entre dernier et premier point divisée par nombre d'intervalles ; unité par observation, pas par heure |
| Variabilité | Étendue ; coefficient std/moyenne, manquant si moyenne nulle |
| Vitesse | Delta valeur / delta secondes ; manquante pour intervalle non positif |
| Multi-échelle | Moyennes et std sur 3, 5 et 10 observations, fenêtres partielles acceptées |
| Qualité | Reprend les indicateurs préparés en amont ; sinon initialise gap/warning/invalid/duplicate/outlier à false |

Ces fenêtres sont des **nombres de lignes**, pas des durées garanties. Les données
irrégulières doivent donc être traitées explicitement. `EquipmentFeatureBuilder`
agrège toutes les lignes reçues par équipement, sans fenêtre temporelle propre ;
une moyenne de valeurs de capteurs en °C et mm/s n'a pas de sens physique commun.

### 3.2 Anomaly

**Entrées et fenêtre.** Un capteur suffit ; valeur numérique, identifiants et UTC
pour le rattachement. Le détecteur statistique demande `value`, `rolling_mean`,
`rolling_std`. Le z-score demande `sensor_id`, `value`. Isolation Forest utilise
par défaut valeur, moyenne/std glissantes, delta, vitesse, pente, étendue et CV.
Aucun type physique obligatoire ni durée minimale n'est imposé. Isolation Forest
ne calcule rien avec moins de deux lignes complètes ; cela n'est pas un seuil de
suffisance industrielle. Le pipeline avancé est nécessaire aux features par défaut
de la forêt ; le pipeline de base seul ne les fournit pas toutes.

**Calculs.** Écart absolu > 3 × std ; z-score classique > 3 en valeur absolue ;
z-score robuste `0.6745 × (valeur − médiane) / MAD`, seuil strict > 3,5.
Moyenne/std/médiane/MAD sont calculés sur tout le lot par capteur. Isolation Forest
fait `fit_predict` sur tout le lot de lignes complètes fourni, contamination 0,05,
seed 42. Il s'agit bien d'un apprentissage non supervisé à chaque appel, pas du
chargement d'un modèle entraîné et versionné. La forêt ne groupe pas par capteur :
l'appelant doit isoler les séries compatibles avant de l'appeler.

**Score et alerte.** `UnifiedAnomalyScorer` combine les indicateurs binaires
statistique/robuste/forêt aux poids 0,25/0,35/0,40, normalisés par leur somme.
Score sans unité dans [0,1], alerte si score >= 0,6 ; aucune probabilité de panne.
Le z-score classique est calculé mais n'entre pas dans ce vote ; le score brut
`-score_samples` de la forêt n'y entre pas non plus. Sans forêt, les deux autres
signaux atteignent ensemble exactement 0,6 ; les signaux indisponibles ne causent
pas de renormalisation. Aucun `level` générique n'est produit. La synthèse équipement
déclare une anomalie dès qu'au moins une ligne est anormale.

**Manquants et limites.** Std/MAD nulles ou indisponibles donnent des z-scores NaN,
comparaisons fausses ; les lignes incomplètes de forêt restent non anormales.
Les colonnes de vote absentes/NA valent zéro : « non calculable » risque donc d'être
présenté comme « normal ». Une valeur infinie n'est pas exclue par le seul notna.
Les statistiques sur tout le lot incorporent des points futurs pour une relecture
historique. La fenêtre glissante inclut le point évalué et peut masquer un saut.

**Persistance/provenance.** `persist_anomaly` exige equipment_id, reprend timestamp
de mesure comme predicted_at, score, is_anomaly, méthode comme model_name et raison
seule dans details. Version, paramètres, fenêtre et provenance des features ne sont
pas conservés ; level/horizon restent nuls. Aucun appel de production reliant les
détecteurs à cet adaptateur identifié. La faible série DEV ne valide pas un seuil.

### 3.3 Failure risk

**Entrées et fenêtre.** Features numériques/booléennes de mesures et événements de
maintenance avec equipment_id, maintenance_type et started_at. Un capteur suffit
techniquement ; aucun capteur imposé par les wrappers. Horizon des labels : 24 h
par défaut, strictement positif et configurable ; fenêtre des features indépendante.

**Cible.** `FailureLabeler` recherche la prochaine maintenance `corrective` démarrée
strictement après chaque mesure du même équipement. Label 1 si délai <= horizon,
sinon 0. Une corrective à l'instant exact est exclue ; started_at invalide est ignoré.
Le statut, le code de panne et la réalité d'une défaillance ne sont pas validés.
Le délai jusqu'au début d'intervention n'est pas nécessairement celui jusqu'à la panne.
Sans corrective future connue, 0 ne prouve pas l'absence de panne : fin de suivi
et censure ne sont pas gérées.

**Préparation/inférence.** `FailureRiskPreparer` sépare la cible, retire les colonnes
connues de fuite (dates de panne, délai cible, identifiants/codes, informations
post-intervention), conserve les colonnes numériques/booléennes restantes. Pas
d'allowlist exhaustive, d'imputation ni de standardisation intégrée. La baseline
logistique et la forêt nécessitent au moins deux classes à fit ; predict_proba prend
la deuxième colonne sans vérifier explicitement que classes_[1] correspond à 1.
Il manque un contrat imposant une cible strictement binaire.

**Score/seuils.** Probabilité estimée [0,1], non calibrée ; score = probabilité × 100,
sans unité. Niveaux : low < 0,25 ; medium [0,25 ; 0,50[ ; high [0,50 ; 0,75[ ;
critical >= 0,75. Le scorer ne rejette pas explicitement les NaN ; pas de politique
d'alerte booléenne associée. Les importances globales de forêt sont une explication
globale, pas une causalité ni une explication locale individuelle.

**Persistance/provenance.** `persist_failure_risk` accepte probabilité, score, niveau,
date, identifiants optionnels, nom/version/horizon optionnels. Il borne la probabilité
mais ne recalcule ni score ni niveau ; is_alert reste nul. Details contient uniquement
failure_probability. Pas de store, artefact ou service/route d'inférence identifié.
Les métriques accuracy, précision, rappel, F1, confusion et ROC AUC existent comme
outils, sans performance DEV démontrée. Le jeu DEV ne constitue pas une population
de défaillances suffisante et représentative.

### 3.4 Health score

**Entrées et fenêtre.** POST `/{equipment_id}/health-score` reçoit probabilité de
panne, score d'anomalie, nombres valid/warning/invalid et trois booléens de maintenance.
Les probabilités/scores sont bornés [0,1], comptes >= 0 avec total > 0. Aucun capteur,
timestamp, horizon ou intervalle obligatoire : l'appelant déclare tous les signaux.
Le service vérifie seulement l'existence de l'équipement puis calcule.

**Formule heuristique.** Failure health = (1 − p) × 100 ; anomaly health =
(1 − anomalie) × 100 ; qualité = (valid + 0,5 × warning) / total × 100 ; maintenance =
100 moins 40 si corrective en cours, 30 si maintenance échue et 10 si prévue bientôt,
plancher 0. Agrégation 40 % panne, 30 % anomalie, 15 % qualité, 15 % maintenance,
arrondie à deux décimales ; poids personnalisables en Python et contrôlés pour une
somme de 1. Aucun apprentissage ni artefact.

**Sens/seuils.** Indice sans unité [0,100], plus haut = meilleur. Healthy >= 85,
good >= 70, degraded >= 50, poor >= 30, critical < 30. Ces catégories sont des règles,
pas des probabilités ni une durée de vie. Pas d'is_alert produit automatiquement.

**Persistance/provenance et limites DEV.** La route ne persiste pas.
`persist_health_score`, distinct et non raccordé à elle, stocke score, niveau,
quatre composantes, date fournie et nom health_score par défaut ; version facultative.
Il ne stocke pas les poids, comptes ou signaux sources. Les dataclasses internes
ne valident pas à elles seules les résultats fournis à l'adaptateur. Une démo avec
panne/anomalie inventées resterait une simulation de formule ; les dates des
signaux ne sont ni alignées ni contrôlées par le service.

### 3.5 RUL

**Entrées/labels.** Pour l'apprentissage, features numériques/booléennes et
maintenances correctives démarrées ; label = heures calendaires jusqu'au prochain
started_at strictement futur du même équipement. Aucune corrective future : cible
manquante, ligne supprimée par `RULPreparer`. Censure et cycles après réparation
non modélisés ; sélection des seules lignes avec événement futur connu. Cette
RUL est un proxy du délai jusqu'à intervention, pas une durée de vie physique validée.

**Inférence HTTP.** POST `/api/v1/equipments/{equipment_id}/rul` reçoit
`features: dict[str,float]`, sans mesure, fenêtre, unité ou timestamp obligatoire.
Le service vérifie l'équipement, charge le modèle, lit feature_names_in_, rejette
les clés manquantes/surnuméraires, réordonne les colonnes, prédit une ligne puis
persiste. Les noms `temperature` et `vibration` présents dans les tests sont ceux
des fixtures ; ils ne prouvent pas les colonnes du binaire local. Aucun raccord
automatique aux mesures, normalisation d'unité ou contrôle de fraîcheur.

**Algorithme/score.** Forêt de régression ; prédiction ramenée au minimum à 0.
Baseline de comparaison : médiane des cibles d'entraînement. Sortie `rul_hours` en
heures, plus bas = plus urgent. Critical <= 24, warning ]24 ; 72], watch ]72 ; 168],
healthy > 168. Pas d'intervalle d'incertitude ni de seuil calibré par équipement.
Évaluateur MAE/RMSE en heures et R² disponible, sans résultat industriel établi.

**Persistance/provenance.** `persist_rul` écrit score = rul_hours, niveau,
details.rul_hours, model_name fixé à rul_random_forest par l'appelant HTTP et
predicted_at = heure UTC d'exécution. Model_version, horizon, sensor_id,
measurement_id et is_alert restent nuls dans ce chemin. Ni valeurs d'entrée,
empreinte d'artefact, date des mesures ni fenêtre ne sont enregistrées. Le nom
constant ne constitue pas une preuve de provenance. Les float du corps ne font
pas l'objet d'un contrôle explicite de finitude ; dataclass résultat et comparaisons
de seuil ne suffisent pas à garantir cette finitude avant écriture.

## 4. Persistance et relations : chemins identifiés, non déclenchés

`PredictionRecord` contient 14 colonnes : id, equipment_id, sensor_id,
measurement_id, prediction_type, score, level, is_alert, model_name, model_version,
horizon_hours, details, predicted_at, created_at. Equipment obligatoire ; capteur et
mesure facultatifs. Trois FK indépendantes avec ON DELETE CASCADE ; aucune relation
ORM dédiée dans PredictionRecord, aucune FK composite garantissant la cohérence
Equipment/Sensor/Measurement. Company/Site se déduisent seulement via Equipment.
Pas de relation FK entre une recommandation et les prédictions qui la fondent.

La migration `backend/migrations/versions/d6ec01cf13b6_add_prediction_records.py`
crée les mêmes colonnes/FK/index simples, sans CHECK d'échelle/type/niveau/horizon,
contrainte d'unicité de calcul ou manifeste de modèle. Les défauts UTC de dates
sont côté ORM ; la migration n'ajoute pas de défaut serveur à ces dates.

| Point d'entrée | Chemin vers l'écriture | Effet |
| --- | --- | --- |
| POST RUL | route equipment → RULPredictionService.predict_for_equipment → RULModelStore.load → RULService.predict → PredictionService.persist_rul → create → repository.create | INSERT prediction_records puis commit avant réponse HTTP |
| Appel Python de persist_anomaly/failure_risk/health_score/rul | Adaptateur → PredictionRecordCreate → PredictionService.create | Vérification équipement puis même écriture ; aucune orchestration automatique identifiée pour les trois premiers |
| Appel Python direct PredictionService.create | Construction ORM → PredictionRepository.create | db.add, flush, refresh ; service commit puis refresh ; pas de mode dry-run |
| Appel Python direct PredictionRepository.create | db.add + flush + refresh | INSERT possible avant commit ; transaction à la charge de l'appelant |
| POST Health Score | route → HealthScoreService → calculateur | Lecture équipement et calcul seulement ; aucune PredictionRecord |
| GET historique | route → get_paginated → repository items + count | Lecture seule, aucun calcul ni écriture d'historique |
| POST recommandations | RecommendationService.recommend_from_latest_predictions → MaintenanceRecommendationRepository.create | Lit latest de chaque type et écrit maintenance_recommendations ; ne produit pas de PredictionRecord |

Les suppressions de parents peuvent aussi supprimer les prédictions par cascade.
Les tests créent des lignes et entraînent parfois des modèles temporaires si on les
exécute ; ils ont été seulement lus. La répétition du POST RUL ajoute des lignes,
sans clé d'idempotence ; une erreur après commit peut laisser une ligne alors que
le client croit l'appel échoué. Pas de rollback explicite dans ce service.

GET historique : filtre équipement, type/niveau/alerte et dates inclusives
`predicted_at >= start_time`, `<= end_time`, tri date puis id décroissants,
pagination <= 100 côté route. Les bornes diffèrent de l'extraction de mesures
à fin exclusive. Count et items sont deux lectures distinctes. Méthodes get_by_id
et latest existent en Python, sans route HTTP correspondante.

## 5. Qualité, temps et sécurité

### Fuite temporelle : absence non démontrée

- Les décalages et fenêtres sont triés par capteur et utilisent le passé avec point
  courant inclus : acceptable pour détecter après réception du point, pas pour
  prétendre l'avoir prévu. Même timestamp : ordre par id sans antériorité physique.
- Z-score/MAD et IQR sont estimés sur tout le lot ; le détecteur de trous utilise
  la médiane de tous les intervalles ; la forêt est ajustée et évaluée sur le même
  lot. Un backtest historique peut incorporer le futur. Borner chaque appel au
  cutoff et distinguer une analyse rétrospective d'une prédiction en ligne.
- `TemporalDatasetSplitter` trie UTC puis découpe 60/20/20 par nombre de lignes.
  Il ne purge pas les labels dont l'événement dépasse la frontière d'apprentissage,
  n'ajoute pas d'embargo lié à l'horizon et peut couper des timestamps égaux entre
  lots. Pas de séparation par cycles/équipements ni contrôle des fenêtres chevauchantes.
- Les preparers excluent des colonnes de fuite connues mais autorisent toute autre
  colonne numérique ; une colonne cible renommée ou un agrégat futur peut entrer.
  Le statut actuel de capteur/équipement joint à des mesures anciennes n'est pas
  historisé et peut lui aussi divulguer une information ultérieure.
- Les labels futurs sont légitimes pour superviser un apprentissage hors ligne ;
  il faut garantir qu'ils n'entrent pas dans X et que leur période d'observation
  était complètement disponible au cutoff d'entraînement.

### Données invalides, manquantes et périmètre

La politique qualité distingue good, suspect/estimated et bad/missing/inconnue.
Le cleaner accepte les warnings par défaut ; suppression d'outliers optionnelle,
désactivée par défaut. Retirer automatiquement un outlier pourrait précisément
supprimer le signal recherché. Le contrôle isfinite existe comme utilitaire de
politique qualité mais n'est pas une barrière imposée par tous les chemins.
`DataQualityReport` recherche les valeurs non numériques/NA, sans exclure à lui seul
les infinis. Pas d'imputation ou rééchantillonnage global, de seuil de couverture,
de contrôle de fraîcheur ou d'abstention commun. Les capteurs entièrement absents
d'un DataFrame ne peuvent pas être repérés par le détecteur de silence seul.

Les schémas Measurement imposent un timestamp avec fuseau, mais ceux des prédictions
ne l'imposent pas ; pd.to_datetime(..., utc=True) peut interpréter une date naïve
comme UTC. Score générique float libre, niveau libre et JSON non borné permettent
des incohérences. Horizon positif contrôlé au DTO, pas par CHECK SQL. Les adaptateurs
de santé/RUL reçoivent des dataclasses sans validation autonome du score/niveau.

Les jointures et filtres de l'extracteur sont cohérents pour sélectionner une chaîne
industrielle ; ils ne sont pas une autorisation. Routes ML et historique dépendent
de get_db, sans principal ni autorisation entreprise/site/équipement. Changer un id
peut viser un autre tenant. create ne vérifie pas que la mesure appartient au capteur
ni que celui-ci appartient à l'équipement. Ne pas déduire une isolation serveur de
la cascade de sélection UI ou d'un test de filtrage equipment_id.

Le consommateur RecommendationService prend les dernières valeurs de chaque type
indépendamment, sans synchroniser leurs dates, versions, horizons ou fraîcheur.
Un premier historique de démonstration pourrait donc alimenter des recommandations
si cette autre route est appelée. L'isolation de la démo doit couvrir ce consommateur.

### Réserves B-PRE-01 à B-PRE-11

Référentiel : `docs/etape-ui-9.1-predictions.md`, section 4, et maintien dans
`docs/ui-9.7-predictions-delivery.md`. Aucune réserve n'est levée par cet audit.

| Réserve | Constat ML 1 et conséquence pour la suite |
| --- | --- |
| B-PRE-01 | Authentification/autorisation multi-tenant absentes. Bloque une exposition SaaS ; démonstration locale isolée uniquement avant traitement serveur dédié. |
| B-PRE-02 | Score/niveau génériques ; risque de valeurs incohérentes/non finies. Contrat par type et distinction heuristique/probabilité/durée avant interprétation. |
| B-PRE-03 | Dates naïves et périodes inversées non durcies ; extraction fin exclusive contre historique fin inclusive. Fixer cutoff UTC, bornes et tests dédiés. |
| B-PRE-04 | FK indépendantes ; create valide seulement Equipment. Vérifier toute la chaîne entreprise/site/équipement/capteur/mesure avant une première écriture. |
| B-PRE-05 | Details non discriminé et non borné. Définir un schéma versionné, bornes de taille/profondeur et sélection des métadonnées autorisées ; limites UI seulement visuelles. |
| B-PRE-06 | Cascades détruisant l'historique. Ne pas nettoyer une démo par suppression de parents dans DEV ; conservation/archivage à décider séparément. |
| B-PRE-07 | OFFSET/COUNT distincts et index simples. Absence de snapshot/cohérence sous concurrence ; pas de conclusion de performance sans mesure ultérieure autorisée. |
| B-PRE-08 | POST RUL calcule et commit ; joblib de confiance requis, chemin absent divulgué, TypeError non intercepté. Aucun usage de cette route pour préparer la démo ML 1. |
| B-PRE-09 | Alimentation partielle : Health Score non persisté, anomalie/risque non raccordés. Une liste vide ne prouve pas l'absence de modèles. |
| B-PRE-10 | Métadonnées facultatives et absence de contraintes SQL équivalentes aux DTO. Provenance non certifiée, données historiques potentiellement illisibles au contrat Read. |
| B-PRE-11 | Détail/latest seulement Python. La liste existante suffit au premier scénario ; pas de nouvel endpoint requis pour le démontrer. |

## 6. Tests existants : lecture, sans exécution

| Ensemble | Couverture constatée dans les sources |
| --- | --- |
| `tests/data_pipeline`, `data_cleaning`, `feature_engineering` | Extraction et filtres, tri, qualité, dédoublonnage, fenêtres/lags/tendance/vitesse, cas vides, multi-capteurs, dates égales et features partielles |
| `tests/anomaly_detection` | Détecteurs réels sur données synthétiques, seuils, MAD/std nuls, NA, moins de deux lignes complètes, reproductibilité, vote, orchestration et synthèse équipement |
| `tests/failure_risk` | Labels/horizon et UTC, indices répétés, exclusion de colonnes de fuite connues, split temporel, logistique/forêt sur synthétique, scorer et métriques |
| `tests/health_score` | Formules, composantes, poids, niveaux, validation des comptes/probabilités, service et route |
| `tests/rul` | Labels et absence de panne future, preparer, régressions, évaluateur, seuils, store temporaire, service/route, persistance et intégration entraînement synthétique → API → repository |
| `tests/predictions` | Mapping des quatre types, commit/refresh, FK et lecture sur fixtures, pagination/filtres/ordre, schémas et route GET |

Les fixtures communes de `tests/dashboard/support.py` utilisent SQLite mémoire par
défaut et permettent aussi une URL PostgreSQL de test facultative ; aucun de ces
chemins n'est exécuté. Les tests RUL emploient des mocks ou des modèles temporaires,
pas une validation de l'artefact local. Le test d'intégration RUL calcule une erreur
sur les données d'apprentissage et vérifie surtout le raccordement technique ;
il ne démontre pas une généralisation.

Lacunes à traiter avant validation : invariance des résultats passés quand on ajoute
des données futures, purge/embargo des labels, timestamps égaux entre partitions,
censure en fin de suivi, refus des infinis/NaN, abstention pour fenêtre insuffisante,
cohérence des unités et des rattachements, autorisation tenant, provenance/version,
idempotence concurrente et échec transactionnel. Aucun résultat de tests antérieur
n'est revendiqué comme vérifié lors de ML 1.

## 7. Données DEV : possibilités et limites

Le fichier suivi `infra/development/demo-data.json` décrit quatre équipements,
six capteurs, 18 mesures (trois par capteur) et trois maintenances fictives. Le
rapport UI 9.6 documente ensuite 2 entreprises, 4 sites, 6 équipements, 7 capteurs,
18 mesures, 3 maintenances et **0 prediction_records** ; UI 9.7 confirme ce constat
historique. Ces nombres ne sont pas des lectures de base réalisées dans ML 1.

La pompe `UI47-EQ-A-PUMP` / Pompe de circulation P101 appartient au site
`UI47-SITE-A-PROD`, entreprise `UI47-COMP-A`. UI 9.6 la référence comme equipment_id=1,
site_id=1, company_id=1 ; ces ids ne doivent pas être supposés stables ailleurs.
Capteurs du JSON : `UI47-SEN-PUMP-TEMP` en °C et `UI47-SEN-PUMP-VIB` en mm/s.
UI 7.5 documente sensor_id=1 et trois températures good : 64,2, 65,1, 65,4,
les 14, 15 et 16 octobre 2026 à 08:00 UTC (dernier instant avec .123456 seconde).
Il s'agit de valeurs lues dans les sources, sans recalcul.

Trois points quotidiens ne constituent ni un régime normal robuste, ni un jeu
train/validation/test, ni une preuve de panne. Ils ne fournissent pas dix observations
complètes pour les grandes fenêtres ; des features initiales restent manquantes.
La pompe a une maintenance préventive, pas de corrective future dans le JSON :
ses labels RUL seraient non renseignés par la logique existante ; ses labels panne
sans événement seraient des zéros sans garantie de suivi. Le compresseur n'a qu'une
corrective démarrée documentée ; celle planifiée du convoyeur sans started_at ne
sert pas d'événement de panne. Aucun de ces cas ne suffit à valider un modèle supervisé.

Les documents signalent déjà une dérive administrative de description/updated_at
du capteur par rapport au seed strict. Rejouer le seed ou « restaurer » l'historique
ne convient pas pour préparer une démonstration. Les statuts actuels ne doivent pas
être projetés arbitrairement sur les mesures d'octobre.

## 8. Premier scénario proposé, soumis à validation

### Cible et algorithme retenus

Surveiller uniquement la température de la pompe P101, par son code stable et sa
chaîne entreprise/site vérifiée, dans une copie de démonstration indépendante.
Réutiliser `StatisticalAnomalyDetector`, sans SensorAnomalyDetector (qui entraîne
une forêt à chaque appel). L'objectif est de démontrer mesure → signal calculé →
PredictionRecord → liste, avec la mention **« anomalie statistique, démonstration,
sans probabilité de panne »**. Aucun calcul des trois autres types pour ce pilote.

Le détecteur accepte des statistiques fournies ; proposer pour la suite une moyenne
et une std échantillonnale sur les **10 mesures valides strictement antérieures**
du même capteur. À cadence d'une mesure par jour, cela représente dix observations
antérieures, pas une fenêtre fixe de 10 h. Retenir une cadence quotidienne UTC et
une couverture complète dans le jeu synthétique ; en cas de trou, doublon, unité
incompatible, valeur non finie, fenêtre incomplète ou std nulle : s'abstenir et
expliquer la raison. Ces règles ne sont pas actuellement implémentées.

Le choix d'un seuil 3 × std réutilise le défaut du détecteur ; il est pédagogique
et reste à valider sur données industrielles. Les statistiques doivent être
préparées en amont avec décalage, car WindowFeatureBuilder inclut aujourd'hui le
point courant. Pas de réutilisation aveugle du vote unifié : un signal statistique
seul n'atteint pas son seuil par défaut.

### Mesures et démonstration reproductible

Prévoir un petit jeu synthétique figé d'au moins 12 points de température avec UTC,
qualité good, unité °C, ids propres au bac à sable et rattachements explicites :
10 points de référence non constants, un point témoin normal puis un saut conçu
pour dépasser le seuil. Fixer le cutoff de chaque évaluation et les dates du jeu ;
ne pas employer l'heure du jour pour simuler les observations. Conserver les trois
valeurs DEV uniquement comme contexte documentaire ; ne pas les modifier, prolonger
ou attribuer faussement à un événement réel.

Les 10 points sont un choix de démonstration et non une exigence établie du domaine.
Le pilote n'est réalisable tel quel sur les trois seules valeurs historiques :
il nécessite ce jeu distinct et un petit raccordement futur explicitement validé.

### Validation à prévoir dans une étape ultérieure

1. Vérification manuelle des statistiques et de l'écart sur le jeu figé, puis
   comparaison aux sorties du détecteur ; seuil strict `>` et égalité sans alerte.
2. Point normal, saut positif/négatif, série constante, fenêtre insuffisante,
   valeurs NaN/inf, qualité bad/missing, doublons et trous : comportement attendu
   écrit à l'avance ; aucune prédiction « normale » lorsque le calcul est impossible.
3. Ajout ou modification de points après le cutoff : aucune sortie antérieure ne
   change ; point évalué absent de sa référence ; ordre et précision UTC préservés.
4. Mesure d'un autre équipement/site/entreprise et unité incorrecte : refus avant
   écriture ; aucun mélange de capteurs dans les statistiques.
5. Mapping et lecture de l'historique : ids cohérents, score/niveau/alerte conformes,
   métadonnées exactes, filtres de dates et aller-retour DTO ; conservation du JSON.
6. Répétition du même calcul et erreur au moment de l'écriture : au plus une ligne
   pour la même clé de calcul, rollback effectif, aucune ligne partielle ni impact
   sur les tables de mesures. Tests isolés à concevoir, aucun n'est lancé ici.

### Persistance contrôlée à concevoir

Prévoir deux opérations distinctes : préparation sans écriture retournant une
proposition inspectable, puis persistance explicite de cette proposition validée.
Le `PredictionService.create` existant commit lui-même : une simple enveloppe
transactionnelle externe ne suffit pas à garantir une annulation globale. Définir
la transaction du pilote et sa gestion d'erreur avant d'utiliser ce chemin.

Contrat proposé pour ce pilote uniquement : prediction_type anomaly, model_name
`statistical_deviation`, model_version explicite liée au contrat et au HEAD ;
score 0/1 = indicateur binaire de dépassement, is_alert identique, level nul,
horizon nul (détection à réception, pas anticipation). Ce score doit être déclaré
distinct du vote unifié existant et ne doit pas être interprété comme une probabilité.
Si aucune valeur n'est calculable, ne pas créer une ligne à score zéro.

Details versionné et borné à prévoir : caractère synthétique, run_id, code capteur,
unité, horodatage de mesure/cutoff, bornes et taille de référence, moyenne/std,
seuil/multiplicateur, valeur observée, politique qualité, empreinte du jeu et version
du code. predicted_at correspondrait à l'instant du point évalué ; created_at à
l'écriture. Définir cette convention explicitement pour éviter la différence avec
la route RUL actuelle. Aucun artefact entraîné n'est nécessaire.

`persist_anomaly` ne conserve aujourd'hui que reason dans details et ne prend pas
model_version : il ne permet pas à lui seul cette traçabilité. Un raccordement futur
devra soit enrichir cet adaptateur, soit construire un DTO validé pour create, après
résolution des contrôles métier et de transaction. La clé d'idempotence proposée
combine équipement/capteur/mesure, type, version de méthode et empreinte de référence ;
un simple « SELECT puis INSERT » ne garantit pas l'unicité concurrente. Sa protection
devra être choisie et testée séparément, sans migration dans ML 1.

### Protection des historiques DEV

Ne persister le pilote que dans un bac à sable jetable explicitement séparé de la
base DEV permanente, avec configuration et garde de destination vérifiées avant
toute écriture future. Employer uniquement des fixtures synthétiques identifiées,
pas un seed sur DEV. Aucun INSERT/UPDATE/DELETE sur les mesures ou prédictions DEV,
aucune remise à zéro de tables, aucun nettoyage par cascade. Ne pas appeler la route
de génération des recommandations. La suppression éventuelle concernera seulement
l'environnement de démonstration autorisé, jamais les parents des données DEV.

Pour présenter la liste réelle de l'application, envisager ultérieurement une
instance dédiée de démonstration connectée au bac à sable. Ne pas changer le backend
DEV permanent pour obtenir une capture. Sans environnement isolé validé, limiter
la démonstration à une proposition de résultat sans persistance.

## 9. Étapes ML suivantes proposées

1. Valider ce rapport, le périmètre anomalie statistique seul, la convention du score,
   le jeu synthétique et l'environnement isolé. Aucune mise en œuvre avant validation.
2. Dans une étape ultérieure distincte, formaliser contrat d'entrée/sortie, cutoff,
   abstention, provenance, rattachements et stratégie transactionnelle/idempotente ;
   ajouter le raccordement minimal et les validations ciblées du pilote.
3. Démontrer un signal normal et une alerte explicables, persistés uniquement dans
   le bac à sable, puis lus par la liste existante ; documenter les limites sans
   revendiquer une précision industrielle.
4. Après acceptation du pilote, préparer un corpus de pannes réellement qualifiées,
   un suivi complet, une séparation temporelle purgée et une évaluation hors période.
   Comparer logistique/forêt de risque et médiane/forêt RUL ; calibrer les scores et
   documenter les artefacts avant tout raccordement supervisé.
5. Intégrer ensuite le Health Score comme indice heuristique versionné, seulement
   lorsque ses composantes ont une provenance et une fraîcheur cohérentes. Traiter
   les réserves transverses, notamment B-PRE-01/04, avant toute exposition multi-tenant.

**Statut de livraison : audit documentaire terminé, aucune chaîne déclenchée ;
rapport en attente de validation. ML 2 non commencé.**
