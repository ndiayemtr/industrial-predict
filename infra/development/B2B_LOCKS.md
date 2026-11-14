# AUTH-B2B-DEV-5B-4F — fonctions de verrouillage, mode fermé

Définitions uniques : `b2b_locks.py`. Le fichier `b2b-lock-install.review.sql`
est un modèle de revue pour un déploiement distinct, terminé par ROLLBACK.
Aucun exécuteur, migration automatique ou nouveau mode de lancement n'est ajouté.
Ne pas le lancer, ni utiliser b2b-migrate/migrate pour installer ces objets.

## Contrats v1

| Signature dans b2b_lock | Résultat | Prédicats et verrou |
| --- | --- | --- |
| lock_user_v1(integer) | 0–1 state text | id positif exact, FOR UPDATE OF u ; suspendu conservé pour le traitement applicatif/admin existant |
| lock_external_identity_v1(integer,integer,text,text) | 0–1 id integer, issuer text, subject text | user_id obligatoire et soit external_id positif avec issuer/subject NULL, soit paire issuer/subject exacte avec external_id NULL ; FOR SHARE OF e |
| lock_memberships_v1(integer) | 0–N id, user_id, company_id integer, state, role text | utilisateur exact, toutes les appartenances, ORDER BY id, FOR SHARE OF m |
| lock_membership_permissions_v1(integer,integer) | 0–N permission, role text | appartenance exacte et parent rattaché au même utilisateur, ORDER BY permission, FOR SHARE OF p ; parent déjà verrouillé |
| lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone) | 0–1 transaction_id text | digests state/browser/policy, contrat et created_at <= now < expires_at, FOR UPDATE OF t |

Tout identifiant doit être positif ; les chaînes d'identité sont non vides,
bornées à 2048 caractères, sans bordures blanches ni contrôles. Les digests OIDC
sont 64 hexadécimaux minuscules ; contrat non vide, borné à 128 caractères ;
instant fini, fourni par le contrat UTC existant. Les NULL sont explicitement
contrôlés (aucun STRICT qui transformerait un argument invalide en absence).
Les paramètres invalides lèvent une erreur constante 22023 sans valeurs privées.
Pas de LIMIT, SKIP LOCKED ou exception absorbée. Les magasins conservent leurs
contrôles de cardinalité et de cohérence, et les comparaisons exactes issuer/sub.

Les fonctions PL/pgSQL sont SECURITY DEFINER, VOLATILE et PARALLEL UNSAFE.
Leur search_path fixé est pg_catalog, pg_temp ; les objets applicatifs sont
entièrement qualifiés. Pas de SQL dynamique, changement de rôle, commit, appel
réseau, INSERT/UPDATE/DELETE. session_user doit être ui47_app ; current_user est
le propriétaire pendant l'exécution. Cette vérification ne prouve pas une identité
OIDC, une session ou une entreprise : le backend garde toutes ces responsabilités.

## Transaction applicative préservée

Les appels SQLAlchemy sont paramétrés et typés sur la session existante. Aucun
nouveau moteur, connexion ou transaction. Les verrous restent jusqu'à la fin de
la transaction appelante ; l'ordre utilisateur → session → identité → appartenances
→ permissions est conservé. Le verrou de session reste direct avec ses trois UPDATE
réellement nécessaires. Le contrôle user_id des appartenances retournées est aussi
explicite. Aucune appartenance ou permission n'est déduite de l'adresse email.

READ COMMITTED, lock_timeout 5s, statement_timeout 15s et contrôles après attente
restent aux mêmes endroits. Pour OIDC, la fonction ne mesure pas l'horloge : le
SELECT clock_timestamp séparé puis DELETE RETURNING avec tous les prédicats
temporels restent après le verrou. Pas de secret avant commit confirmé, aucun
retry automatique, erreurs/commits incertains toujours traités par les magasins.
Un rollback de savepoint peut libérer des verrous : aucun code ne doit absorber
cette erreur et continuer une autorisation. Ces opérations nécessitent une
transaction READ WRITE, contrairement à l'audit READ ONLY des ACL.

## Déploiement ultérieur à approuver

1. Qualifier la destination DEV et TLS verify-full par les mécanismes officiels,
   le baseline sans droits B2B et les sauvegarde/restauration isolée. Prévoir la
   nouvelle publication SQL et son approbation hors des migrations historiques.
2. Revoir le modèle d'installation séparé sous ui47_admin superutilisateur : il
   vérifie base/OID, version, cluster, instance, révision et TLS serveur. CREATE
   ROLE/SCHEMA échouent si un objet existe déjà ; aucun IF NOT EXISTS/replacement
   ne masque une divergence. Le schéma appartient à ui47_migrator ; les cinq
   fonctions appartiennent à ui47_b2b_lock_owner, NOLOGIN NOINHERIT sans capacités
   superuser/createdb/createrole/replication/bypassrls ni appartenance de rôle.
3. Le propriétaire reçoit USAGE public/b2b_lock, SELECT limité aux prédicats et
   résultats sur cinq tables et les cinq UPDATE de clés nécessaires aux verrous.
   Il n'a ni INSERT/DELETE, ni accès aux sessions, séquences ou tables industrielles,
   ni CREATE de schéma/base ou TEMP. Il ne lit ni nonce ni code_verifier OIDC.
4. Dans la transaction de création, retirer EXECUTE à PUBLIC sur chaque signature.
   Donner à ui47_migrator EXECUTE WITH GRANT OPTION sur ces seules signatures :
   cette délégation technique lui permet l'attribution future sans devenir membre
   du propriétaire NOLOGIN. Ses appels restent refusés par session_user. Aucune
   USAGE/EXECUTE applicative n'est attribuée par l'installation. Le modèle vérifie
   le contrat fermé puis termine par ROLLBACK ; aucune version COMMIT autorisée ici.
5. Après installation approuvée séparément, les modèles d'ACL applicatives
   comportent 10 accords table/colonne, USAGE b2b_lock et 5 EXECUTE : 16 accords
   ciblés, aucune délégation à ui47_app, aucun UPDATE de clé ni droit de séquence.
   Ils vérifient avant/après les ACL, signatures/résultats/noms de paramètres,
   propriétaire, langage/attributs/search_path et SHA-256 du corps de chaque
   fonction ; refus de PUBLIC, fonctions supplémentaires et droits owner excessifs.
6. Après tout éventuel commit approuvé : nouvelle connexion officielle ui47_app
   et qualification indépendante. Le candidat demeure non activable, Google et
   métier fermés. Le mode préparation accepte l'absence de b2b_lock ; s'il existe,
   il exige le contrat fermé exact et aucun droit applicatif sur ce schéma/fonctions.

Retour arrière applicatif : le modèle inverse retire d'abord les 5 EXECUTE et
USAGE, puis le delta table/colonne, et vérifie le contrat fermé avant ROLLBACK.
Il conserve fonctions et rôle technique. Leur suppression ultérieure est une
maintenance distincte, après arrêt des consommateurs et examen des dépendances,
jamais CASCADE ni réinstallation des UPDATE sensibles. Aucun script ne modifie
les ACL industrielles. Toutes les empreintes des nouveaux modèles demandent une
nouvelle revue ; les empreintes des migrations historiques restent inchangées.

## Validation et limites

Tests ciblés hors ligne : définition des cinq signatures, validations/prédicats,
ordres/verrous et absence d'écritures ; appels des magasins et sélecteurs exacts,
cardinalité, session appelante, refus interentreprises, expirations, rollback,
commits incertains ; catalogues simulés (droits manquants/excessifs, PUBLIC,
propriétaire, signatures, corps, search_path et délégation) ; mode préparatoire.
Ces tests ne constituent pas une exécution PL/pgSQL ni une preuve de verrous réels.

Résultat du lot : 91 tests backend et 43 sous-cas réussis, 45 tests infrastructure
réussis ; git diff --check propre. Commandes ciblées (aucune suite globale) :

```powershell
Set-Location -LiteralPath 'D:\projets\industrial-predict'
& '.\backend\.venv\Scripts\python.exe' -B -m pytest tests/core/test_application_session_store.py tests/core/test_oidc_transaction_store.py tests/b2b_runtime/test_runtime.py -q
Set-Location -LiteralPath 'D:\projets\industrial-predict\infra\development'
& '..\..\backend\.venv\Scripts\python.exe' -B -m unittest test_b2b_activation test_b2b_locks test_manage
```

Le canal privé de réveil asyncio Windows a bloqué sous sandbox ; le diagnostic
borné a identifié socketpair/accept, avant les appels applicatifs. L'exécution
hors sandbox a réussi, avec les doubles et interdictions PostgreSQL/réseau des
tests toujours actifs. Aucune connexion à un service PostgreSQL/Google n'en découle.

Après validation distincte uniquement : PostgreSQL 17.10 isolé, destination,
rôles et transport qualifiés par le dispositif existant. Tester réellement les
cinq fonctions avec arguments valides/invalides, les refus UPDATE directs,
PUBLIC/autres appelants, les objets temporaires/search_path détournés, les
cardinalités et le maintien des verrous après retour. Deux connexions doivent
exercer suspension, révocation, réaffectation, permissions concurrentes,
consommation OIDC unique, expiration après attente et rollback. Aucune instance
n'a été créée, recherchée ou utilisée pour exécuter ces scénarios dans ce lot.

Risques résiduels : une connexion applicative compromise peut demander des verrous
sur d'autres lignes et causer de la contention. Les paramètres ne sont pas une
preuve d'autorisation. Les droits INSERT sessions, INSERT/DELETE OIDC et UPDATE
d'activité/révocation/remplacement des sessions subsistent, ainsi que le CRUD
industriel historique. Les nouvelles fonctions ne constituent pas un RLS ou une
isolation SQL complète des tenants. Les insertions concurrentes de permissions
(lignes absentes avant lecture) restent régies par le protocole administratif.
