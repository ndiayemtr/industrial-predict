# P101-DEV-3D-EXEC-1 — noyau transactionnel et compilation fermée

Implémentation hors ligne. Aucun serveur, conteneur ou moteur Docker consulté.
Aucune migration exécutée, aucun build, téléchargement, writer métier ou endpoint.
Les composants INFRA-3 et RUNNER-1 publiés, les gardes et les révisions sont inchangés.

## Ce qui fonctionne effectivement

`compiler.compile_release()` produit une release SQL depuis les 14 sources
publiées, sans les importer. Le garde existant vérifie manifeste, parents,
empreintes UTF-8/LF et ancres AST. Le compilateur recapture/revérifie chaque source,
puis travaille exclusivement sur ces chaînes immuables en mémoire.

Le décodeur fermé n'accepte dans upgrade que les appels déclaratifs reconnus,
types/contraintes SQLAlchemy explicitement énumérés, constantes et listes. Ni
eval/exec, import de révision, Python arbitraire, autocommit_block, op.get_bind,
connexion ou appel dynamique. Le seul SQL littéral est celui des sources
approuvées (fonctions/triggers P101). Les corps PL/pgSQL ne sont pas découpés
sur leurs points-virgules.

Alembic 1.19.1 et SQLAlchemy 2.0.52 servent uniquement au rendu PostgreSQL
`as_sql=True`, sans env.py, command.upgrade, run_migrations, stamp ou create_all.
Le dialecte est explicitement configuré avec `paramstyle='named'` pour produire
du SQL natif : le dialecte DB-API pyformat doublerait les `%`, dont `%ROWTYPE`.
La release n'est pas une chaîne à réinterpoler via `%` ou à corriger par remplacement
global de `%%`. Le futur transport devra respecter ce contrat de SQL natif.
Le tableau de version est rendu par le hook Alembic version_table_impl et
SQLAlchemy ; ses INSERT/UPDATE sont ordonnés après chaque upgrade, dans la même
transaction externe. Ils ne servent jamais à marquer un schéma non installé.
Le digest de release couvre DDL et bookkeeping. Cette compilation ne démontre
pas encore l'acceptation/effet des DDL par PostgreSQL 17.10.

`execution_authority.Intent` définit une nouvelle intention versionnée EXEC-1,
distincte des opérations fermées B2B existantes. Elle lie autorité/clé/UUID,
opération, campagne, ressources, programme/release/fixture, état initial et
catalogue approuvé, ainsi qu'une fenêtre UTC <= 15 minutes. La vérification
Ed25519 réelle réutilise TrustedKey et ses règles de validité/révocation. Aucun
booléen favorable, SignatureReview construit manuellement ou clé provenant de
l'intention ne remplace la signature. Aucun émetteur/signataire opérationnel,
clé privée ou racine de confiance n'est fourni. Une signature valide ne prouve
pas le consentement humain ni l'origine de l'inventaire.

`ReplayReservations` réutilise les primitives B2B d'écriture exclusive fsync et
de verrou OS. L'appelant fournit un répertoire local existant `p101q-exec-*`, sans
symlink/junction ni chemin substitué. Une réservation exclusive par
campagne/opération précède toute session SQL et survit à un nouvel objet/processus.
Elle n'est jamais supprimée, même après succès ou refus : une nouvelle signature
ou un nouvel UUID d'approbation ne permet pas de rejouer cette première opération.
Un claim sans outcome est incertain. Les outcomes sont exclusifs et non réécrits.
Perte/altération de stockage, ACL non fiables ou erreurs d'I/O imposent arrêt et
réconciliation externe. Aucun effacement/reset automatique. fsync du fichier ne
constitue pas une preuve de persistance des entrées de répertoire après panne
électrique ; cette durabilité et les ACL réelles restent à qualifier.

## Algorithmes exécutables, backend simulé uniquement

`execution.CampaignExecutor` reçoit séparément campagne attendue, CollectorPolicy,
inventaire attendu, clés publiques de confiance, réservations, digest de catalogue
indépendant et horloge UTC. `expected_bindings(operation)` prépare les métadonnées
à faire signer extérieurement. Il ne délivre aucune autorisation.

`run_simulated(backend, intent, signature)` n'accepte que le type concret
SimulatedBackend, sans sous-classe ou callback générique. Ce backend conserve
des lignes/transactions en mémoire et enregistre le DDL : il n'implémente pas
PostgreSQL, ses contraintes ou sa concurrence. Les faits TLS/SQL sont des doubles,
même si leur chaîne X.509 et la signature d'intention sont vérifiées réellement
hors ligne par cryptography 50.0.2.

Pour `migrate`, le noyau :

1. Vérifie signature, contenu, inventaire moteur/ressources et campagne exacte ;
   réserve durablement l'opération avant ouverture de session.
2. Vérifie certificat, liaison TlsBinding/session/socket, rôle, adresse/base,
   version, cluster, instance et absence de marqueur DEV/privilèges élevés.
3. Possède une transaction externe ; vérifie l'état vide, applique les 14 révisions
   et leur versionnement dans l'ordre compilé, vérifie le catalogue avant commit.
4. Revérifie la signature non expirée, l'identité et les ressources avant COMMIT.
5. Après acquittement, ouvre un observateur distinct et compare le catalogue.

Pour `first-pair`, le noyau :

1. Vérifie identité, catalogue approuvé et absence de données déjà présentes.
2. Dans une transaction unique, insère les 15 lignes synthétiques du seed avec
   résolution des références via RETURNING et vérification de la projection seed.
3. Réutilise l'évaluateur et pair_plan RUNNER-1 : préallocation de l'id prédiction,
   journal complet avant prédiction, association réciproque, contraintes différées
   forcées puis un seul COMMIT. Aucun UPDATE de finalisation ou retry SQL.
4. Relit depuis un observateur : objet connexion distinct, objet socket distinct,
   handle différent et PID PostgreSQL différent, pendant que le writer est encore
   ouvert. Chaque session est vérifiée pour le même cluster/instance/certificat.
   Des UUID distincts seuls ne suffisent pas. La paire entière est comparée par
   le comparateur RUNNER-1 ; son digest n'est pas une attestation réelle.

Un échec d'identité avant BEGIN entraîne fermeture, sans rollback SQL envoyé vers
une destination non validée. Un échec avant COMMIT tente un rollback et n'annonce
que son résultat simulé. L'état passe à uncertain AVANT l'appel COMMIT. Une perte
d'acquittement avant/après effet reste incertaine : pas de rollback prétendument
probant, retry ou relecture automatique qui transformerait l'absence en succès.
Une vérification échouant après commit acquitté conserve commit_status=confirmed,
avec statut de vérification échouée. Une erreur de fermeture ou de journalisation
ne fabrique pas un rollback ; la réservation conservée interdit toute réexécution.

Les rapports héritent d'Offline : real_attested/authenticated/execution_authorized
restent faux. Les succès portent le nom simulated_commit_confirmed. Aucun log de
DSN, mot de passe, signature, certificat ou paramètres de connexion. Le rapport
ne conserve que statuts, flags et empreinte de preuves. Les diagnostics publics
sont constants via les gardes réutilisés. Mémoire/débogueur et processus modifié
ne sont pas dans cette garantie ; ce n'est pas une sandbox Python hostile.

## Ce qui reste fermé et pourquoi

`CampaignExecutor.run_live` refuse inconditionnellement avant d'inspecter les
arguments ; aucun flag, signature ou callback ne l'ouvre. Le CLI RUNNER-1 et ses
anciens refus restent inchangés. Le transport INFRA-3 n'est ni élargi ni utilisé
pour envoyer les écritures. Aucun fournisseur SQL RW effectif n'est livré ici.

Il manque précisément un backend concret qualifié fournissant ensemble :

- Collecte moteur/ressources réelle fraîche, profil de livraison TLS/secrets et
  contrôle de l'inventaire juste avant usage, sans mutation des conteneurs existants.
- Session TLS/SCRAM RW avec certificat capturé sur sa propre socket, timeouts et
  types/bindings de paramètres adaptés ; INFRA-3 reste limité aux métadonnées RO.
- Collecteurs pré-bootstrap, privilèges réels et catalogue complet normalisé,
  baseline indépendante approuvée, contrôle du nombre de lignes du versionnement.
- Chargement/verrouillage/relecture des sources de fixture, prévention des écritures
  concurrentes, puis véritable observateur sans pool ou socket partagé.
- Consentement humain authentifié, distribution des racines, révocation réelle,
  stockage anti-rejeu administré avec ACL/ownership vérifiés et protocole d'arrêt.

Les primitives moteur, TLS et seed du simulateur ne doivent pas être adaptées en
changeant simplement une étiquette « réel » ou en retirant un test de type. Une
activation exige une implémentation concrète et une revue séparées. Ainsi aucune
sécurité d'exécution réelle n'est affirmée à partir des doubles.

L'image de base, les wheels Linux et les hashes du lock transitif restent absents.
`exec1-dependencies.json` ajoute les références du compilateur/autorité, sans
prétendre compléter le build reproductible. Le manifeste de contenu signé étend
la liste RUNNER-1 aux nouveaux modules et aux helpers B2B utilisés. Aucun paquet
ou image installé/téléchargé, aucune autorité existante modifiée.

## Validation initiale hors ligne

Les nouveaux tests couvrent rendu des 14 révisions et refus de Python arbitraire,
sources inconnues/altérées, signatures valides/invalides/révoquées/expirées,
identités interdites, base non vide, ordre transactionnel, seed/paires simulés,
incertitude avant/après commit, reprise du registre, indépendance par objets/PID,
catalogue divergent et fermeture après commit connu. Aucun PostgreSQL, Docker,
réseau ou migration réelle. Une qualification SQL/TLS réelle reste indispensable.

Le venv backend fournit pandas/SQLAlchemy/Alembic ; cryptography est uniquement
dans le venv de tests cryptographiques existant. La campagne charge son site-packages
en dernier dans le seul processus pytest (même CPython 3.12.10), sans installation
ou modification des venv. Ce montage de validation n'est pas le futur runner.

La campagne initiale EXEC-1 a donné **48 passed in 34.70s**, exclusivement sur
`test_execution.py`. Ce résultat précède la revue ci-dessous ; la campagne complète
n'est pas relancée. Aucun test global, build ou accès réel.

## Revue ciblée avant commit - 9 novembre 2026

Défaut **P2 corrigé** : le dialecte PostgreSQL par défaut rendait le SQL littéral
PL/pgSQL avec `public.prediction_records%%ROWTYPE`. Le rendu pyformat dépendait
d'une désinterpolation DB-API absente du contrat de release SQL. Le choix explicite
du paramstyle named conserve désormais `%ROWTYPE`. Les sept SQL littéraux P101
(trois fonctions et quatre triggers) sont comparés intégralement aux sources
approuvées par le test de régression ; aucune migration ou garde n'est modifié.
Le digest de release et le contenu à signer changent : toute intention fondée
sur l'ancien rendu doit être recalculée, jamais réutilisée implicitement.

Le décodage fermé, les 14 parents/empreintes et l'ordre de versionnement ont été
revus. Les appels non reconnus échouent ; aucun corps Python de révision n'est
exécuté. Le rendu de defaults, colonnes, index et contraintes est délégué aux
constructeurs/operations de versions épinglées, sans schéma métier réécrit à la
main. Cela ne prouve toujours pas l'équivalence des effets sur PostgreSQL réel.

Les intentions lient destination/inventaire, sources, release SQL et état attendu.
La vérification des clés, de leur révocation déclarée et des fenêtres UTC ne vaut
pas approbation opérationnelle déjà obtenue. La réservation exclusive et le verrou
OS sérialisent réserve/inspection/outcome ; une interruption laissant un claim
sans résultat est incertaine et interdit toute nouvelle tentative du même couple
empreinte de campagne/opération. L'accès direct au registre peut réserver ou
refuser, mais ne peut autoriser un backend réel. La localité/ACL du stockage, son
intégrité et sa tenue après panne électrique restent des prérequis externes.

La transaction prévoit journal avant prédiction, FK différées forcées et un seul
commit. Le résultat inconnu demeure incertain ; un échec de relecture après ACK
ne devient pas un rollback. L'observateur est vérifié par objets socket/session
et PID, au-delà des UUID, mais uniquement dans le double admis.

Limite du simulateur explicitée : le DDL est enregistré sans être interprété,
`stage_pair` construit ses lignes via le mapping attendu, et le catalogue est
injecté. Un succès simulé ne démontre donc pas que les INSERT SQL ont produit
ces lignes, ni que defaults, triggers, UNIQUE, FK, verrous ou snapshots PostgreSQL
ont été appliqués. Le test source/rendu ajouté couvre le défaut identifié sans
transformer cette simulation en qualification SQL. `run_live` reste fermé.

Seuls les tests concernés par le compilateur et la liaison de la release à
l'autorisation ont été relancés : **8 passed in 6.39s**. Ils couvrent le rendu
des 14 révisions, la préservation des sept SQL littéraux, le parcours de migration
simulé et les cinq refus d'intentions signées mais non liées aux valeurs attendues.
La campagne complète des 48 tests n'est pas relancée. Les temporaires sont créés
dans le workspace puis nettoyés. Aucun test PostgreSQL, build ou accès Docker.
