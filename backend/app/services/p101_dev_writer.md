# P101-DEV-3B — port PostgreSQL désactivé

## Décision et périmètre

Implémentation partielle sûre, conformément au repli demandé. Aucun INSERT,
verrou, flush, commit, rollback, ouverture de connexion, endpoint ou branchement
runtime n'est ajouté. Aucun accès DEV/P101/OIDC, Docker ou Alembic n'a été réalisé.
Le port n'est pas qualifié pour une écriture réelle.

Préconditions initiales constatées : branche `feature/auth-b2b-identity-access`,
HEAD `1d795dd8b655144b313aea937a4a4ca8cb01b3a3`, arbre propre et index vide.

Le modèle `PredictionRecord` examiné possède une PK technique mais aucune clé
unique d'opération P101 et aucun journal de réconciliation. Ses FK métier ont
des suppressions en cascade. Une recherche préalable ou un verrou Python ne
garantiraient donc pas l'unicité durable. Aucun catalogue réel n'a été consulté :
une contrainte éventuellement déployée ailleurs ne peut pas être présumée.

La politique Python exige un grant explicite `predictions:analyze`, sous le
plafond du rôle. Le modèle `MembershipPermissionRecord` inclut cette permission ;
le contrat `authorization.py` indique que sa migration/qualification SQL reste
distincte. L'état réel des bases n'est pas attesté. Aucun rôle, email ou domaine
ne suffit à autoriser l'analyse.

## Contrat livré

`P101PostgreSQLWriter` expose les six méthodes attendues par `OrchestrationPort`.
Le constructeur reçoit uniquement des dépendances serveur explicites :

- `destination: PostgreSQLDestination` : base, utilisateur de session, rôle
  effectif, adresse et port serveur exacts ; pas de valeur par défaut ni de lecture
  de configuration ou de secret. Les sockets Unix (adresse/port SQL NULL) sont
  refusés par ce contrat TCP strict.
- `caller_provider: CurrentCallerProvider` : fournisseur de confiance du contrat
  B2B existant. Un objet typé ne prouve pas l'authenticité du fournisseur.
- `read_context` : fabrique de contexte DEV-2 appartenant à l'appelant ; `read()`
  lui délègue le cycle de vie sans installer de moteur ni de session.

`current_caller()` délègue au fournisseur, valide structure, référence et date
exactes. Dans l'orchestrateur, la politique existante reste appliquée. Ce
fournisseur ne retient pas contractuellement de verrous dans la transaction SQL
reçue : raison supplémentaire pour ne jamais activer la persistance actuelle.

`preflight(session, plan, now)` est un diagnostic optionnel hors du parcours
`persist()` : il reçoit une Session synchrone déjà liée à une Connection et une
transaction explicitement démarrée par l'appelant. Il ne termine aucune transaction.
Il retourne un `PredictionRecord` **transitoire, sans identifiant et non attaché**.
Ce retour n'est ni une autorisation d'insertion ni un résultat persistant.

Contrôles effectivement implémentés dans ce diagnostic :

- Session active, BEGIN explicite, sans savepoint, autoflush ou modifications
  ORM en attente ; mode de jonction `rollback_only` ; même Connection pour les
  modèles métier concernés et `PredictionRecord`. Un Engine est refusé avant SQL.
- PostgreSQL synchrone psycopg 3, connexion native identique, ouverte, non cassée,
  non invalidée ; autocommit strictement False et statut natif INTRANS. Réutilise
  le contrôle natif DEV-2, sans tentative de réparation.
- Isolation SERIALIZABLE et transaction serveur réellement READ WRITE ; identité
  de destination SQL comparée exactement ; redirection de schéma refusée.
- Identité et transaction physiques inchangées avant/après les contrôles et la
  relecture. Une anomalie produit uniquement `P101_DEV_WRITER_REFUSED`, sans cause
  ni contexte brut de pilote ou d'identité.
- Rafraîchissement B2B via le fournisseur à `now`, même acteur que la préparation,
  grant explicite pour l'entreprise préparée. Un refus précède les SELECT métier.
- Relecture SQL qualifiée `public` de la chaîne, cible et fenêtre entière de
  candidats DEV-2, limite de 33 pour refuser au-delà de 32 sans troncature réussie.
  Réutilisation des projections et de la conversion de mesures DEV-2.
- Comparaison exacte des sources, rattachements et contexte préparés ; évaluation
  par l'adaptateur existant avec la date d'observation originale pour comparer les
  empreintes. Comparaison du `Computed` entier, y compris score, statistiques,
  détails et empreintes ; vérification de la clé d'opération de DEV-3A.
- Mapping via `PredictionDraft.values()` : identifiants, indice binaire d'anomalie
  (jamais une probabilité de panne), alerte, dates, modèle/version, statistiques,
  provenance et empreintes dans les détails. `Abstained`/`Rejected` sont refusés
  avant toute requête. Aucun appel au service qui commit ni au repository qui flush.

Ces SELECT observent un instantané SERIALIZABLE, mais le diagnostic ne verrouille
pas les sources ou l'autorité. Il ne prouve pas que celles-ci sont encore actuelles
au retour et ne prévient pas une mutation concurrente. Il ne doit pas servir de
précontrôle suivi d'un `session.add()` externe.

## Barrière d'écriture et concurrence

`write()` refuse avant acquisition d'une ressource. `lock_and_reload()`,
`reserve_and_stage()` et `finish()` refusent aussi, y compris en appel direct,
après précontrôle réussi ou avec une décision ALLOW fabriquée. Aucun paramètre
d'activation ou callback d'insertion/commit ne permet de lever cette barrière.

L'orchestrateur peut préparer un résultat avec les dépendances de lecture
injectées ; sa tentative de persistance retourne REFUSED, sans id, et consomme
le plan. Aucune nouvelle tentative automatique n'est ajoutée. `finish()` ne
prétend jamais avoir confirmé un commit. Un refus du writer ne doit pas être
interprété comme preuve de rollback d'une transaction effectuée par un autre code.

Les appels concurrents ou répétés n'écrivent rien. Ce comportement ne constitue
pas une implémentation d'unicité : il n'existe volontairement aucun faux registre
en mémoire. Les tests de commit confirmé/incertain de DEV-3A concernent uniquement
son port simulé, jamais le writer concret livré ici.

## Proposition minimale, sans migration ni exécution

Pour ouvrir ultérieurement le chemin, faire valider puis implémenter ensemble :

1. Un journal PostgreSQL permanent d'opérations P101. Clé d'opération unique et
   unicité du tuple entreprise/équipement/capteur/mesure cible/modèle/version,
   empreintes des sources et du résultat, acteur audité, référence de prédiction
   unique et résultat conservé. Réservation atomique par INSERT soumis à la
   contrainte, puis INSERT de prédiction et finalisation du journal **dans la même
   transaction**. Un conflit ne remplace jamais une prédiction existante.
   Pas de suppression en cascade du journal : conserver son résultat et une
   référence avec politique RESTRICT, ou définir explicitement un mécanisme de
   tombstone immuable. La rétention métier doit préserver l'unicité après suppression.
2. Un fournisseur B2B transactionnel de confiance qui vérifie session vivante,
   expiration/révocation, lien externe exact, compte, adhésion et grants et retient
   les verrous jusqu'à fin de transaction. L'intégration doit coordonner les
   modifications de ces mêmes données d'autorité, y compris suppressions et grants.
   Qualifier le CHECK SQL permettant `predictions:analyze`, sans accorder le grant
   automatiquement. Ne pas présumer la version réellement déployée.
3. Une stratégie PostgreSQL qualifiée de blocage des mutations ET insertions
   fantômes : par exemple verrous de tables SHARE sur toutes les tables d'autorité
   et sources industrielles, acquis dans un ordre global avant rafraîchissement
   et relecture. Cette option bloque tous les DML concurrents sur ces tables et
   doit être évaluée pour sa contention. Des verrous de lignes seuls ne protègent
   pas la fenêtre contre les insertions ; SERIALIZABLE seul n'impose pas la fraîcheur
   à l'instant du commit. Une variante par révision/verrou de périmètre impose la
   coopération de **tous** les producteurs, via architecture ou triggers à qualifier.
4. Un propriétaire explicite de commit, sans auto-commit de sortie du contexte.
   Seul son acquittement fiable produit COMMIT_CONFIRMED et un id confirmé.
   Toute perte de connexion pendant le commit produit UNCERTAIN, jamais un retry
   aveugle ni une suppression compensatoire. Réconciliation indépendante par la
   clé durable avec autorité serveur, après résolution de la transaction initiale.
   Une lecture momentanément absente ne suffit pas à prouver son rollback.

Le journal est une proposition de nouveau schéma, pas une table supposée existante.
Une simple colonne unique sur `prediction_records` ne résout pas à elle seule la
rétention sous cascade et la conservation du résultat à commit incertain. Aucun
fichier de migration ni DDL exécutable n'est livré.

## Vérification hors ligne

Campagne exécutée depuis la racine, Python du venv backend :

```text
backend/.venv/Scripts/python.exe -m pytest tests/p101_dev_writer tests/p101_dev_orchestration tests/p101_dev_sql tests/p101_dev tests/p101_anomaly tests/core/test_authorization.py tests/core/test_caller_session.py -q
503 passed, 135 subtests passed in 22.46s
```

Les nouveaux tests réutilisent les fixtures synthétiques et la barrière réseau
DEV-2 (création de moteurs, connexions Engine/psycopg et sockets interdits).
Ils couvrent précontrôle Computed autorisé, refus B2B sans grant/interentreprises/
révocation/acteur différent/décision navigateur/date périmée, rattachements et
sources divergents, résultat falsifié, connexion et transaction invalides,
autocommit ambigu, READ ONLY, changement de transaction, résultats non Computed,
échec sans retry, tentatives concurrentes/répétées et nouvelle instance du port,
et intégration de la barrière dans l'orchestrateur.

Les tests DEV-3A existants de la même campagne couvrent réservation simulée,
échec avant commit, acquittement, commit incertain (y compris effet
simulé avant perte d'acquittement) et interdiction de replay. Ils ne prouvent ni
verrous PostgreSQL, ni unicité après crash, ni durabilité réelle, ni authentification.
Une campagne isolée PostgreSQL réelle sera indispensable après validation humaine
de l'architecture et des migrations. Elle est exclue de cette mission.

Fichiers ajoutés uniquement : ce document, `p101_dev_writer.py` et
`tests/p101_dev_writer/test_writer.py`. Aucun endpoint, changement Angular,
migration, commit ou push. Index laissé vide. Arrêt pour validation humaine.
