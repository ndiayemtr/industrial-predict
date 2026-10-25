# ML 2 — Conception du pilote d'anomalie statistique P101

Date : 25 octobre 2026. Statut : conception documentaire soumise à validation.
Référence : [audit ML 1](ml-1-existing-prediction-audit.md), intégralement conservé.

## 1. Référence Git, portée et décisions

État initial vérifié : dépôt `D:/projets/industrial-predict`, branche `main`, HEAD
`85d4bf0f1a03bbb841b5c2deebb8f12786c22dca`, index et arbre propres.
Branche créée : `docs/ml-2-p101-anomaly-design`, au même HEAD. Main n'est pas modifiée.
Seul ce document est ajouté ; aucun commit, fetch, push, merge ou rebase.

Cette étape ne crée ni code ni dataset séparé. Les valeurs et résultats ci-dessous
sont une spécification et une dérivation mathématique sur papier, sans exécution
de calcul. Aucun accès PostgreSQL/HTTP, import applicatif, test/build, entraînement,
chargement joblib ou ajout de package. ML 3 à ML 5 restent non autorisés.

Le pilote vise une copie synthétique de la pompe P101 et un seul capteur de
température en °C. Il détecte un écart à un historique court, après réception d'une
observation. Il ne prédit ni panne future, ni probabilité de panne, ni durée de vie.
Isolation Forest, risque de panne, Health Score, RUL et recommandations sont exclus.

Décisions proposées :

- Réutiliser exclusivement `StatisticalAnomalyDetector`, avec des statistiques
  causales préparées en amont ; ne pas appeler SensorAnomalyDetector.
- Dix observations good, finies, strictement antérieures, à cadence quotidienne
  UTC complète. Aucune interpolation, imputation ou suppression silencieuse.
- Deux états métier : `computed` ou `abstained`. Une abstention n'a ni score,
  ni is_alert, ni PredictionRecord.
- Préparer un résultat inspectable sans écriture, puis autoriser explicitement sa
  persistance dans un bac à sable distinct. Jamais dans `industrial_predict_dev`.
- Idempotence garantie ultérieurement par une contrainte unique transactionnelle,
  pas par un simple contrôle préalable côté application.

## 2. Architecture et raccordements à prévoir

Flux futur, non implémenté dans ML 2 :

1. Un manifeste synthétique immuable décrit les parents, les mesures, leurs dates
   de disponibilité et l'empreinte du jeu. Aucun accès base dans le calcul pur.
2. Un validateur contrôle le contrat, la hiérarchie, le cutoff et les dix créneaux
   de référence. Il produit une abstention explicite ou une entrée calculable.
3. Un préparateur calcule moyenne et std échantillonnale sur ces seuls dix points.
   Il fournit au détecteur une ligne `value`, `rolling_mean`, `rolling_std`.
4. `StatisticalAnomalyDetector.detect(..., threshold_std=3.0)` fournit écart,
   seuil et booléen ; un adaptateur produit une proposition immutable documentée.
5. Un validateur de persistance séparé vérifie autorisation, destination réelle,
   rattachements et identité de la proposition, puis écrit atomiquement.
6. Une instance UI/API de démonstration consulte seulement le GET historique.

Sources relues statiquement :
`backend/app/anomaly_detection/statistical_detector.py`,
`services/prediction_service.py`, `repositories/prediction_repository.py`,
`models/prediction_record.py`, `schemas/prediction_record.py`, ainsi que
`frontend/src/app/features/predictions/{models/prediction.model.ts,data-access/predictions-api.service.ts,utils/prediction-display.ts,utils/prediction-json-preview.ts}`.

Écarts avec l'existant : WindowFeatureBuilder inclut le point évalué ; il ne doit
pas alimenter directement cette référence. Le détecteur ne protège pas seul contre
std nulle, unités incohérentes ou valeurs non finies. `persist_anomaly` ne conserve
que reason et ne reçoit pas model_version. `PredictionService.create` commit
intérieurement. Il faudra un chemin de persistance dédié, maîtrisant sa transaction,
sans changer implicitement le comportement des autres producteurs.

## 3. Contrat d'entrée et chronologie

### 3.1 Identité et données admises

Manifeste proposé `p101-temperature-fixture-v1`, explicitement `synthetic=true`.
Hiérarchie exclusivement fictive :

| Objet | Identifiant logique | Code |
| --- | --- | --- |
| Entreprise | DEMO-COMP-001 | MLDEMO-COMP-P101 |
| Site | DEMO-SITE-001 | MLDEMO-SITE-P101 |
| Équipement | DEMO-EQ-001 | MLDEMO-EQ-P101 |
| Capteur | DEMO-SEN-001 | MLDEMO-SEN-P101-TEMP |

Nom équipement : « Pompe P101 — démonstration synthétique ». Type équipement pump ;
type capteur temperature ; unité exactement `°C` après normalisation Unicode NFC.
Pas de conversion implicite de C, Celsius, °F ou K. Aucun parent/code UI47 réutilisé.
Les identifiants logiques ne sont pas des clés SQL. En ML 4 seulement, une table de
correspondance validée les reliera aux entiers positifs propres au bac à sable.

Chaque observation porte : identifiant logique unique, chaîne complète des parents,
valeur numérique, unité, qualité, `timestamp`, `available_at`, et `synthetic=true`.
Pour ce jeu, available_at désigne l'instant fictif de disponibilité de l'observation,
pas une date administrative fabriquée dans Measurement. Le modèle Measurement
actuel ne porte pas cette information : elle devra rester dans le manifeste figé
et la provenance du pilote. Aucun historique réel de réception n'est prétendu.

Valeurs : nombres réels finis, booléens et chaînes numériques refusés ; champ absent,
null, NaN, +inf ou -inf interdits. Qualité exactement good ; suspect, estimated,
bad, missing et inconnue provoquent une abstention dans le périmètre utile.
Aucun rejet par seuil physique inventé ; les bornes d'exploitation métier ne sont
pas établies. Les statistiques intermédiaires doivent aussi rester finies.

### 3.2 Temps, cutoff et fenêtre

Pour une cible de timestamp T :

- Entrées avec offset obligatoire, normalisation UTC ; représentation canonique
  `YYYY-MM-DDTHH:MM:SS.ffffffZ`, précision maximale microseconde, sans arrondi silencieux.
- Cutoff C explicite : instant maximal de connaissance. Pour le jeu proposé,
  C = T + une minute, et available_at = timestamp + une minute pour chaque point.
  La cible doit avoir T <= C et available_at <= C.
- Référence : exactement les dix instants T−10 jours à T−1 jour, une observation
  par jour à 08:00 UTC, strictement avant T, available_at <= C. Début inclus T−10j,
  fin exclue T. Le point évalué ne figure jamais dans sa référence.
- Ces dix observations doivent toutes être good, finies, du même capteur et de
  même unité. Ne pas remonter plus loin pour remplacer une donnée invalide : la
  continuité quotidienne est une condition supplémentaire aux dix points valides.
- Pas de tolérance de cadence en v1 : un décalage même faible dans les dix créneaux
  constitue une cadence incompatible. Cette convention pédagogique ne décrit pas
  une acquisition industrielle réelle.
- Trier les observations utiles par instant UTC croissant ; les identifiants
  servent à vérifier l'unicité, jamais à départager arbitrairement deux mesures
  du même capteur au même instant.
- Doublon d'identifiant dans la cible/référence ou deux observations au même instant
  pour le capteur : abstention, même si valeurs égales. Deux offsets représentant
  le même instant sont des doublons. Aucun « garder le dernier ».

Les points timestamp > T ne sont pas des références, même connus à C. Une donnée
disponible après C n'entre jamais dans ce snapshot, même si son timestamp est ancien.
Si elle complète un créneau qui était absent à C, le résultat au cutoff reste une
abstention. Une réévaluation avec un autre cutoff est une nouvelle proposition,
soumise à validation ; elle ne réécrit pas une décision passée.

Un contrôle structurel global rejette un manifeste corrompu. Les contrôles de
qualité/statistiques portent ensuite sur la cible et ses dix créneaux seulement :
des valeurs futures ajoutées au snapshot ne doivent pas modifier un résultat passé.

### 3.3 Formule exacte et abstention

Pour x₁…x₁₀ de référence :

μ = (Σxᵢ)/10 ; s² = Σ(xᵢ−μ)²/9 ; s = √s² ; d = |x_cible−μ| ; seuil = 3s.

Anomalie si et seulement si d > 3s. Égalité : résultat calculé sans alerte.
Moyenne, std, écart et seuil en °C ; score binaire sans unité. Aucun arrondi avant
comparaison, aucune epsilon ajoutée à la règle. Une tolérance n'est admise que pour
comparer des statistiques attendues en tests, jamais pour déplacer le seuil métier.
La frontière numérique devra être testée avec des valeurs exactement représentables.
Une modification de politique numérique impose une nouvelle version de méthode.

Ordre de validation et codes d'abstention, liste fermée :

| Priorité | Code | Condition |
| --- | --- | --- |
| 1 | INVALID_INPUT | Champ requis absent, type interdit, identifiant invalide, date naïve/non parsable ou précision non supportée |
| 2 | INCONSISTENT_PARENT | Capteur/mesure hors chaîne ou manifeste non synthétique ; ne pas ignorer silencieusement une mesure présentée comme référence |
| 3 | UNIT_MISMATCH | Unité autre que °C ou unités divergentes |
| 4 | DUPLICATE_OBSERVATION | Doublon problématique d'id ou d'instant dans le périmètre utile |
| 5 | TARGET_UNAVAILABLE | Cible postérieure à C ou disponible après C |
| 6 | INSUFFICIENT_HISTORY | Moins de dix observations antérieures disponibles au début de la série |
| 7 | GAP_OR_CADENCE | Créneau requis absent dans un historique déjà commencé ou cadence incompatible ; notamment arrivée tardive d'une référence |
| 8 | INVALID_VALUE | Valeur absente, null ou non finie dans cible/référence |
| 9 | INVALID_QUALITY | Qualité autre que good dans cible/référence |
| 10 | ZERO_STD | s = 0, même si la cible est différente de la référence constante |
| 11 | NONFINITE_STATISTIC | Moyenne, variance, std, écart ou seuil non fini |

Une valeur absente dans une observation présente est INVALID_VALUE ; une observation
absente suit les règles d'historique/trou. Contrôler les champs présents avant toute
opération arithmétique ; l'ordre ci-dessus classe les motifs, il n'autorise pas un
calcul sur une entrée invalide. Retourner le premier motif applicable et les ids
concernés ; ne pas appeler le détecteur en abstention.

Sortie `abstained` : statut, code, explication bornée, cible/cutoff et version ;
`prediction=null`, aucun score/is_alert et aucune écriture PredictionRecord.
Sortie `computed` : statut, proposition PredictionRecord sans id/created_at,
statistiques et empreintes. Ce résultat ne constitue pas une autorisation de persister.

## 4. Jeu synthétique figé et attentes sur papier

Les 12 lignes ci-dessous constituent la spécification du jeu, pas une création de
mesures. Chaque ligne appartient à DEMO-SEN-001/DEMO-EQ-001 et à leurs parents de
la section 3. Qualité good, unité °C, synthetic true pour les douze lignes.
available_at reprend la même date à 08:01:00Z. Dataset id : `p101-temp-synthetic-v1`.

| Id logique mesure | Timestamp UTC fixe | Température °C | Usage |
| --- | --- | --- | --- |
| DEMO-M-001 | 2026-01-01T08:00:00Z | 65 | Référence |
| DEMO-M-002 | 2026-01-02T08:00:00Z | 63 | Référence |
| DEMO-M-003 | 2026-01-03T08:00:00Z | 67 | Référence |
| DEMO-M-004 | 2026-01-04T08:00:00Z | 64.5 | Référence |
| DEMO-M-005 | 2026-01-05T08:00:00Z | 65.5 | Référence |
| DEMO-M-006 | 2026-01-06T08:00:00Z | 64.5 | Référence |
| DEMO-M-007 | 2026-01-07T08:00:00Z | 65.5 | Référence |
| DEMO-M-008 | 2026-01-08T08:00:00Z | 65 | Référence |
| DEMO-M-009 | 2026-01-09T08:00:00Z | 65 | Référence |
| DEMO-M-010 | 2026-01-10T08:00:00Z | 65 | Référence |
| DEMO-M-011 | 2026-01-11T08:00:00Z | 65 | Témoin normal |
| DEMO-M-012 | 2026-01-12T08:00:00Z | 70 | Anomalie positive |

Attentes mathématiques dérivées sans outil de calcul : les dix premières valeurs
ont une somme de 650 et une moyenne de 65. Leurs écarts sont 0, −2, +2, −0,5, +0,5,
−0,5, +0,5, 0, 0, 0 ; somme des carrés = 4 + 4 + quatre fois 0,25 = 9.
Variance échantillonnale = 9/9 = 1 °C² ; s = 1 °C ; seuil = 3 °C.

| Cible | Référence exacte | Cutoff C | μ ; s ; d ; seuil | Attente |
| --- | --- | --- | --- | --- |
| DEMO-M-011 | DEMO-M-001…010 | 2026-01-11T08:01:00Z | 65 ; 1 ; 0 ; 3 °C | computed, score 0, is_alert false |
| DEMO-M-012 | DEMO-M-002…011 | 2026-01-12T08:01:00Z | 65 ; 1 ; 5 ; 3 °C | computed, score 1, is_alert true |

Pour la seconde fenêtre, 001 sort et 011 entre avec la même valeur 65 : son
multiensemble est identique, donc moyenne et std identiques sans refaire le calcul.
Les dix premiers points sont des références, pas dix résultats « normaux »
persistables : leur historique propre est insuffisant et ils conduiraient à abstention.

Variantes de test seulement, hors dataset v1 : remplacer la cible 012 par 60
donne d = 5 et une alerte négative ; par 68 ou 62 donne d = 3 et aucune alerte.
Ces variantes portent de nouveaux identifiants de dataset/empreintes ; ne pas
modifier le jeu figé sous le même nom.

Les températures historiques P101 64,2 / 65,1 / 65,4 des 14–16 octobre 2026, citées
par ML 1 à partir d'UI 7.5, ne figurent pas dans ce jeu. Les dates de janvier sont
fictives et ne représentent ni une reconstitution du passé ni des données DEV.

### Empreintes et reproductibilité

Spécifier ultérieurement une sérialisation canonique UTF-8 sans BOM : objet à clés
triées, séparateurs JSON compacts, chaînes NFC, dates UTC à six décimales, valeurs
de température sous forme de chaînes décimales normalisées dans le manifeste
canonique (65, 64.5 ; aucun zéro final superflu ni notation exponentielle).
Les valeurs restent numériques dans le calcul et dans PredictionRecord.details.
Observations triées par timestamp puis id ; parents, unités, qualité et available_at
inclus. SHA-256 de ces octets = dataset_sha256 ; référence de dix observations
canonisée selon les mêmes règles = reference_sha256.

Le digest du dataset couvre tout le jeu et sa disponibilité, pas seulement les
valeurs. Aucun digest n'est calculé ni inventé dans ML 2 : les emplacements symboliques
ci-après seront remplacés par 64 caractères hexadécimaux minuscules en ML 3.
Deux futurs résultats peuvent garder les mêmes statistiques tout en portant un
nouveau dataset_sha256 après ajout de données futures ; l'invariance temporelle
porte sur décision/statistiques/référence utile, pas sur l'empreinte globale du jeu.

## 5. Contrat de sortie PredictionRecord

| Champ | Règle pour un résultat computed |
| --- | --- |
| id | Entier positif attribué à la persistance, absent de la proposition |
| equipment_id | Entier SQL du bac à sable correspondant à DEMO-EQ-001 |
| sensor_id | Entier SQL du bac à sable correspondant à DEMO-SEN-001, obligatoire dans ce pilote |
| measurement_id | Entier SQL de la cible ; cohérent avec sensor_id, obligatoire |
| prediction_type | anomaly |
| score | 0.0 ou 1.0 uniquement : indicateur binaire, jamais une probabilité |
| is_alert | false si score 0 ; true si score 1 |
| level | null |
| horizon_hours | null, car aucune anticipation |
| predicted_at | Timestamp UTC de la cible, pas cutoff ni date d'exécution |
| created_at | Instant UTC réel de première persistance, attribué dans la transaction, >= cutoff et predicted_at ; inchangé lors d'un retry |
| model_name | statistical_deviation |
| model_version | p101-stat-v1, version immuable du contrat/méthode/paramètres |
| details | Objet conforme au schéma ci-dessous ; jamais null pour ce pilote |

Le SHA du code qui réalisera ML 3 devra être fourni séparément dans details ;
ne pas prétendre que le HEAD documentaire actuel contient cette implémentation.
Toute modification de fenêtre, qualité, cutoff, formule, comparaison ou politique
de précision change model_version. Pas d'artefact ML entraîné.

### Schéma details versionné et borné

Forme normative proposée, représentée comme inventaire de champs (aucun faux
JSON prêt à persister avec empreinte ou id inventé) :

| Chemin | Type / contrainte |
| --- | --- |
| schema_version | Chaîne constante p101-anomaly-details-v1 |
| synthetic | Booléen true obligatoire |
| run_id | UUID canonique de la première préparation autorisée, <= 36 caractères |
| reason | Texte fixe « Démonstration synthétique : dépassement statistique, indicateur binaire sans probabilité de panne. » pour alerte ; variante « absence de dépassement » pour normal, <= 240 caractères |
| producer.method_version | p101-stat-v1, identique à model_version |
| producer.code_revision | SHA Git complet de l'implémentation validée, 40 hexadécimaux |
| asset.company_code / site_code / equipment_code / sensor_code | Quatre chaînes des parents synthétiques section 3, <= 64 caractères chacune |
| asset.equipment_id / sensor_id | Entiers SQL positifs, identiques aux champs racine |
| dataset.id | p101-temp-synthetic-v1, <= 64 caractères |
| dataset.sha256 | SHA-256 réel du manifeste canonique, 64 hexadécimaux |
| target.fixture_id / measurement_id | Id logique <= 32 caractères et entier SQL positif de la cible |
| target.timestamp / available_at | Instants UTC canoniques ; timestamp identique à predicted_at |
| target.value / unit / quality | Nombre fini, chaîne °C, chaîne good |
| reference.count / ddof / cadence_seconds | Entiers constants 10 / 1 / 86400 |
| reference.start_at / end_at | Instants du premier et du dernier point retenus, inclusifs ; end_at < target.timestamp |
| reference.sha256 | Empreinte réelle des dix observations ordonnées |
| reference.observations | Tableau de longueur exactement 10 ; objets fixture_id, measurement_id, timestamp, available_at, value, quality ; ids SQL reliés au même capteur |
| statistics.mean / sample_std / absolute_deviation / threshold | Nombres finis en °C ; std > 0 et seuil = 3 × std |
| statistics.multiplier / comparison / score_semantics | Constantes 3 / absolute_deviation>threshold / binary_indicator_non_probabilistic |
| cutoff_utc | C UTC canonique, identique au cutoff de préparation autorisé |
| prepared_at | Date UTC réelle de préparation, >= C, indépendante des observations fictives |
| idempotency_key | Empreinte canonique réelle décrite section 6, 64 hexadécimaux |

Fermer chaque objet aux propriétés inconnues. Limites serveur à implémenter :
details compact <= 6 000 octets UTF-8 ; aucune chaîne libre > 240 caractères ;
maximum dix objets de référence ; profondeur maximale six conteneurs depuis la
racine details ; aucun NaN/inf, valeur hors JSON, contenu HTML ou secret.
Dans cette forme, le chemin le plus profond est details → reference → observations
→ observation, donc quatre conteneurs. Refuser un dépassement, jamais tronquer
une preuve nécessaire. Les ids numériques ne participent pas à l'empreinte du
manifeste logique, mais leur correspondance sera validée en transaction.

Compatibilité avec le frontend actuel : conserver les 14 champs Read, y compris
ceux valant null ; nombres finis, ids entiers positifs sûrs en JavaScript, dates avec
offset. La liste affichera « Indice d’anomalie », valeur brute 0 ou 1, alerte Oui/Non,
niveau Non renseigné ; elle ne transforme pas ce score en pourcentage. `details.reason`
est déjà présenté et le reste est consultable en JSON. Les limites proposées restent
sous l'aperçu UI de 10 000 caractères/six niveaux ; les tests futurs devront le vérifier
sur la sérialisation réelle. Pas de modification frontend requise pour lire le contrat.
Le contexte synthétique doit être visible par le nom de l'équipement et le motif ;
la liste seule ne constitue pas une authentification de provenance.

## 6. Préparation, autorisation et persistance

### Phase A — Préparer et valider, sans écriture

Le calcul pur reçoit un snapshot mémoire figé et produit computed/abstained.
Une couche de préparation produit, pour computed, un dossier inspectable avec
les deux cibles, références, résultats, versions, empreintes et destination prévue.
Elle attribue run_id/prepared_at sans ouvrir de transaction d'écriture. Aucun
autoflush ni appel à repository.create ; aucune connexion base nécessaire au calcul.
Le mapping SQL peut être renseigné et revérifié plus tard en phase B, sans changer
les identités logiques ni les résultats autorisés.

L'autorisation future doit nommer le bac à sable, le dataset, la méthode, les deux
cibles et l'empreinte du dossier de préparation. Un accord pour ML 2 ne vaut ni
autorisation de créer une base, ni accord de persistance ML 4. Refuser un dossier
altéré ou une destination différente, demander une nouvelle autorisation explicite.

### Phase B — Vérifier la destination et écrire atomiquement

Garde de destination à concevoir avant toute opération future : allowlist positive
du serveur/port/base/rôle et identifiant immuable d'instance, par exemple base dédiée
`industrial_predict_ml_sandbox` ; marqueur d'environnement `ml_sandbox` concordant,
distinct des services DEV. Le nom de base seul et une variable d'environnement ne
suffisent pas. Vérifier la destination effective et l'identité de session lors de
l'ouverture, puis dans la transaction. Refuser explicitement industrial_predict_dev
et toute identité inattendue. Aucun mot de passe ou DSN complet dans les preuves.

Le rôle du bac à sable n'a aucun droit sur DEV. L'instance UI/API de démonstration
utilise uniquement cette destination ; la validation du manifeste et des comptes
s'effectuera plus tard, uniquement après autorisation. Aucune requête correspondante
n'est lancée ici. Pas de scénario de démonstration branché à la base DEV permanente.

Ordre transactionnel futur proposé :

1. Ouvrir une session dédiée sans modifications en attente. Début d'une transaction
   unique pour les deux résultats 011 et 012 et leurs entrées d'idempotence.
2. Vérifier l'instance autorisée, puis verrouiller les parents et les onze/douze
   mesures utiles selon une politique empêchant modification ou suppression jusqu'au
   commit. Vérifier Equipment → Site → Company, Sensor → Equipment, Measurement →
   Sensor ; comparer codes, valeurs, qualité, UTC et empreintes au dossier approuvé.
   Les fixtures du bac à sable doivent être immuables pour le rôle du pilote.
3. Réserver les clés uniques d'idempotence en ordre déterministe, puis insérer les
   deux PredictionRecord et associer leurs ids au registre dans la même transaction.
4. Sérialiser et valider les Read et details avant commit, y compris limites/finitude.
   Toute erreur provoque rollback de tout le lot, registre inclus. Aucun commit par ligne.
5. Commit unique. Si le résultat du commit est inconnu après déconnexion, résoudre
   par la clé sur une nouvelle session ; ne pas réinsérer aveuglément.

Ne pas appeler `PredictionService.create` ni `persist_anomaly` dans cette transaction
car create commit intérieurement et l'adaptateur perd les métadonnées. Prévoir en
ML 4 un service dédié sans commit interne, utilisant une couche repository sous
contrôle transactionnel. `PredictionRepository.create` fait flush/refresh mais ne
commit pas ; sa réutilisation est possible après validation de ses effets, sans
modifier les contrats des autres producteurs. Aucune implémentation ou migration ici.

### Idempotence et concurrence : choix proposé

Prévoir un registre SQL dédié au pilote dans le seul bac à sable, avec contrainte
UNIQUE sur `idempotency_key`, lien unique vers PredictionRecord et empreinte du
contenu métier validé. Sa création éventuelle nécessite une évolution de schéma
autorisée en ML 4 ; le schéma actuel ne fournit pas cette garantie.

Clé = SHA-256 du tuple canonique : identifiant d'instance bac à sable, dataset_sha256,
codes équipement/capteur, id logique et timestamp de cible, cutoff UTC, type anomaly,
model_name, model_version, code_revision, paramètres du contrat et reference_sha256.
Inclure les observations/available_at via leurs empreintes. Exclure run_id,
prepared_at, created_at et ids SQL alloués : un retry avec un nouveau run_id ne doit
pas créer une seconde prédiction identique dans la même instance.

Le registre est réservé avant insertion des prédictions, dans la même transaction.
Deux transactions concurrentes sur la même clé : une seule devient propriétaire ;
l'autre attend la résolution du conflit d'unicité, puis relit dans une transaction
valide. Même empreinte de contenu métier : retourner l'id et created_at existants,
sans modifier le run_id originel. Contenu différent pour la même clé : conflit
explicite, aucune écriture. Ne pas masquer une incohérence sous un succès de retry.
Conflit technique/deadlock : rollback, retry borné de la transaction complète selon
une politique testée ; aucun fallback sans contrainte unique.

Empreinte de contenu métier : champs déterministes de sortie, identités logiques,
référence, paramètres, cutoff, statistiques et versions, sans métadonnées de tentative
ni dates/ids alloués. La provenance de première écriture est conservée ; une nouvelle
tentative n'écrase pas l'historique. La contrainte du registre doit être obligatoire
pour ce producteur : rôle applicatif sans voie de contournement, pas de création
manuelle via le service générique. Le registre et la prédiction ont la même politique
de conservation ; pas de cascade permettant de libérer silencieusement une clé.

Un changement d'empreinte/version/cutoff donne une nouvelle clé et une nouvelle
proposition à autoriser ; ce n'est pas un retry. Détecter aussi les doublons métier
dans un dossier avant transaction. Sans registre unique autorisé et vérifié, phase B
interdite ; la démonstration reste une préparation sans persistance.

## 7. Matrice de validation future — aucune exécution dans ML 2

### Tests purs (ML 3)

| Cas | Données / vérification | Résultat attendu |
| --- | --- | --- |
| T01 Série normale | Jeu v1, cible 011 | μ=65, s=1, seuil=3, d=0 ; computed/0/false |
| T02 Saut positif | Jeu v1, cible 012 | Même référence statistique, d=5 ; computed/1/true |
| T03 Saut négatif | Variante cible 012 à 60 | d=5 ; computed/1/true |
| T04 Égalité au seuil | Variantes cible à 68 puis 62 | d=3 ; computed/0/false ; aucun >= |
| T05 Fenêtre incomplète | Début de série, seulement neuf antécédents | INSUFFICIENT_HISTORY, prediction null |
| T06 Référence constante | Dix valeurs identiques, cible normale puis différente | ZERO_STD dans les deux cas, jamais normal implicite |
| T07 NaN/inf/null/manquant | Chaque position cible/référence | INVALID_VALUE, aucun appel détecteur ni score |
| T08 Mauvaise qualité | suspect/estimated/bad/missing/inconnue | INVALID_QUALITY ; pas de substitution par point plus ancien |
| T09 Timestamp dupliqué | Ids différents, même instant ou offsets équivalents ; doublon id | DUPLICATE_OBSERVATION, même si valeurs identiques |
| T10 Trou / cadence | Retirer un créneau interne ; décaler un point d'une seconde | GAP_OR_CADENCE, pas d'interpolation |
| T11 Unité | °F, K, C ou mélange | UNIT_MISMATCH, pas de conversion implicite |
| T12 Mauvais parent | Capteur d'une autre pompe, équipement d'un autre site/entreprise | INCONSISTENT_PARENT avant calcul |
| T13 Fuite temporelle | Ajouter/modifier des points timestamp > T | Statistiques/décision/référence utile inchangées ; empreinte globale éventuellement différente |
| T14 Disponibilité tardive | Référence timestamp < T mais available_at > C | Non disponible au snapshot ; abstention pour créneau manquant |
| T15 Cible après cutoff | T > C ou available_at cible > C | TARGET_UNAVAILABLE |
| T16 Point courant exclu | Faire varier seulement la cible | μ et s inchangés ; seuls d/décision changent |
| T17 UTC/ordre | Permutation des lignes, offsets équivalents, précision microseconde | Même sélection/valeurs ; dates naïves refusées ; cadence exacte maintenue |
| T18 Canonisation | Ordre des clés et variantes d'écriture numérique équivalentes | Mêmes octets canoniques/empreintes ; modification d'une donnée utile détectée |
| T19 Résultat/JSON | DTO computed vs abstained, valeurs non finies/clé inconnue/details trop grand | Contrat valide seulement si invariants respectés ; abstention non convertible en score 0 |
| T20 Frontière numérique | Valeurs 65, s=1, cibles 68/62 exactement représentables ; valeurs voisines spécifiées en tests | Comparaison stricte conforme sans arrondi préalable |

### Tests d'intégration (ML 4, destination autorisée uniquement)

| Cas | Vérification | Acceptation |
| --- | --- | --- |
| I01 Garde destination | DEV, identité inattendue ou marqueur absent | Refus avant écriture, zéro ligne |
| I02 Mapping industriel | Ids existants mais parent ou contenu divergent | Refus de tout le lot ; aucune fuite inter-équipement |
| I03 Insertion nominale | Deux computed du dossier approuvé | Exactement deux lignes et deux clés ; 14 champs Read, dates UTC, score/alerte/details cohérents |
| I04 Retry séquentiel | Même clé/contenu avec nouveau run_id | Mêmes ids et created_at, cardinalité inchangée, provenance initiale conservée |
| I05 Concurrence | Deux sessions synchronisées sur mêmes clés | Une paire de résultats seulement ; aucune prédiction orpheline ; mêmes ids retournés |
| I06 Conflit de contenu | Même clé avec contenu métier divergent | Conflit explicite sans écriture ni mise à jour de l'existant |
| I07 Rollback | Erreur après première insertion, réservation, flush ou sérialisation | Aucune nouvelle ligne ni réservation du lot conservée |
| I08 Commit incertain | Déconnexion simulée à l'issue du commit | Résolution par clé, aucune duplication au retry |
| I09 Course sur les sources | Modification/suppression concurrente d'une référence | Blocage/refus par verrou/immutabilité ; pas de persistance sur source modifiée |
| I10 Lecture historique | GET équipement démo, filtre anomaly/is_alert, dates égales inclusives et pagination | Seulement les bonnes lignes, tri predicted_at/id décroissant ; score brut, nulls explicites |
| I11 Abstention | Toutes les abstentions pures transmises à phase B | Zéro PredictionRecord, aucun faux normal |
| I12 Conservation / isolement | Mesures et tables hors pilote comparées avant/après dans le bac à sable | Aucune modification des sources ni recommandation ; preuves de destination sans secrets |

GET et tests SQL sont des activités futures, pas des opérations autorisées par ML 2.
Un test de filtrage n'est pas une preuve d'autorisation multi-tenant ; une campagne
serveur dédiée reste nécessaire avant exposition SaaS.

### Démonstration navigateur (ML 5)

Instance dédiée, données synthétiques visibles : naviguer vers l'équipement de
démonstration et l'historique via la liste existante. Vérifier les deux lignes,
les dates des 11/12 janvier, score 0/1, alerte Non/Oui, niveau non renseigné,
nom/version de méthode, motif synthétique et JSON complet lisible sans troncature.
Filtrer les alertes puis recharger : pas de nouvelles lignes, GET seulement.
Ne pas appeler de POST RUL/Health Score/recommandations. Conserver captures et preuves
de destination, sans identifiants de connexion. Aucune interaction navigateur ici.

## 8. Risques résiduels et réserves B-PRE

Le jeu est pédagogique, très petit et construit pour être vérifiable. Il ne permet
aucune mesure de précision industrielle, de taux de fausse alerte ou de probabilité
de panne. Le seuil trois sigma n'est pas une garantie probabiliste sans hypothèses
sur la distribution ; ces hypothèses ne sont pas revendiquées. La cadence exacte
et l'abstention sur std nulle réduisent volontairement le périmètre. Les outliers
précédents pourraient influencer une future fenêtre ; le pilote ne propose pas de
nettoyage automatique ni de généralisation au-delà des deux cibles.

Le code actuel ne fait respecter ni les nouveaux contrats ni l'idempotence décrite.
La disponibilité temporelle est simulée par manifeste. La désignation model_version
exprime une version de méthode heuristique, pas un entraînement. Les empreintes
assurent une identité de contenu, pas l'authenticité d'une source ou une signature.

| Réserve ML 1 | Correspondance dans la conception | État après ML 2 |
| --- | --- | --- |
| B-PRE-01 | Bac à sable et rôle sans accès DEV ; validation chaîne entière ; pas d'exposition SaaS | Ouverte : aucune authentification/autorisation serveur ajoutée |
| B-PRE-02 | Score binaire 0/1, invariant is_alert, abstention sans score, finitude | Encadrée par contrat proposé uniquement ; validation générique existante inchangée |
| B-PRE-03 | UTC, cadence, cutoff/available_at, cible exclue, bornes de référence et GET inclusif distingués | Ouverte côté backend ; futurs tests dédiés |
| B-PRE-04 | Mapping logique/SQL et contrôle transactionnel des quatre niveaux et mesures | Ouverte, FK indépendantes inchangées |
| B-PRE-05 | Details fermé, versionné, <= 6 000 octets, dix références, profondeur bornée | Ouverte : limites serveur proposées, non implémentées |
| B-PRE-06 | Fixtures immuables, pas de nettoyage DEV/cascade, conservation registre/prédictions | Ouverte : politique globale de conservation non modifiée |
| B-PRE-07 | Démo de deux lignes sans écrivain concurrent durant consultation ; tests concurrence d'insertion séparés | Ouverte : OFFSET/COUNT et index actuels inchangés |
| B-PRE-08 | Aucun POST RUL, artefact ou joblib ; transaction dédiée future et idempotence unique | Ouverte sur les chemins RUL existants |
| B-PRE-09 | Deux phases explicites et alimentation du seul type anomaly ; aucune génération automatique | Ouverte sur les autres producteurs ; pilote non implémenté |
| B-PRE-10 | Versions, code_revision, empreintes, détails et dossier d'autorisation ; nulls conformes | Ouverte sur historiques et provenance générale ; aucune donnée réparée |
| B-PRE-11 | Consultation GET historique existant, aucun besoin d'endpoint détail/latest nouveau | Limite assumée conservée |

Une proposition documentaire n'enlève aucune réserve de ML 1. Les recommandations
consomment les dernières prédictions sans distinguer intrinsèquement les démos :
séparer l'instance et exclure leur génération reste nécessaire.

## 9. Critères d'acceptation de ML 2

- Branche dédiée au HEAD attendu ; main inchangée ; index vide ; seul ce rapport ajouté.
- Périmètre limité à l'anomalie statistique P101 synthétique, sans accès DEV.
- Contrats définis pour dix références antérieures, std échantillonnale, seuil strict,
  qualité, unités, doublons, cutoff et disponibilité ; abstention sans faux normal.
- Douze valeurs fixes et attentes mathématiques dérivées sur papier ; fenêtre du
  second point explicitement glissante ; historique réel distinct.
- Mapping PredictionRecord et details borné/versionné compatibles avec le transport
  frontend ; version/empreinte non inventées pour une implémentation absente.
- Séparation préparation/autorisation/persistance ; solution transactionnelle tenant
  compte du commit interne actuel et garantie unique de concurrence à prévoir.
- Matrice de tests purs/intégration/navigateur et risques résiduels explicites ;
  B-PRE-01 à B-PRE-11 conservées, sans affirmation de réserve levée.
- Aucun code, calcul, dataset en base, HTTP, test/build, package ou commit ; contrôle
  documentaire et `git diff --check` seulement. L'acceptation technique de cette
  conception revient à l'utilisateur ; elle n'autorise pas automatiquement ML 3.

## 10. Roadmap minimale proposée, non autorisée

| Étape | Livrable futur minimal | Condition de sortie |
| --- | --- | --- |
| ML 3 — Calcul pur et tests | Contrats validés, fixture canonique en fichier isolé, sélection causale, abstention, préparation statistique et adaptateur StatisticalAnomalyDetector ; tests purs T01–T20 | Résultats conformes aux attentes, invariance temporelle prouvée, empreintes réelles et version d'implémentation établies, sans base ni écriture |
| ML 4 — Persistance atomique en bac à sable | Destination distincte explicitement autorisée, fixtures SQL propres, mapping, garde destination, registre unique et service transactionnel ; I01–I12 | Atomicité, rollback et idempotence concurrente démontrés ; historique lisible ; aucune écriture DEV ; schéma/rôle et provisioning autorisés séparément |
| ML 5 — Démonstration et validation | Instance UI/API dédiée, dossier des deux résultats approuvé, persistance explicite autorisée puis consultation GET navigateur | Deux lignes explicables et traçables, labels synthétiques visibles, preuves de lecture et absence de duplication ; limites validées par l'utilisateur |

**ML 2 : rapport livré pour validation. ML 3, ML 4 et ML 5 non commencés.**
