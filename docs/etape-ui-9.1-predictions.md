# UI 9.1 - Analyse et conception du module Prédictions

Date : 24 octobre 2026. Statut : conception proposée, en attente de validation.

## 1. Contexte, objectifs et méthode

Industrial Predict AI utilise Angular 21.2.25 standalone, Nebular 17.0.0,
TypeScript strict, FastAPI, SQLAlchemy, PostgreSQL et des modules ML internes.
UI 8.8 est intégrée dans la référence de départ demandée `024c740`.
Objectif UI 9 : consulter les prédictions déjà persistées d'un équipement,
avec contexte industriel explicite et contrats réellement exposés.

UI 9.1 est exclusivement documentaire. Seul ce document est créé. Aucun
composant, contrat backend, migration, package ou document historique modifié.
Aucun test, build, import/exécution Python métier, calcul ML, appel HTTP,
accès PostgreSQL, seed ou opération Docker effectué. L'audit repose sur les
sources et les tests existants lus, sans les exécuter.

Préparation Git : branche initiale `main`, arbre propre ; `HEAD`, `main` et
la référence locale `origin/main` identiques à
`024c740a64a084def6f2c495f492feb7143c53dd`. Branche créée et utilisée :
`docs/ui-9-predictions-design`. La création a nécessité une relance autorisée
car le sandbox interdisait initialement l'écriture des références Git.
Aucun fetch : la concordance avec le serveur distant en direct n'est pas
certifiée ; la synchronisation constatée concerne les références locales.

Les documents d'architecture et de statut contiennent encore des références
historiques antérieures à la fusion UI 8.8. Le code à `024c740` prévaut pour
cet audit ; ces documents ne sont pas actualisés pendant UI 9.1.

## 2. Inventaire exact des API pertinentes

### 2.1 Historique : seule API Prédictions consommée par le MVP

`GET /api/v1/equipments/{equipment_id}/predictions`

Preuves : `backend/app/main.py` enregistre le routeur Equipment sous `/api/v1` ;
`backend/app/api/routes/equipment.py::get_equipment_predictions` expose la route ;
`PredictionService.get_paginated` vérifie l'existence de l'équipement puis lit
les items et leur compte dans `PredictionRepository`.

| Paramètre | Emplacement | Contrat backend réel |
| --- | --- | --- |
| `equipment_id` | chemin, obligatoire | `int`, aucune contrainte `ge=1` sur la route ; un entier inexistant donne 404 |
| `page` | query, facultatif | `int >= 1`, défaut 1 |
| `page_size` | query, facultatif | `int` de 1 à 100, défaut 20 |
| `prediction_type` | query, facultatif | enum `anomaly`, `failure_risk`, `health_score`, `rul` ; défaut `None` |
| `level` | query, facultatif | chaîne de 1 à 50 caractères, égalité exacte ; aucun enum ; défaut `None` |
| `is_alert` | query, facultatif | booléen, défaut `None` ; transmettre explicitement `false` est valide |
| `start_time` | query, facultatif | `datetime`, défaut `None`, comparaison `predicted_at >= start_time` |
| `end_time` | query, facultatif | `datetime`, défaut `None`, comparaison `predicted_at <= end_time` |

Tous les filtres présents sont combinés par AND. Les valeurs nulles Python
signifient filtre omis ; le texte query `null` n'est pas une valeur nulle JSON.
Le client émettra seulement `true` ou `false` pour le booléen, et omettra les
autres filtres non choisis. Sans filtre d'alerte, les lignes true, false et NULL
peuvent être retournées ; aucun filtre « NULL uniquement » n'est exposé.

Réponse 200 : `Page[PredictionRecordRead]`, exactement
`{ items: PredictionRecordRead[], total: int, page: int, page_size: int, pages: int }`.
`total >= 0`, `pages >= 0`, `page >= 1`, `page_size >= 1` ;
`pages = ceil(total / page_size)`, ou 0 si total vaut 0.
Le total utilise les mêmes filtres que les items. Pagination OFFSET/LIMIT,
tri imposé `predicted_at DESC, id DESC`, sans paramètre de tri.
Une page au-delà du dernier résultat est acceptée : items vides, total conservé.
Équipement existant sans historique : 200, items vides, total 0 et pages 0.

Erreurs : 404 `{"detail":"Equipment not found"}` ; 422 de validation FastAPI
avec `detail` tableau d'erreurs (`loc`, `msg`, `type`, autres champs possibles).
Les erreurs SQL et de sérialisation ne sont pas traduites par cette route en
erreurs métier dédiées. Aucun contrat 401/403 implémenté sur cette route.
Aucun contrôle d'ordre des dates ni exigence d'offset n'y est déclaré.
Des bornes égales sont valides et sélectionnent l'instant exact ; une période
inversée n'est pas explicitement rejetée. Les deux bornes sont inclusives.

Effets : lecture de l'équipement, SELECT des items et COUNT ; aucun appel ML,
`create`, flush ou commit dans ce chemin. La session est fermée par `get_db`.
Isolation : filtre par equipment_id seulement, sans identité utilisateur,
vérification d'appartenance à un tenant ni politique d'accès à la ressource.

Il n'existe pas de route HTTP `GET /predictions/{id}`, de GET « latest », de
liste globale `/predictions`, ni de POST générique de prédiction enregistré.
Les méthodes Python `get_by_id`, `get_latest_by_equipment_and_type`,
`get_history_for_equipment` et `create` ne constituent pas des endpoints.

### 2.2 Opérations de calcul, exclues du MVP et jamais appelées ici

| Méthode et URL | Entrée obligatoire | Facultatifs | Réponse et effets |
| --- | --- | --- | --- |
| `POST /api/v1/equipments/{equipment_id}/health-score` | chemin `equipment_id: int` ; corps `failure_probability: float [0,1]`, `anomaly_score: float [0,1]`, `valid_count`, `warning_count`, `invalid_count: int >= 0` | `corrective_in_progress`, `overdue_maintenance`, `planned_soon: bool`, défaut false | 200 `HealthScoreRead` ; calcul à partir du corps fourni, sans persistance dans ce service |
| `POST /api/v1/equipments/{equipment_id}/rul` | chemin `equipment_id: int` ; corps `features: dict[str,float]` | aucun champ métier facultatif déclaré | 200 `RULPredictionRead` ; chargement du modèle, inférence et persistance avec commit |

Ces identifiants de chemin n'ont pas de borne positive explicite. Les corps
sont obligatoires et non nullables ; aucune pagination, filtre ou tri.
Health Score exige au moins une observation qualité : somme des trois compteurs
strictement positive, sinon 422. Réponse exacte :
`{ equipment_id: int, health_score: float, health_level: str, components: { failure_health: float, anomaly_health: float, data_quality_health: float, maintenance_health: float } }`.
Tous ces champs sont non nullables ; aucun horodatage ni identifiant de
PredictionRecord n'est renvoyé. 404 équipement absent ; 422 pour corps invalide.
La route intercepte seulement `LookupError`. Le service ne déduit pas ses
entrées des mesures ou maintenances stockées et n'appelle pas `persist_health_score`.

RUL : les noms exacts des features dépendent de `model.model.feature_names_in_`,
donc ne sont pas découvrables via ce contrat. Features manquantes ou inattendues
et absence de résultat donnent 422 avec `detail` chaîne. Corps invalide : 422
FastAPI. Équipement absent : 404. Artefact absent : 503 avec `detail` chaîne.
Réponse exacte : `{ equipment_id: int >= 1, rul_hours: float >= 0, rul_level: str }`,
non nullable. Le service persiste avant de répondre, date UTC courante,
`model_name="rul_random_forest"`, sans version renseignée. Un nouvel appel peut
donc créer une nouvelle ligne, y compris après une répétition automatique.
`RULModelStore.load` utilise `joblib.load` et vérifie ensuite le type de modèle ;
`TypeError`, corruption d'artefact ou autres erreurs non interceptées n'ont pas
de traduction métier garantie. Aucun chargement d'artefact réalisé dans l'audit.

Anomaly Detection et Failure Risk sont présents comme modules Python et
méthodes de persistance ; aucun endpoint HTTP de calcul dédié n'est enregistré
dans `main.py` ou les routeurs examinés. Leur présence ne prouve ni un modèle
entraîné disponible en DEV, ni une alimentation automatique de l'historique.
Les explainers Python ne sont pas des services HTTP d'explication par ligne.

Frontière de périmètre : les routes Equipment `/recommendations` sont un
autre contrat fonctionnel, avec GET d'historique et POST de génération.
Elles ne sont pas des sources de prédictions ou d'explications pour UI 9.
Aucune consommation ou conception de leur écran n'est incluse ici.

### 2.3 GET de référence pour la sélection et les rattachements

| URL sous `/api/v1` (GET) | Paramètres | Réponse, ordre et erreurs |
| --- | --- | --- |
| `/companies` | page=1, page_size=20 (1..100), search facultatif de 1..100 caractères | `Page[CompanyRead]`, id ASC ; 422 query invalide |
| `/sites` | mêmes paramètres ; company_id facultatif entier >=1 | `Page[SiteRead]`, id ASC ; 422 query invalide |
| `/equipments` | mêmes paramètres ; site_id facultatif entier >=1, status et criticality facultatifs enums | `Page[EquipmentRead]`, id ASC ; 422 query invalide |
| `/companies/{company_id}` | chemin int obligatoire | `CompanyRead`, 404 Company not found, 422 chemin invalide |
| `/sites/{site_id}` | chemin int obligatoire | `SiteRead`, 404 Site not found, 422 chemin invalide |
| `/equipments/{equipment_id}` | chemin int obligatoire | `EquipmentRead`, 404 Equipment not found, 422 chemin invalide |

Page est le même schéma qu'en 2.1 ; `page >= 1`. Search porte sur nom/code pour
Company et Site, nom/code/type pour Equipment (ILIKE). Status Equipment :
`operational|maintenance|out_of_service` ; criticality : `low|medium|high|critical`.
Les listes ne prouvent pas à elles seules l'existence du parent demandé.
Les chemins détail n'imposent pas `ge=1` explicitement.
CompanyRead : id entier, name/code chaînes, description chaîne ou null,
created_at/updated_at datetime non nuls. SiteRead ajoute company_id entier ;
EquipmentRead ajoute site_id entier, equipment_type chaîne, status et criticality
enums. Ces dates administratives peuvent être naïves, contrairement au stockage
temporel prévu des prédictions. Ces GET n'effectuent pas de calcul ML ni
d'écriture métier, et ne démontrent aucune autorisation multi-entreprises.
Les anciens GET non paginés `/sites/company/{company_id}` et
`/equipments/site/{site_id}` sont écartés au profit des listes paginées.

## 3. Schémas persistés, sémantique et données DEV

### 3.1 PredictionRecordRead et table prediction_records

| Champ JSON | Type Pydantic lu / nullabilité | Stockage et remarque |
| --- | --- | --- |
| `id` | int, non nul | PK Integer, index ; pas de `ge` dans le schéma Read |
| `equipment_id` | int >=1, non nul | FK equipments.id CASCADE, index |
| `sensor_id` | int >=1 ou null | FK sensors.id CASCADE, index |
| `measurement_id` | int >=1 ou null | FK measurements.id CASCADE, index |
| `prediction_type` | enum quatre types, non nul | String(50), index ; aucun CHECK enum SQL |
| `score` | float, non nul | Float ; aucune borne métier ni finitude explicitement imposée par ce schéma |
| `level` | str ou null | String(50), index ; aucun enum ou longueur Pydantic sur la réponse |
| `is_alert` | bool ou null | Boolean ; null distinct de false |
| `model_name` | str ou null | String(100) |
| `model_version` | str ou null | String(50) |
| `horizon_hours` | float >0 ou null | Float ; pas de CHECK SQL |
| `details` | dict[str,Any] ou null | JSON ; objet non discriminé, clés et valeurs imbriquées non spécifiées |
| `predicted_at` | datetime, non nul | DateTime(timezone=True), index |
| `created_at` | datetime, non nul | DateTime(timezone=True) |

Le modèle ORM fournit des défauts Python UTC pour les deux dates ; la migration
ne définit pas de défaut serveur pour ces colonnes. PredictionRecordCreate
requiert predicted_at. `created_at` est la date d'enregistrement, pas une seconde
date de calcul à substituer à predicted_at. Il n'existe ni updated_at, titre,
recommandation, confiance, intervalle d'incertitude ni explication IA dédiée.

La relation Equipment est une FK ; Equipment ne déclare pas de collection ORM
`predictions` dans le fichier lu. Aucun chargement de cette collection n'est requis.
Les FK vers équipement, capteur et mesure sont indépendantes : elles ne
garantissent pas que ces trois références appartiennent à la même chaîne.
PredictionService.create vérifie seulement l'existence de l'équipement.

### 3.2 Interprétation par type, fondée sur les producteurs existants

| Type / libellé proposé | Producteur et score | Niveau et détails réellement persistés |
| --- | --- | --- |
| `anomaly` / Anomalie | persist_anomaly copie anomaly_score ; AnomalyResult le borne à [0,1] | is_alert copie is_anomaly ; level reste null ; model_name=method ; details={reason} si reason non nul, sinon null ; date=timestamp de l'anomalie |
| `failure_risk` / Risque de panne | persist_failure_risk copie risk_score fourni ; FailureRiskScorer produit habituellement probability * 100 | level=risk_level fourni ; details.failure_probability validée [0,1] ; horizon_hours facultatif ; is_alert reste null |
| `health_score` / Indice de santé | persist_health_score copie result.health_score ; calculateur existant produit un indice [0,100], plus élevé = meilleure santé | level=health_level ; details.components contient les quatre composantes santé ; pas de probabilités ; is_alert reste null |
| `rul` / Durée de vie utile restante | persist_rul copie result.rul_hours, unité heures explicite ; régression existante écrête les valeurs négatives à 0 | level=rul_level ; details.rul_hours duplique la valeur ; model_name par défaut rul_random_forest ; is_alert et horizon_hours restent null |

Les niveaux actuels des calculateurs sont : risque `low|medium|high|critical` ;
santé `healthy|good|degraded|poor|critical` ; RUL `critical|warning|watch|healthy`.
Ils ne constituent pas un enum universel de PredictionRecord.level.
Le score d'anomalie unifié combine des signaux de détection pondérés ; il ne
mesure pas une probabilité de panne. Le classifieur de risque utilise actuellement
0,25/0,50/0,75 ; le classifieur santé 85/70/50/30 ; le classifieur RUL a des
défauts configurables 24/72/168 heures. Ces seuils du code ne sont ni exposés
ni historisés dans chaque ligne : l'UI ne les réapplique pas à l'historique.

Limite majeure : le schéma générique permet des scores/niveaux incohérents avec
les producteurs. Les fixtures le montrent aussi (santé 85 avec niveau good ;
persistance risque 0,75 avec high). Afficher le niveau fourni, sans recalculer
la classe ni déduire une probabilité du score. Une probabilité de panne peut
être présentée seulement depuis `details.failure_probability` numérique finie
dans [0,1], explicitement nommée, éventuellement convertie en pourcentage.
Ne jamais appeler la colonne score « probabilité » globalement.

Présentation proposée : anomalie « Indice d'anomalie : valeur » ; risque
« Score de risque déclaré : valeur » sans `%` ni `/100` garanti ; santé
« Indice de santé : valeur / 100 » seulement si le contrat et la provenance du
producteur établissent cette échelle et si la valeur est dans [0,100]. La seule
plage numérique ne permet jamais d'inférer une échelle ; si la provenance ne
permet pas de la confirmer, afficher « Score déclaré : valeur » sans dénominateur.
Une valeur hors de la plage établie est présentée comme « Score déclaré hors
plage attendue » avec valeur brute ; RUL « valeur h »
si valeur non négative, sans date de panne extrapolée. Une incohérence de
details.rul_hours avec score reste signalée, jamais corrigée silencieusement.
Ne pas confondre horizon de risque et durée RUL. Aucune moyenne inter-types.

### 3.3 Migrations et environnement permanent

Chaîne documentaire lue dans les révisions versionnées :
`0468ed5be8f1` Companies -> `50e5051527dc` Sites -> `656260b06cdf` Equipments ->
`572080d9e581` Sensors -> `570ce155aaf8` Measurements ->
`783e16aa6ce3` Maintenance -> `675ebfea0bb5` Equipment criticality ->
`d6ec01cf13b6` PredictionRecord -> `09ac8101e9fe` Maintenance recommendations.
La dernière révision dépend directement de celle créant prediction_records.
Une DEV correctement migrée à `09ac8101e9fe` doit donc contenir cette table et
ses index simples ; aucun index composite équipement/date/id n'est créé.
C'est une compatibilité attendue d'après les fichiers, pas une inspection SQL.

`infra/development/manage.py` et son README imposent la révision `09ac8101e9fe`,
la base `industrial_predict_dev` sur 127.0.0.1:5434, API 8001, Angular 4201,
rôle applicatif `ui47_app`, et huit tables dont prediction_records.
Le proxy DEV vérifie la cible ; aucun repli vers l'environnement historique
5433/8000/4200. Les droits CRUD applicatifs décrits ne sont pas une protection
tenant. La configuration privée et ses secrets ne sont pas lus ici.

Le jeu versionné `demo-data.json` et `seed.py::SCHEMAS` couvrent seulement
Companies, Sites, Equipments, Sensors, Measurements et Maintenance. Le seed
ne produit aucune PredictionRecord ; ses contrôles portent aussi sur les huit
tables et refusent certains chargements initiaux non vides. Ne pas le relancer
pour peupler l'écran. Les fixtures tests ne sont pas des données DEV.

Vérifications différées à UI 9.6 : identité effective de DEV, révision réellement
appliquée, privilèges SELECT, existence/quantité/types et qualité des prédictions,
offsets réellement sérialisés et concordance pagination/stockage. Aucun état
vide ou peuplé de prediction_records n'est présumé aujourd'hui. La disponibilité
d'un artefact RUL n'est pas nécessaire au GET d'historique et n'est pas vérifiée.

## 4. Risques backend et sécurité

Priorités : P1 = forte, bloque une exposition SaaS ou une interprétation fiable ;
P2 = à traiter/encadrer ; P3 = amélioration ou capacité volontairement absente.
Ces constats proposent des suites, sans autoriser de correctif backend en UI 9.1.

| Risque | Preuve dans le code | Impact | Priorité / traitement proposé |
| --- | --- | --- | --- |
| B-PRE-01 | route Equipment Depends(get_db) seulement ; repository filtre equipment_id sans principal/tenant ; get_db ouvre une session sans politique de ressource | accès à l'historique d'un autre équipement par identifiant ; calculs voisins également accessibles | P1, bloque production SaaS multi-tenant ; authentification et autorisation serveur à concevoir séparément ; cascade UI insuffisante |
| B-PRE-02 | PredictionRecordBase.score float libre, level str libre ; persist_failure_risk ne vérifie pas risk_score contre probability | échelles incohérentes, niveaux contradictoires, sérialisation potentiellement invalide de nombres non finis | P1 pour interprétation ; afficher données déclarées, vérifier finitude et ne pas inventer de pourcentage/seuil ; validation backend discriminée à proposer |
| B-PRE-03 | datetime simple dans la route et les DTO ; repository >= et <=, sans validation de période/offset | dates naïves ambiguës, inversion acceptée ; réutilisation des aides fin exclusive incorrecte | P2 ; validation frontend dédiée avec offset et début <= fin ; durcissement backend ultérieur |
| B-PRE-04 | create vérifie Equipment seul ; trois FK indépendantes dans la migration | capteur/mesure potentiellement rattachés à un autre équipement, intégrité métier non assurée | P1 avant liens descendants ou production ; ne pas produire de navigation capteur/mesure depuis ces seuls IDs |
| B-PRE-05 | details dict[str,Any], JSON sans schéma/limite déclarée | détails mal formés ou volumineux, divulgation de contenu du producteur, affichage trompeur | P2 ; validation de chaque champ connu, texte échappé et JSON dépliable borné ; les limites de 10 000 caractères et six niveaux concernent uniquement la présentation frontend, ni le volume réseau ni la taille autorisée par le backend ; schéma versionné futur |
| B-PRE-06 | table et modèle : CASCADE pour equipment/sensor/measurement | suppression d'un parent détruit des lignes historiques ; absence de garantie d'archivage immuable | P2 ; aucun DELETE UI 9 ; politique de conservation backend séparée |
| B-PRE-07 | repository OFFSET/LIMIT + COUNT distinct, index simples seulement | coût des grandes pages, total/items susceptibles de diverger sous écritures concurrentes ; ordre stable ne garantit pas un snapshot | P2 ; page <=100, aucun chargement exhaustif ; diagnostic SQL/index et pagination alternative après mesure autorisée |
| B-PRE-08 | POST RUL persiste avant réponse ; FileNotFoundError->503 ; joblib.load, TypeError non intercepté ; detail inclut le chemin absent | répétitions d'inférence créent des lignes, erreurs artefact possibles, divulgation d'un chemin interne ; artefact chargé doit être de confiance | P2, hors MVP ; interdire POST dans transport Angular ; durcissement/idempotence/erreurs et gestion artefacts à proposer séparément |
| B-PRE-09 | HealthScoreService ne persiste pas ; persist_health_score est une méthode distincte ; aucun calcul HTTP anomalie/risque | calcul disponible ne signifie pas historique alimenté ; liste vide mal interprétée | P2 ; état vide neutre, aucune génération automatique ni diagnostic d'absence de modèle à partir du GET |
| B-PRE-10 | Read impose enum/horizon >0 mais SQL n'a pas ces CHECK ; path equipment_id int sans ge ; métadonnées modèle facultatives | données SQL historiques invalides peuvent faire échouer la réponse ; provenance/modèle exact parfois inconnus | P2 ; erreurs de contrat explicites, métadonnées absentes affichées comme telles ; audit réel différé |
| B-PRE-11 | get_by_id et latest existent seulement en Python, sans route ; pas de recherche/tri HTTP de prédictions | écran détail rechargeable ou tri/recherche globale impossibles avec les contrats présents | P3, limite assumée ; détails dans la page, pas de nouvel endpoint requis pour le MVP |

Les requêtes SQL utilisent les expressions SQLAlchemy paramétrées. Cela ne
résout pas B-PRE-01. Aucun résultat de cet audit ne certifie une isolation
multi-tenant, un contrôle RBAC, un déploiement sûr ou des artefacts ML fiables.

## 5. Audit frontend et parcours utilisateur

L'application comporte un Shell Nebular, Sidebar, Header, routes Angular lazy
et composants standalone avec OnPush. `NAVIGATION_ITEMS` contient déjà
`/predictions`, status available ; `app.routes.ts` l'envoie actuellement vers
FeaturePlaceholderComponent. Sidebar détermine l'état actif par section en
ignorant query params et fragments. Pas de feature predictions implémentée.

Dashboard suit page -> façade locale signals/switchMap -> service GET ; ses
agrégats, ses périodes et son absence de KPI ML restent distincts. Ne pas
intégrer de nouvelles métriques dans Dashboard pendant UI 9.
Maintenance fournit le meilleur précédent de cascade Entreprise/Site/Équipement,
catalogues paginés, contrôles des parents et annulation des lectures obsolètes.
Measurements fournit les calculs purs d'instants à microsecondes et la
préservation des offsets, ainsi que la distinction brouillon/filtres appliqués.
Les helpers de période de ces deux modules ne sont pas réutilisables tels quels
pour les bornes inclusives Prédictions.

Equipment Detail résout Equipment -> Site -> Company avec erreurs et retry
séparés ; ses liens Sensors et Maintenance reposent sur les parents réels.
Il ne consomme pas les prédictions aujourd'hui. Ses tests excluent actuellement
le libellé Prédiction : les attentes de navigation devront être ajustées dans
l'étape autorisée, tout en conservant l'absence de calcul/chargement ML en fiche.

Parcours proposé :

1. Sidebar -> Prédictions : titre et instruction de sélection, catalogue
   entreprises paginé ; aucune entreprise par défaut et aucun GET historique.
2. Choisir Entreprise, puis Site de cette entreprise, puis Équipement de ce site.
   Les catalogues descendants sont désactivés sans parent, paginés côté serveur,
   et présentent nom/code métier. Changer de parent efface descendants et résultats.
3. Vérifier via GET détail les identifiants et les rattachements réels. Une URL
   complète peut préremplir les choix ; une référence falsifiée ou incompatible
   bloque le GET historique. Une URL partielle permet de poursuivre la sélection,
   sans inférer une entreprise ou sélectionner le premier résultat.
4. Charger la page 1 d'historique dès que les trois références sont validées.
   Appliquer les filtres disponibles, changer de page ou de taille ; chaque
   changement de filtre/taille remet à page 1 et conserve le périmètre validé.
5. Déplier les détails d'une ligne déjà reçue, sans requête supplémentaire.
   Revenir à la fiche équipement ou à la liste précédente avec contexte explicite.
6. Depuis Equipment Detail, « Voir les prédictions » est disponible seulement
   quand les vrais parents sont résolus ; ouverture de /predictions avec les
   trois IDs réels, page 1 et page_size 20. Aucun filtre Equipment de recherche,
   statut ou criticité n'est réinterprété comme filtre Prédictions.

## 6. Structure proposée des écrans

Une seule page liste, pas de page `/predictions/:predictionId` : le GET paginé
fournit déjà les 15 champs, sans GET détail permettant un rechargement autonome.
Pas de graphique, classement inter-types, tableau de bord ML ou bouton calculer.

Ordre de lecture : PageHeader « Prédictions », aide de consultation ; sélection
hiérarchique ; rappel nom/code des trois références ; filtres appliqués ; état
de lecture ; tableau d'historique et pagination. Les filtres métier sont type,
niveau libre exact (1..50 caractères), alerte Tous/Oui/Non, début/fin de
predicted_at. Niveau ne propose pas une liste fermée fondée sur les lignes de
la seule page courante. Aucun search, filtre modèle/capteur, score min/max ou tri
interactif n'est exposé car aucun contrat correspondant n'existe.

Les bornes UTC ont date, heure avec secondes et fraction optionnelle jusqu'à
six chiffres. Aucune heure, date actuelle ou période par défaut inventée.
Application explicite et réinitialisation des bornes ; aide « début et fin
inclus ». Validation immédiate des champs modifiés, blocage local à Appliquer
et focus sur le résumé d'erreur, selon les conventions UI 8.8.

Colonnes : date/heure de prédiction, type, valeur avec libellé spécifique,
niveau déclaré, alerte Oui/Non/Non renseignée, action « Détails ».
L'équipement est rappelé dans le contexte, sans répéter son ID technique en titre.
Un panneau natif details/summary par ligne affiche modèle/version/horizon si
présents, date d'enregistrement distincte, champs de details connus et JSON
complémentaire échappé. « Aucun détail fourni » pour null ; objet vide distinct.
Les IDs sensor/measurement, s'ils sont montrés dans les métadonnées, sont des
références déclarées sans lien ni nom inventé.

États : idle invite à choisir ; loading masque les résultats du périmètre
précédent ; empty sans filtre dit « Aucune prédiction enregistrée pour cet
équipement » ; empty avec filtres dit « Aucune prédiction ne correspond aux
filtres » et permet leur effacement. Total >0 avec items vides et page hors
plage propose retour page 1, sans prétendre que l'équipement n'a pas d'historique.
Un GET vide ne dit pas « modèle absent ». Pas de données fictives de remplacement.

Réseau/5xx : ErrorState avec retry manuel de la même requête appliquée ;
404 : référence indisponible, retour aux choix ; 422 : filtres/paramètres à
corriger ; 401/403 éventuels : accès refusé sans retry automatique, sans les
présenter comme une protection déjà implémentée. Réponse mal formée ou scope
incohérent : erreur non réessayable automatiquement, aucun résultat exposé.
Une absence de modèle RUL n'est pas un état du GET ; son 503 appartient au POST
exclu. Un 503 du GET reste une indisponibilité sans cause supposée.

## 7. Contrats frontend et architecture technique proposés

Tous les chemins suivants sont envisagés seulement ; aucun n'est créé en UI 9.1.

| Fichiers sous `frontend/src/app/` | Responsabilité future |
| --- | --- |
| `features/predictions/models/prediction.model.ts` | PredictionType union exacte, PredictionRead (15 champs), PredictionPage=Page<PredictionRead>, JsonValue récursif sans any |
| `features/predictions/models/prediction-page-query.model.ts` | equipment_id obligatoire ; page/page_size et filtres GET optionnels, sans company_id/site_id HTTP |
| `features/predictions/models/predictions-state.model.ts` | query UI avec trois IDs, états discriminés idle/loading/empty/success/error et brouillons séparés |
| `features/predictions/data-access/predictions-api.service.ts` et `.spec.ts` | méthode list uniquement GET /equipments/{id}/predictions ; validation requête/réponse ; faux booléen préservé |
| `features/predictions/predictions-list.facade.ts` et `.spec.ts` | références, rattachements, état local, switchMap/DestroyRef, retry manuel, filtrage/page |
| `features/predictions/predictions.routes.ts` et `.spec.ts` | route vide lazy vers liste, title et pageTitle ; pas de route détail |
| `features/predictions/pages/predictions-list/predictions-list.component.ts`, `.html`, `.scss`, `.spec.ts` | cascade, URL, brouillons, présentation, détails dépliables et pagination |
| `features/predictions/utils/prediction-time.ts` et `.spec.ts` | validation de période inclusive dédiée ; aide de saisie sans message de fin exclusive |
| `features/predictions/utils/prediction-display.ts` et `.spec.ts` | présentation type/niveau/score et accès sûrs aux détails hétérogènes |
| `features/predictions/utils/prediction-navigation.ts` et `.spec.ts` | whitelist du contexte et construction des retours internes |

Points d'intégration futurs : `app.routes.ts` pour le loadChildren predictions ;
`app.routes.spec.ts` pour la route lazy ; Equipment Detail `.ts/.html/.spec.ts`
et un test de navigation dédié pour les liens aller-retour ; SCSS de la fiche
et `styles/_buttons.scss` si un sélecteur d'action doit être ajouté, avec les
états hover/active/focus/reduced-motion. Ne pas créer un second style de boutons.
La configuration Sidebar existe déjà et n'exige pas une nouvelle entrée.

Réutilisations : Page core, ReferenceDataApiService, quatre composants partagés
PageHeader/LoadingState/EmptyState/ErrorState, businessReferenceLabel, tokens
et mixin navigation-action. Les instants peuvent utiliser `measurementInstant`,
`measurementUtcParts` et `formatMeasurementUtc` comme fonctions pures ; ne pas
importer le service HTTP ou la façade Measurements. Ne pas appeler
validateMeasurementPeriod/validateMeasurementPeriodDraft pour les prédictions :
ils refusent l'égalité et leur texte indique une fin exclusive.
Pas d'extraction transverse ou de modification des helpers existants requise
par cette conception ; l'adaptation des brouillons reste dans la nouvelle feature.

DTO : les clés nullables de PredictionRead sont présentes avec `| null`, pas
des propriétés optionnelles. details : `{ [key: string]: JsonValue } | null`,
JsonValue = string | number | boolean | null | JsonValue[] | objet récursif.
Les vues typées reason/failure_probability/components/rul_hours sont des
adaptations validées à l'exécution, pas des garanties du JSON générique.
level reste `string | null` ; les traductions connues ont un repli texte
échappé pour une valeur inconnue. prediction_type reste l'union exacte du backend.

Le service valide les entiers sûrs positifs, page_size 1..100, enum, booléen,
longueur Unicode de level et instants calendaires avec offset. Il lit la
réponse comme donnée à vérifier : structure complète, nombres finis,
nullabilité, identifiants, type, horizon, dates, page/compteurs, puis appartenance
de toutes les lignes à equipment_id. Pas de coercition silencieuse ni rejet
d'un niveau simplement inconnu. Une valeur hors plage d'un producteur n'est
pas transformée en pourcentage : elle est signalée comme donnée déclarée.

Query URL prévue : company_id, site_id, equipment_id, page, page_size,
prediction_type, level, is_alert, start_time, end_time. Seuls equipment_id dans
le chemin et les filtres/pagination de 2.1 partent vers l'historique API.
Une valeur absente diffère de `false`, de zéro et d'une chaîne vide invalide.
Valeur critique invalide ou clé reconnue dupliquée : message local et lecture
historique bloquée jusqu'à correction ; aucune suppression silencieuse d'un
filtre invalide qui élargirait les résultats. Clés étrangères au contrat ignorées.

Pour le retour Prédictions -> Equipment -> Prédictions, prévoir un contexte
de navigation typé, limité à `from=predictions` et à des paramètres préfixés
`pre_` correspondant exactement à la whitelist ci-dessus. Construire les
destinations avec RouterLink/UrlTree à chemins fixes `/predictions` et
`/equipments/{id}` ; ne jamais accepter une URL de retour arbitraire.
Ce contexte est indépendant de listQuery Equipment et de ses vrais parents.
Un retour reçu ne déclenche aucune lecture de scope non vérifié. En absence
de contexte valide, retour à /predictions sans filtre. Les liens vers d'autres
modules ne propagent ni les paramètres pre_ ni les filtres Prédictions.
La liste rétablit son état par URL après rechargement ; les panneaux dépliés
n'ont pas besoin d'être persistés. Les fragments éventuels sont limités à des
ancres locales connues, sans redirection ou interprétation HTML.

## 8. Décisions PRE proposées

Toutes les décisions ci-dessous sont à valider, aucune n'est réputée approuvée.

| ID | Décision |
| --- | --- |
| PRE-01 | MVP strictement read-only : uniquement GET historique et GET références ; aucun calcul, POST/PATCH/DELETE, seed, modèle de remplacement ou polling |
| PRE-02 | Trois sélections explicites requises ; chargement historique seulement après résolution et validation de la chaîne réelle ; aucun défaut d'entreprise |
| PRE-03 | Vérifier id demandé=id reçu, equipment.site_id=site.id, site.company_id=company.id et chaque item.equipment_id ; incohérence bloque l'affichage ; le contrôle UI n'est pas une autorisation |
| PRE-04 | URL source de l'état appliqué, brouillons séparés ; type/niveau/alerte/période seulement ; page 1 lors de changement de filtre/taille/périmètre ; conserver explicitement false |
| PRE-05 | DTO stricts reflétant nullabilité et enum exacts ; JSON sans any ; validation HTTP à l'exécution ; pas de coercition ni d'extensions de contrat inventées |
| PRE-06 | Période predicted_at [début, fin], bornes inclusives et égalité permise ; filtres comparés comme instants avec offsets et précision microseconde conservés, chaînes ISO originales préservées ; aucune normalisation silencieuse altérant les chaînes temporelles ou les instants ; ne pas transformer la fin en borne exclusive |
| PRE-07 | Afficher date de prédiction et date d'enregistrement séparément ; conserver fractions, offsets et chaînes des filtres, sans normalisation silencieuse altérant les chaînes temporelles ou les instants ; UTC annoncé seulement si offset valide ; si date naïve reçue, erreur de contrat et aucune conversion implicite ; les filtres restent inclusifs avec égalité permise selon PRE-06 |
| PRE-08 | Présentation spécifique par type selon le contrat et la provenance du producteur ; aucune échelle universelle du score, aucune échelle inférée de la seule plage numérique, notamment aucun Health Score sur 100 sans provenance et contrat établissant cette échelle ; aucun recalcul du niveau ; RUL en heures, santé non probabiliste, probabilité de panne seulement si fournie et validée |
| PRE-09 | Détails dans la liste ; reason et composantes seulement présents/valides ; données supplémentaires JSON échappées, sans innerHTML, script, lien automatique, explication ou recommandation générée ; limites de 10 000 caractères et six niveaux uniquement pour la présentation JSON frontend, sans limite du volume réseau ni de la taille autorisée par le backend |
| PRE-10 | Distinguer idle, loading, historique vide, résultat filtré vide, page hors plage et erreur ; aucune inférence de modèle absent sur un GET vide ; retry manuel réseau/5xx uniquement |
| PRE-11 | Navigation Equipment <-> Prédictions issue des parents réels ; contexte de retour typé et whitelist, chemins internes fixes ; filtres entre modules indépendants |
| PRE-12 | Un h1, labels et aides associées, erreurs annoncées et focus explicite, tableau caption/th scope, alerte et niveau textuels ; clavier et responsive sans information dépendant seulement de la couleur |
| PRE-13 | Pagination serveur 20 par défaut, choix 20/50/100 avec toute valeur URL valide 1..100 conservée ; catalogues paginés par 50 ; pas d'auto-chargement exhaustif, N+1 par ligne ou recalcul lors d'un dépliage |
| PRE-14 | Façade locale signals/switchMap et destruction des abonnements ; annuler lectures obsolètes, ne pas laisser des données d'un ancien scope visibles ; pas de cache global multi-équipements |
| PRE-15 | Absence de sécurité multi-tenant constatée et bloquante pour production SaaS ; aucun filtre UI, contrôle de cible DEV ou mode lecture seule ne lève B-PRE-01 |
| PRE-16 | Les valeurs libres level, les seuils non historisés et les artefacts optionnels limitent l'interprétation ; aucune donnée DEMO présentée comme prédiction réelle ; recette DEV différée et portée des preuves explicites |

Pour PRE-09, proposition de bornes de rendu UI : aperçu JSON de 10 000 caractères,
profondeur de présentation structurée de 6 niveaux, avertissement explicite si
tronqué ; ne jamais modifier l'objet reçu. Ces limites concernent uniquement la
présentation JSON frontend : elles ne limitent ni le volume réseau ni la taille
autorisée par le backend et n'empêchent pas une réponse réseau volumineuse.
Conserver un dépliage local pour les métadonnées sans exposer du HTML actif.

Pour PRE-12 : cibles d'action >=44 px selon mixin partagé, focus visible,
messages associés par aria-describedby/aria-invalid, une zone d'alerte principale,
aria-busy pendant lecture et annonces sobres des résultats. Tester 320 à
1440 px, seuils Shell 1023/1024 px, zoom réel 200/400 %, clavier et lecteur
d'écran ; dérouler textes longs/JSON dans leur conteneur sans débordement global.
Ces critères sont proposés, pas déjà vérifiés sur un écran Prédictions.

## 9. Découpage proposé UI 9.2 à UI 9.7

| Étape | Travail futur après validation | Critère de sortie |
| --- | --- | --- |
| UI 9.2 | DTO, transport GET, validations, temps inclusif et tests unitaires/HTTP isolés | contrat exact, false/null, pages, quatre types, offsets et égalité testés ; aucun endpoint de calcul appelé |
| UI 9.3 | façade, cascade et catalogues paginés, liste/URL, filtres et états | aucune lecture historique hors chaîne validée ; annulation des anciennes requêtes, états vides/erreurs et pages hors plage couverts |
| UI 9.4 | présentation spécifique des scores/niveaux et détails dépliables | 15 champs représentables, JSON sûr, données incomplètes/incohérentes traitées, aucune page détail ou explication inventée |
| UI 9.5 | route lazy et navigation Equipment <-> Prédictions, styles et accessibilité | retours directs/rechargement et whitelists vérifiés ; aucun transfert de filtres d'un module vers un autre |
| UI 9.6 | recette d'intégration DEV expressément autorisée, GET et vérifications de données en lecture seule selon cadre alors validé ; contrôles responsive/clavier et tests/build nécessaires | identité/révision et données réellement constatées ; distinguer preuves DEV, simulations et cas non testables ; aucune génération pour remplir l'écran |
| UI 9.7 | bilan de livraison et documentation de l'architecture réellement livrée | exigences PRE rapprochées des preuves, limites maintenues, validation avant toute publication Git |

Si DEV n'a aucune prédiction, UI 9.6 valide réellement le parcours et l'état vide.
Les quatre types, pages multiples et détails sont alors prouvés uniquement par
fixtures isolées, étiquetées comme simulations ; pas par une assertion de
persistance réelle. Une éventuelle alimentation DEV doit faire l'objet d'une
demande distincte, sans être une condition cachée de recette.
Commit/push/merge/rebase restent soumis à validation explicite ; cette conception
ne lance aucune de ces étapes, ni UI 9.2.

## 10. Critères de validation et limites de preuve

UI 9.1 est recevable si le seul fichier ajouté est ce document, la branche
documentaire part de `024c740`, les contrats sont sourcés, les décisions sont
identifiées comme propositions et `git diff --check` est sans erreur.
Aucun résultat de test/build nouvellement exécuté ne doit être annoncé.

Critères applicatifs futurs :

- Journal HTTP isolé : GET autorisés seulement ; aucun POST health-score/rul,
  recommendations, aucune lecture Dashboard supplémentaire ou polling.
- Chaînes réelles et falsifiées, URL partielle/invalide/dupliquée, erreur d'un
  catalogue, parents absents, autre équipement dans une réponse, changement
  rapide de sélection et retry des mêmes filtres appliqués.
- Pages 1/dernière/hors plage, total nul ou non nul, filtres seuls/combinés,
  is_alert=false et NULL, level inconnu ou Unicode trop long, absence de tri
  ou recherche inventés ; taille 100 et rejet 101.
- Dates avec offsets équivalents, fractions jusqu'à six chiffres, borne unique,
  début=fin accepté, début>fin bloqué, calendrier invalide et naïf refusés,
  chaîne inchangée si saisie non modifiée. Fin incluse prouvée séparément des
  conventions Maintenance/Measurements.
- RUL zéro/non négative et détails contradictoires ; santé et risque hors
  plages attendues ; niveau inconnu ; absence de modèle/version/horizon ;
  JSON null/vide/imbriqué/volumineux et reason contenant du HTML échappé.
- Erreurs 404/422/401/403/réseau/500/503, réponse structurellement invalide ;
  aucune substitution par données fictives ou valeur zéro en cas d'absence.
- Navigation aller-retour et rechargement, paramètres pre_ invalides,
  URL externe de retour ignorée, focus clavier et états responsive/accessibles.

Preuves existantes réutilisées sans réexécution :
`tests/predictions/test_route.py` décrit structure exacte, pagination, 404/422,
bornes inclusives, alerte false et équipement vide ; `test_repository.py` décrit
ordre et filtres, dont un cas PostgreSQL offsets ; `test_schemas.py` vérifie
les quatre PredictionType ; `test_persistence.py` décrit les mappings producteurs.
Le README Predictions rapporte historiquement, au 9 octobre, 44 réussites et
1 ignoré sur 45, mais parle encore de trois types : le test actuel incluant
RUL prévaut. Ce bilan historique ne prouve pas une nouvelle exécution à `024c740`.
Les tests RUL et Health Score présents documentent leurs réponses/erreurs ;
aucune preuve de leur réussite courante n'est ajoutée par l'audit.
Les résultats UI 8.8 restent également historiques et ne valident pas UI 9.

## 11. Fichiers examinés

Inventaire des sources lues ou consultées par recherche ciblée ; certaines
lectures de documents et modules de contexte sont partielles. Aucun dossier
de dépendances, artefact binaire, configuration privée ou secret n'est audité.

- Contexte : `README_AI.md`, `docs/architecture.md`,
  `docs/frontend-architecture.md`, `docs/project-status.md`, `docs/ui-design.md`,
  `docs/ui-buttons-harmonization.md`, `docs/ui-8.8-ux-polish.md`.
- Routes et noyau backend : `backend/app/main.py`,
  `backend/app/api/routes/equipment.py`, `companies.py`, `sites.py` et inventaire
  des décorateurs des autres routeurs ; `backend/app/core/enums.py`,
  `backend/app/core/pagination.py`, `backend/app/core/database.py`.
- Schémas : `backend/app/schemas/prediction_record.py`, `pagination.py`,
  `health_score.py`, `rul.py`, `company.py`, `site.py`, `equipment.py`.
- Persistance : `backend/app/models/prediction_record.py`, `equipment.py` ;
  `backend/app/repositories/prediction_repository.py`, et recherches ciblées
  sur `company_repository.py`, `site_repository.py`, `equipment_repository.py` ;
  `backend/app/services/prediction_service.py`, `health_score_service.py`,
  `rul_prediction_service.py`, `rul_service.py`.
- ML : `backend/app/ml/risk_score.py`, `baseline_classifier.py`,
  `random_forest_classifier.py`, `prediction_explainer.py`, `rul_schemas.py`,
  `rul_classifier.py`, `rul_model_store.py`, `rul_random_forest_regressor.py`,
  `rul_prediction_explainer.py` ; `backend/app/ml/health_score/schemas.py`,
  `calculator.py`, `aggregator.py`, `classifier.py` ;
  `backend/app/anomaly_detection/schemas.py`, `unified_score.py`,
  `sensor_detector.py`, `equipment_detector.py`.
- Migrations : `backend/migrations/versions/d6ec01cf13b6_add_prediction_records.py`,
  `09ac8101e9fe_add_maintenance_recommendations.py` ; revision/down_revision des
  sept migrations antérieures citées en 3.3.
- DEV : `infra/development/README.md`, `manage.py`, `seed.py`, `demo-data.json` ;
  recherche ciblée dans `compose.yaml`. Aucun lanceur exécuté.
- Tests backend lus ou inventoriés par noms de cas : `tests/predictions/README.md`,
  `support.py`, `test_route.py`, `test_schemas.py`, `test_repository.py`,
  `test_service.py`, `test_persistence.py` ; `tests/rul/test_route.py`,
  `test_persistence.py` ; `tests/health_score/test_route.py`.
- Socle frontend : `frontend/package.json`, `frontend/src/app/app.routes.ts`,
  `layout/navigation/navigation.config.ts`, `layout/sidebar/sidebar.component.ts`,
  `shared/pages/feature-placeholder/feature-placeholder.component.ts`,
  `shared/components/error-state/error-state.component.ts`,
  `core/api/reference-data-api.service.ts`, `core/models/reference-data.model.ts`,
  `shared/utils/datetime-display.ts`, inventaire des composants shared.
- Conventions frontend : `features/maintenance/maintenance-list.facade.ts`,
  `maintenance.routes.ts`, `data-access/maintenance-api.service.ts`,
  `pages/maintenance-list/maintenance-list.component.ts` et `.html` ;
  `features/measurements/measurements-list.facade.ts`,
  `utils/measurement-time.ts`, `utils/measurement-period-draft.ts` ;
  `features/equipments/pages/equipment-detail/equipment-detail.component.ts`
  et `.html`, assertions ciblées de son `.spec.ts` ;
  `features/dashboard/data-access/dashboard-api.service.ts`,
  `features/dashboard/dashboard.facade.ts` ; `frontend/src/styles/_actions.scss`,
  `_buttons.scss`. Les chemins de features de cette liste sont relatifs à
  `frontend/src/app/`.

## 12. État Git final et attente de validation

- Branche : `docs/ui-9-predictions-design`.
- HEAD, main et origin/main local : `024c740a64a084def6f2c495f492feb7143c53dd`.
- Seul ajout constaté : `docs/etape-ui-9.1-predictions.md`, non suivi et non indexé.
- Index vide ; aucun changement exécutable ou des rapports historiques.
- Contrôles documentaires réussis, sans diagnostic : `git diff --check` et
  contrôle du fichier nouveau non suivi avec
  `git diff --no-index --check -- /dev/null docs/etape-ui-9.1-predictions.md`.
- Aucun commit, push, merge ou rebase. Aucun test/build ou accès DEV.

Validation attendue : périmètre read-only, PRE-01 à PRE-16, détails dans la liste,
contrat temporel inclusif, interprétation prudente des scores, navigation sûre,
risques B-PRE-01 à B-PRE-11 et découpage UI 9.2 à UI 9.7. UI 9.2 n'est pas commencée.
