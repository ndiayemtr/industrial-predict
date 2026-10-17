# UI 4.7.2 - Environnement PostgreSQL d'intégration isolé

> Rapport historique UI 4.7.2. La transition vers `industrial_predict_dev` est exécutée en UI 4.7.2.1. Les anciennes commandes UI47 ci-dessous sont obsolètes ; utiliser le [guide permanent](../infra/development/README.md) et le [rapport d'exécution](ui-4.7.2.1-development-environment.md).

Vérification effectuée le 17 octobre 2026 sur `feature/frontend-sites`, HEAD `e8702b0`.
UI 4.7.3 n'est pas commencée. Aucun scénario métier de création, modification ou suppression n'a été exécuté.

## Ressources créées

| Ressource | Valeur constatée |
| --- | --- |
| Projet Compose | `industrial-predict-ui47` |
| Conteneur | `industrial-predict-postgres-ui47` |
| Volume dédié | `industrial-predict-postgres-ui47-data` |
| Réseau dédié | `industrial-predict-ui47_default` |
| Base | `industrial_predict_ui47` |
| PostgreSQL | `17.10 (Debian 17.10-1.pgdg13+1)` |
| Publication PostgreSQL | `127.0.0.1:5434` vers le port conteneur `5432` |
| FastAPI distinct | `http://127.0.0.1:8001` |
| Angular distinct | `http://127.0.0.1:4201` |
| Révision Alembic | `09ac8101e9fe` |
| Identifiant système du nouveau cluster | `7697614558579179559` |

L'image PostgreSQL déjà disponible localement a été utilisée avec `--pull never`, épinglée par digest :

```text
postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317
```

Les ports `5434`, `8001` et `4201` étaient libres avant création. L'espace disponible vérifié était supérieur à 100 Go sur C: et D:. Aucun nouveau port n'est publié sur toutes les interfaces. Le réseau et le volume UI47 sont distincts des ressources existantes. Le conteneur n'a pas de politique de redémarrage automatique.

## Bases et services protégés

Le conteneur `industrial-predict-postgres`, son volume `industrial-predict_postgres_data` et son port `5433` n'ont été ni modifiés ni redémarrés. Son identifiant de conteneur et son instant de démarrage sont identiques avant et après l'opération.

Les deux bases suivantes ont été examinées uniquement par des transactions `REPEATABLE READ READ ONLY` :

- `industrial_predict` ;
- `industrial_predict_restore_ui471_20261017t121921z`.

Pour chacune, les empreintes des lignes des neuf tables, les compteurs, les colonnes, les contraintes, les index, les séquences et leurs valeurs, les références métier et la révision Alembic sont identiques avant et après. PETROSEN et le site `id=3` sont conservés, y compris son code `DEMO-SITE-001 (inchangé)`.

Le cluster existant conserve son identifiant `7673083456081215526`, différent du cluster UI47. Aucune archive UI 4.7.1 ni base temporaire n'a été supprimée ou restaurée dans UI47. L'API habituelle sur `8000`, Angular sur `4200` et le fichier `backend/.env` sont inchangés.

## Comptes, secrets et privilèges

Trois secrets distincts ont été générés, sans les afficher. Ils restent hors Git dans `D:\integration\industrial-predict\ui47`, avec héritage ACL Windows désactivé et accès limité à l'utilisateur courant, SYSTEM et Administrateurs.

Ce répertoire contient `config.json`, `compose.env` et les fichiers `admin-password.txt`, `migrator-password.txt`, `app-password.txt`. Aucune chaîne de connexion ni aucun mot de passe n'est conservé dans le dépôt. Compose monte uniquement le secret d'administration sous forme de fichier ; les autres secrets sont lus par les lanceurs locaux.

| Compte | Usage et droits constatés |
| --- | --- |
| `ui47_admin` | Administration du nouveau cluster, superutilisateur créé par l'image PostgreSQL ; jamais utilisé par le moteur SQL de FastAPI. |
| `ui47_migrator` | Connexion à la nouvelle base, propriétaire du schéma `public` et des objets migrés ; DDL réservé aux migrations. Aucun droit superutilisateur, création de base/rôle, réplication ou contournement RLS. |
| `ui47_app` | Connexion, usage du schéma, SELECT/INSERT/UPDATE/DELETE sur les huit tables métier, USAGE sur les huit séquences, SELECT seul sur `alembic_version`. |

Le compte applicatif n'a aucun droit superutilisateur, création de base/rôle, réplication, contournement RLS, création dans `public`, table temporaire, TRUNCATE, TRIGGER, REFERENCES, modification d'Alembic ou propriété de table. Il n'appartient à aucun autre rôle. Il ne possède ni SELECT ni UPDATE sur les séquences. Les droits PUBLIC sur la base et le schéma ont été révoqués uniquement dans UI47.

Les privilèges ont été vérifiés dans les catalogues, sans exécuter de DML métier ni appeler `nextval`. Les secrets et les rôles sont séparés pour le développement local ; ce dispositif ne constitue pas une autorisation SaaS multi-entreprises et n'isole pas les processus d'un même utilisateur Windows entre eux.

## Migrations et état initial

Les neuf migrations existantes ont été exécutées, depuis une base sans table publique jusqu'à `09ac8101e9fe`, avec le compte de migration. Les droits du compte applicatif ont été accordés après les migrations.

Le résultat comprend neuf tables publiques, dont `alembic_version`, 18 contraintes, 41 index et huit séquences. Les colonnes, contraintes et index correspondent au manifeste du schéma de développement validé. Les huit séquences sont à `last_value=1`, `is_called=false`.

| Table métier | Nombre de lignes |
| --- | ---: |
| companies | 0 |
| sites | 0 |
| equipments | 0 |
| sensors | 0 |
| measurements | 0 |
| maintenance_records | 0 |
| prediction_records | 0 |
| maintenance_recommendations | 0 |

Aucune donnée PETROSEN n'a été copiée. Seule la table technique Alembic contient la révision attendue.

## FastAPI et refus de cible incorrecte

Le lanceur [manage.py](../infra/development/manage.py) exige un `--config` explicite hors du dépôt. Il refuse notamment les ports habituels, l'ancien nom de base, l'ancien cluster, un marqueur absent et des secrets absents ou mal formés. Il affecte `DATABASE_URL` explicitement avant tout import des paramètres et du moteur SQL existants. Une comparaison vérifie que le moteur chargé possède exactement l'URL attendue ; aucun repli vers `backend/.env` n'est prévu.

Le processus API utilise exclusivement `ui47_app` sur `127.0.0.1:5434/industrial_predict_ui47`, sans rechargement automatique, lié à `127.0.0.1:8001`. Le wrapper ajoute uniquement dans ce processus une route de diagnostic GET `/__ui47/identity` et un contrôle SQL avant chaque requête. Les fichiers applicatifs et les contrats API métier ne sont pas modifiés.

Cette route lit l'identité via le moteur effectif de l'application : base, rôle, version PostgreSQL, nom du cluster, marqueur d'instance configuré dans la nouvelle base, révision et attributs de rôle. Son PID de connexion a été retrouvé dans `pg_stat_activity` du nouveau cluster, sous `ui47_app` dans `industrial_predict_ui47`. L'identifiant système a été vérifié séparément avec l'identité d'administration ; aucun droit supplémentaire de lecture des fonctions d'administration n'a été accordé au compte API.

Un contrôle d'identité en échec renvoie 503 avant le gestionnaire métier. L'en-tête `X-Industrial-Predict-Environment: ui47-integration` accompagne les réponses acceptées.

## Angular et vérification avant les essais

Le démarrage habituel, `angular.json`, le proxy habituel et le préfixe relatif `/api/v1` restent inchangés. La commande distincte utilise uniquement la configuration Angular `development`, le port `4201` et [angular-proxy.cjs](../infra/development/angular-proxy.cjs).

Ce proxy a une cible fixe `127.0.0.1:8001`, sans cible `8000`. Avant chaque transfert de `/api/v1/**` et `/__ui47/**`, il effectue un GET d'identité sans cache, avec délai maximal de deux secondes et refus des redirections. Base, instance, rôle, migration et en-tête doivent correspondre. Un échec termine la réponse en 503 sans transfert. Le chemin d'arrêt a été vérifié avec le comportement `bypass` de la version Vite installée.

Avant chaque futur essai CRUD, lancer `check`, puis vérifier dans le navigateur l'URL `http://127.0.0.1:4201/__ui47/identity` et utiliser exclusivement `http://127.0.0.1:4201`. La base doit être `industrial_predict_ui47`, le rôle `ui47_app`, la révision `09ac8101e9fe` et le marqueur d'instance doit correspondre à `config.json`. En cas d'écart, ne pas soumettre le formulaire.

Le serveur de simulation UI 4.6.2 est conservé sans modification. Ce lancement UI47 correspond à une vraie API sur une base vide dédiée, et non à une simulation. Aucun test CRUD réel n'est autorisé par cette étape.

## Commandes de démarrage et d'arrêt

Depuis `D:\projets\industrial-predict`, utiliser le Python du backend déjà installé. Les ressources et identités ont été initialisées pendant UI 4.7.2 ; les commandes suivantes servent au redémarrage de cet environnement existant. Elles ne recréent pas les secrets ou les rôles en cas de perte du volume.

```powershell
$ui47Config = 'D:\integration\industrial-predict\ui47\config.json'
& backend/.venv/Scripts/python.exe -B infra/ui47/manage.py db-start --config $ui47Config
& backend/.venv/Scripts/python.exe -B infra/ui47/manage.py check-db --config $ui47Config
```

Dans un terminal dédié, lancer l'API au premier plan :

```powershell
& backend/.venv/Scripts/python.exe -B infra/ui47/manage.py api --config D:/integration/industrial-predict/ui47/config.json
```

Dans un second terminal, vérifier la cible puis lancer Angular au premier plan :

```powershell
& backend/.venv/Scripts/python.exe -B infra/ui47/manage.py check --config D:/integration/industrial-predict/ui47/config.json
& backend/.venv/Scripts/python.exe -B infra/ui47/manage.py frontend --config D:/integration/industrial-predict/ui47/config.json
```

En cas de contrôle en échec, interrompre la procédure. Un port occupé bloque le démarrage ; aucun port alternatif n'est accepté automatiquement. `db-start` et `db-stop` vérifient le projet, le volume et la publication du conteneur avant de le gérer.

Pour arrêter, utiliser Ctrl+C dans les terminaux Angular puis API, puis :

```powershell
& backend/.venv/Scripts/python.exe -B infra/ui47/manage.py db-stop --config D:/integration/industrial-predict/ui47/config.json
```

Cette commande arrête uniquement le service UI47. Ne pas utiliser `down -v`, supprimer un volume, modifier les secrets ou réexécuter une initialisation sans validation. La commande `migrate` utilise l'identité distincte de migration et la révision fixe ; elle a déjà été exécutée et n'est pas nécessaire au lancement courant.

## Validations exécutées

- Huit tests Python du lanceur réussis : configuration explicite, refus de champs absents, cibles protégées, secrets invalides, collisions de ressources et identités SQL incohérentes.
- Dix tests Node du proxy réussis : configuration absente, base/port incorrects, identité valide, contrôle par requête, erreurs HTTP, API indisponible, migration, rôle et marqueur incorrects. Les objets POST de ces tests sont entièrement simulés ; aucun POST HTTP n'a été envoyé.
- Compilation Angular de développement réussie avec le lancement séparé, puis GET de `/sites/new` en 200. Les tailles affichées par cette compilation de développement ne constituent pas une mesure du bundle de production.
- GET FastAPI `/health` et `/__ui47/identity` en 200 ; GET Companies et Sites via Angular en 200, listes vides.
- API UI47 arrêtée de manière contrôlée : GET Sites via Angular en 503 ; API habituelle sur 8000 toujours en 200. Après redémarrage UI47, identité et lectures de nouveau valides.
- CLI sans configuration ou avec base/ports protégés : code de sortie 2, avant connexion à cette cible.
- Comparaison intégrale des deux bases protégées et de la configuration backend : inchangées. Les 22 fichiers de travail UI 4.6/UI 4.6.2 préexistants conservent leurs empreintes.
- `git diff --check`, contrôle des nouveaux fichiers et liens internes du présent rapport : réussis.

Les premiers essais des tests Python ont révélé un défaut de fixture Docker, corrigé, ainsi qu'une restriction d'accès au répertoire temporaire du bac à sable Windows. L'exécution finale avec accès au répertoire temporaire passe les huit tests. Aucun défaut n'a nécessité une modification du backend.

Les suites applicatives Angular/backend et le build de production n'ont pas été relancés pour cette étape d'infrastructure ; aucun résultat historique ne leur est attribué. Aucun code applicatif, dépendance ou budget n'a été modifié. Les validations de CRUD réel et de suppressions en cascade restent hors périmètre.

Les preuves détaillées sont conservées hors Git dans le répertoire privé : manifestes avant/après des deux bases, structure UI47, vérifications HTTP, coupure du proxy, refus CLI, état Git et `final-verification.json`. Ce répertoire contient aussi des secrets : ne pas le publier en bloc.

## État final et fichiers

Les trois services UI47 sont démarrés à l'issue de la vérification. Les ressources existantes restent en fonctionnement. Aucun commit, push ou merge n'a été réalisé. La branche et le HEAD sont inchangés et l'index Git est vide.

Six fichiers sont ajoutés par UI 4.7.2 :

- [compose.yaml](../infra/development/compose.yaml) ;
- [manage.py](../infra/development/manage.py) ;
- [test_manage.py](../infra/development/test_manage.py) ;
- [angular-proxy.cjs](../infra/development/angular-proxy.cjs) ;
- [angular-proxy.test.cjs](../infra/development/angular-proxy.test.cjs) ;
- le présent rapport.

Les changements préexistants de README_AI, project-status, roadmap et des fichiers UI 4.6/UI 4.6.2 sont préservés. Validation attendue avant UI 4.7.3.
