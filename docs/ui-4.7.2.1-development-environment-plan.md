# UI 4.7.2.1 - Plan de pérennisation du développement

Statut : plan approuvé et exécuté après autorisation explicite. Voir le [rapport d'exécution](ui-4.7.2.1-development-environment.md) et le [guide permanent](../infra/development/README.md). Le contenu ci-dessous conserve les constats et la procédure prévus avant exécution.

Constats du 17 octobre 2026 sur `feature/frontend-sites`, HEAD `e8702b0`. Les 28 fichiers de travail préexistants sont conservés à l'identique. Aucun commit, push ou merge.

## Motif de l'arrêt avant adaptation

La demande impose : « Si le changement de nom implique une interruption de service ou une opération destructive, arrêter et présenter le plan avant exécution. »

FastAPI et Angular sont actifs sur 8001 et 4201. Une session `ui47_app` inactive est conservée par le pool FastAPI dans `industrial_predict_ui47`. Le renommage nécessite de fermer ces connexions et de relancer l'API avec la nouvelle cible. Aucun arrêt, renommage ou changement de configuration n'a été effectué pendant cette analyse.

La [documentation PostgreSQL 17](https://www.postgresql.org/docs/17/sql-alterdatabase.html) prévoit le renommage avec une identité autorisée, connectée à une autre base. L'identité d'administration dédiée existante suffit ; aucun nouveau compte privilégié n'est nécessaire.

## Vérifications effectuées en lecture seule

| Élément | Résultat actuel |
| --- | --- |
| Conteneur | `industrial-predict-postgres-ui47`, sain et actif |
| Volume | `industrial-predict-postgres-ui47-data`, montage vérifié |
| PostgreSQL | 17.10, publication `127.0.0.1:5434` uniquement |
| Cluster dédié | `7697614558579179559` |
| Base actuelle | `industrial_predict_ui47`, OID `16384` dans ce cluster |
| Base cible | `industrial_predict_dev` absente de ce cluster |
| Alembic | `09ac8101e9fe` |
| Tables métier | Huit tables, toutes à zéro ligne |
| API effective | Connexion à `industrial_predict_ui47` avec `ui47_app` |
| Droits API | CRUD métier et USAGE des séquences ; aucun superutilisateur, DDL ou droit de modification d'Alembic |
| Tests relancés | Huit tests Python et dix tests Node réussis |

Les tables vides sont `companies`, `sites`, `equipments`, `sensors`, `measurements`, `maintenance_records`, `prediction_records` et `maintenance_recommendations`.

Les manifestes des bases `industrial_predict` et `industrial_predict_restore_ui471_20261017t121921z` ont été recalculés dans des transactions `REPEATABLE READ READ ONLY`. Identités, lignes, compteurs, colonnes, contraintes, index, séquences et références métier correspondent aux relevés de fin UI 4.7.2. PETROSEN et le site `id=3` sont inchangés. Aucun secret n'a été affiché.

## Inventaire des références à adapter

La recherche dans les fichiers non ignorés du dépôt retrouve les appellations UI47 dans cinq fichiers opérationnels sous `infra/ui47/` et dans le [rapport historique UI 4.7.2](ui-4.7.2-integration-environment.md).

| Fichier | Références concernées |
| --- | --- |
| [compose.yaml](../infra/development/compose.yaml) | Projet, service, conteneur, volume, nom de base, rôle d'administration, secret, variables privées, cluster et healthcheck |
| [manage.py](../infra/development/manage.py) | Cible imposée, rôles, paramètre SQL d'instance, mode, chemin de configuration, contrôles Docker, route d'identité, messages et lancement Angular |
| [angular-proxy.cjs](../infra/development/angular-proxy.cjs) | Variable de configuration, base attendue, mode, route d'identité, rôle et messages |
| [test_manage.py](../infra/development/test_manage.py) | Fixtures des cibles, rôles et identités |
| [angular-proxy.test.cjs](../infra/development/angular-proxy.test.cjs) | Configuration, marqueurs, chemins et fixtures |

Hors Git, `config.json` et `compose.env` contiennent les paramètres opérationnels. Le répertoire privé et plusieurs fichiers de preuve portent aussi des appellations UI47. Les preuves historiques ne doivent pas être réécrites ou publiées avec les secrets.

Les noms physiques de ressources et de rôles peuvent rester historiques, en étant déclarés explicitement dans la configuration durable. Il faut éviter un remplacement global qui changerait involontairement le projet Compose, le volume, les privilèges ou les preuves validées.

## Architecture cible proposée

| Élément | Cible après validation |
| --- | --- |
| Base de développement de tous les modules | `industrial_predict_dev` |
| Ports locaux | 5434 pour PostgreSQL, 8001 pour FastAPI, 4201 pour Angular |
| Données et stockage | Même cluster et même volume persistant |
| Conteneur | Même nom `industrial-predict-postgres-ui47` ; éventuelle recréation technique décrite ci-dessous |
| Projet/service Compose | Identités historiques conservées pour gérer le service existant |
| Rôles | `ui47_admin`, `ui47_migrator`, `ui47_app`, secrets et privilèges conservés |
| Outillage générique | `infra/development/` |
| Configuration privée de lancement | `D:\integration\industrial-predict\development\config.json` |
| Mode et variable de lancement | `local-development`, `INDUSTRIAL_PREDICT_DEV_CONFIG` |
| Diagnostic local proposé | `/__dev/identity`, avec contrôle de cible avant requête |

Les noms `industrial_predict_test`, `industrial_predict_demo` et `industrial_predict_prod` sont réservés à des travaux ultérieurs ; aucune de ces bases ne sera créée ici.

Le moteur FastAPI recevra explicitement la nouvelle URL avant tout import des paramètres. La configuration de développement devra refuser la base historique et les ports habituels. Angular conservera le préfixe relatif `/api/v1`, une cible fixe sur 8001 et le blocage en cas d'identité incorrecte. Aucun contrat métier ni fichier applicatif n'a besoin d'être modifié pour cette adaptation.

La révision attendue restera explicitement `09ac8101e9fe` pour cette validation. Son évolution future devra suivre une migration validée, avec le compte distinct de migration ; le lancement courant ne devra pas appliquer automatiquement des migrations. Le compteur de lignes ne sera pas une condition de démarrage permanente : la vacuité est un prérequis de cette transition, puis des données fictives seront possibles après validation ultérieure.

## Point Docker nécessitant une décision

Le healthcheck actuel contient littéralement `pg_isready -U ui47_admin -d industrial_predict_ui47`. Après renommage, il ne vérifierait plus la bonne cible. `pg_isready` peut même annoncer un serveur disponible avec un nom de base erroné, en journalisant l'échec de connexion : voir la [documentation PostgreSQL](https://www.postgresql.org/docs/17/app-pg-isready.html).

Le Docker installé ne propose pas de modification du healthcheck avec `docker container update` ; cela correspond aux [options documentées](https://docs.docker.com/reference/cli/docker/container/update/). Modifier le fichier Compose seul ne modifie pas ce paramètre du conteneur en cours.

Recommandation soumise à validation : remplacer techniquement le seul conteneur dédié, sous le même nom, avec la même image épinglée et le même volume existant, afin d'actualiser le healthcheck, `POSTGRES_DB` et le libellé du cluster. L'identifiant Docker du conteneur changerait ; l'identifiant PostgreSQL du cluster et le stockage devraient rester identiques. Aucun deuxième environnement ni volume ne serait créé. Il ne s'agit donc pas d'une conservation stricte de l'objet conteneur actuel, et ce remplacement n'est pas considéré comme autorisé à ce stade.

Sans cette autorisation, le renommage seul reste envisageable après arrêt des clients, mais laisserait un healthcheck obsolète. Cette variante n'est pas recommandée pour l'environnement permanent. Aucune modification interne du binaire de contrôle, création de base factice ou désactivation silencieuse du contrôle n'est proposée.

## Procédure proposée, non exécutée

1. Préparer les fichiers génériques et leurs tests, sans les utiliser avant la fenêtre de transition. Préserver les empreintes des travaux UI 4.6/UI 4.6.2 et les preuves UI 4.7.2. Conserver les identités physiques Compose existantes.
2. Revalider le cluster, le volume, la vacuité des huit tables et l'absence de `industrial_predict_dev`. Sauvegarder la structure UI47 et ses paramètres hors Git avec les outils PostgreSQL 17.10, sans toucher aux sauvegardes historiques.
3. Arrêter uniquement Angular 4201 puis FastAPI 8001 par les processus identifiés. Ne pas arrêter les services 4200, 8000 ou le conteneur historique. Vérifier qu'il ne reste aucune connexion à la base UI47. En présence d'une session inattendue, arrêter la procédure plutôt que la terminer de force.
4. Depuis la base de maintenance `postgres` du cluster sur 5434, avec l'identité d'administration dédiée, effectuer uniquement le renommage suivant après nouvelle vérification d'identité :

   ```sql
   ALTER DATABASE industrial_predict_ui47 RENAME TO industrial_predict_dev;
   ```

5. Vérifier que l'OID de la base, ses objets, propriétaires, ACL, séquences et la révision n'ont pas changé. Adapter le marqueur d'instance SQL au nom générique, en conservant sa valeur. Ne réappliquer ni données ni migrations.
6. Préparer la configuration privée générique avec les mêmes secrets, sous ACL restreintes. Conserver le répertoire de preuves et la configuration précédente pour le retour arrière ; aucune suppression automatique. Actualiser les gardes de cible, les messages, le diagnostic et le proxy.
7. Si le remplacement technique est approuvé, arrêter et recréer uniquement le service dédié via son identité Compose existante, en réattachant exclusivement le volume identifié. Vérifier le montage et la publication avant démarrage. Le volume doit déjà exister ; aucune initialisation d'un volume vide, aucun `down -v`, aucun téléchargement ou changement de version PostgreSQL.
8. Recontrôler le même identifiant système PostgreSQL, la base renommée, les huit tables vides, la révision et les droits minimaux. Redémarrer FastAPI puis Angular avec les lanceurs génériques. Corréler l'identité HTTP et la session SQL effective.
9. Tester les refus de configuration, l'absence de repli et une coupure contrôlée de la seule API de développement. Exécuter les tests de configuration et les contrôles Git. Recalculer les manifestes des deux bases protégées et les empreintes des travaux préexistants.

Aucune opération CRUD métier, import PETROSEN, création de rôle ou base supplémentaire n'est incluse dans ce plan.

## Commandes durables envisagées

Ces commandes sont une proposition. Les fichiers génériques n'existent pas encore et ne doivent pas être utilisés avant adaptation validée.

```powershell
$devConfig = 'D:\integration\industrial-predict\development\config.json'
& backend/.venv/Scripts/python.exe -B infra/development/manage.py db-start --config $devConfig
& backend/.venv/Scripts/python.exe -B infra/development/manage.py check-db --config $devConfig
```

Dans deux terminaux dédiés, avec le même chemin explicite de configuration : `api`, puis `check` et `frontend`. Pour l'arrêt : Ctrl+C dans Angular puis FastAPI, puis `db-stop`. Les commandes devront conserver les gardes de projet, volume, port et identité ; elles ne devront jamais choisir automatiquement la configuration historique.

## Retour arrière et critères de réussite

Avant réouverture des services, un échec entraîne l'arrêt de la transition. Après fermeture des seules connexions dédiées, le renommage inverse est possible depuis `postgres`. La configuration et, si nécessaire, le conteneur antérieurs pourront être rétablis sur le même volume. Aucun volume ni base ne sera supprimé ; aucune restauration écrasante n'est prévue. Une identité ambiguë impose un arrêt pour validation.

La transition sera terminée uniquement après preuve que FastAPI et Angular utilisent `industrial_predict_dev`, que les tables sont toujours vides, les privilèges inchangés, le healthcheck cohérent, le cluster et le volume conservés, le repli impossible et les deux bases historiques inchangées. Les tests de l'architecture cible ne sont pas encore exécutés ; les 18 tests réussis pendant cette analyse concernent la configuration UI47 actuelle.

## État de livraison de ce plan

Seul ce document est ajouté pendant cette analyse. Les cinq fichiers d'outillage UI47, les configurations privées et les 28 fichiers préexistants ne sont pas modifiés. Les services UI47 restent actifs. `git diff --check`, les liens internes et les tirets simples sont contrôlés avant remise.

L'interruption dédiée et le remplacement technique ont été explicitement autorisés puis exécutés. Les scénarios CRUD UI 4.7.3 restent soumis à une validation distincte.
