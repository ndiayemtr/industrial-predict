# UI 4.7.4 - Validation réelle de création, lecture et modification des Sites

Exécution le 19 octobre 2026 sur `feature/frontend-sites`, HEAD `8554684`, dépôt propre avant intervention. Aucun commit, push ou merge. UI 4.7.5 non commencée. Ce rapport attend la validation de l'utilisateur.

## Cible vérifiée avant toute écriture

- Angular : `127.0.0.1:4201` ; FastAPI : `127.0.0.1:8001` ; PostgreSQL : `127.0.0.1:5434`.
- Base effective : `industrial_predict_dev`, PostgreSQL 17.10, cluster `industrial-predict-development`, OID 16384. Identité d'instance identique sur SQL, API et proxy Angular.
- Alembic : `09ac8101e9fe`. Rôle SQL utilisé par FastAPI : `ui47_app`, non superutilisateur, sans CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS, DDL ou modification d'Alembic.
- Le lanceur dédié et le proxy [DEV](../infra/development/README.md) imposent cette cible, contrôlent son identité et n'ont aucun repli vers 8000. Les trois ports étaient liés à 127.0.0.1.
- Les huit compteurs correspondaient exactement au seed. Les neuf clés étrangères ne présentaient aucun orphelin ; aucun code dupliqué.

Le premier contrôle dans le bac à sable a été refusé par les permissions de lecture de la configuration privée. Le contrôle effectif a ensuite réussi avec les permissions requises, avant tout POST. Aucun secret n'a été affiché ou copié dans ce rapport.

## Méthode de preuve HTTP

Les actions de création et de modification ont été effectuées dans les formulaires Angular du navigateur intégré, sans interception ni réponse simulée. Le simulateur UI 4.6.2 n'est pas utilisé.

L'API DEV a été temporairement relancée avec un observateur ASGI externe aux fichiers applicatifs. Il conserve la méthode, le chemin, la query string et les corps exacts de requête/réponse. Il transmet les réponses réelles de FastAPI et ne change pas les corps autorisés. Les contrôles d'identité du lanceur restent actifs.

Un garde-fou de l'observateur n'autorise que les POST avec le code dédié et l'entreprise A vérifiée, puis les PATCH de l'identifiant réellement créé avec uniquement name/description. PUT, DELETE et les autres écritures sont bloqués. Aucun blocage de ce garde-fou n'a été rencontré. L'observateur n'a aucun chemin de connexion à une base historique.

Un premier contrôle immédiatement après le redémarrage a rencontré l'indisponibilité transitoire de l'API. Le formulaire a présenté le catalogue indisponible ; une fois l'identité DEV revérifiée avec succès, l'action Réessayer a chargé les deux entreprises. Aucune écriture n'a précédé ce contrôle réussi. Un second lancement de diagnostic a été refusé parce que le port était déjà occupé ; aucune seconde API n'a été créée sur un autre port.

Après les captures, l'observateur a été arrêté et le lanceur API DEV normal a été rétabli sur 8001. Son identité SQL a été vérifiée de nouveau. Aucun fichier applicatif ou de configuration suivi n'a été modifié.

## Création réelle depuis Angular

Entreprise explicitement choisie : `INDUSTRIE DEMO A - UI47-COMP-A`, identifiant interne vérifié 1.

POST `/api/v1/sites`, corps exact :

```json
{"company_id":1,"name":"Site de validation UI 4.7.4","code":"UI474-SITE-20261019-01","description":"Donnée fictive dédiée à la validation CRUD réelle UI 4.7.4."}
```

Réponse réelle **201** :

```json
{"name":"Site de validation UI 4.7.4","code":"UI474-SITE-20261019-01","description":"Donnée fictive dédiée à la validation CRUD réelle UI 4.7.4.","id":4,"company_id":1,"created_at":"2026-10-19T10:02:19.947122","updated_at":"2026-10-19T10:02:19.947122"}
```

Redirection vers `/sites/4?company_id=1&page=1&page_size=20`. Toast et région `role=status` distincte : « Site créé avec succès. ». La fiche chargée affiche le nom, code, entreprise et description attendus. La ligne est présente dans PostgreSQL avant le test de modification. Un rechargement complet du navigateur relit la même fiche et conserve les valeurs.

## Modification réelle depuis la fiche

Le lien Modifier conserve le contexte dans `/sites/4/edit?company_id=1&page=1&page_size=20`. Seuls le nom et la description ont été saisis à nouveau. L'entreprise est affichée en lecture seule ; les dates restent des informations de suivi.

PATCH `/api/v1/sites/4`, corps exact :

```json
{"name":"Site de validation UI 4.7.4 - Modifié","description":"Description modifiée depuis Angular pour valider le PATCH réel UI 4.7.4."}
```

Réponse réelle **200** :

```json
{"name":"Site de validation UI 4.7.4 - Modifié","code":"UI474-SITE-20261019-01","description":"Description modifiée depuis Angular pour valider le PATCH réel UI 4.7.4.","id":4,"company_id":1,"created_at":"2026-10-19T10:02:19.947122","updated_at":"2026-10-19T10:03:00.620618"}
```

Le PATCH ne contient ni code, ni company_id, ni date. Redirection vers la fiche, toast et confirmation accessible « Site modifié avec succès. ». Le rechargement complet de la fiche relit les valeurs persistées. Les comparaisons SQL avant/après modification montrent exactement trois colonnes changées : name, description et updated_at. Code, entreprise, id et created_at sont identiques.

Les horodatages administratifs retournés sont sans fuseau ; leur affichage conserve les composantes serveur. Aucune conversion du modèle ou des valeurs HTTP n'a été ajoutée.

## Liste, recherche et navigation

- Retour à la liste avec company_id=1, page=1, page_size=20.
- Pagination réelle à page_size=1, taille acceptée par le contrat et l'URL : trois pages distinctes pour A, dans l'ordre backend par id croissant. Page 1 : production ; page 2 : logistique ; page 3 : site dédié. Suivant est désactivé sur la dernière page.
- Recherche explicite du code dédié depuis la page 3 : retour à page=1, un résultat, taille conservée.
- Ouverture de la fiche depuis ce résultat et retour : company_id, search, page et page_size conservés dans les liens et l'URL.
- Sélection de B : réinitialisation existante de page/recherche, un site énergétique. Recherche du code dédié dans B : zéro résultat, état Aucun résultat, action Effacer la recherche et pagination masquée.
- Ces contrôles valident un filtre ergonomique, pas une autorisation multi-entreprises.

## Erreurs réelles contrôlées

### Conflit 409 depuis Angular

Une seconde création utilise le même code dédié, avec le nom « Tentative contrôlée de doublon UI 4.7.4 » et la description « Cette tentative doit être refusée sans nouvelle ligne. ».

FastAPI répond **409** avec `{"detail":"Site with code 'UI474-SITE-20261019-01' already exists."}`. L'interface conserve les saisies, reste sur la création et présente une alerte générique de conflit, sans toast de succès. La cause connue de ce scénario ne change pas le traitement prudent général de l'interface.

### Validation 422 sur le véritable endpoint via le proxy

Le formulaire Angular bloque normalement un nom obligatoire absent. Pour exercer réellement FastAPI sans contourner les contrôles Angular dans le navigateur, un appel HTTP contrôlé séparé a été effectué via `127.0.0.1:4201`, après les mêmes vérifications d'identité :

```json
{"company_id":1,"code":"UI474-SITE-20261019-01","description":"Requête volontairement invalide UI 4.7.4, nom absent."}
```

Réponse **422**, erreur Pydantic `type=missing`, `loc=["body","name"]`. Aucune ligne insérée. Ce contrôle démontre le refus réel de FastAPI via le proxy ; il n'est pas présenté comme une reproduction navigateur d'un 422 ni comme une nouvelle validation de son affichage Angular.

La trace finale comporte exactement quatre requêtes d'écriture : POST 201, PATCH 200, POST 409, POST 422. Aucun PATCH supplémentaire, PUT, DELETE ou transfert d'entreprise.

## Persistance et intégrité

| Table | Avant | Après création | Après modification et refus |
| --- | ---: | ---: | ---: |
| companies | 2 | 2 | 2 |
| sites | 3 | 4 | 4 |
| equipments | 4 | 4 | 4 |
| sensors | 6 | 6 | 6 |
| measurements | 18 | 18 | 18 |
| maintenance_records | 3 | 3 | 3 |
| prediction_records | 0 | 0 | 0 |
| maintenance_recommendations | 0 | 0 | 0 |

Comparaison de toutes les colonnes des **36 lignes seed** : aucune différence. Les tables autres que Sites sont intégralement identiques. Dans Sites, les trois lignes seed sont identiques et seule la ligne dédiée id=4 est ajoutée. Les neuf relations FK n'ont aucun orphelin après l'essai, et les codes des quatre catalogues restent uniques. Les réponses POST/PATCH ont été comparées aux instantanés SQL.

Le site dédié est **conservé**. Aucun DELETE, reset, seed apply, migration ou modification de schéma. Aucune connexion ni opération de cette étape n'a visé industrial_predict, PETROSEN, son site historique id=3 ou industrial_predict_restore_ui471_20261017t121921z. L'id=3 du seed DEV appartient à la base distincte ; il est également inchangé.

## Preuves locales et captures

Répertoire ignoré par Git : `D:\projets\industrial-predict\frontend\tmp\ui-4.7.4`.

- `http.jsonl` : trace des GET et quatre requêtes d'écriture arrivées à l'API réelle.
- `writes-exact.json` : corps POST/PATCH et réponses exacts, dont 409/422.
- `before.json`, `created.json`, `updated.json`, `after.json` : instantanés SQL en lecture seule avec identités, compteurs et contrôles d'intégrité.
- `comparison.json` : assertions de conservation et bilan des écritures.
- `controlled-422.json` : requête invalide et réponse réelle.
- Captures JPEG : 01 formulaire de création ; 02 confirmation de création ; 03 fiche créée ; 04 formulaire de modification ; 05 confirmation de modification ; 06 fiche modifiée ; 07 recherche ; 08 absence dans B ; 09 conflit ; 10 fiche finale persistante.
- Les captures de confirmation immédiate peuvent présenter le chargement de la fiche ; les captures suivantes montrent son contenu entièrement chargé.
- Les scripts temporaires snapshot.py, observe_api.py et check_422.py restent dans ce répertoire ignoré, ainsi que les sorties techniques. Aucun secret n'y est volontairement enregistré ; les en-têtes d'authentification et les URL SQL ne sont pas journalisés.

## Limites et incidents d'outillage

- Lors d'un contrôle complémentaire d'abandon après le 409, l'action Annuler a provoqué un blocage du contrôle automatisé du navigateur ; l'API de dialogue n'a pas permis d'établir sa résolution. Ce parcours d'abandon n'est donc pas déclaré validé manuellement ici. Une nouvelle fiche dans un nouvel onglet a confirmé l'état persistant sans écriture supplémentaire. Les tests unitaires de protection font partie de la suite complète.
- Les confirmations accessibles sont observées dans le DOM/AX ; aucun lecteur d'écran réel n'a été testé. Aucun nouveau test exhaustif de zoom ou de responsive n'est revendiqué.
- Aucun scénario de suppression ou de transfert n'est exécuté. Pas de test de charge, panne concurrente ou autorisation multi-tenant. Les limites de sécurité existantes restent applicables.

## Vérifications techniques

Exécution séquentielle, sans concurrence entre la suite de tests et le build :

1. Première commande Angular sous restriction de fichiers : échec d'outillage EPERM lors du renommage d'un fichier de cache temporaire Windows, 42 fichiers en échec d'initialisation, **aucun test exécuté**. Aucun échec d'assertion n'est attribué à cette tentative. Sortie conservée dans angular-tests.log.
2. Nouvelle exécution avec les permissions de fichiers nécessaires, sans modification du code : **581 tests réussis dans 42 fichiers**, durée Vitest 30,22 s, début 10:07:57 UTC. Compilation des tests 13,243 s. Sortie dans angular-tests-elevated.log.
3. Build production réussi : 25,373 s, terminé à 10:09:08 UTC, sortie dédiée production. Avertissement existant : **601 509 octets, soit 601,51 ko**, pour un budget warning de 500 ko ; dépassement 101,51 ko. Aucun budget relevé.
4. Les **31 fichiers JS/CSS** du build ont des empreintes identiques à ceux du contrôle avant commits : total 785 921 octets, aucune variation de bundle. Page édition différée 12 291 octets, formulaire partagé 10 457 octets.
5. Corps et réponses HTTP comparés champ par champ aux instantanés SQL : conformes. Les requêtes de snapshot utilisent des transactions READ ONLY et le compte applicatif vérifié.
6. git diff --check conforme ; rapport contrôlé aussi pour les espaces de fin de ligne, les tirets simples et son lien interne. Les fichiers de preuves, scripts et builds restent ignorés par Git.

Les résultats techniques sont également conservés dans technical-results.json. Aucun changement applicatif, de dépendance ou de budget. Les tests Sass/npm ne sont pas revendiqués comme relancés dans cette étape, qui n'a pas modifié le code.

## État Git final

Branche `feature/frontend-sites`, HEAD `8554684`. Seul nouveau fichier suivi proposé : ce rapport, non ajouté à l'index.

```text
?? docs/ui-4.7.4-real-sites-crud.md
```

Aucun commit, push ou merge. Aucune correction applicative engagée et aucun début d'UI 4.7.5. Les données réelles de test sont conservées jusqu'à décision ultérieure. Les secrets historiques déjà présents dans l'historique Git restent une dette distincte ; aucun secret n'est ajouté par ce rapport.
