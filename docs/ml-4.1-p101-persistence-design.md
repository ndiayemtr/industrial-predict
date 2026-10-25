# ML 4.1 — Préparation de la persistance atomique P101

Date : 25 octobre 2026. Statut : conception documentaire à valider.

Références conservées : [ML 1](ml-1-existing-prediction-audit.md),
[ML 2](ml-2-p101-anomaly-design.md), [ML 3](ml-3-p101-anomaly-core.md).

## 1. Référence Git et périmètre

État initial vérifié : dépôt `D:/projets/industrial-predict`, branche
`feature/ml-3-p101-anomaly-core`, HEAD
`b6b4d521b9c9456c160433e9343efd48d3c0168d`, index et arbre propres.
Branche créée depuis ce HEAD : `feature/ml-4-p101-persistence`.
Seul ce document est ajouté ; aucun code exécutable n'est modifié.

Lecture statique seulement : aucun import applicatif, accès PostgreSQL/HTTP,
création de base/rôle/table/migration, provisionnement, requête ou écriture SQL,
calcul ML, test/build ou package ajouté. Aucun commit, push, merge ou rebase.
Les identifiants et opérations ci-dessous sont des propositions de conception,
pas des ressources disponibles ou des commandes exécutées. ML 4.2 et ML 5 ne sont
pas commencés. L'écriture autorisée se limite au présent document et à la branche Git.

Décision proposée : un service dédié reçoit **le lot complet des deux computed**
validés et un dossier d'autorisation précis. Il possède sa session et sa transaction,
réutilise le repository sans commit, et associe chaque résultat à un registre unique
du seul bac à sable. Il ne passe pas par PredictionService.create ni persist_*.

## 2. Analyse précise de l'existant

| Source examinée | Comportement constaté | Réutilisation / changement minimal proposé |
| --- | --- | --- |
| `backend/app/models/prediction_record.py` | 14 colonnes ; équipement obligatoire ; capteur/mesure facultatifs ; trois FK indépendantes ON DELETE CASCADE ; Float, JSON, dates avec fuseau ; défauts UTC ORM | Conserver le modèle général ; construire des lignes avec tous les champs du pilote explicitement validés |
| `backend/migrations/versions/d6ec01cf13b6_add_prediction_records.py` | Révision d6ec01cf13b6, parent 675ebfea0bb5 ; mêmes 14 colonnes/FK ; index simples ; aucune unicité de calcul, aucun CHECK score/type/horizon, aucun défaut serveur pour les dates | Ne pas réécrire cette migration ; compléter uniquement le schéma dédié du bac à sable |
| `backend/app/repositories/prediction_repository.py`, create | add, flush, refresh ; aucun commit | Réutilisable dans la transaction possédée par le service ; flush est déjà une écriture SQL, jamais une opération de préparation |
| `backend/app/services/prediction_service.py`, create | Valide seulement l'existence Equipment ; construit l'ORM ; repository.create puis commit et refresh | Ne pas appeler pour le pilote : deux appels pourraient laisser une seule ligne après un échec ; ne pas changer ses contrats existants |
| persist_anomaly | Vérifie equipment_id ; score et alerte de l'AnomalyResult ; méthode comme nom ; reason seul dans details ; timestamp comme predicted_at ; appelle create | Non réutilisable tel quel : perd détails/version et commit par résultat |
| persist_failure_risk | Probabilité bornée ; score/niveau fournis sans cohérence recalculée ; détails réduits à probability ; appelle create | Aucun appel ; ne pas utiliser comme modèle de validation suffisante |
| persist_health_score / persist_rul | Dataclasses de résultat, métadonnées partielles ; appellent create | Aucun appel ; invariants dédiés à l'anomalie P101 uniquement |
| `backend/app/core/database.py` | engine construit à l'import depuis settings.database_url ; sessionmaker autoflush=False/autocommit=False ; get_db ouvre puis ferme, sans unité de travail explicite | Factory dédiée avec destination imposée ; ne pas emprunter la session d'une route ni une session déjà utilisée |
| `backend/app/core/config.py` | Charge notamment `.env` ; database_url requise | Pas de repli vers cette configuration DEV ; charger/vérifier la configuration privée du pilote avant les imports applicatifs à effets de configuration |
| `backend/migrations/env.py`, `backend/alembic.ini` | env remplace sqlalchemy.url par settings.database_url ; online crée un moteur et connecte ; offline exécute aussi le chemin de migration ; Base.metadata est la cible | Aucune invocation dans ML 4.1 ; chemin de migration sandbox explicite à isoler, sans URL par défaut héritée |
| `backend/app/models/__init__.py` | Importe les modèles et peuple les métadonnées | Import contrôlé utile aux tables générales ; éviter de greffer automatiquement les objets sandbox au démarrage de tous les environnements |
| `tests/dashboard/support.py`, `tests/predictions/support.py` et README | SQLite mémoire par défaut ; DATABASE_URL neutralisée à l'import ; option DASHBOARD_TEST_DATABASE_URL ; connexion + transaction externe, schéma UUID, schema_translate_map, create_all, Session(connection), rollback final | Bon exemple de séparation et de fixtures ; insuffisant pour prouver un commit visible entre deux connexions ou les contraintes de la vraie migration |
| `tests/recommendations/test_migration.py` | Lecture AST de migration, sans upgrade/downgrade | Réutiliser le principe pour les contrôles statiques de la future migration |
| `tests/test_sensor_crud.py` | Session distincte pour vérifier une écriture validée ; SQLite avec StaticPool | Réutiliser le principe de relecture fraîche, pas SQLite pour la concurrence PostgreSQL |

Le get_db existant ne coordonne pas les commits des services : fermer la session
libère/annule un travail restant, mais ne peut pas annuler un commit déjà réussi.
Avec SQLAlchemy, même une première lecture peut ouvrir une transaction implicitement.
Le futur service doit donc ouvrir son contexte transactionnel **avant** toute requête
de garde ou de mapping et refuser une session sale ou déjà engagée.

La dernière migration générale identifiée dans les fichiers est 09ac8101e9fe
(maintenance_recommendations), descendante de d6ec01cf13b6. Il s'agit de l'ordre
des sources, pas de l'état d'une base contrôlé aujourd'hui. Les tests SQL existants
utilisent create_all ; cela ne prouve pas l'application ni le fonctionnement des
migrations Alembic, triggers, grants ou contraintes différées proposés ici.

## 3. Architecture proposée et fichiers futurs

Séparer trois frontières :

1. **Validation sans écriture** : lot logique immutable, manifeste complet, preuves
   de révision et autorisation ; vérification du contrat ML 3 et préparation d'un
   dossier inspectable. Aucun repository ni ouverture de session dans cette phase.
2. **Validation SQL et écriture atomique** : session dédiée, garde effective,
   rattachements verrouillés, deux clés d'idempotence, deux prédictions, commit unique.
3. **Consultation** : DTO Read matérialisés avant commit, retournés après succès ;
   GET historique existant avec une session de lecture du seul bac à sable.

Fichiers envisagés pour une étape d'implémentation distincte, **aucun créé ici** :

| Fichier / emplacement proposé | Responsabilité |
| --- | --- |
| `backend/app/services/p101_persistence_service.py` | Orchestration du lot et unique transaction ; aucune recommandation ni autre calcul |
| `backend/app/schemas/p101_persistence.py` | Entrée/dossier validé, erreurs typées, sortie de lot et contrat final des détails SQL |
| `backend/app/repositories/p101_idempotency_repository.py` | Réservation unique, lecture des conflits et contrôle du contenu ; aucun commit |
| `backend/app/models/p101_persistence_record.py` | Métadonnées explicites du registre sandbox, importées par le chemin dédié uniquement |
| `backend/app/p101_sandbox/session.py` et `guard.py` | Factory de session, garde avant écriture, identité d'instance et configuration sans défaut DEV |
| `backend/p101_migrations/` | Environnement Alembic sandbox distinct, historique et version_table dédiés, migration du registre et protections |
| `tests/p101_persistence/` | Tests purs des mappings ; fixtures PostgreSQL dédiées ; transaction, concurrence, provenance, GET et migration |
| Documentation de la future étape | Configuration sans secret, preuves, inventaire avant/après et compte rendu |

Ne pas modifier les routes, frontend, détecteur statistique, services persist_* ou
modèle général PredictionRecord pour ajouter un endpoint de génération. L'exécution
future sera une entrée locale explicite et contrôlée, hors API DEV permanente.
L'import des modèles actuels passe par core.database ; la factory sandbox devra
fixer une configuration sandbox avant cet import ou isoler les métadonnées dans
son adaptateur. Elle ne doit pas créer silencieusement un moteur ciblant DEV.

## 4. Contrats d'entrée, provenance et validation

### 4.1 Lot admis

Entrée conceptuelle : exactement deux objets Computed ML 3 pour DEMO-M-011 et
DEMO-M-012, sans doublon, avec le manifeste synthétique v1 immuable, le mapping
logique attendu, une révision de calcul attestée, une révision de persistance
attestée et le dossier d'autorisation. Une Abstained, un dictionnaire imitant
computed, un objet partiel ou un autre équipement provoque un refus de tout le lot.
Pas de score zéro créé pour une abstention. Ces erreurs de persistance sont des
erreurs distinctes ; ne pas étendre les onze codes d'abstention du calcul pur.

Le dossier autorisé fixe : destination et instance sandbox, méthode/version,
dataset_sha256, deux cibles et leurs cutoffs, empreintes de référence, empreinte
du contenu métier et révisions de code. Sa modification exige une nouvelle
validation. run_id et prepared_at identifient la première préparation conservée ;
un retry ne devient pas un nouveau résultat parce qu'il a un nouveau run_id.

### 4.2 Provenance du code

Le commit réel du calcul ML 3 est maintenant connu :
`b6b4d521b9c9456c160433e9343efd48d3c0168d`. Ce SHA désigne bien les modules/fixture
commités et non une branche documentaire ; **aucun calcul n'est relancé dans ML 4.1**.
Les preuves antérieures restent celles du rapport ML 3 : 73 tests du pilote et
38 tests / 51 sous-cas de régression sans entraînement. Elles ne deviennent pas
des résultats de test de persistance.

Les propositions ML 3 peuvent encore contenir code_revision=null/pending_commit ou
un SHA/requires_validation. Le service ne doit pas les persister dans cet état.
La future préparation autorisée doit fournir la révision réelle ; la frontière de
persistance vérifie hors calcul : commit accepté, fichiers du calcul/fixture
conformes à cette révision, arbre d'exécution sans modification de ces sources,
dossier de preuves approuvé et révision de persistance elle-même validée après son
futur commit. Un simple format SHA ou le HEAD courant ne suffit pas.

Ne pas appeler validate_proposal sur les détails SQL enrichis : il ferme le contrat
**logique** et n'accepte que pending_commit/requires_validation. D'abord valider la
proposition logique originale, ensuite construire une copie SQL avec un validateur
final dédié. Celui-ci impose producer.code_revision attesté, retire revision_status
provisoire et ajoute une preuve de la révision du raccordement dans le reçu de lot.
La proposition logique initiale n'est ni mutée ni artificiellement promue par le
seul changement d'une chaîne de statut. Aucun changement de version de la méthode
statistique n'est nécessaire si formule, sélection et paramètres restent identiques.

### 4.3 Empreintes et rattachements SQL

Avant session, valider les deux propositions avec le contrat logique ML 3, leurs
statistiques et leur contenu. La revalidation pure prévue par ML 3 pourra recalculer
ses statistiques/empreintes **uniquement dans une future étape autorisée**, jamais
dans ML 4.1. Elle ne doit ni entraîner ni déclencher un autre pipeline.

Dans la transaction, vérifier :

- Codes et ids logiques DEMO exacts ; Company → Site → Equipment → Sensor réels
  uniques et cohérents. Type pump, capteur temperature, unité °C, noms de démo
  explicites ; aucun id historique UI47 accepté ou supposé.
- Mapping mesure par id logique du manifeste approuvé vers id SQL entier positif,
  unique et sûr pour JavaScript ; chaque Measurement doit appartenir au capteur.
  Ne pas apparier uniquement par valeur ou réutiliser les numéros DEMO comme ids SQL.
- Union des deux références et cibles : les douze mesures 001…012. Pour chaque
  référence, exactement dix lignes ordonnées, timestamp strictement antérieur à sa
  cible, cadence quotidienne à 08:00 UTC, qualité good et valeur finie identique.
- Comparaison des timestamps par instant UTC à précision microseconde, sans arrondi
  ni comparaison de dates administratives naïves. Recherche aussi des ids/instants
  ambigus ou de mesures supplémentaires dans les créneaux utiles ; ne pas ignorer
  un doublon présent en SQL mais absent du mapping.
- Valeur SQL double precision égale à la valeur numérique attendue du manifeste
  v1 (entiers/demi-entiers exactement représentables), sans tolérance qui masquerait
  une modification. Une unité ou qualité divergente fait refuser tout le lot.
- Reconstruction des empreintes depuis les lignes verrouillées + les métadonnées
  logiques du manifeste. Measurement ne contient ni fixture_id, ni synthetic, ni
  available_at : ces faits viennent du dossier synthétique validé, pas d'une preuve
  d'ingestion SQL. Leur absence dans le modèle ne doit pas conduire à inventer une
  disponibilité réelle ou à assimiler created_at d'un parent à available_at.
- Concordance des empreintes complètes dataset/références et du cutoff de chaque
  cible ; aucune correction automatique d'un manifeste ou d'une ligne.

Les empreintes v1 attendues restent celles consignées par ML 3, sans recalcul ici.
Le registre ne garantit pas l'authenticité cryptographique d'une source : celle-ci
repose sur la procédure de validation, les droits et l'identité de la destination.

### 4.4 Mapping final des 14 champs

| Champ Read | Règle de persistance |
| --- | --- |
| id | Véritable valeur de séquence PostgreSQL, jamais un id factice ; réservée dans la transaction si nécessaire au registre |
| equipment_id | Id SQL unique résolu pour DEMO-EQ-001 |
| sensor_id | Id SQL unique résolu pour DEMO-SEN-001 |
| measurement_id | Id SQL de DEMO-M-011 ou DEMO-M-012 selon la cible |
| prediction_type | anomaly |
| score | 0.0 pour 011 ; 1.0 pour 012, indicateur non probabiliste |
| level | null |
| is_alert | false pour 011 ; true pour 012 |
| model_name | statistical_deviation |
| model_version | p101-stat-v1 |
| horizon_hours | null |
| details | Contrat SQL fermé/versionné de ML 2, enrichi uniquement avec ids vérifiés, code_revision attesté et vraie idempotency_key |
| predicted_at | Timestamp UTC de la cible : 11 ou 12 janvier 2026 à 08:00 ; pas l'heure d'écriture |
| created_at | Instant UTC réel de première écriture attribué explicitement dans la transaction ; commun au lot neuf ; jamais remplacé au retry |

Pour details, garder synthetic, run, motif, codes équipement/capteur et parents,
cible et dix observations, μ/s/écart/seuil/multiplicateur, cutoff/prepared_at,
dataset/reference_sha256 et version de méthode. Ajouter les ids SQL aux emplacements
prévus par ML 2 ; appliquer après enrichissement la limite 6 000 octets UTF-8,
chaînes <= 240 caractères, dix références, six niveaux maximum et finitude stricte.
Pas de DSN, mot de passe, dump, requête arbitraire ou configuration privée dans JSON.

Le DTO final ferme ses champs supplémentaires et vérifie niveau/horizon null,
score/alerte cohérents et created_at >= prepared_at >= cutoff >= timestamp cible.
Les métadonnées administratives des parents ne servent pas à ces comparaisons.
PredictionRecordCreate/Read génériques sont réutilisables en validation finale,
mais leurs contrôles seuls ne suffisent pas ; le validateur dédié complète les
invariants métier. La sortie est un reçu de lot créé/existant contenant deux DTO
Read matérialisés, ids/clés, instance et révisions, sans objet ORM encore attaché.

## 5. Registre concurrent : schéma minimal et migration proposée

### 5.1 Table dédiée

Nom proposé : `p101_pilot.idempotency_records`, dans le seul bac à sable.
Schéma conceptuel, aucune DDL créée ou exécutée :

| Colonne | Type / contrainte proposée |
| --- | --- |
| idempotency_key | varchar(64), PRIMARY KEY donc UNIQUE immédiate/non différable, NOT NULL ; CHECK exactement 64 hexadécimaux minuscules |
| key_canonical | text NOT NULL, UTF-8 borné à 4 096 octets ; tuple canonique exact servant au digest |
| content_sha256 | varchar(64) NOT NULL, même CHECK hexadécimal |
| content_canonical | text NOT NULL, borné à 16 384 octets ; projection métier canonique déterministe, sans secrets |
| prediction_id | integer NOT NULL, UNIQUE immédiate, FK vers public.prediction_records.id, NO ACTION, DEFERRABLE INITIALLY DEFERRED |
| first_created_at | timestamptz NOT NULL, égal au created_at de la prédiction liée |

Pas de statut « pending » persistant, pas de ligne autorisée sans prédiction au
commit et pas de suppression en cascade depuis le registre. La FK différée permet
de réserver une clé avant la ligne de prédiction tout en gardant prediction_id
NOT NULL. L'id est obtenu de la **véritable séquence attachée** à PredictionRecord,
résolue par les métadonnées PostgreSQL du schéma autorisé ; ne pas inventer son nom
ni utiliser max(id)+1. La consommation d'une séquence n'est pas annulée par rollback :
des trous d'ids après conflit/échec sont normaux et ne prouvent pas une ligne orpheline.

Une simple FK registre → prédiction ne force pas l'inverse. Prévoir donc dans la
migration sandbox un **constraint trigger différé** sur les insertions/modifications
de prédictions du producteur P101, exigeant au commit exactement une entrée de
registre correspondante, avec même clé dans details, type/nom/version, ids et date.
Un trigger de cohérence symétrique sur le registre vérifie que sa prédiction est
du producteur attendu et correspond au contenu canonique validé. Les objets sont
qualifiés par schéma ; aucune résolution via un search_path modifiable.

Le rôle d'exécution ne peut ni désactiver les triggers, changer session_replication_role,
ni modifier/supprimer les lignes du registre ou les prédictions. Un contrôle préalable
d'insertion limité à ce rôle sandbox refuse les autres producteurs et les champs
P101 incompatibles. Ces protections préviennent aussi un appel accidentel du service
générique avec les mêmes identifiants. Aucun trigger proposé dans DEV permanent.
Le rôle de maintenance reste une autorité privilégiée : ses actions doivent être
séparées, explicites et tracées, pas prétendues impossibles par ces contrôles.

### 5.2 Clé et contenu canonique

Tuple de clé versionné `p101-idempotency-v1` : UUID réel d'instance sandbox,
dataset_sha256, codes équipement/capteur, id logique de cible, timestamp cible,
cutoff UTC, type anomaly, model_name, model_version, code_revision du calcul,
paramètres du contrat et reference_sha256. La révision du raccordement figure
dans le reçu/preuve d'exécution ; modifier le raccordement sans changer la méthode
ne doit pas suffire à dupliquer les mêmes résultats.

Canonisation : clés triées, UTF-8 sans BOM, JSON compact, chaînes NFC, UTC à six
décimales, nombres sous forme décimale normalisée dans la projection de hachage.
Réutiliser les primitives ML 3 appropriées, avec un schéma fermé spécifique au tuple
(leur normalisation des dates est actuellement attachée aux noms timestamp et
available_at ; normaliser explicitement cutoff et tout autre champ avant encodage).
SHA-256 des octets canoniques = idempotency_key. Ne calculer aucune clé effective ici.

Projection de contenu : champs déterministes type/score/alerte/niveau/horizon,
date cible, identités logiques complètes, données des références/cible, paramètres,
statistiques, empreintes et version/révision de calcul. Exclure run_id, prepared_at,
created_at et ids SQL alloués. Le mapping SQL est contrôlé séparément contre la
ligne existante à chaque retry ; son exclusion n'autorise pas un remapping silencieux.
Conserver les octets canoniques en plus des digests permet de détecter aussi un
conflit de contenu ou une collision, sans compter seulement sur une égalité de hash.

### 5.3 Réservation, conflits et visibilité

Réserver les deux clés dans l'ordre lexicographique identique pour toutes les
sessions. La réservation PostgreSQL utilise une insertion avec traitement ciblé
du conflit sur la **seule PK idempotency_key**, sans écraser la ligne existante.
La cible UNIQUE de l'upsert doit rester non différable ; seule la FK est différée.

En isolation READ COMMITTED, la transaction perdante attend la résolution du conflit.
Si rien n'est retourné parce qu'une autre transaction a validé la clé, exécuter une
**nouvelle instruction SELECT** pour obtenir le snapshot frais et vérifier la ligne.
Un SELECT dans le même énoncé/snapshot peut manquer la ligne concurrente ; ne pas
l'interpréter comme une clé libre. Si le concurrent rollback, l'insertion peut
réussir. Toute erreur de FK ou d'une autre contrainte reste une erreur, pas un retry
idempotent « réussi ». Aucune capture générale d'IntegrityError suivie de SQL sur une
transaction PostgreSQL déjà en échec : rollback complet puis nouvelle transaction.

Pour une clé existante : comparer key_canonical et content_canonical/digest,
réhydrater la prédiction liée et vérifier ses 14 champs et le mapping actuel.
Identité et contenu identiques : retourner les ids, created_at, run_id et détails
originels sans UPDATE. Contenu différent : conflit explicite, rollback et aucun
remplacement. Un mélange déjà-existant/nouveau pour ce lot v1 de deux cibles est
une incohérence de lot : rollback, aucune réparation automatique d'un historique
partiel. Lot entièrement nouveau ou entièrement existant seulement.

### 5.4 Migration et conservation

Prévoir un environnement Alembic sandbox séparé de `backend/migrations`, avec sa
propre table de version dans p101_pilot. Le bootstrap explicite de la base vide
appliquera d'abord les migrations générales attendues via une configuration sandbox
contrôlée, puis la migration dédiée. Celle-ci vérifiera la présence/le schéma de
prediction_records et la révision générale autorisée avant d'ajouter registre,
contraintes, fonctions/triggers sandbox et marqueur d'environnement. Les révisions
générales et leurs fichiers ne seront pas réécrits ; aucun numéro de nouvelle
révision n'est inventé dans cette conception.

La migration dédiée et ses droits ne sont ni autochargés ni appliqués lors d'un
démarrage applicatif. Le bootstrap initial du marqueur relève du provisionnement
admin distinct et autorisé, pas d'un contournement de la garde du service.
Le downgrade doit refuser des données de pilote présentes sauf procédure explicite
d'export/conservation/destruction du **seul bac à sable**. Pas de nettoyage par
DELETE de parents ni de remise à zéro de tables partagées. Les FK NO ACTION du
registre doivent empêcher la cascade actuelle des parents de détruire silencieusement
une prédiction déjà référencée ; ce comportement doit être prouvé en test sandbox.

## 6. Transaction atomique du lot

1. Valider hors SQL le dossier et les deux Computed ; refuser toute abstention,
   provenance provisoire non attestée, cible supplémentaire ou répétée.
2. Acquérir une nouvelle session exclusivement liée au moteur sandbox validé ;
   aucune mutation en attente. Ouvrir une transaction unique avant la première
   requête. READ COMMITTED explicite, horodatage UTC, délais de verrou/requête bornés.
3. Dans cette transaction, vérifier l'identité effective de destination, le marqueur,
   les rôles/droits, les révisions générales/sandbox et protections obligatoires.
   Aucun nextval, flush, INSERT ou réservation avant cette garde.
4. Lire et verrouiller dans un ordre stable les parents et les douze mesures ;
   contrôler les rattachements et contenus section 4, et les créneaux sans ambiguïté.
   Des verrous SHARE empêchent UPDATE/DELETE des lignes retenues jusqu'au commit.
   Ils n'empêchent pas à eux seuls l'insertion d'un nouveau doublon : les rôles du
   pilote/API n'ont aucun droit d'écriture sur les mesures et le provisionneur est
   arrêté pendant la session. Tout provisionnement concurrent doit suivre le même
   protocole exclusif ; à défaut, refuser le scénario et ne pas revendiquer une
   protection contre les phantoms grâce aux seuls verrous de lignes.
5. Produire les clés/projections, puis réserver les deux entrées en ordre stable.
   Pour un lot neuf, allouer les vrais ids SQL dans la transaction et réserver
   les lignes du registre avec ces ids avant création des prédictions. Choisir une
   fois l'instant UTC réel de première écriture avant ces réservations pour renseigner
   first_created_at et le futur created_at à l'identique. Pour un lot
   existant conforme, ne réécrire aucune date ni aucune métadonnée.
6. Pour un lot neuf, construire les deux PredictionRecord avec ids réservés et
   created_at UTC réel unique déjà choisi après validation. Appeler le repository
   sans commit : les flush/refresh restent dans la transaction unique. Vérifier
   les détails SQL fermés/bornés et matérialiser deux DTO Read sérialisables.
7. Forcer la vérification des contraintes différées nommées du pilote avant le
   commit pour détecter les liens manquants/incohérents. Ne pas s'arrêter à un
   flush réussi : des contraintes peuvent encore échouer à la validation finale.
8. Commit unique du lot et du registre. Retourner le reçu seulement après succès ;
   utiliser les DTO déjà matérialisés pour éviter un refresh implicite après commit
   dû à l'expiration ORM. Fermer la session dans tous les cas.

Toute exception avant commit, y compris sérialisation, FK, conflit de contenu ou
second résultat invalide, provoque rollback de tout nouveau travail du lot. Aucun
savepoint n'est utilisé pour accepter le premier résultat seul. Ne pas promettre
de rollback des séquences ni d'une transaction dont le serveur a déjà validé le commit.

Deadlock/erreur de sérialisation : rollback, puis au maximum deux nouvelles tentatives
du **lot entier**, si l'autorisation reste valide, avec nouveau contrôle destination
et sources ; aucune boucle infinie ni bascule vers un mode sans registre. Délais
et diagnostic seront vérifiés dans les tests futurs ; un conflit métier n'est pas
rejoué automatiquement.

### Commit incertain

Déconnexion pendant/après commit : retourner un état distinct « issue inconnue »,
sans affirmer échec/rollback. Conserver les deux clés, l'empreinte de dossier et
l'identité sandbox, sans secrets. Dans une nouvelle session gardée sur la même
instance, rechercher les deux clés : deux lignes conformes → succès existant avec
ids initiaux ; aucune ligne → un retry autorisé peut réserver les mêmes clés,
l'unicité arbitrant une transaction originale encore en cours ; une seule ligne
ou divergence → incohérence, arrêt et diagnostic. Si la résolution ne peut aboutir
avant le délai, conserver « inconnue » et ne pas inventer une issue.

## 7. Bac à sable : préparation proposée, aucune ressource créée

Choix recommandé : instance/cluster PostgreSQL local séparé du DEV permanent,
base dédiée proposée `industrial_predict_ml_sandbox`, volume séparé, port hôte
explicitement réservé ultérieurement. Aucun port ou UUID n'est déclaré disponible
aujourd'hui. Le nom est une proposition ; l'identité effective sera autorisée avant
provisionnement. Ne pas réutiliser les lanceurs/configurations DEV ni leurs comptes.

Prévoir trois rôles distincts, noms définitifs à approuver : propriétaire/migrateur
hors exécution, pilote d'écriture limité, lecteur GET. Le rôle pilote n'est ni
superuser, owner, membre d'un rôle DEV, BYPASSRLS, CREATEROLE, CREATEDB ou détenteur
de DDL. Droits : lecture des parents/mesures/marqueur/révisions ; insertion/lecture
du registre et des seules prédictions P101 via les protections décrites ; usage de
la séquence concernée. Aucun UPDATE/DELETE de sources, registre ou historique,
aucune insertion de recommandations. Le lecteur ne possède aucun droit d'écriture.

Pour les verrouillages SHARE, ne pas accorder UPDATE général sur les sources au
rôle pilote. Prévoir dans la migration sandbox une fonction de lecture/verrouillage
SECURITY DEFINER limitée aux codes/ids du manifeste autorisé : propriétaire sans
accès DEV, objets qualifiés, search_path fixe de confiance, paramètres bornés,
vérification du session_user appelant et aucun SQL dynamique. Elle ne réalise aucun
DML métier ; les verrous restent portés par la transaction appelante. Retirer EXECUTE
à PUBLIC et ne l'accorder qu'au rôle pilote. Contrôler les droits exacts et l'absence
d'accès à d'autres actifs en test PostgreSQL ; aucune simulation SQLite ne vaut preuve.
La garde vérifie l'identité applicative avant/après l'appel, sans confondre le
current_user interne de cette fonction avec session_user.

Sur un cluster partagé, l'absence de GRANT explicite sur DEV ne suffirait pas :
CONNECT peut provenir de PUBLIC, de membres hérités ou d'une règle d'authentification.
Le cluster séparé, ses secrets distincts et ses règles d'accès doivent interdire
l'authentification du compte pilote au DEV permanent. Aucun privilège sur DEV ne
sera modifié pour cette préparation ; aucune connexion d'essai à DEV n'est prévue.

### Identité et garde obligatoire

Configuration privée hors Git, sous ACL restreintes et sans copie des secrets DEV :
hôte/port publié, adresse/port attendus côté serveur, base, rôle, UUID d'instance,
révisions attendues et emplacement de secrets. Aucun fallback vers DATABASE_URL,
`.env`, backend/alembic.ini ou fichier de configuration DEV. Aucun dump exporté.

Marqueur proposé `p101_pilot.environment_guard`, singleton en lecture seule pour
le rôle pilote : purpose `p101-ml-sandbox`, UUID aléatoire d'instance, nom de base,
identifiant de provisionnement et révision de schéma. Seul le propriétaire admin
peut l'écrire. Une copie de base n'est pas automatiquement une nouvelle instance
autorisée : régénérer/autoriser son identité explicitement.

Vérification effective future, avant toute écriture :

- Destination transport autorisée, identité de la connexion authentifiée et preuve
  d'instance concordante ; interdire les connexions Unix/socket inattendues.
- Adresse et port réels du serveur, base effective, session_user et current_user,
  aucun changement de rôle non prévu ; UUID/marqueur et révisions concordants.
- Distinguer port publié sur l'hôte et port interne de PostgreSQL : en conteneur,
  inet_server_port peut rester le port interne alors que le client utilise un
  autre port. Valider les deux contre la topologie privée approuvée, pas une égalité
  incorrecte avec le port publié.
- Rôle non privilégié et protections du registre/triggers présentes et actives.
  Refus explicite de `industrial_predict_dev` et de toute autre cible non approuvée,
  même si un marqueur homonyme existe. Nom et marqueur seuls ne sont pas des
  authentifications fortes ; l'isolement transport/rôle/instance les complète.

La garde est répétée à chaque transaction, y compris après reconnexion et retry ;
pas seulement au lancement du processus ou dans l'UI. Les migrations et la création
initiale du marqueur ont une procédure d'autorisation admin différente, sans rendre
la garde du service facultative.

## 8. Plan de validation futur I01–I12

### Prérequis et niveaux de tests

**Unitaires sans base** : contrats computed/abstained, fermeture du lot, mapping sur
objets factices, invariants des 14 champs, provenance, canonisation de clé/contenu,
bornes JSON enrichi, contenu identique/divergent et refus d'ids ambiguës. Ne pas
importer les fixtures partagées qui ouvrent une base ou entraînent un modèle.

**PostgreSQL transactionnel** : environnement explicitement autorisé, pilote psycopg
déjà déclaré, migrations générales + sandbox validées, marqueur/droits, fixture
synthétique chargée une seule fois par provisionnement autorisé. Les tests lisent
les sorties/contrats préparés ; aucune nécessité d'entraîner ou d'appeler RUL/Health
Score. SQLite peut aider certains mappings, jamais certifier UNIQUE concurrente,
upsert/visibilité, timestamptz, triggers différés ou un commit réel.

Prévoir un schéma ou une base jetable **déjà isolé du DEV**, initialisé et validé
hors transaction des travailleurs, avec des connexions indépendantes réellement
commitées. Ne pas copier la fixture DatabaseCase telle quelle pour ces tests : sa
transaction externe annulée et son schéma non commité ne sont pas visibles d'une
deuxième connexion. Dédier une configuration `P101_TEST_DATABASE_URL` privée sans
repli vers DASHBOARD_TEST_DATABASE_URL/DATABASE_URL ; absence → tests explicitement
non exécutables, jamais sélection automatique de DEV.

**Concurrence** : deux sessions/processus, barrières déterministes avant réservation,
délais bornés, session d'observation fraîche et contrôle des verrous/contraintes.
Pas de partage d'une Session SQLAlchemy entre threads, pas de sleeps servant de
preuve de concurrence, pas de pseudo-commit sous transaction externe.

**GET** : d'abord test d'intégration de route avec dépendance de session remplacée
par la destination sandbox gardée, sans contacter l'API DEV. Un futur test HTTP
réseau nécessite une autorisation distincte et une instance dédiée ; aucune
démonstration navigateur prévue dans ML 4.1.

| Cas ML 2 | Plan de mise en œuvre et preuve attendue |
| --- | --- |
| I01 Garde destination | Unitaires : configuration DEV/UUID/port/rôle/révision/marqueur faux refusés avant allocation/INSERT ; PostgreSQL sandbox : identité réelle contradictoire refusée, zéro ligne ; jamais contacter DEV pour tester son refus |
| I02 Mapping industriel | Wrong Company/Site/Equipment/Sensor/Measurement, unité/valeur/qualité/date divergentes, doublon SQL ou id inconnu : lot entier refusé, inventaire inchangé |
| I03 Insertion nominale | Deux registres et deux prédictions validés par commit réel ; nouvelle connexion lit les 14 champs, détails bornés, ids réels et mêmes dates de première écriture |
| I04 Retry séquentiel | Même contenu avec run_id/prepared_at de tentative différents : mêmes ids, created_at et détails originels ; aucun UPDATE ni ligne supplémentaire |
| I05 Concurrence | Deux réservations simultanées, commit du gagnant puis snapshot frais du perdant : exactement deux prédictions, deux clés, mêmes ids ; scénario gagnant rollback également couvert |
| I06 Conflit de contenu | Même clé et contenu divergent, collision de digest simulée en test, mapping SQL différent ou lot partiellement existant : conflit explicite, rollback sans remplacement |
| I07 Rollback | Injecter une erreur après réservation, première insertion, second flush, validation JSON et contrôle différé : nouvelle connexion ne voit aucun ajout du lot ; prédictions préexistantes conservées ; trous de séquence admis |
| I08 Commit incertain | Couper la connexion au voisinage du commit avec contrôle du serveur de test ; vérifier les branches validé/non validé/non résolu et le retry sur mêmes clés, sans doublon |
| I09 Course sur sources | UPDATE/DELETE refusés pour le rôle pilote ; tentative privilégiée coordonnée bloquée par verrous puis diagnostiquée ; insertion de mesure concurrente interdite au rôle ; provisionnement exclusif vérifié |
| I10 Lecture historique | Route GET équipement sandbox : type anomaly, is_alert true/false, périodes inclusives/égalité, ordre predicted_at/id décroissants et pagination ; aucun POST ni calcul déclenché |
| I11 Abstention | Toute Abstained ou lot mêlé computed/abstained refusé avant transaction d'écriture ; pas de score normal implicite |
| I12 Intégrité | Empreintes/compteurs par table avant/après, seuls registre et deux PredictionRecord changent ; parents/mesures/maintenances/recommandations inchangés ; test séparé de suppression/cascade uniquement sur fixture jetable autorisée |

Les tests AST vérifient aussi table/FK différée/UNIQUE immédiate, protections inverses,
absence de DDL générale destructive et portée du downgrade. Les tests PostgreSQL
doivent appliquer la vraie migration sandbox, pas seulement Base.metadata.create_all.
Le contournement par insertion P101 sans registre doit échouer au plus tard au
contrôle des contraintes ; le rôle lecteur ne doit pas pouvoir écrire.

### Preuves d'intégrité et nettoyage

Chaque campagne future produit une preuve de destination expurgée, révisions de
code/schéma, dossier synthétique autorisé, résultats I01–I12 et inventaires canoniques
avant/après. Relecture dans une nouvelle session pour confirmer la visibilité après
commit ; comparer les valeurs/digests, pas seulement les compteurs. Les séquences
peuvent avancer après rollback sans que les données métier changent.
Le contrôle de non-modification DEV repose sur la séparation des ressources et
l'absence de connexion DEV, pas sur des SELECT de contrôle qui exigeraient un accès
DEV non autorisé. Nettoyage éventuel uniquement des ressources de test identifiées
et explicitement autorisées, hors transaction des travailleurs ; aucun seed/DELETE
dans la base permanente, aucun reset de volume pour réparer un échec de test.

## 9. Risques et B-PRE-01 à B-PRE-11

| Réserve | Encadrement proposé et limite persistante |
| --- | --- |
| B-PRE-01 | Identité SQL et bac à sable gardés ; aucun mécanisme SaaS d'authentification/autorisation ajouté ; réserve ouverte |
| B-PRE-02 | Validation dédiée score binaire/alerte/finitude et champs null ; producteurs génériques inchangés ; ouverte |
| B-PRE-03 | Instants UTC/cutoff et mapping précis, bornes GET inclusives distinguées ; routes existantes non durcies ; ouverte |
| B-PRE-04 | Validation de toute la chaîne et des douze mesures sous verrou ; FK générales indépendantes inchangées ; ouverte |
| B-PRE-05 | JSON final fermé/borné et contenu canonique ; aucun durcissement global du stockage ou du transport ; ouverte |
| B-PRE-06 | Registre NO ACTION et droits empêchant la perte silencieuse du pilote ; politique générale CASCADE non changée ; ouverte |
| B-PRE-07 | Lot minuscule et consultation sans écrivain concurrent pour la démo ; aucune garantie nouvelle de snapshot/count ou performance API ; ouverte |
| B-PRE-08 | Évite create/persist_* et joblib/RUL ; transaction et unicité proposées, non implémentées ; risques actuels RUL inchangés ; ouverte |
| B-PRE-09 | Chemin explicite de deux anomalies seulement ; aucun historique alimenté aujourd'hui ni orchestration générale ; ouverte |
| B-PRE-10 | Révision calcul connue, provenance d'exécution et schéma à attester ; données historiques non réparées ; ouverte |
| B-PRE-11 | GET liste existant suffit ; pas d'endpoint détail/latest prévu ; limite conservée et ouverte |

Risques résiduels : erreur de configuration au bootstrap, droits de verrouillage
mal dimensionnés, garde contournée par un compte propriétaire, import d'un moteur
DEV, absence de protections inverses, commit incertain et future indisponibilité
du serveur. Chaque risque a un refus ou une preuve de test attendu ; aucun n'est
déclaré résolu par cette conception. Les deux signaux synthétiques ne prédisent
pas une panne et ne doivent jamais déclencher des recommandations automatiques.

## 10. Checklist d'autorisation avant toute implémentation

- [ ] Valider ce rapport et ses choix : lot de deux computed, registre à FK différée,
  protections inverses, READ COMMITTED, retries bornés et absence de réparation partielle.
- [ ] Autoriser séparément le périmètre de code ML 4.2 et les seuls tests unitaires
  souhaités ; une validation documentaire n'autorise pas une connexion PostgreSQL.
- [ ] Autoriser séparément la création des ressources sandbox : cluster/volume,
  port publié/interne, nom de base, UUID/marqueur, propriétaire et rôles dédiés,
  emplacement privé et règles de non-accès DEV ; aucun secret dans Git.
- [ ] Valider la migration sandbox et son bootstrap, la révision générale attendue,
  les fonctions/triggers, droits exacts de verrouillage et conservation ; autoriser
  explicitement leur application uniquement sur cette instance identifiée.
- [ ] Valider la préparation des douze fixtures SQL synthétiques et leur mapping,
  l'immuabilité des sources, les révisions de calcul/persistance et le dossier de preuves.
- [ ] Autoriser nominativement les tests PostgreSQL I01–I12, les connexions concurrentes,
  commits/rollbacks réels, injections de panne et éventuel nettoyage du seul espace jetable.
- [ ] Autoriser distinctement la première persistance des deux résultats et la
  consultation GET sur l'instance dédiée ; aucune autorisation implicite ML 5.

Sans les autorisations correspondantes, rester à la documentation ou aux seuls
travaux explicitement autorisés ; aucune création automatique d'infrastructure.

## 11. Livraison et contrôles documentaires

Seul ajout prévu/réalisé : `docs/ml-4.1-p101-persistence-design.md`.
Branche `feature/ml-4-p101-persistence`, HEAD attendu conservé
`b6b4d521b9c9456c160433e9343efd48d3c0168d`, index vide ; contrats ML 1/2/3 et code
du pilote inchangés. Contrôles finaux réussis : git status ne montre que ce nouveau
document, aucun diff de fichier suivi ni contenu indexé ; git diff --check et
contrôle du nouveau document contre NUL sans erreur d'espacement. Les douze lignes
I01–I12 et les onze réserves B-PRE sont présentes ; aucun secret détecté dans le rapport.

**Rapport en attente de validation. Aucune mise en œuvre ML 4.2 ou ML 5 autorisée
ou commencée.**
