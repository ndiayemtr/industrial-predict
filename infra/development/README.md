# Environnement permanent de développement

Le parcours de sauvegarde au schéma installé, d'installation A/B et de retour
arrière fermé est décrit dans [B2B_DEPLOYMENT.md](B2B_DEPLOYMENT.md).
Ces opérations exigent des approbations séparées ; aucun lancement courant ne
les exécute.

Le contexte explicite de qualification isolée et son relais TLS sont décrits
dans [B2B_QUALIFICATION.md](B2B_QUALIFICATION.md). Il reste désactivé par défaut
et ne permet aucun démarrage applicatif.

## AUTH-B2B-DEV-5B-4F — verrouillages préparés, aucun déploiement

La matrice candidate retire les cinq UPDATE de clés de ui47_app et prévoit
USAGE sur b2b_lock et EXECUTE sur cinq signatures exactes. Les deux magasins
appellent ces fonctions sur leur session existante ; il n'existe aucun repli
vers les anciens UPDATE. Leur usage exige donc un déploiement SQL ultérieur
approuvé. Le seul lancement autorisé reste b2b-preparation, sans Google ni métier.
Voir les [contrats, prérequis et limites](B2B_LOCKS.md). Aucun objet, rôle ou droit
SQL n'a été installé par ce lot. Les scripts et empreintes de revue précédents
sont remplacés ; aucune migration historique ni empreinte approuvée n'est modifiée.

## AUTH-B2B-DEV-5B-4B — profil candidat, aucun runtime ouvert

`b2b-preparation` reste le seul profil de lancement. Le profil
`b2b-auth-candidate` décrit et qualifie les ACL B2B ; il n'est **pas activable**.
Les commandes `api`, `frontend`, `check-db`, migrations et Docker refusent
`--runtime-profile b2b-auth-candidate` avant de charger le profil privé.
Un champ privé `runtime_profile` différent de `b2b-preparation` est également
refusé. Aucun drapeau ne monte Google ou les anciens CRUD.

Le seul nouveau point d'entrée est un plan **hors ligne**, sans lecture du
profil privé, de la CA ou d'un mot de passe, sans moteur SQL ni accès Google :

```powershell
Set-Location -LiteralPath 'D:\projets\industrial-predict'
& '.\backend\.venv\Scripts\python.exe' '.\infra\development\manage.py' b2b-auth-plan --config 'D:\integration\industrial-predict\development\config.json' --runtime-profile b2b-auth-candidate --role ui47_app
```

Le chemin est comparé à l'inventaire DEV approuvé existant. Le rapport JSON
contient destination, révision, rôle, matrice, SQL de revue aller/retour et SHA-256
du plan ; `live_checks_performed=false`, `activation_available=false`.
Ce hash identifie un plan, il ne vaut ni approbation humaine ni preuve SQL.

### Matrice exacte proposée

Les listes complètes et ordonnées sont dans `b2b_activation.COLUMNS` ; les fichiers
`b2b-auth-grants.review.sql` et `b2b-auth-revoke.review.sql` sont des modèles de
revue générés depuis cette même matrice et contrôlés par les tests.

| Table | SELECT par colonne | INSERT par colonne | UPDATE par colonne | Droit de table |
| --- | --- | --- | --- | --- |
| local_users | id, state | aucun | aucun | aucun |
| external_identities | id, user_id, issuer, subject | aucun | aucun | aucun |
| company_memberships | id, user_id, company_id, state, role | aucun | aucun | aucun |
| membership_permissions | membership_id, permission, role | aucun | aucun | aucun |
| application_sessions | les 13 colonnes du contrat | les mêmes 13 | last_activity_at, revoked_at, replaced_by | aucun |
| oidc_transactions | les 13 colonnes du contrat | les mêmes 13 | aucun | DELETE |

Toutes les autres permissions B2B sont interdites, notamment SELECT/INSERT/UPDATE
au niveau table, REFERENCES, TRIGGER, TRUNCATE, MAINTAIN et délégation.
Aucun droit sur les trois séquences B2B. Les droits UPDATE de clés sont réservés
au propriétaire technique NOLOGIN des fonctions, avec SELECT limité aux colonnes
de leurs prédicats et résultats. Le candidat exige leur contrat exact et refuse
ces UPDATE sur le rôle applicatif. Les fonctions ne décident aucune autorisation.
Aucun provisioning, purge de sessions ou gestion des appartenances n'est accordé.

`inspect_db(config, profile='b2b-auth-candidate')` prépare la qualification en
lecture seule via le moteur ui47_app existant ; aucun appel n'en est effectué par
la nouvelle CLI hors ligne. Les contrôles d'identité, révision b2b_0002_analyze,
CA/SHA-256 et verify-full, propriétaires, tables et séquences sont réutilisés.
Les privilèges effectifs sont contrôlés avec has_table_privilege ET
has_column_privilege, pour chaque colonne et chaque permission. Sont refusés :
colonnes inattendues, droits manquants/excessifs, tout lien de rôle (y compris
SET ROLE), accords B2B à PUBLIC, options de délégation et grantor autre que
ui47_migrator pour les accords à ui47_app. Une erreur/ambiguïté interrompt le contrôle.

Les droits industriels historiques et leurs contrôles restent inchangés : CRUD
sur les huit tables et USAGE sur leurs séquences. Le candidat est donc une
qualification du **delta B2B**, pas une certification du moindre privilège global.
Leur réduction éventuelle exige un lot et un rollback approuvés séparément avant
une ouverture réelle. Aucun de ces droits ne monte une route HTTP.

### Procédure future de droits — ne pas exécuter dans ce lot

1. Arrêter les processus applicatifs contrôlés, conserver le mode fermé. Capturer
   les ACL effectives et brutes, grantors, rôles, propriétaires et empreintes des
   scripts. Qualifier sous ui47_app l'identité/TLS et l'état préparatoire sans
   droit B2B. Une sauvegarde actualisée et sa restauration isolée doivent être
   validées selon la procédure approuvée ; ne pas réutiliser un instantané périmé.
2. Faire approuver destination, hash du plan, matrice (dont UPDATE pour verrous),
   état initial exact et plan inverse. Aucun exécuteur de GRANT n'est fourni dans
   manage.py ; ne pas utiliser b2b-migrate ou migrate pour les ACL.
3. Après autorisation distincte, utiliser le transport privé approuvé verify-full
   et le propriétaire ui47_migrator. Le modèle SQL vérifie rôle, version 17.10,
   base/OID, cluster, instance, TLS et révision avant ses 16 GRANT ciblés.
   Les fonctions fermées doivent déjà être installées et qualifiées séparément.
   Il n'est applicable qu'au baseline B2B vide validé, jamais à une ACL ambiguë.
4. Dans cette même transaction propriétaire, les blocs `DO $acl$` vérifient
   explicitement les droits du rôle nommé ui47_app avant ET après le delta.
   Ils n'utilisent aucun changement de rôle : DEV-5B-4C a confirmé que le
   propriétaire ne peut pas emprunter l'identité applicative. Ils contrôlent
   les privilèges effectifs table/colonne, la forme et les propriétaires des
   six tables, les attributs du rôle, ses appartenances, PUBLIC, les grantors
   et les options de délégation. Une anomalie lève une exception et annule
   la transaction. La procédure aller exige préparation → candidat ; le
   retrait exige candidat → préparation. Aucun replay sur un autre état.
   Une autre connexion ne voit pas les accords non commités.
   N'effectuer aucun test OIDC/écriture de données dans cette transaction.
   Les deux modèles terminent volontairement par **ROLLBACK**. Seule une revue
   humaine ultérieure pourra préparer leur version à COMMIT après contrôle exact.
5. Après commit autorisé, requalifier avec une nouvelle connexion officielle
   ui47_app : `inspect_db(config, profile='b2b-auth-candidate')` conserve les
   vérifications d'identité, de révision et de transport avant `inspect_acl`.
   `inspect_named_acl(connection, profile=...)` sert uniquement à contrôler
   le rôle nommé depuis une connexion propriétaire déjà qualifiée ; ce helper
   ne crée aucune connexion et ne remplace pas les contrôles de destination.
   Comparer les ACL à la preuve attendue. Maintenir l'application arrêtée : le
   lanceur préparatoire refusera ces nouvelles ACL. Ce lot n'offre pas de lancement
   candidat et ne permet pas de poursuivre automatiquement vers Google.

Retour arrière : avant commit, ROLLBACK ; après commit, arrêter les éventuels
consommateurs, vérifier l'état candidat exact et l'absence de dérive/délégation,
puis faire approuver le modèle inverse (16 REVOKE ciblés, sans ALL ni CASCADE),
avec le même grantor. Vérifier dans la transaction propriétaire l'absence de
droits B2B du rôle nommé ui47_app par le second bloc du modèle inverse, puis, après commit autorisé,
refaire le contrôle préparatoire complet sous une nouvelle connexion ui47_app.
Si l'état ne correspond pas à la preuve, arrêter pour revue ; ne pas révoquer
aveuglément les droits d'un autre lot et ne pas restaurer la base active pour
annuler des ACL. Aucun enregistrement ni objet du schéma n'est supprimé.
L'inverse restaure les privilèges effectifs, sans garantir la représentation
brute initiale des ACL (par exemple NULL contre une ACL explicite du propriétaire).

### DEV-5B-4D — risque des droits UPDATE : décision avant attribution

Analyse historique : la décision SECURITY DEFINER est maintenant retenue par
DEV-5B-4F. La matrice courante ci-dessus et B2B_LOCKS.md remplacent les propositions
de maintien temporaire des cinq UPDATE ci-dessous ; les risques résiduels demeurent.

Cause du blocage : le propriétaire n'est ni superutilisateur ni autorisé à
prendre le rôle applicatif. Les anciennes instructions de changement de rôle
sont remplacées par les contrôles nommés ci-dessus, sans nouvelle appartenance.
Les scripts restent des modèles terminant par ROLLBACK, sans exécuteur de droits.
Le contrôle SQL `ssl=true` ne prouve pas à lui seul verify-full : le transport
client officiel et la CA approuvée restent des préconditions obligatoires.

Les magasins actuels verrouillent l'utilisateur FOR UPDATE, puis la session
FOR UPDATE et l'identité externe FOR SHARE ; appartenances et permissions sont
prises FOR SHARE et conservées dans la transaction appelante. Le magasin OIDC
consomme une transaction après FOR UPDATE et échantillonne l'horloge après attente.
Ordre des verrous, contrôles après attente et absence de retry restent obligatoires.

| Option | Sécurité interentreprises / mutations | Transactions actuelles | Complexité et qualification |
| --- | --- | --- | --- |
| UPDATE ciblés actuels | Le backend contrôle le tenant, mais le rôle SQL peut réellement modifier les clés ; membership_id peut déplacer une permission vers une autre appartenance compatible. Aucun RLS ne limite les lignes. | Compatibilité directe et verrous conservés. | Faible ; nécessite acceptation explicite du risque. Ce n'est pas une réduction de capacités. |
| Verrous de lignes plus faibles | FOR KEY SHARE n'empêche pas une suspension ou certaines modifications de droits ; tous les modes de verrouillage de ligne exigent encore UPDATE sur une colonne. | FOR NO KEY UPDATE pourrait réduire certaines contentions, pas les privilèges ; KEY SHARE ne préserve pas les garanties générales de révocation. | Tests de concurrence nouveaux pour tout changement ; aucun gain de privilèges. Ne pas changer les magasins pour cette raison. |
| Petites fonctions SECURITY DEFINER de verrouillage | Retire à ui47_app les cinq UPDATE de clés accordés seulement pour verrouiller. Les fonctions ne modifient aucune donnée et verrouillent uniquement des lignes sélectionnées par requêtes fixes. L'autorisation tenant reste vérifiée par le backend ; ce n'est pas un RLS. | Appels sur la même connexion et transaction, sans commit interne ; mêmes ordre, prédicats et contrôles après attente. | Option ciblée recommandée pour réduire ces droits : nouveau lot approuvé, fonctions/owner dédiés, migration nouvelle et qualification PostgreSQL isolée. Aucun objet ajouté ici. |
| Séparation de rôles pour opérations sensibles | Réduit le périmètre d'un composant si l'isolation des processus et secrets est réelle. Deux identifiants dans le même processus compromis ne garantissent pas cette isolation. | Un second moteur/une seconde transaction ne remplace pas les verrous conservés de la transaction métier ; risque de rupture d'atomicité. | Plus élevée : assemblage, secrets, procédures et tests supplémentaires. Garder l'administration/provisioning séparée ; éviter un second rôle pour contourner les verrous. |

Recommandation : ne pas attribuer les UPDATE de clés du candidat actuel sans
acceptation explicite. Pour réellement supprimer ce risque, préparer dans un
lot distinct les seules opérations de lecture verrouillée nécessitant
UPDATE(id) sur local_users/external_identities/company_memberships,
UPDATE(membership_id) et UPDATE(transaction_id), via des fonctions restreintes.
Le candidat actuel reste inchangé et non activable ; ce document ne constitue
pas une approbation de sa matrice pour ouverture réelle.

Conditions impératives des futures fonctions : propriétaire dédié NOLOGIN,
non superutilisateur, distinct du migrateur, sans autorité administrative et
avec droits SQL limités ; objets et signatures qualifiés, search_path sûr
(pg_catalog, schéma de confiance, pg_temp en dernier), aucun SQL dynamique,
aucun identifiant SQL sélectionnable par le client, paramètres strictement
validés. Révoquer EXECUTE à PUBLIC et accorder seulement les signatures prévues
au rôle applicatif dans la transaction de création. Fonctions VOLATILE,
sans commit ni connexion externe ; renvoyer uniquement les données déjà
autorisées à la lecture. Les paramètres identifient des lignes, jamais une
autorisation : conserver les vérifications serveur du sujet, de la session,
de l'entreprise et des permissions, sans retour booléen fourni par le client.

Tests futurs requis : rejet des appels/signatures non autorisés, PUBLIC,
search_path détourné, arguments invalides et appels hors périmètre ; refus des
UPDATE directs de clés sous ui47_app ; identité des lignes et modes de verrous,
attentes à deux connexions, suspension/révocation/relinking, rechargement des
permissions, rollback, expiration après attente et commit incertain. Les
nouveaux objets demanderont leur propre migration et empreintes, sans retoucher
les révisions approuvées ; les magasins ne seront adaptés qu'après validation.

Limites : les fonctions de verrouillage ne retirent pas INSERT/DELETE OIDC,
INSERT de sessions ni UPDATE(last_activity_at,revoked_at,replaced_by), nécessaires
aux opérations existantes. Le rôle conserve donc des capacités sensibles sur
toutes ces lignes ; une compromission SQL peut notamment invalider des sessions
ou lever certaines révocations. Les droits industriels historiques restent aussi
inchangés. Une exigence d'isolation des tenants au niveau SQL demanderait une
conception complémentaire des opérations autorisées ; ces fonctions seules ne
permettent pas de la revendiquer. Ne pas déduire une autorisation métier du domaine email.

Références PostgreSQL 17 :
[privilèges des verrous SELECT](https://www.postgresql.org/docs/17/sql-select.html),
[conflits des verrous](https://www.postgresql.org/docs/17/explicit-locking.html),
[SECURITY DEFINER et précautions](https://www.postgresql.org/docs/17/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY).
Les tests de ce lot utilisent uniquement des doubles et des revues de SQL généré ;
les nouveaux blocs SQL n'ont pas été exécutés ni qualifiés sur PostgreSQL.
Les empreintes des scripts et du plan changent avec ces contrôles : les anciens
hashes de revue DEV-5B-4C ne valident pas ces nouvelles versions. Les empreintes
des migrations et leur politique restent inchangées.

### Assemblage ultérieur et tests

L'unique raccordement prévu reste `app.b2b_runtime.install_google_b2b` avec le
SqlRuntime ui47_app qualifié, configuration OIDC explicite et chargeur de secret
serveur. Ce symbole est seulement documenté dans le plan, jamais importé/appelé
par ce lot. Une prochaine validation devra apporter HTTPS, callback/remise de
session et nouveau mode explicite. Ne pas importer app.main/app.core.database,
monter les CRUD historiques, ouvrir le proxy métier ni changer Angular ici.

Tests ciblés sans réseau, depuis `infra/development` :

```powershell
& '..\..\backend\.venv\Scripts\python.exe' -m unittest test_b2b_activation test_b2b_locks test_manage
```

Ils vérifient les permissions individuellement, les origines PUBLIC/héritage/
délégation, la forme des colonnes publiée, les scripts inverses, les refus CLI,
le rôle applicatif, la conservation des contrôles d'identité/TLS et les deux
seules routes diagnostics du runtime préparatoire. Ils ne qualifient pas une ACL
PostgreSQL réelle ; aucune connexion réelle n'est autorisée dans ces tests.

## AUTH-B2B-DEV-5B-1 — préparation du runtime

Le lanceur officiel attend maintenant exactement `b2b_0002_analyze`, quinze
tables publiques (huit métier, six B2B, Alembic) et onze séquences nommées :
les huit `<table_métier>_id_seq` et `local_users_id_seq`,
`external_identities_id_seq`, `company_memberships_id_seq`. Tous ces objets et
`public` doivent appartenir à `ui47_migrator` ; le rôle applicatif reste `ui47_app`.
Le départ des migrations approuvées demeure `09ac8101e9fe`, sans changement de
politique, de publication ou d'empreinte.

`api` prépare le composant `SqlRuntime` existant sur un moteur unique construit
depuis le profil privé approuvé : `b2b_transport`, CA épinglée par SHA-256,
`verify-full`, paramètres SQL masqués, aucun `PG*` hérité et aucun repli. Le
lanceur n'importe plus l'assemblage historique `app.main` ni son chargement `.env`.
**Seuls GET `/health` et `/__dev/identity` sont montés**, sans documentation API,
CRUD, endpoints Google ou fournisseur B2B. Les écrans métier ne sont pas réactivés.
La connexion Google et la remise d'une session au navigateur restent hors périmètre.

Les contrôles d'identité incluent l'identifiant système réel du cluster,
l'OID/marqueur d'instance et TLS côté serveur. Le rôle applicatif doit pouvoir
lire `pg_control_system()` ; en cas de permission manquante, le contrôle refuse,
sans élargissement de rôle ni GRANT automatique. La configuration privée, la CA
réelle et les ACL SQL n'ont pas été lues ou qualifiées pendant ce lot.

Cette phase conserve le profil industriel historique contrôlé (CRUD sur les huit
tables, USAGE seul sur leurs séquences), sans l'exposer par HTTP. Elle refuse tout
accès applicatif aux six tables B2B et à leurs trois séquences tant qu'un profil
d'activation distinct n'est pas approuvé. Aucun privilège n'est appliqué ici.

Privilèges à qualifier pour une activation ultérieure, **pas à accorder dans ce lot** :

| Objets | Besoins du code existant |
| --- | --- |
| `oidc_transactions` | SELECT, INSERT, DELETE ; UPDATE d'une colonne pour le verrou de consommation |
| `application_sessions` | SELECT, INSERT ; UPDATE limité à `last_activity_at`, `revoked_at`, `replaced_by` ; aucun DELETE |
| `local_users`, `external_identities` | SELECT ; UPDATE minimal de colonne pour les verrous de ligne, sans provisioning |
| `company_memberships`, `membership_permissions` | SELECT ; privilège minimal permettant FOR SHARE, sans gestion implicite des droits |
| `equipments`, `sites` | SELECT et privilège minimal permettant les verrous du runtime ; écritures métier autorisées séparément |
| `alembic_version` | SELECT uniquement |
| Trois séquences B2B | Aucun droit requis par les adaptateurs session/OIDC ; provisioning administratif séparé |

Un UPDATE de colonne permettant un verrou est une véritable capacité d'écriture,
pas un privilège « verrou seulement ». Aucune colonne d'identité/appartenance
n'est déclarée inoffensive ici. Le choix d'un profil acceptable doit être revu
avant de lever le refus de préparation ; pas d'UPDATE global, DDL, rôle propriétaire,
création de rôle/base, BYPASSRLS ou droit de modifier Alembic pour le runtime.

Validation du lot exclusivement sur doubles : 21 tests du gestionnaire (dont
les dix historiques), 19 tests du proxy sans réseau, 39 tests B2B/Alembic hors
connexion réussis. Aucune connexion DEV, lecture de secret privé, migration,
commande Docker, attribution de droit ou connexion Google effectuée.

## Installation B2B préparée — AUTH-B2B-DEV-2

Le gestionnaire dispose d'actions explicites `b2b-preflight`, `b2b-backup`,
`b2b-rehearse` et `b2b-migrate`, décrites avec leurs commandes exactes et conditions
d'arrêt dans le [dossier AUTH-B2B-DEV-2](../../docs/auth-b2b-dev-2.md).
Seule la prévalidation est hors connexion. Les autres actions nécessitent une
confirmation humaine interactive distincte ; la migration exige une sauvegarde
actuelle et une restauration isolée vérifiées. Elles n'ont pas été exécutées dans
ce lot. La cible B2B est exactement `b2b_0002_analyze`, sans P101, sans GRANT.
Ne pas employer la commande historique `migrate` pour B2B. Les gardes runtime et
proxy sont désormais adaptés au seul schéma installé, en mode préparation fermé
décrit ci-dessus ; cela ne constitue pas une activation du runtime Google.

La base locale est `industrial_predict_dev` sur `127.0.0.1:5434`, avec FastAPI sur `8001` et Angular sur `4201`. La phase actuelle limite l'API officielle aux diagnostics. Les ressources PostgreSQL UI 4.7.2 sont réutilisées ; aucun nouveau volume ou compte n'est nécessaire.

Le [rapport de transition](../../docs/ui-4.7.2.1-development-environment.md) décrit les vérifications et les ressources conservées. Ne pas utiliser les anciens lanceurs `infra/ui47/` ou leur configuration privée.

## Démarrer

Depuis `D:\projets\industrial-predict`, avec le Python du backend et Node déjà installés :

```powershell
$devConfig = 'D:\integration\industrial-predict\development\config.json'
& backend/.venv/Scripts/python.exe -B infra/development/manage.py db-start --config $devConfig
& backend/.venv/Scripts/python.exe -B infra/development/manage.py check-db --config $devConfig
```

Arrêter la procédure si une commande échoue. `db-start` démarre uniquement le conteneur existant, avec contrôle du projet, du volume et de sa date de création. Il ne crée ni conteneur ni volume et ne lance aucune migration. Le volume Compose est externe : son absence est une erreur, jamais un signal pour réinitialiser une base.

Dans un terminal dédié, démarrer l'API au premier plan :

```powershell
& backend/.venv/Scripts/python.exe -B infra/development/manage.py api --config D:/integration/industrial-predict/development/config.json
```

Dans un autre terminal, vérifier l'identité et démarrer Angular :

```powershell
& backend/.venv/Scripts/python.exe -B infra/development/manage.py check --config D:/integration/industrial-predict/development/config.json
& backend/.venv/Scripts/python.exe -B infra/development/manage.py frontend --config D:/integration/industrial-predict/development/config.json
```

Ouvrir `http://127.0.0.1:4201`. Avant tout futur essai métier autorisé, vérifier `http://127.0.0.1:4201/__dev/identity` : base `industrial_predict_dev`, rôle `ui47_app`, mode `local-development`, instance conforme à la configuration privée et révision attendue. En cas d'écart, ne pas soumettre de formulaire.

Le proxy utilise exclusivement `127.0.0.1:8001`, vérifie l'identité avant chaque transfert et renvoie 503 en cas d'échec. Il ne possède aucune cible sur 8000. L'API vérifie aussi sa cible SQL avant chaque requête. Les ports occupés et configurations manquantes ou incorrectes provoquent un échec, sans sélection automatique d'un autre port ou environnement.

## Arrêter

Utiliser Ctrl+C dans les terminaux Angular puis FastAPI, puis :

```powershell
& backend/.venv/Scripts/python.exe -B infra/development/manage.py db-stop --config D:/integration/industrial-predict/development/config.json
```

Cette commande arrête seulement le conteneur dédié ; elle conserve le volume. Ne pas utiliser `down -v`, supprimer un volume ou réinitialiser PostgreSQL pour résoudre une erreur de connexion. Une recréation technique est une opération de maintenance explicite, pas une action du démarrage courant.

## Configuration et droits

- Secrets distincts dans `D:\integration\industrial-predict\development`, hors Git, sous ACL Windows restreintes. Ne pas afficher les fichiers de mots de passe ou les URL complètes de connexion.
- Compte API `ui47_app` non superutilisateur : CRUD sur les tables métier, USAGE des séquences et lecture d'Alembic. Aucun DDL ni modification d'Alembic.
- Compte `ui47_migrator` réservé aux migrations explicites, avec droits DDL dans `public`, sans superutilisateur.
- Compte `ui47_admin` conservé pour la maintenance du seul cluster dédié. Le moteur FastAPI utilise le compte applicatif.
- PostgreSQL 17.10 épinglé par digest, boucle locale uniquement, volume persistant conservé.
- Révision runtime attendue : `b2b_0002_analyze`. Le départ historique des migrations reste `09ac8101e9fe`. Toute évolution des migrations et droits des nouveaux objets nécessite une mise à jour explicite validée. Aucun lancement courant n'applique de migration.
- Les compteurs de tables peuvent évoluer lors de futurs essais autorisés ; leur vacuité n'est pas un prérequis permanent du lanceur.

Les services historiques 5433/8000/4200, la base `industrial_predict`, PETROSEN et la restauration UI 4.7.1 sont conservés. Ils ne constituent pas la cible des commandes ci-dessus. Les environnements `industrial_predict_test`, `industrial_predict_demo` et `industrial_predict_prod` ne sont pas créés par cet outillage. Ce dispositif local ne démontre pas une autorisation SaaS multi-entreprises.

## Tests de configuration

```powershell
& backend/.venv/Scripts/python.exe -B -m unittest discover -s infra/development -p test_manage.py -v
node --test infra/development/angular-proxy.test.cjs
git diff --check
```

Ces tests utilisent des fixtures et des requêtes simulées, sans écriture HTTP métier. Les tests d'identité effectifs passent par `check-db`, `check` et les GET de diagnostic.

## Jeu fictif reproductible

Le [jeu de données versionné](../../docs/ui-4.7.3-development-data.md) couvre Companies, Sites, équipements, capteurs, mesures et maintenances. Il est réservé à `industrial_predict_dev`, avec contrôle des identités PostgreSQL, FastAPI et Angular avant toute insertion.

```powershell
& backend/.venv/Scripts/python.exe -B infra/development/seed.py check --config D:/integration/industrial-predict/development/config.json
& backend/.venv/Scripts/python.exe -B infra/development/seed.py apply --config D:/integration/industrial-predict/development/config.json
```

La première application exige huit tables vides. Une application sur le jeu complet inchangé ne crée aucun doublon et n'écrit aucune ligne. Les conflits, modifications du jeu ou chargements partiels sont refusés. Aucun reset, écrasement ou suppression automatique. Les nouvelles suppressions nécessitent une autorisation distincte.

Tests du seed exclusivement en mémoire :

```powershell
& backend/.venv/Scripts/python.exe -B -m unittest discover -s infra/development -p test_seed.py -v
```
