# Environnement permanent de développement

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
