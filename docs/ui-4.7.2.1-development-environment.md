# UI 4.7.2.1 - Environnement permanent de développement

Transition exécutée le 17 octobre 2026 après autorisation explicite du [plan](ui-4.7.2.1-development-environment-plan.md), sur `feature/frontend-sites`, HEAD `e8702b0`. Aucun commit, push ou merge. Aucun scénario CRUD métier ni travail UI 4.7.3.

## Architecture effective

| Élément | Valeur vérifiée |
| --- | --- |
| Base permanente, tous modules | `industrial_predict_dev` |
| PostgreSQL | 17.10, publication `127.0.0.1:5434` uniquement |
| Conteneur dédié | `industrial-predict-postgres-ui47`, recréé sous le même nom, sain |
| Volume | `industrial-predict-postgres-ui47-data`, intégralement conservé |
| Projet et service Compose | `industrial-predict-ui47` / `postgres-ui47`, identités conservées |
| Réseau existant | `industrial-predict-ui47_default` |
| Cluster PostgreSQL | `7697614558579179559`, inchangé |
| OID de la base dans ce cluster | `16384`, inchangé |
| FastAPI | `http://127.0.0.1:8001`, mode `local-development` |
| Angular | `http://127.0.0.1:4201` |
| Alembic | `09ac8101e9fe`, aucune migration réexécutée |

Le [guide permanent](../infra/development/README.md) contient les commandes de démarrage, de contrôle et d'arrêt. L'outillage est désormais dans `infra/development/`, utilisable indépendamment du module Sites.

Les noms Docker et les noms de rôles historiques sont conservés pour réutiliser les ressources et leurs droits. Les bases de tests automatisés, démonstration et production ne sont pas créées. La base historique `industrial_predict` n'est pas la cible de développement de ces lanceurs.

## Déroulement et conservation

Avant l'interruption, les huit tables métier étaient vides. Les identités Docker/PostgreSQL, le contenu des bases protégées, les ACL, propriétaires, rôles, objets, séquences et fichiers de travail ont été relevés. Une sauvegarde logique complète de la seule base isolée a été réalisée avec `pg_dump` 17.10 au format personnalisé, puis contrôlée avec `pg_restore --list`.

```text
D:\integration\industrial-predict\development\evidence\development-before-rename.dump
40529 octets
SHA-256 : 2c9f7340b2b7e18763c8158c2e4e66542c2702aa69311a9776c9d90ae7da99b8
```

Cette archive est conservée ; elle n'a pas été restaurée dans les bases existantes. Les sauvegardes UI 4.7.1 restent intactes.

Seuls les processus Angular 4201 et FastAPI 8001 identifiés ont été arrêtés. Après vérification de l'absence de session restante, la base isolée a été renommée depuis la base de maintenance `postgres` du cluster dédié. Aucun DROP, création de base ou import métier n'a été exécuté. Le marqueur d'instance a été conservé sous le paramètre générique `app.development_instance_id`.

Le seul conteneur dédié a ensuite été recréé, avec la même image épinglée et le volume externe existant. Son identifiant Docker a changé ; l'identifiant système PostgreSQL, l'OID de la base, les métadonnées du volume, les objets, les rôles, les ACL et les séquences sont inchangés.

L'image est conservée sans téléchargement :

```text
postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317
```

Le healthcheck cible désormais `industrial_predict_dev`. `POSTGRES_DB` et le libellé du cluster ont été actualisés dans le conteneur dédié. Aucun conteneur historique n'a été redémarré et aucun volume n'a été supprimé ou créé pendant la transition.

## Comptes et secrets

Les trois comptes et les valeurs de leurs secrets sont conservés :

- `ui47_app` : CRUD sur les huit tables métier, USAGE seul sur les huit séquences, usage du schéma et lecture seule d'Alembic ; aucun superutilisateur, DDL, création de base/rôle, table temporaire, TRUNCATE, TRIGGER, REFERENCES, réplication, contournement RLS ou appartenance à un autre rôle.
- `ui47_migrator` : identité distincte pour les migrations, propriétaire des objets et du schéma, sans superutilisateur. Une connexion effective avec son secret conservé a été vérifiée.
- `ui47_admin` : administration du cluster dédié ; le moteur applicatif FastAPI utilise exclusivement `ui47_app`.

La configuration permanente et les copies identiques des secrets se trouvent dans `D:\integration\industrial-predict\development`, hors Git, sous ACL Windows restreintes. La configuration et les preuves privées UI47 antérieures sont conservées pour traçabilité et retour arrière. Aucun mot de passe ou chaîne complète de connexion n'est publié.

## Connexions et absence de repli

Le lanceur exige une configuration explicite hors Git. Il impose la base de développement, les ports locaux, l'OID attendu, un marqueur d'instance et un cluster distinct de l'historique. `DATABASE_URL` est affectée avant l'import des paramètres et du moteur applicatif ; le moteur chargé est comparé à cette cible. Aucun contrat métier ou fichier backend n'est modifié.

La route locale GET `/__dev/identity` interroge le moteur effectif. Après redémarrage, elle indique `industrial_predict_dev`, `ui47_app`, l'instance attendue et `09ac8101e9fe`. Le PID SQL renvoyé a été corrélé avec `pg_stat_activity` du cluster dédié. Le même diagnostic via Angular confirme le parcours `4201 -> 8001 -> 5434 -> industrial_predict_dev`.

Le proxy conserve une cible fixe `127.0.0.1:8001`. Il vérifie l'identité avant chaque transfert, refuse les redirections et termine en 503 si le contrôle échoue. L'API vérifie également sa cible SQL avant chaque requête. La variable de lancement est désormais `INDUSTRIAL_PREDICT_DEV_CONFIG` ; les modes, messages et chemins de diagnostic sont génériques.

Le démarrage courant utilise `compose start`, avec contrôle préalable du volume et de sa date de création. Il ne recrée aucune ressource et n'initialise aucune base vide. Le volume est déclaré externe. La commande de migration reste distincte et explicite, sans exécution au démarrage.

## Résultats des vérifications

- PostgreSQL sain après recréation ; nom cible du healthcheck vérifié dans la configuration effective du conteneur.
- Métadonnées du volume, image, cluster, OID, objets, propriétaires, ACL, rôles et séquences comparés avant/après : conservés.
- Neuf tables publiques, 18 contraintes, 41 index et huit séquences conservés. Les huit tables métier ont toujours zéro ligne ; aucune donnée PETROSEN n'a été copiée.
- GET des diagnostics direct et via Angular, santé API, listes Companies/Sites et page `/sites/new` : 200. Listes métier vides. Aucun POST, PATCH ou DELETE HTTP envoyé.
- API dédiée arrêtée de manière contrôlée : GET Sites via Angular en 503, alors que l'API historique 8000 répond toujours en 200. Après redémarrage, le diagnostic et les lectures via Angular fonctionnent à nouveau.
- CLI sans configuration, avec cible historique ou ancienne configuration UI47 : sortie 2, sans repli.
- Dix tests Python du lanceur et dix tests Node du proxy réussis. Les fixtures POST sont simulées, sans requête métier réelle. Les contrôles couvrent notamment le refus des identités incohérentes et l'interdiction de provisionner ou recréer depuis `db-start`.
- Configuration Compose résolue vérifiée : un seul service, volume existant externe, image épinglée et publication locale uniquement. La commande permanente `db-start` a été exécutée avec succès sur le conteneur existant.
- Compilation Angular de développement réussie sur 4201. Les suites applicatives Angular/backend et le build de production n'ont pas été relancés pour cette adaptation d'infrastructure ; aucun résultat historique n'est attribué à une nouvelle exécution.
- `git diff --check`, contrôles des espaces, tirets simples, liens internes modifiés et absence des secrets générés dans les fichiers de livraison : conformes.

Les manifestes des deux bases protégées ont été recalculés dans des transactions de lecture seule avant et après l'opération : `industrial_predict` et `industrial_predict_restore_ui471_20261017t121921z` sont inchangées, y compris PETROSEN et le site `id=3`. Le conteneur historique et son démarrage sont inchangés, comme `backend/.env`.

Les preuves détaillées, la sauvegarde et les copies antérieures des cinq fichiers d'outillage sont conservées sous `D:\integration\industrial-predict\development\evidence`. Ce répertoire est voisin des secrets privés : ne pas publier le répertoire privé en bloc.

## Fichiers et état Git

- Cinq fichiers d'outillage déplacés de `infra/ui47/` vers `infra/development/` et adaptés : `compose.yaml`, `manage.py`, `test_manage.py`, `angular-proxy.cjs`, `angular-proxy.test.cjs`.
- Nouveau [guide permanent](../infra/development/README.md) et présent rapport d'exécution.
- README_AI enrichi d'un lien vers le lancement permanent, en conservant les modifications antérieures.
- Rapport UI 4.7.2 et plan UI 4.7.2.1 : liens actualisés et indication de leur statut historique. Les versions précédentes sont conservées dans les preuves privées.

Les 21 autres fichiers préexistants sont identiques à leurs empreintes initiales. Le contenu antérieur de README_AI est également conservé, vérifié en retirant uniquement le paragraphe ajouté. Aucun fichier applicatif, dépendance ou budget n'est modifié pendant cette transition.

Branche finale : `feature/frontend-sites`. HEAD : `e8702b0`. Index vide, travaux non commités conservés. Les trois services de développement restent actifs. Aucune suppression de base, volume ou sauvegarde, aucune création de donnée métier et aucune correction destructive entreprise.

Validation attendue avant les scénarios CRUD UI 4.7.3.
