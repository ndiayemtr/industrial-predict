# P101-DEV-3C — journal durable, déclaration hors ligne

## État du livrable

Préconditions vérifiées : branche `feature/auth-b2b-identity-access`, HEAD
`fbb980e3c3cc059457033e5af9e4a23fc50639a5`, arbre propre et index vide.
Ce lot prépare des métadonnées ORM et une publication de migration gardée.
Aucune migration, connexion, écriture métier ou activation du writer n'est faite.
Les modules de révision ne sont ni importés ni exécutés par les tests.

## Modèle et identité d'opération

`P101PredictionOperation`, enregistré avec les autres modèles sans I/O, décrit
`public.p101_prediction_operations` (22 colonnes, toutes NOT NULL) :

L'ORM conserve les noms non qualifiés des modèles existants ; le futur déploiement
doit fixer search_path à public. La révision qualifie explicitement public.

- `id` : PK technique entière ; `idempotency_key` : SHA-256 hexadécimal unique.
- Entreprise, site, équipement, capteur et mesure cible : identifiants audités.
- Modèle et version, limités à `statistical_deviation` / `p101-dev-stat-v1`.
- `input_sha256`, `result_sha256` et `result_details_json` : empreinte d'entrée,
  empreinte des détails et texte canonique exact du `Computed` (6000 octets max).
  `result_sha256` reprend précisément `Computed.details_sha256`, sans introduire
  un nouvel algorithme d'empreinte du résultat.
  Le résultat conserve statistiques, provenance et contexte ; son indice binaire
  n'est jamais une probabilité de panne.
- Acteur : `actor_user_id`, `actor_issuer`, `actor_subject`, exactement le tuple
  audité par DEV-3A. Ni cookie, token, rôle, permission ni email. Ce snapshot
  d'identité n'est pas une preuve d'authentification et ne donne aucun grant.
- `state`, `score` binaire, `is_alert`, `prediction_id`, `target_at`, `prepared_at`,
  `recorded_at`. Le score et l'alerte conservent le résultat complet hors des détails.

La clé conserve exactement la sérialisation DEV-3A : SHA-256 UTF-8 du JSON compact
`[company_id,equipment_id,sensor_id,measurement_id,model_name,model_version]`.
La contrainte SQL construit la même chaîne pour les constantes de modèle admises.
Le site, l'acteur, les empreintes, le cutoff et la date d'observation ne changent
pas cette identité. Une même opération avec un contenu différent doit être refusée
comme conflit, jamais mise à jour. Une future version du modèle nécessite une
nouvelle publication explicitement revue ; aucune normalisation implicite.

## Un seul état, réservation sans ligne incomplète

`recorded` décrit un enregistrement logique complet, pas un commit acquitté.
Il n'ajoute pas de nouvel état à `PersistenceState`. Pas d'état `pending`,
`reserved`, `uncertain` ou `commit_confirmed` dans la table.

Lors d'une future intégration, le propriétaire de transaction devra allouer
explicitement un id de prédiction sans insérer la prédiction, insérer le journal
complet avec cet id et récupérer son id technique, puis insérer la prédiction
portant le même id préalloué et `p101_operation_id = journal.id`. Allocation
et réservation ne confirment aucune prédiction ; les trous de séquence sont admis.
Les deux FK composites et le trigger de cohérence sont DEFERRABLE INITIALLY DEFERRED : la prédiction
peut être absente lors de la réservation, mais doit exister et concorder avant
commit. Aucun UPDATE de finalisation ni commit intermédiaire n'est nécessaire.
Cela respecte le refus de doublon avant INSERT de prédiction du port DEV-3A.

Les UNIQUE sont immédiats : clé, tuple métier DEV-3A et `prediction_id` unique.
En cas de conflit de réservation, aucune prédiction de cette tentative ne doit
avoir été insérée. Un journal seul ne peut pas devenir durable si la FK/validation
échoue. L'existence d'une ligne n'est observable par une autre transaction qu'après
commit ; un `recorded_at` n'est pas une date d'acquittement.

Après perte d'acquittement, le client reste UNCERTAIN. La réconciliation future
devra rechercher la clé avec une autorisation actuelle et vérifier les empreintes.
Une absence momentanée ne prouve pas un rollback ; aucun retry automatique.
Ce lot ne fournit ni réservation, ni allocation d'id, ni requête de réconciliation.

## Intégrité SQL déclarée

Le modèle et la migration décrivent indépendamment les mêmes colonnes,
PK/UNIQUE/FK/CHECK. Les CHECK imposent ids positifs, SHA-256 minuscules, modèle et
état exacts, score 0/1 et alerte cohérente, identité auditée non vide et bornée selon les contrats B2B, dates
finies et `prepared_at <= recorded_at`, taille et SHA-256 du texte résultat.
Le SHA-256 utilise la fonction native PostgreSQL, sans installation de pgcrypto.

Le payload JSON doit être un objet du schéma DEV-1, avec entreprise/site/équipement/
capteur/cible/modèle et empreinte d'entrée identiques aux colonnes. L'expression
est terminée par IS TRUE : une clé JSON absente ne peut pas passer par SQL NULL.
Cela vérifie une concordance déclarative, pas la vérité des mesures ni le calcul
de l'empreinte d'entrée. Le futur writer doit recharger les sources sous protection
et réutiliser l'évaluateur existant. Le texte et son hash restent ceux du producteur
canonique DEV-1 ; SQL ne réimplémente pas son encodage canonique numérique.

Les deux FK sont RESTRICT en suppression et modification, différées pour
l'insertion. Le trigger de contrainte `p101_operations_prediction_matches`, AFTER
INSERT et différé, relit la prédiction FOR SHARE et compare :

- Association `prediction.p101_operation_id = journal.id`, identifiants
  équipement/capteur/mesure, modèle/version et type `anomaly`.
- Date cible, date de création et absence de level/horizon.
- Score 0/1 et alerte cohérente ; détails JSON sémantiquement identiques au texte
  canonique conservé ; timestamp cible des détails identique à `target_at`.

Trois fonctions de trigger, SECURITY INVOKER avec search_path fixé à
`pg_catalog, pg_temp`, et quatre triggers sont déclarés. Pas de SQL dynamique,
SECURITY DEFINER, grant ou recherche d'autorité dans ces fonctions.

## Conservation et portée sur les prédictions

Le journal refuse UPDATE et DELETE, même avant commit, ainsi que TRUNCATE.
La FK RESTRICT empêche la suppression d'une prédiction référencée, y compris par
cascade depuis les sources. Le trigger TRUNCATE du journal interdit également
la suppression collective de sa preuve par TRUNCATE CASCADE.

FIX1 corrige la restriction P1 initiale : le trigger `p101_predictions_no_mutation`
interdit UPDATE/DELETE uniquement si `OLD.p101_operation_id IS NOT NULL`.
Le modèle/version ne figure plus dans son prédicat. Il ne consulte ni journal,
ni cache, ni décision externe. Le détachement, la substitution de l'association,
la modification de PK ou de contenu d'une ligne déjà liée rencontrent tous le
même refus, même si NEW propose NULL ou la même valeur. Une ligne liée nouvellement
insérée dans la transaction est également protégée ; pour annuler la tentative,
le propriétaire doit rollback plutôt que détacher/supprimer la ligne.

Les prédictions non journalisées ont `p101_operation_id = NULL`, y compris les
données historiques : aucune reprise automatique, aucun UPDATE de backfill.
Leurs UPDATE/DELETE restent soumis aux seules règles métier préexistantes ; le
nouveau trigger ne s'applique pas. Les cascades depuis Equipment/Sensor/Measurement
restent CASCADE dans l'ORM et les anciennes migrations : elles peuvent supprimer
les prédictions non liées. Si une cascade atteint une prédiction liée, le trigger
et les FK RESTRICT empêchent la perte de preuve et font échouer l'instruction.
La suppression d'un parent contenant à la fois des lignes liées et non liées
reste donc refusée atomiquement, sans suppression partielle durable.

La FK interdit le TRUNCATE global de prediction_records seul,
même si le journal est vide ; TRUNCATE CASCADE rencontre le refus du journal.
Il n'existe pas de TRUNCATE limité aux seules lignes non liées ; cette restriction
administrative demeure nécessaire pour la rétention, sans bloquer leur DELETE.

## FIX1 — association bidirectionnelle et références circulaires

Une colonne entière nullable `prediction_records.p101_operation_id`, sans défaut,
identifie l'association. Deux paires UNIQUE immédiates servent de cibles :
`prediction_records(id, p101_operation_id)` et
`p101_prediction_operations(id, prediction_id)`.

Les références SQL natives, DEFERRABLE INITIALLY DEFERRED, sont exactement :

```text
journal(prediction_id, id) -> prediction_records(id, p101_operation_id)
prediction_records(p101_operation_id, id) -> journal(id, prediction_id)
```

La première paire est entièrement NOT NULL : aucun journal ne peut devenir durable
avec un marqueur absent ou différent sur sa prédiction. La seconde utilise MATCH
SIMPLE : un marqueur NULL ne requiert aucun journal, mais un marqueur non NULL
exige exactement l'opération qui référence cette prédiction. MATCH FULL serait
incorrect ici, car la PK de prédiction reste non NULL pour les lignes historiques.
Le UNIQUE prediction_id du journal et les paires réciproques excluent double
journal et référence croisée. Aucune association invalide ne doit passer au commit,
même si le trigger de comparaison métier n'était pas considéré dans ce raisonnement.

Les contraintes d'association reposent sur les FK/UNIQUE PostgreSQL, pas sur un
EXISTS soumis à la visibilité MVCC. Le prédicat d'immuabilité utilise directement
la ligne OLD. Un rattachement initial NULL -> id modifie réellement cette ligne :
le moteur doit sérialiser les mutations concurrentes de la même ligne, réévaluer
le trigger sur sa version actuelle ou refuser par erreur de sérialisation.
L'effet exact sous READ COMMITTED, REPEATABLE READ et SERIALIZABLE reste à qualifier
sur PostgreSQL réel, notamment journalisation contre UPDATE/DELETE/cascade.

Ordre DDL : ajouter la colonne nullable à la table existante ; créer sa paire
UNIQUE ; créer le journal avec sa paire UNIQUE et sa FK vers prediction_records ;
ajouter la FK inverse par ALTER TABLE ; installer fonctions et triggers.
Aucune contrainte ne référence une table ou colonne non encore créée. L'ORM
déclare `use_alter=True` sur la FK inverse pour exprimer ce cycle DDL. Les deux PK
conservent leur génération SERIAL via `autoincrement="ignore_fk"`, puisque chacune
participe désormais à une FK composite. La migration ne modifie ni la séquence ni
les valeurs de la PK historique de prediction_records.

L'import des modèles enregistre aussi le journal pour résoudre les références
ORM ; il ne crée ni connexion, table, relation de cascade ou ordonnanceur d'écriture.
Un create_all n'est toujours pas un déploiement équivalent : il manque les triggers.

Les ids industriels et l'acteur du journal sont des snapshots : pas de FK vers
des rattachements mutables ou des adhésions qui détruiraient l'audit. La cohérence
historique de l'entreprise provient du payload protégé ; l'appartenance actuelle
et le grant restent la responsabilité du futur writer transactionnel.

La table ne force pas rétroactivement chaque prédiction existante à avoir un
journal. Le futur chemin P101 doit impérativement créer les deux dans la même
transaction. Les droits du rôle runtime devront interdire DDL, désactivation des
triggers, changement de session_replication_role et modification des protections.
Un propriétaire/superutilisateur peut retirer les protections : aucune garantie
absolue contre un administrateur privilégié n'est prétendue. La rétention est
illimitée dans cette déclaration ; toute purge exigera un lot séparé explicitement
approuvé. Le downgrade lève systématiquement une erreur, sans DROP.

## Publication gardée et position dans la chaîne

Nouvelle révision : `p101_0001_operations`, parent direct `b2b_0002_analyze`.
Ordre après le head historique `09ac8101e9fe` :

```text
12e2fc65f372 -> 4b7e2a91c6d0 -> b2b_0001_sessions
             -> b2b_0002_analyze -> p101_0001_operations
```

La liste fermée passe de quatre à cinq publications. L'entrée ajoutée contient
parent, chemin exact, empreinte UTF-8/LF et scope des deux tables et trois fonctions.
Les triggers sont attachés aux tables déclarées dans ce scope. La protection
`general_migrations.py` ajoute une empreinte AST fixe indépendante, couvrant aussi
chaque corps PL/pgSQL. Recalculer le manifeste seul n'approuve aucune modification.
Les neuf sources historiques et quatre révisions précédentes restent inchangées.

Le domaine de confiance général reste distinct du runtime P101. Il n'existe ici
aucune signature ni autorité d'approbation authentifiée : ne pas en inventer.
Le précontrôle reste `authenticated=False`, `execution_enabled=False`.
`request_execution()` refuse, même avec connexion injectée. `env.py` et INI inerte
restent inchangés. Aucun chargeur Alembic opérationnel ni exécuteur n'est ajouté.
Les `op.execute()` du nouveau fichier sont uniquement des déclarations SQL
fixes reconnues par l'empreinte AST ; aucun de ces appels n'a été exécuté.

## Qualification restant nécessaire

Les tests hors ligne comparent AST, manifeste, métadonnées indépendantes et DDL
compilé ; ils ne prouvent pas que PostgreSQL accepte ou applique ces protections.
Une qualification isolée sur la version PostgreSQL cible devra vérifier :

1. Installation transactionnelle complète (PL/pgSQL, fonctions natives, schémas,
   droits), catalogue exact et empreintes après application autorisée.
2. Réservation avant prédiction et commit cohérent ; absence de prédiction,
   contenu divergent ou FK invalide rejetés au commit, sans ligne partielle.
3. Deux transactions/instances concurrentes pour la même opération : une seule
   réservation et prédiction durables ; conflits de contenu refusés, sans retry.
4. UPDATE/DELETE/TRUNCATE du journal refusés ; UPDATE/DELETE/cascades de prédictions
   non liées autorisés, y compris P101 ; mutations/détachement/substitution/cascades
   de lignes liées refusés. Tester les associations erronées, deux rattachements
   concurrents, journalisation contre mutation et anciennes vues transactionnelles.
5. Perte d'acquittement avant/après commit, redémarrage et réconciliation par clé,
   conservation du même résultat et distinction entre absence et rollback prouvé.
6. Fournisseur B2B dans la transaction d'écriture, locks acquis avant la première
   lecture fixant le snapshot, révocation et changement de sources/rattachements
   refusés, insertions fantômes empêchées jusqu'au commit.

Le writer DEV-3B demeure inchangé et entièrement désactivé. Un journal ne remplace
ni authentification, ni autorisation, ni verrous de sources ou d'autorité.

## Résultat des tests ciblés

Campagne historique DEV-3C avant FIX1 (non relancée telle quelle) :

```text
backend/.venv/Scripts/python.exe -m pytest tests/p101_dev_writer tests/p101_dev_orchestration tests/p101_dev_sql tests/core/test_general_migrations.py tests/core/test_professional_account_migration.py tests/core/test_application_session_migration.py tests/core/test_analysis_permission_migration.py tests/core/test_oidc_migration.py -q
388 passed in 21.00s
```

Les tests de publication existants sont adaptés uniquement au nouveau nombre de
révisions/sources et au nouveau head ; leurs contrôles historiques restent actifs.
Les tests du journal ajoutent comparaison complète du schéma, concordance de clé
DEV-3A et de mapping du résultat, inspection des protections SQL, refus d'une
publication altérée même après rehashage du manifeste, et refus d'exécution après
précontrôle exact avec connexion injectée. Les barrières réseau/SQL/Alembic des
fixtures existantes restent actives. Ces résultats n'attestent aucune concurrence
ni durabilité PostgreSQL réelle. Aucun test de migration n'importe une révision.

FIX1 ajoute l'inspection des FK composites et de l'ordre DDL, le maintien des
cascades existantes et de la génération des PK, le prédicat sur le marqueur OLD,
ainsi qu'une matrice synthétique d'appartenance aux paires référencées (association
correcte, absence, double journal, référence croisée). Cette matrice vérifie la
relation mathématique décrite par les métadonnées ; elle n'émule pas PostgreSQL,
les triggers, les verrous ou le commit. Les mutations de source simulées couvrent
également le retour à un prédicat global et la dégradation d'une FK composite.
L'unique campagne FIX1 a été exécutée après préparation de toutes les corrections :

```text
backend/.venv/Scripts/python.exe -B -m pytest tests/p101_dev_writer tests/p101_dev_orchestration tests/p101_dev_sql tests/core/test_general_migrations.py tests/core/test_professional_account_migration.py tests/core/test_application_session_migration.py tests/core/test_analysis_permission_migration.py tests/core/test_oidc_migration.py -q
404 passed in 19.93s
```

Aucun second lancement de tests n'a été effectué pour FIX1. Les contrôles d'espaces
et de périmètre Git ont ensuite confirmé l'absence de modification des révisions
publiées, du writer, des politiques B2B, d'env.py/INI, d'Angular et d'infrastructure.
Le lot global DEV-3C + FIX1 comprend quatre créations et huit modifications :
`prediction_record.py` et l'enregistrement ORM dans `models/__init__.py` s'ajoutent
aux dix fichiers DEV-3C initiaux. Branche et HEAD sont inchangés, index vide.
Aucun commit, push, accès PostgreSQL/Docker ou exécution de migration.

Références : [triggers différés](https://www.postgresql.org/docs/18/sql-createtrigger.html),
[contraintes et FK](https://www.postgresql.org/docs/18/sql-createtable.html),
[SHA-256 natif](https://www.postgresql.org/docs/18/functions-binarystring.html).

Arrêt pour validation humaine. Aucun commit ou push dans ce lot.
