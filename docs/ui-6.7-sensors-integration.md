# UI 6.7 : validation intégrée Sensors

> UI 6.7.2 du 21 octobre 2026 : l’action Equipment -> Sensors est ajoutée et
> vérifiée avec les parents réels, sans reprise des filtres Equipment. 393 tests
> ciblés, 1 179 tests complets et build production réussis. Les 40 lignes métier
> sont inchangées. Sections 1 à 9 historiques ; section 10 : état courant et
> réserves restantes. Aucun commit, push ou merge.

Date : 21 octobre 2026, UTC. Branche : `feature/frontend-sensors`.
HEAD attendu et constaté : `576314d`. Dépôt propre au démarrage.

## Résultat : arrêt avant toute écriture métier

**Validation intégrée non réalisée : précondition B-SEN-01 non satisfaite sur
le processus API actif. Aucun POST, PATCH ou DELETE n’a été envoyé.**

L’identité de la chaîne DEV est conforme, mais le processus API est antérieur
au correctif. Le contrôle du seed révèle également un écart préexistant, laissé
intact. Aucun service n’a été redémarré et aucun seed réappliqué pour contourner
ces constats. Seuls les diagnostics de lecture et ce rapport ont été réalisés.

## 1. Identité DEV contrôlée

Les commandes documentées dans
[infra/development/README.md](D:/projets/industrial-predict/infra/development/README.md)
ont été examinées puis les contrôles suivants exécutés :

```powershell
backend/.venv/Scripts/python.exe -B infra/development/manage.py check-db --config D:/integration/industrial-predict/development/config.json
backend/.venv/Scripts/python.exe -B infra/development/manage.py check --config D:/integration/industrial-predict/development/config.json
backend/.venv/Scripts/python.exe -B infra/development/seed.py check --config D:/integration/industrial-predict/development/config.json
```

Les deux premiers contrôles passent. Le troisième passe les vérifications
d’identité et de ressources, puis refuse le contenu du seed avec `SeedConflict`.
Le mode check impose une transaction de lecture seule : aucune insertion,
mise à jour, réapplication ou restauration n’a eu lieu.

Des GET directs sans redirection vers les deux endpoints suivants ont confirmé
HTTP 200 et l’en-tête `X-Industrial-Predict-Environment: local-development` :

- `http://127.0.0.1:8001/__dev/identity` ;
- `http://127.0.0.1:4201/__dev/identity`, à travers le proxy Angular.

| Propriété | Résultat concordant HTTP et SQL |
| --- | --- |
| Mode | local-development |
| Base | industrial_predict_dev |
| PostgreSQL | 127.0.0.1:5434 ; version 17.10 |
| API | 127.0.0.1:8001 |
| Angular | 127.0.0.1:4201 |
| Rôle API et lectures métier | ui47_app |
| OID de la base | 16384 |
| Instance | fb3284bd-fb7b-4c22-b620-96a1564b1d0c |
| Cluster | industrial-predict-development |
| Révision Alembic | 09ac8101e9fe |

Le preflight du seed vérifie également le conteneur existant
`industrial-predict-postgres-ui47`, le volume persistant
`industrial-predict-postgres-ui47-data`, sa date de création et le marqueur du
cluster dédié. Aucune ressource Docker créée ou modifiée.

Le rôle ui47_app est non superutilisateur, sans CREATEDB, CREATEROLE, REPLICATION
ou BYPASSRLS. Le contrôle des droits confirme CRUD sur les huit tables, USAGE
seulement sur les huit séquences, absence de CREATE de schéma/base/TEMP, de droit
de modification Alembic, de propriété de tables ou d’appartenance à un autre rôle.
Le rôle ui47_migrator existe, non superutilisateur, et n’a pas été utilisé.
ui47_admin est le compte de maintenance superutilisateur du cluster dédié ; le
preflight documenté du seed l’utilise uniquement pour lire l’identité du cluster.
Toutes les lectures métier et empreintes de cette étape utilisent ui47_app.

Le proxy versionné vise exclusivement 8001 et contrôle l’identité avant chaque
transfert. Le lanceur vérifie aussi l’identité SQL avant chaque requête API.
Aucune cible de fallback vers 8000, 4200 ou 5433 n’a été utilisée. Aucune connexion
à industrial_predict, à une restauration historique ou à PETROSEN. Aucun secret,
mot de passe ou URL complète de connexion n’est reproduit dans les preuves.

## 2. Blocage : code exécuté par l’API

Le correctif B-SEN-01 est présent dans le dépôt : méthode
SensorRepository.get_by_code, égalité exacte `Sensor.code == code`, portée globale
sans filtre equipment_id. Il a été enregistré dans le commit `4defbe9`,
`fix(backend): restore Sensor code lookup and cover CRUD`, le 20 octobre à
16:04:09 UTC.

| Preuve locale | Valeur |
| --- | --- |
| Processus écoutant 8001 | PID 20824, python, lié à 127.0.0.1 |
| Commande | infra/development/manage.py api --config D:/integration/industrial-predict/development/config.json |
| Démarrage UTC du processus | 2026-10-20T07:27:27.3138172Z |
| Dernière écriture UTC de sensor_repository.py | 2026-10-20T15:06:45.6238629Z |

Le lancement API fait un import de app.main puis uvicorn.run sans reload.
app.main importe les routes Sensors ; celles-ci importent SensorService, qui
importe SensorRepository au niveau module. Le processus existait donc avant
l’ajout de get_by_code et ne recharge pas automatiquement ce module. L’identité
HTTP expose la révision SQL, pas une révision Git des modules Python chargés.
La présence actuelle du correctif sur disque ne valide pas le code en mémoire.

**Il n’est pas possible de confirmer B-SEN-01 actif sur ce processus. La
précondition obligatoire échoue ; le scénario d’écriture est arrêté.**
Aucun POST de sondage, PATCH de code identique, tentative susceptible de provoquer
500 ou redémarrage implicite n’a été effectué. Reprise à prévoir après un
redémarrage explicite de l’API DEV sur le code actuel et de nouveaux contrôles.

## 3. État préexistant du seed et des essais historiques

Fixture `industrial-predict-demo-v1`, empreinte SHA-256 :
`5ec44cc118bb4978d7d2d9c9238d6ee1a6fa606bc14514fdec06f054db46731b`.

Les 36 lignes du seed sont présentes, sans clé naturelle manquante ou ambiguë.
35 lignes correspondent aux valeurs de la fixture. Une ligne diffère déjà au
premier instantané UI 6.7 :

| Table | Id et code | Écart préexistant |
| --- | --- | --- |
| sensors | 1, UI47-SEN-PUMP-TEMP | description et updated_at |

La description lue est `Capteur fictif` ; updated_at vaut
`2026-10-20 22:11:55.315993` sans indication de fuseau dans la colonne.
L’origine de cette modification n’est pas déterminée ici. Elle n’est pas
attribuée à UI 6.7 et aucune restauration n’a été tentée. Le refus de seed check
ne signifie donc pas que le jeu est incomplet : il signale une divergence de
contenu déjà présente. L’accord sur sa conservation devra être précisé avant
une reprise exigeant un seed strictement identique à la fixture.

Les trois lignes supplémentaires des essais précédents sont présentes : site
`UI474-SITE-20261019-01`, équipement `UI5-EQ-TEST-001` et équipement
`UI57-EQ-20261020-01`. Aucun changement à ces essais historiques dans DEV.
Il s’agit de lignes de la base DEV, sans accès à une base historique.

Le code envisagé `UI67-SEN-20261021-01`, adapté à la date de cette intervention,
compte zéro occurrence en SQL avant et après les diagnostics. Aucun id retourné
puisqu’aucune création n’a eu lieu. La chaîne disponible pour un futur essai a
été vérifiée en SQL : équipement 1 / UI47-EQ-A-PUMP, site 1 / UI47-SITE-A-PROD,
entreprise 1 / UI47-COMP-A. Aucun rattachement choisi ou changé dans un formulaire.

## 4. Compteurs et preuves SQL en lecture seule

Les diagnostics imposent `SET TRANSACTION READ ONLY`, vérifient l’identité via
inspect_connection avant les SELECT métier et terminent par rollback. Aucun
import du moteur backend par défaut : connexion construite exclusivement avec
la configuration DEV documentée. Aucun appel à migrate ou seed apply.

Instantanés : `2026-10-21T06:35:30.932872+00:00` puis `2026-10-21T06:36:15.715100+00:00`.

| Table | Avant diagnostics | Après arrêt | Variation |
| --- | ---: | ---: | ---: |
| companies | 2 | 2 | 0 |
| sites | 4 | 4 | 0 |
| equipments | 6 | 6 | 0 |
| sensors | 6 | 6 | 0 |
| measurements | 18 | 18 | 0 |
| maintenance_records | 3 | 3 | 0 |
| prediction_records | 0 | 0 | 0 |
| maintenance_recommendations | 0 | 0 | 0 |

Les empreintes SHA-256 des huit tables sont identiques avant/après, sur toutes
les colonnes de leurs lignes ordonnées par id. Les 39 lignes métier présentes
sont conservées, y compris la divergence préexistante du seed. Cette comparaison
prouve l’absence de changement durant les diagnostics ; elle ne démontre pas
que la base correspondait à la fixture avant cette intervention.

Exemples de SELECT exécutés, avec paramètres pour le code :

```sql
SELECT count(*) FROM public.sensors;
SELECT count(*) FROM public.sensors WHERE code = :code;
SELECT row_to_json(t)::text FROM public.sensors t ORDER BY id;
SELECT id, code, description, updated_at
FROM public.sensors WHERE code = 'UI47-SEN-PUMP-TEMP';
SELECT count(*) FROM (
  SELECT code FROM public.sensors GROUP BY code HAVING count(*) > 1
) d;
```

Zéro code Sensor dupliqué. Zéro orphelin sur les chaînes Site -> Company,
Equipment -> Site, Sensor -> Equipment, Measurement -> Sensor et
MaintenanceRecord -> Equipment. PredictionRecord et MaintenanceRecommendation
sont vides. Ces lectures ne constituent pas une validation de concurrence.

Preuves locales ignorées par Git, sans mot de passe :

- [Identités, compteurs, empreintes et état initial](D:/projets/industrial-predict/frontend/tmp/ui-6.7/before.json).
- [Instantané local réactualisé pendant UI 6.7.1 ; dates initiales conservées dans comparison.json](D:/projets/industrial-predict/frontend/tmp/ui-6.7/preflight.json).
- [Comparaison avant/après](D:/projets/industrial-predict/frontend/tmp/ui-6.7/comparison.json).
- [Écart du seed lu avant toute écriture](D:/projets/industrial-predict/frontend/tmp/ui-6.7/preexisting-seed-difference.json).
- [Diagnostic SQL et HTTP en lecture seule](D:/projets/industrial-predict/frontend/tmp/ui-6.7/preflight.py).

## 5. Parcours non exécutés et preuves simulées distinctes

| Contrôle demandé | Résultat UI 6.7 |
| --- | --- |
| Identités Angular -> FastAPI -> PostgreSQL | Vérifiées en lecture |
| Correctif B-SEN-01 actif dans API 8001 | Non confirmé ; processus antérieur, arrêt |
| POST Angular 201 et payload réel | Non exécuté |
| PATCH Angular 200 limité à name/status/description | Non exécuté |
| Actualisation et persistance du nouveau capteur | Non exécutées ; aucun nouveau capteur |
| Liste, recherche, statut et pagination dans Angular | Non exécutés dans cette étape après l’arrêt |
| Equipment -> Sensors et Sensor -> Equipment | Non exécutés dans cette étape |
| Conservation du contexte URL réel | Non vérifiée dans cette étape |
| Doublons, orphelins, conservation des lignes préexistantes | Vérifiés en lecture SQL |
| Dialogue natif beforeunload | Non vérifié manuellement ; réserve conservée |

Aucun navigateur n’a été utilisé pour soumettre un formulaire. Aucune capture
d’un succès réel, réponse POST/PATCH, ou preuve de navigation ne peut être fournie
pour UI 6.7. Les preuves HTTP de cette étape sont uniquement les GET d’identité.
Les réserves ne sont pas remplacées par des captures synthétiques de UI 6.6.

Les **1 153 tests Angular réussis et le build production validé de UI 6.6** sont
des références historiques. Ils n’ont pas été relancés. Les scénarios 409/422,
doubles soumissions, abandon de brouillon, beforeunload, réseau et navigation
échouée restent des preuves simulées HttpTestingController et Router, distinctes
d’une validation intégrée réelle. Aucun conflit ou échec artificiel n’a été
provoqué par une écriture supplémentaire dans DEV.

## 6. Réserves et conditions de reprise

- Faire repartir explicitement l’API DEV avec le correctif B-SEN-01, puis refaire
  les contrôles d’identité avant tout essai. Aucun changement de code nécessaire
  n’est proposé dans cette étape.
- Clarifier la divergence préexistante de UI47-SEN-PUMP-TEMP. Ne pas appliquer le
  seed ni restaurer cette ligne sans instruction spécifique.
- Reprendre ensuite le scénario autorisé avec une seule création et un seul
  PATCH, après nouvelle vérification d’absence du code et relevé des compteurs.
- B-SEN-02 : écarts Pydantic/SQL sur blancs, longueurs et null non corrigés.
- B-SEN-03 : conflits d’intégrité et concurrence, IntegrityError et transactions
  non harmonisées non corrigés. Aucune garantie nouvelle issue des SELECT.
- Absence d’authentification et d’isolation multi-tenant : la cascade Angular et
  les marqueurs DEV ne constituent pas des autorisations de ressource.
- Dialogue natif beforeunload : réserve manuelle maintenue.

## 7. État Git et point d’arrêt

Seul fichier à livrer : `docs/ui-6.7-sensors-integration.md`. Diagnostics et JSON
sous frontend/tmp ignoré, aucun artefact ou secret ajouté au suivi. Aucun fichier
exécutable suivi modifié ; HEAD `576314d` conservé, index vide.
`git diff --check` contrôlé. Aucun changement applicatif, backend, SQL, migration,
Docker ou package. Aucune écriture métier PostgreSQL, aucun DELETE, commit, push
ou merge. Aucun accès à la base historique. UI 6.8 non commencée.

**Point d’arrêt : UI 6.7 bloquée avant les écritures, rapport soumis à validation.
Le parcours réel de création/modification reste à exécuter après levée des
préconditions, sans présenter cette intervention comme une validation complète.**

## 8. UI 6.7.1 : diagnostic DEV et redémarrage autorisé

### 8.1 Périmètre et résultat actuel

Intervention le 21 octobre 2026. Branche feature/frontend-sensors, HEAD 576314d.
Le seul fichier documentaire déjà non suivi au démarrage est ce rapport, conservé
et actualisé. Aucun fichier exécutable suivi modifié.

**Mission A réalisée : API DEV redémarrée, identité conforme et get_by_code
confirmé chargé dans le processus servant 8001. Mission B réalisée en lecture :
écart réel par rapport à la fixture, origine indéterminée. Aucune correction des
données et aucune reprise des écritures UI 6.7.**

### 8.2 Redémarrage de la seule API DEV

La procédure README, le lanceur manage.py et les sources SensorRepository ont
été relus. Avant intervention, les GET d’identité 8001/4201 et les contrôles SQL
confirment encore industrial_predict_dev sur 5434, ui47_app, instance
fb3284bd-fb7b-4c22-b620-96a1564b1d0c et Alembic 09ac8101e9fe.

Le propriétaire vérifié de 127.0.0.1:8001 était PID 20824, démarré le 20 octobre
à 07:27:27 UTC, avec la commande DEV et la configuration privée attendues.
Ce processus a été arrêté de façon ciblée, sans arrêt d’Angular ni de PostgreSQL.
Le terminal d’origine n’étant pas attaché à cette intervention, Stop-Process a
été utilisé sur le seul PID vérifié plutôt qu’un Ctrl+C dans un terminal inconnu.
La libération du port a été contrôlée avant de démarrer son remplaçant.

Commande officielle exécutée depuis D:/projets/industrial-predict, via un
processus détaché à fenêtre masquée et journaux locaux :

```powershell
backend/.venv/Scripts/python.exe -B infra/development/manage.py api --config D:/integration/industrial-predict/development/config.json
```

Aucune modification de config.json, du proxy, du lanceur ou des sources backend.
Aucun port alternatif ou fallback. Aucun db-start, db-stop, migrate ou seed apply.
Le nouveau lanceur a PID 27764 ; son processus Python serveur a PID **28360**,
démarré à **2026-10-21T06:51:07.344935Z** et écoutant 127.0.0.1:8001.
L’API est laissée en fonctionnement après les contrôles.

Un contrôle juste après lancement a trouvé le serveur encore indisponible pendant
l’initialisation. Le contrôle suivant, après fin du démarrage, confirme la santé
et l’identité ; aucun contournement, nouvelle cible ou modification de paramètres.

### 8.3 Preuve du chargement effectif de B-SEN-01

Un observateur temporaire sitecustomize, hors sources applicatives et ignoré par
Git, a été fourni par PYTHONPATH au seul processus de lancement. Il utilise le
profilage Python pour observer l’entrée dans uvicorn.run. Il lit les objets déjà
importés, ne remplace aucune méthode, ne crée aucune route et ne soumet aucune
requête métier. Il désactive le profilage avant de laisser démarrer le serveur.
Cette instrumentation de diagnostic n’est pas une modification de configuration
persistante ; son dossier reste une preuve locale, sans ajout au suivi Git.

Preuve produite **dans le processus 28360**, à
**2026-10-21T06:51:30.430998Z**, puis comparée au PID du listener effectif :

- Module chargé : backend/app/repositories/sensor_repository.py du dépôt attendu.
- Méthode callable : SensorRepository.get_by_code.
- Signature : `(self, code: str) -> app.models.sensor.Sensor | None`.
- Code exécuté : SELECT Sensor avec égalité exacte Sensor.code == code, puis
  self.db.scalar(statement). Aucun équipement ou parent dans les noms référencés.
- Bytecode de la méthode chargée identique à celui recompilé depuis la source
  actuelle, et empreinte de source inchangée au contrôle final.
- SHA-256 source :
  `eb326b91b283ffafc64abee64bbb6bea0e80d3cb251cb80ace29d939042dea1f`.
- SHA-256 bytecode chargé :
  `6a405c4a294cee9b63304a5c57ec1c6a5c4b06219ed81bdd7a16cac1892310a9`.

Cette preuve confirme la présence effective du correctif dans l’API active.
Elle ne prétend pas valider un POST ou PATCH réel : la méthode n’a pas été appelée
pour tenter une écriture métier pendant UI 6.7.1.

Contrôles après démarrage :

| Contrôle réel | Résultat |
| --- | --- |
| manage.py check | Identités SQL et API conformes, privilèges attendus |
| GET 8001/__dev/identity | 200, local-development, industrial_predict_dev, ui47_app |
| GET 4201/__dev/identity | 200, même instance et révision via le proxy Angular |
| GET 8001/health | 200, environment local-development, status healthy |
| GET 8001/api/v1/sensors/1 | 200, valeurs actuelles du capteur |
| GET 4201/api/v1/sensors/1 | 200, mêmes valeurs via le proxy |
| seed.py check | Refus SeedConflict attendu : divergence de contenu inchangée |

### 8.4 Écart exact du seed

Comparaison SQL sous SET TRANSACTION READ ONLY, rôle applicatif, au capteur id 1
et à la fixture compilée par le vrai mécanisme seed.compile_fixture/payload :

| Champ | Valeur actuelle | Attente exacte du seed |
| --- | --- | --- |
| description | `Capteur fictif` | `Capteur fictif.` |
| updated_at | `2026-10-20 22:11:55.315993` | `2026-10-16 12:00:00` |

Le point final constitue la seule différence de description. Ces horodatages
sont des valeurs de colonne sans fuseau ; aucune conversion n’a été supposée.
Nom, code, type, unité, statut, équipement et created_at correspondent exactement
au seed. Les 36 lignes seed sont présentes, sans clé manquante ou ambiguë.
35 lignes sont entièrement conformes ; cette ligne a les deux écarts ci-dessus.

Le contrôle existing_rows compare chaque champ attendu après canonical. Pour une
chaîne, canonical ne normalise ni espaces ni ponctuation. Pour une date sans
fuseau, il conserve la valeur. Il refuse donc correctement description et
updated_at différents ; il n’existe pas de faux positif de fuseau démontré ici.
seed check ne restaure rien et seed apply refuserait aussi cette divergence.

**Conclusion : la donnée de démonstration a réellement changé par rapport à sa
référence. Le contrôle d’intégrité fonctionne selon son contrat. L’écart est
compatible avec une ancienne saisie de test, mais cette origine n’est pas prouvée.
Il n’est pas possible de le qualifier de modification métier voulue ou de simple
erreur de saisie avec les seules preuves disponibles.**

### 8.5 Traces et limites d’attribution

Traces locales examinées :

- L’instantané UI 5.7 sql-after.json, observé le 20 octobre à
  07:25:59.905299 UTC, rapporte seed unchanged avec 36 lignes conformes.
  verification-summary.json confirme cette comparaison. L’écart est donc
  postérieur à cet état documenté et antérieur au premier relevé UI 6.7.
- Les instantanés UI 4.7.4/4.7.5 disponibles montrent la description avec point
  et l’horodatage seed. Ils confortent la valeur de référence, sans attribuer
  la modification ultérieure.
- Les traces synthétiques UI 6.6 concernent seulement des PATCH de code sur
  sensors/1000 avec fixtures en mémoire ; elles ne prouvent aucune modification
  de sensors/1 dans PostgreSQL DEV.
- Les journaux du lanceur API rétabli lors de UI 5.7 sont vides. Son lanceur
  désactive access_log ; aucun journal HTTP métier de l’instant enregistré
  ne fournit le payload, l’auteur ou l’origine du changement.
- Lecture seule de pg_settings : log_statement=none,
  log_min_duration_statement=-1, logging_collector=off, destination stderr.
  Aucun trigger applicatif de traçabilité trouvé sur public.sensors.
- docker logs sur le seul conteneur DEV dédié, fenêtre
  2026-10-20T22:10:00Z à 22:13:00Z : retour 0, aucune ligne. Cette absence
  de trace ne prouve pas l’absence d’une modification dans cette fenêtre.

Le modèle Sensor déclare updated_at avec onupdate=datetime.utcnow ; une mise à
jour via l’ORM est compatible avec l’horodatage constaté. Cela ne démontre ni
le canal HTTP, ni l’auteur, ni l’heure réelle d’une action : la colonne seule
n’est pas un journal d’audit. L’absence d’authentification empêche également
une attribution utilisateur fiable. Aucun accès à une autre base pour enquêter.

Un essai de lecture de shared_preload_libraries par le rôle applicatif a été
refusé par PostgreSQL ; la transaction a été abandonnée sans écriture. Aucune
élévation de rôle ni permission supplémentaire demandée. Le diagnostic a ensuite
utilisé uniquement les paramètres visibles de pg_settings.

### 8.6 Options de résolution proposées, non exécutées

| Option | Effet et risque | Décision nécessaire |
| --- | --- | --- |
| Conserver les valeurs actuelles et accepter explicitement cet écart pour la recette DEV | Préserve les données et l’historique constaté. seed check reste rouge. La reprise peut comparer une baseline documentée avec cette seule divergence acceptée, sans prétendre à un seed strictement intact | Option recommandée si l’objectif est la recette Sensors sans réinitialisation ; accord explicite sur cette exception et sur la reprise UI 6.7 |
| Restaurer la référence de façon ciblée après arbitrage | Écrase une valeur actuelle dont l’intention n’est pas connue. Restaurer seulement le point ne rétablit pas updated_at ; un PATCH normal lui donnerait une nouvelle date. Revenir à la date seed reviendrait à réécrire une information de suivi | Autorisation distincte, valeurs avant/après exactes, conservation d’une preuve préalable et définition du traitement de l’horodatage |
| Faire évoluer ultérieurement la politique de contrôle du seed | Peut distinguer fixture initiale et données de démonstration modifiables, mais une tolérance trop large masquerait des écarts réels | Chantier séparé de conception et tests, sans changement ici du seed ou de ses attentes |

Aucune de ces options n’est appliquée. En particulier, aucune suppression,
réapplication globale du seed, modification de fixture, correction de date ou
mise à jour automatique destinée à rendre le contrôle vert.

### 8.7 Huit tables et preuves avant/après UI 6.7.1

Instantanés UTC : 2026-10-21T06:49:40.504167+00:00 puis 2026-10-21T06:55:27.446083+00:00.

| Table | Avant | Après | Empreinte de toutes les lignes |
| --- | ---: | ---: | --- |
| companies | 2 | 2 | Identique |
| sites | 4 | 4 | Identique |
| equipments | 6 | 6 | Identique |
| sensors | 6 | 6 | Identique |
| measurements | 18 | 18 | Identique |
| maintenance_records | 3 | 3 | Identique |
| prediction_records | 0 | 0 | Identique |
| maintenance_recommendations | 0 | 0 | Identique |

Les 39 lignes, leurs valeurs et horodatages sont inchangés. La divergence du seed,
les trois essais historiques de DEV et l’absence du code UI67-SEN-20261021-01
sont conservés. Aucune insertion, mise à jour ou suppression métier.

Pièces locales ignorées par Git :

- [Preuve d’import dans le processus actif](D:/projets/industrial-predict/frontend/tmp/ui-6.7.1/active-api-import.json).
- [Identité du processus serveur](D:/projets/industrial-predict/frontend/tmp/ui-6.7.1/active-process.json).
- [Observateur temporaire de lecture au démarrage](D:/projets/industrial-predict/frontend/tmp/ui-6.7.1/startup-observer/sitecustomize.py).
- [Journal de démarrage](D:/projets/industrial-predict/frontend/tmp/ui-6.7.1/api.stdout.log).
- [Santé et GET de lecture](D:/projets/industrial-predict/frontend/tmp/ui-6.7.1/health-and-reads.json).
- [Comparaison exacte au seed](D:/projets/industrial-predict/frontend/tmp/ui-6.7.1/seed-diagnosis.json).
- [Résumé de recherche des logs DEV](D:/projets/industrial-predict/frontend/tmp/ui-6.7.1/log-search-summary.json).
- [Baseline UI 6.7.1](D:/projets/industrial-predict/frontend/tmp/ui-6.7/ui671-before.json).
- [État SQL final UI 6.7.1](D:/projets/industrial-predict/frontend/tmp/ui-6.7.1/final.json).
- [Comparaison des empreintes](D:/projets/industrial-predict/frontend/tmp/ui-6.7.1/comparison.json).

Le script local de diagnostic UI 6.7 réécrit preflight.json ; ce fichier a été
réactualisé pendant UI 6.7.1. before.json et comparison.json conservent les
preuves et dates du premier arrêt ; les pièces spécifiques ci-dessus distinguent
la présente intervention.

### 8.8 État Git et arrêt demandé

Seul docs/ui-6.7-sensors-integration.md est actualisé. Les sources exécutables
suivies, fixture, configuration privée, proxy, migrations, packages et Docker
restent inchangés. Les observateurs, PID, logs et JSON de diagnostic sont ignorés.
HEAD 576314d, index vide ; git diff --check et contrôle des espaces du document
réussis. Aucun commit, push ou merge. Aucun accès à la base historique.

Les 1 153 tests Angular et le build UI 6.6 restent des références historiques,
non relancées. B-SEN-02/03, authentification/isolation multi-tenant et la réserve
manuelle beforeunload ne sont pas modifiés par ce diagnostic.

**En attente de validation du diagnostic et d’un choix sur l’écart du seed.
Aucune correction de données ni reprise des tests intégrés UI 6.7 autorisée par
cette seule intervention. UI 6.8 non commencée.**

## 9. Reprise UI 6.7 autorisée : parcours réel Angular -> API -> PostgreSQL

### 9.1 Décisions et préconditions

Reprise le 21 octobre 2026 sur feature/frontend-sensors, HEAD 576314d.
Le rapport était le seul fichier non suivi et reste le seul fichier à livrer.
Aucun exécutable suivi modifié : les 1 153 tests Angular et le build UI 6.6
restent des références historiques, non relancées.

Décisions utilisateur appliquées : conserver le capteur id 1 tel que constaté,
ne pas modifier la fixture ni son contrôle, accepter uniquement pour cette
recette sa divergence de description/updated_at, sans déclarer le seed strict
conforme. Le code explicitement demandé est **UI67-SEN-20261020-01**, malgré
une exécution le 21 octobre ; aucune substitution par le code envisagé auparavant.

Avant toute écriture :

- Identités SQL, API 8001 et Angular 4201 vérifiées avec la configuration DEV,
  industrial_predict_dev sur 127.0.0.1:5434, ui47_app non superutilisateur,
  instance fb3284bd-fb7b-4c22-b620-96a1564b1d0c et Alembic 09ac8101e9fe.
- PID API 28360 encore identique à la preuve d’import UI 6.7.1 ; source B-SEN-01
  inchangée. Avant le scénario, l’observateur de preuve a aussi confirmé la
  même méthode chargée dans son propre processus PID 3708.
- 39 lignes métier relevées avec compteurs, empreintes globales et empreintes
  par id sur toutes les colonnes des huit tables.
- SELECT code exact : zéro occurrence de UI67-SEN-20261020-01.
- Sensor id 1 toujours description `Capteur fictif` et updated_at
  `2026-10-20 22:11:55.315993`, inchangé par rapport au diagnostic accepté.
- Parent réel vérifié : équipement id 1 / UI47-EQ-A-PUMP, site id 1 /
  UI47-SITE-A-PROD, entreprise id 1 / UI47-COMP-A.

La sélection entreprise -> site -> équipement a également été effectuée
explicitement dans la liste Angular, sans sélection arbitraire. La liste affichait
alors les deux capteurs initiaux de la pompe.

### 9.2 Capture des échanges réels, sans simulation

Les actions de création et de modification ont été effectuées dans le navigateur
sur **http://127.0.0.1:4201**, via les formulaires Angular réels et leur proxy.
Aucune soumission par script SQL ou requête métier directe, aucun serveur de
fixtures, aucun mock de réponse ou interception navigateur.

Le navigateur disponible ne fournissant pas de journal réseau complet, le
mécanisme de preuve temporaire de UI 5.7 a été adapté hors sources, sous
frontend/tmp/ui-6.7-reprise. Il enveloppe le serveur ASGI réel démarré avec
manage.api et la même configuration DEV sur 8001 ; il enregistre les corps exacts
et statuts sans remplacer les réponses. Les contrôles d’identité DEV du lanceur
et du proxy restent actifs. Il autorise seulement le POST exact une fois puis
le PATCH exact une fois sur l’id effectivement retourné ; toute autre écriture
serait bloquée. Aucun blocage n’a été déclenché.

Cette instrumentation ponctuelle n’est ni un changement de code applicatif suivi
ni un changement de schéma ou de configuration privée. Après la recette,
l’observateur HTTP est arrêté et l’API normale rétablie sur 8001, PID **8880**.
Une observation de démarrage ponctuelle, désactivée avant le service, confirme
encore get_by_code dans ce processus. Identités 8001/4201, santé healthy et GET
persistant du capteur sont revérifiés après cette restauration.

### 9.3 Création réelle : POST 201

Capture serveur UTC : `2026-10-21T07:07:19.333685+00:00`.

`POST /api/v1/sensors`, corps exact envoyé par Angular :

```json
{"name":"Capteur température - Validation UI 6.7","code":"UI67-SEN-20261020-01","status":"active","description":"Capteur fictif de validation de création.","equipment_id":1,"sensor_type":"temperature","unit":"°C"}
```

Réponse HTTP **201**, identifiant **7** :

```json
{"name":"Capteur température - Validation UI 6.7","code":"UI67-SEN-20261020-01","sensor_type":"temperature","unit":"°C","description":"Capteur fictif de validation de création.","status":"active","id":7,"equipment_id":1,"created_at":"2026-10-21T07:07:19.297309","updated_at":"2026-10-21T07:07:19.297309"}
```

La fiche réelle charge Sensor 7 -> Equipment 1 -> Site 1 -> Company 1.
Elle affiche le code, temperature, °C, Actif et la description attendus.
Navigation de succès, toast et message accessible observés. Une lecture SQL
avant toute modification confirme tous les champs de la réponse 201. Aucun
company_id/site_id, id ou date dans le POST.

### 9.4 Modification réelle : PATCH différentiel 200

Dans le formulaire partagé du capteur 7 : entreprise, site, équipement, type
et unité sont affichés en lecture seule. Les seuls changements saisis sont
le nom demandé, le statut Inactif et la description demandée. Le code est
conservé sans modification. Informations de suivi visibles avant les actions.

Capture serveur UTC : `2026-10-21T07:08:20.660902+00:00`.

`PATCH /api/v1/sensors/7`, corps exact :

```json
{"name":"Capteur température - Modifié UI 6.7","status":"inactive","description":"Capteur fictif modifié pour valider le PATCH différentiel."}
```

Réponse HTTP **200** :

```json
{"name":"Capteur température - Modifié UI 6.7","code":"UI67-SEN-20261020-01","sensor_type":"temperature","unit":"°C","description":"Capteur fictif modifié pour valider le PATCH différentiel.","status":"inactive","id":7,"equipment_id":1,"created_at":"2026-10-21T07:07:19.297309","updated_at":"2026-10-21T07:08:20.634363"}
```

Le payload contient **exactement name, status et description**. Aucun code,
type, unité, equipment_id, parent UI, id ou date. Les statuts et corps proviennent
des échanges réels, pas d’une déduction depuis les seuls messages d’interface.

La comparaison SQL entre création et modification trouve exactement name,
status, description et updated_at modifiés. Code, sensor_type, unit,
equipment_id, id et created_at sont identiques. Les réponses HTTP correspondent
aux valeurs SQL ; seul le séparateur textuel des dates est normalisé pour la
comparaison (`T` en JSON contre espace dans la représentation SQL), sans changer
leur heure ni supposer de fuseau.

Retour à la fiche réelle avec confirmation accessible et toast. Actualisation
complète avant puis après rétablissement de l’API normale : même nom modifié,
statut Inactif, description finale et rattachement réel. Aucune autre écriture
ni tentative volontaire de conflit, erreur ou double soumission.

### 9.5 Liste, filtres, pagination et contexte

Contrôles effectués dans Angular et corroborés par les GET réels enregistrés :

| Contrôle | Résultat observé |
| --- | --- |
| Liste de l’équipement 1 | 2 capteurs avant création, 3 après |
| Recherche explicite UI67-SEN-20261020-01 | 1 résultat, capteur id 7 |
| Même recherche, statut inactive | 1 résultat, nom modifié et Inactif |
| Même recherche, statut active | 0 résultat ; état Aucun résultat |
| Retour à inactive | Le résultat réapparaît |
| Pagination serveur | Taille URL valide page_size=1 ; pages 1, 2 et 3 parcourues via Suivant, respectivement ids 1, 2 et 7 |
| Détail depuis liste filtrée | Retour conservant parents, recherche, statut, page et taille |
| Détail depuis page 3 | Retour conservant page=3 et page_size=1 |
| Sensor -> Equipment | Lien réel /equipments/1?site_id=1&company_id=1, fiche parent conforme |
| Equipment -> Sensors | Réserve : aucun lien contextuel dans les pages Equipment actuelles |

La taille 1 a été introduite par l’URL, possibilité valide documentée du contrat
existant ; aucun nouveau choix ajouté au sélecteur 20/50/100 et aucun changement
de code. Les pages suivantes ont été atteintes avec le bouton Suivant.

La liste filtrée construit par exemple :
`/sensors?company_id=1&site_id=1&equipment_id=1&page=1&page_size=20&search=UI67-SEN-20261020-01&status=inactive`.
Le lien de retour depuis le détail reproduit ce contexte. Le lien de retour
après pagination est
`/sensors?company_id=1&site_id=1&equipment_id=1&page=3&page_size=1`.

Les neuf GET liste capturés ne contiennent que equipment_id, page, page_size,
search et status. Aucun company_id/site_id transmis à l’API Sensors. Le lien
Sensor -> Equipment utilise les parents réels et ne recycle pas les filtres
Sensors dans les filtres Equipment.

**Réserve fonctionnelle démontrée :** la fiche Equipment et sa liste ne proposent
actuellement aucun lien contextuel Voir les capteurs. Leurs liens DOM ont été
examinés et les templates correspondants ne contiennent pas cette action.
Ce sens de navigation n’est donc pas validé. Un accès manuel à l’URL Sensors
contextualisée ne remplace pas ce lien. Aucune implémentation ajoutée dans une
mission limitée au rapport ; décision de suite séparée attendue.

Le dialogue natif d’abandon/beforeunload n’a pas été validé manuellement pendant
cette reprise. Réserve conservée ; les tests simulés UI 6.6 restent la preuve
technique disponible, sans annonce de validation navigateur réelle.

### 9.6 Conservation SQL et intégrité

Baseline avant écriture : `2026-10-21T07:03:54.639927+00:00`. Dernier instantané après retour
à l’API normale : `2026-10-21T07:15:15.396529+00:00`.

| Table | Avant | Après création | Après modification et contrôles |
| --- | ---: | ---: | ---: |
| companies | 2 | 2 | 2 |
| sites | 4 | 4 | 4 |
| equipments | 6 | 6 | 6 |
| sensors | 6 | 7 | 7 |
| measurements | 18 | 18 | 18 |
| maintenance_records | 3 | 3 | 3 |
| prediction_records | 0 | 0 | 0 |
| maintenance_recommendations | 0 | 0 | 0 |

39 lignes initiales -> 40 lignes finales, avec **seul ajout de sensors.id=7**.
Toutes les empreintes par id des 39 lignes préexistantes sont identiques avant,
après création, après PATCH et à la fin. Les sept tables autres que Sensors ont
aussi leurs empreintes globales strictement identiques. La table Sensors change
uniquement par l’ajout de la ligne 7 ; ses six lignes initiales sont identiques.

La comparaison conserve toutes les colonnes, y compris les dates, du capteur 1
et des essais DEV UI474-SITE-20261019-01, UI5-EQ-TEST-001 et
UI57-EQ-20261020-01. Le capteur 7 est conservé ; aucun nettoyage ou DELETE.

Les neuf contraintes FK des huit tables ont été contrôlées en lecture : zéro
orphelin. Les codes Company, Site, Equipment et Sensor ne présentent aucun
doublon. Les nouvelles mesures, maintenances, prédictions et recommandations
restent absentes. Aucun transfert ni changement de parent/type/unité.

Toutes les lectures SQL directes utilisent ui47_app avec SET TRANSACTION READ
ONLY et contrôle préalable de l’identité DEV. Aucune écriture SQL directe,
migration ou connexion historique. Les seules écritures métier sont les deux
requêtes HTTP autorisées depuis Angular, sur le nouveau capteur fictif.

### 9.7 Seed, références et réserves conservés

Le capteur 1 reste description `Capteur fictif` et updated_at
`2026-10-20 22:11:55.315993`. L’écart est explicitement accepté par l’utilisateur
pour cette recette seulement, sans modifier la fixture ou sa logique.
Le contrôle strict final a été exécuté en lecture et renvoie encore
**SeedConflict**. Il n’est pas considéré réussi ; la présence de la ligne
supplémentaire 7 n’est pas une restauration du seed.

Preuves réelles de cette étape : GET d’identité, POST 201, PATCH 200, GET de fiche
et liste, observations navigateur, SELECT et empreintes PostgreSQL. Références
historiques distinctes : 1 153 tests Angular réussis et build UI 6.6 validé,
non relancés. 409/422, réseau, doubles soumissions et abandon restent couverts par
ces tests simulés, pas par des écritures supplémentaires dans DEV.

Réserves B-SEN-02 (écarts Pydantic/SQL) et B-SEN-03 (intégrité et concurrence)
conservées. Les succès séquentiels ne démontrent pas la gestion des courses ni
l’atomicité de tous les chemins d’erreur. Absence d’authentification et
d’isolation multi-tenant non corrigée : la sélection des parents n’est pas une
autorisation de ressource. Réserves du lien Equipment -> Sensors et du dialogue
natif précisées ci-dessus. Aucun indicateur IA ou temps réel inventé.

### 9.8 Pièces de preuve et Git final

Toutes les pièces ci-dessous sont locales et ignorées par Git ; aucun secret ou
dump de base n’est ajouté au suivi. Les instantanés conservent les compteurs,
empreintes et seules lignes utiles (capteurs 1 et 7), pas les lignes complètes
de toutes les tables.

- [Deux écritures HTTP exactes](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/writes-exact.json).
- [Journal HTTP réel de la recette](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/observed-http.jsonl).
- [Synthèse de comparaison SQL/HTTP](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/verification-summary.json).
- [Baseline](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/before.json), [création](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/created.json), [modification](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/updated.json), [état final](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/final.json).
- [Neuf FK et unicité](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/integrity.json).
- [Seed strict toujours refusé](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/seed-check-final.json).
- [Identité et persistance après restauration API](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/restored-environment.json).
- [Preuve B-SEN-01 sous observateur HTTP](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/active-observer-import.json), [preuve dans l’API normale rétablie](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/active-restored-api-import.json).

Captures réelles :

- [Formulaire de création](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/01-create-form.jpg).
- [Fiche créée](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/02-created-detail.jpg).
- [Formulaire d’édition](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/03-edit-form.jpg).
- [Modification confirmée](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/04-updated-confirmed.jpg).
- [Persistance après actualisation](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/05-persisted-after-reload.jpg).
- [Recherche Inactif](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/06-search-inactive.jpg), [recherche Actif vide](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/07-search-active-empty.jpg).
- [Équipement réel](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/08-real-equipment.jpg).
- [Pagination page 1](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/09-pagination-page1.jpg), [page 3](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/10-pagination-page3.jpg).
- [Fiche finale après retour à l’API normale](D:/projets/industrial-predict/frontend/tmp/ui-6.7-reprise/screenshots/11-final-real-persisted.jpg).

Seul docs/ui-6.7-sensors-integration.md est actualisé. HEAD 576314d conservé,
index vide, git diff --check et contrôle des espaces du rapport réussis.
Aucun fichier applicatif, backend/frontend, SQL de schéma, fixture, migration,
Docker, package ou configuration privée modifié. Aucun accès à la base
historique. Aucun commit, push ou merge. UI 6.8 non commencée.

**Création et modification réelles du capteur dédié confirmées ; livraison
soumise à validation avec les réserves documentées. Aucune correction du seed,
implémentation du lien Equipment -> Sensors ou autre écriture autorisée au-delà
du scénario accompli.**

## 10. UI 6.7.2 : action Equipment vers Sensors

### 10.1 Modification et contrat SEN-08

Branche vérifiée feature/frontend-sensors, HEAD 576314d. Au démarrage, seul le
présent rapport était non suivi, avec les preuves UI 6.7 déjà rédigées. Celles-ci
sont conservées ; aucune nouvelle écriture PostgreSQL n’est autorisée ou réalisée.

La fiche Equipment propose maintenant **Voir les capteurs**, sous condition que
Equipment, son Site et la Company réelle soient tous résolus avec succès.
Le computed sensorsQuery refuse les ids non positifs/non sûrs et vérifie
Equipment.site_id == Site.id ainsi que Site.company_id == Company.id.
Un contexte de retour même valide mais différent ne remplace jamais ces valeurs.

URL construite uniquement depuis ces données :
`/sensors?company_id={company.id}&site_id={site.id}&equipment_id={equipment.id}&page=1&page_size=20`.
Aucun search, status, criticality, page ou taille Equipment transféré, aucun
returnUrl accepté par cette action. Le contexte de retour Equipment reste
indépendant et inchangé.

L’action est absente durant le chargement, après erreur Equipment, parent absent,
inaccessible ou incohérent, pendant une relance et immédiatement après changement
d’id. Les données Equipment restent visibles si un parent échoue. Une relance
manuelle réussie permet de réafficher le lien ; aucune requête Sensors déclenchée
par le simple affichage de la fiche Equipment.

L’action utilise navigation-action dans sa variante secondaire. Les sélecteurs
partagés de boutons prennent en charge hover, active, focus et réduction des
animations, avec la transition existante de 120 ms. Aucun nouveau composant de
bouton, style de page global ou package. Hauteur de l’action mesurée : 44 px.

### 10.2 Fichiers concernés

7 fichiers au total, y compris le rapport préexistant :

- [Equipment Detail TypeScript](D:/projets/industrial-predict/frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts) : contexte calculé depuis les références réelles validées.
- [Template Equipment Detail](D:/projets/industrial-predict/frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.html) : action conditionnelle et queryParams explicites.
- [Styles Equipment Detail](D:/projets/industrial-predict/frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.scss) : réutilisation du mixin partagé.
- [Tests Equipment Detail](D:/projets/industrial-predict/frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.spec.ts) : adaptation de l’ancienne assertion qui interdisait toute mention de capteur.
- [Nouveaux tests de navigation](D:/projets/industrial-predict/frontend/src/app/features/equipments/pages/equipment-detail/equipment-sensors-navigation.spec.ts) : 26 scénarios de résolution et de navigation intégrée avec HTTP simulé.
- [Styles d’interactions partagés](D:/projets/industrial-predict/frontend/src/styles/_buttons.scss) : ajout de equipment-sensors aux listes d’actions secondaires et de réduction des animations.
- [Présent rapport](D:/projets/industrial-predict/docs/ui-6.7-sensors-integration.md) : résultats complémentaires et réserves.

Aucun changement aux modèles, DTO, services API, routes Sensors, backend,
fixture, schéma SQL, migrations, Docker, packages ou budgets.

### 10.3 Tests exécutés sur les sources finales

| Validation nouvelle UI 6.7.2 | Résultat |
| --- | --- |
| Tests ciblés Equipment Detail, Sensors et app.routes | 393 tests réussis, 11 fichiers |
| Tests de navigation ajoutés | 26 réussis, inclus dans les deux exécutions |
| Suite Angular complète | 1 179 tests réussis, 58 fichiers |
| Build production | Réussi |
| git diff --check et contrôle des fichiers nouveaux | Réussis |

Couverture nouvelle : chaîne complète obligatoire, parents de retour différents,
absence de reprise de tous les filtres Equipment, changement des query params
sans relecture inutile des parents, liens accessibles au clavier, erreurs parent
réseau/403/404/500, relance manuelle, incohérences Site/Company, FK invalides,
Equipment absent/invalide ou reçu avec un autre id, id changé avec annulation des
lectures obsolètes, clic Router réel jusqu’à la liste Sensors et restauration
des trois sélections. Les tests vérifient l’absence d’appel Sensors avant Company
validée, les paramètres HTTP exacts equipment_id/page/page_size, l’absence de
filtres hérités et le refus de résultats appartenant à un autre équipement.
Aucune écriture HTTP dans ces tests, uniquement HttpTestingController.

Commandes depuis frontend :

```powershell
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.7.2/vitest.config.mjs --include=src/app/features/equipments/pages/equipment-detail/*.spec.ts --include=src/app/features/sensors/**/*.spec.ts --include=src/app/app.routes.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.7.2/vitest.config.mjs
npm.cmd run build -- --configuration production --stats-json
```

Le runner temporaire existant limite Vitest à deux workers, sans nouveau package.
Les 1 153 tests et build UI 6.6 cités aux sections précédentes restent historiques ;
les résultats 1 179 et le build ci-dessus sont bien relancés pour UI 6.7.2.

### 10.4 Navigation réelle DEV en lecture seule

Identités DEV et baseline des 40 lignes vérifiées en lecture avec les mêmes
contrôles explicites, sans backend par défaut ni accès historique. L’API normale
est conservée : aucun observateur HTTP, restart ou changement de configuration
nécessaire pour cette étape.

Fiche réelle ouverte :
`/equipments/1?company_id=2&site_id=3&status=maintenance&criticality=critical&search=UI5-EQ-TEST-001&page=4&page_size=50`.
Le rattachement affiché reste Equipment 1 -> Site 1 -> Company 1 ; la notice de
contexte de retour différent est présente. Le retour Equipment conserve ses
paramètres 2/3 et ses filtres ; Voir les capteurs pointe vers :
`/sensors?company_id=1&site_id=1&equipment_id=1&page=1&page_size=20`.

Le clic a été effectué dans Angular DEV. La liste restaure INDUSTRIE DEMO A,
Site de production et Pompe de circulation P101. Recherche vide, statut Tous,
taille 20, page 1. Seuls les trois capteurs de cet équipement s’affichent :
ids 1 et 2 du seed, puis id 7 de la recette UI 6.7. Les liens de détail conservent
le nouveau contexte Sensors, sans filtre Equipment.

Un GET de lecture explicite supplémentaire via Angular,
`http://127.0.0.1:4201/api/v1/sensors?equipment_id=1&page=1&page_size=20`,
répond 200 avec les mêmes ids 1, 2 et 7, tous equipment_id=1. Il corrobore le
résultat affiché ; les paramètres du clic sont aussi couverts par les tests
HttpTestingController. Aucun nouveau POST, PATCH, DELETE ou transfert.
Les erreurs parent sont couvertes par fixtures isolées ; aucune donnée DEV
n’a été altérée pour fabriquer un parent absent ou incohérent.

### 10.5 Responsive, clavier et captures

Mesures après stabilisation et captures de la zone visible du navigateur réel :

| Cible CSS | Largeur mesurée | Résultat |
| --- | --- | --- |
| 1440 | 1440 | Actions sur une ligne, focus visible |
| 1024 | 1024 | Actions repliées sur deux lignes |
| 1023 | 1023 | Navigation compacte, actions repliées |
| 768 | 768 | Actions repliées sans débordement global |
| 390 | 389 et 391 | Deux rendus voisins contrôlés ; réserve d’arrondi |
| 320 | 320 | Retour puis Voir les capteurs et Modifier, cibles de 44 px |

Aucun débordement horizontal global dans les mesures finales stabilisées.
L’URL du lien reste strictement identique à chaque format. Focus clavier sur
Voir les capteurs obtenu par Maj+Tab depuis Modifier ; contour visible.
Aucun budget augmenté pour cette correction.

Limite conservée : le zoom du navigateur arrondit la cible 390 px à 389 ou
391 px ; une largeur CSS exactement 390 n’est pas revendiquée. Plusieurs essais
de capture pleine page ont échoué dans l’outil, sans erreur de l’application.
Les captures finalement conservées utilisent une zone bornée au viewport ;
elles sont des images réelles, sans reconstruction de l’interface. Les captures
mobiles montrent le haut de la fiche et l’action, pas nécessairement toute la
fiche administrative. L’état de la liste après navigation est aussi conservé
en JSON DOM et en réponse GET réelle.

Captures et preuves locales ignorées par Git :

- [Fiche Equipment 1440](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/screenshots/equipment-1440.jpg).
- [Fiche Equipment 1024](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/screenshots/equipment-1024.jpg).
- [Fiche Equipment 1023](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/screenshots/equipment-1023.jpg).
- [Fiche Equipment 768](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/screenshots/equipment-768.jpg).
- [Fiche Equipment 390-near-389](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/screenshots/equipment-390-near-389.jpg).
- [Fiche Equipment 390-near-391](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/screenshots/equipment-390-near-391.jpg).
- [Fiche Equipment 320](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/screenshots/equipment-320.jpg).
- [Mesures responsive](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/responsive.json).
- [Contexte et résultats après clic réel](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/navigation-real.json).
- [GET DEV corroborant le périmètre](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/read-http.json).

### 10.6 Conservation PostgreSQL et bundle

Instantanés SQL en lecture seule : `2026-10-21T09:38:19.686188+00:00` puis
`2026-10-21T09:47:49.559818+00:00`. Empreintes globales des huit tables et par id
strictement identiques.

| Table | Avant | Après |
| --- | ---: | ---: |
| companies | 2 | 2 |
| sites | 4 | 4 |
| equipments | 6 | 6 |
| sensors | 7 | 7 |
| measurements | 18 | 18 |
| maintenance_records | 3 | 3 |
| prediction_records | 0 | 0 |
| maintenance_recommendations | 0 | 0 |

Les 40 lignes, y compris Sensors 1 et 7 et les essais DEV précédents, sont
inchangées sur toutes leurs colonnes et dates. Le capteur 1 conserve l’écart
accepté. Aucun changement de fixture ou de contrôle du seed ; aucun nouveau
succès du seed strict n’est revendiqué.

- [Baseline](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/before.json).
- [État final](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/after.json).
- [Comparaison des 40 lignes](D:/projets/industrial-predict/frontend/tmp/ui-6.7.2/sql-comparison.json).

Bundle initial production : **605 239 octets, soit 605,24 kB**, contre 605 125
octets en UI 6.6 : **+114 octets**. Avertissement existant du budget initial de
500 kB : dépassement de 105,24 kB. Seuil d’erreur initial 1 MB et budgets
composants 4/8 kB inchangés. Chunk Equipment Detail : 14 208 octets.
Ensemble JS/CSS : 1 018 482 octets, +1 972 par rapport au build UI 6.6.

### 10.7 Réserves restantes et état Git

L’écart fonctionnel SEN-08 constaté en UI 6.7 est corrigé **dans la fiche détail
Equipment**, périmètre demandé. Une action supplémentaire dans la liste Equipment
n’est pas ajoutée. Les mentions d’absence du lien aux sections 9 et antérieures
relatent l’état de la recette précédente, pas l’état courant.

Restent : B-SEN-02, B-SEN-03, absence d’authentification et d’isolation tenant,
réserve manuelle du dialogue natif d’abandon et arrondi responsive 390 px.
Aucun de ces sujets n’est corrigé ou déclaré validé par le présent lien.

Git : 7 fichiers concernés, HEAD 576314d inchangé sur feature/frontend-sensors,
index vide. Aucun backend, SQL, migration, Docker, package ou lockfile modifié.
Images, runners et diagnostics restent ignorés ; aucun secret ou artefact de
build au suivi. Aucun commit, push ou merge, UI 6.8 non commencée.

**Correction SEN-08 et preuves complémentaires soumises à validation avant commit.
Aucune nouvelle écriture métier PostgreSQL effectuée pendant UI 6.7.2.**
