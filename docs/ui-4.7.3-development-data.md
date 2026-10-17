# UI 4.7.3 - Jeu de données de développement reproductible

Suivi : UI 4.7.3 validée par l’utilisateur et enregistrée dans la série de commits avant UI 4.7.4. Les résultats et états Git ci-dessous décrivent l’intervention initiale.

Branche `feature/frontend-sites`, HEAD `e8702b0`. Préconditions vérifiées le 17 octobre 2026 avant toute initialisation. Le chargement est autorisé exclusivement sur `industrial_predict_dev` ; les résultats d'exécution sont consignés à la fin du rapport.

## Préconditions constatées avant chargement

- PostgreSQL 17.10, port `127.0.0.1:5434`, cluster `7697614558579179559`, base `industrial_predict_dev`, OID `16384`.
- Compte applicatif `ui47_app` non superutilisateur ; privilèges inchangés. Écriture avec cette identité, sans rôle de migration ou d'administration.
- Alembic `09ac8101e9fe`, huit tables métier à zéro ligne, aucune donnée PETROSEN.
- Identité SQL effective de FastAPI 8001 vérifiée. Le seed exige aussi l'identité correspondante via Angular 4201, sans redirection HTTP.
- Conteneur dédié et volume persistant identifiés. Bases historiques lues uniquement en transactions de lecture seule pour constituer leurs manifestes avant/après.
- Les 31 fichiers de travail préexistants ont été relevés avant modification. Aucun commit, push ou merge.

Le contrôle `seed.py check` a renvoyé `ready`, zéro écriture et zéro ligne dans les huit tables avant la première application. La fixture a été validée par les schémas Pydantic existants et les longueurs des colonnes SQL réelles.

## Contrats vérifiés et choix de périmètre

Les modèles, schémas, migrations, services et routes des huit entités ont été examinés. Les codes Company et Site sont uniques globalement, limités à 50 caractères en SQL ; ceux des équipements et capteurs sont uniques globalement et limités à 100 caractères. Les noms ont une limite SQL de 150 caractères. Le titre d'une maintenance est limité à 255 caractères.

Les états et criticités proviennent de `app.core.enums`, sans vocabulaire ajouté. Mesures et dates de maintenance exigent un fuseau dans leurs schémas. Les dates administratives des entreprises, sites, équipements et capteurs utilisent des colonnes sans fuseau ; elles restent des littéraux sans fuseau dans le jeu. Les dates d'audit des maintenances sont explicites UTC.

Les mesures n'ont ni code ni unicité SQL sur `(sensor_id, timestamp)`. Les maintenances n'ont pas de code métier unique. Le seed emploie des clés naturelles déterministes et refuse les correspondances multiples.

Les prédictions possèdent des références équipement/capteur/mesure, un type, score, niveau, informations de modèle et dates. Les recommandations portent notamment une priorité, un type, une raison, une action et des signaux typés. Ces deux entités sont volontairement laissées vides : aucune sortie de modèle ni recommandation calculée n'est inventée. Aucune route de calcul ML ou de génération persistante n'est appelée.

## Jeu fictif versionné

La source est [demo-data.json](../infra/development/demo-data.json), version `industrial-predict-demo-v1`. Aucun identifiant numérique n'y figure. Le préfixe UI47 est conservé pour les codes métier demandés ; le mécanisme et son emplacement sont génériques pour tous les modules.

| Entreprise | Site | Équipements |
| --- | --- | --- |
| `UI47-COMP-A` - INDUSTRIE DEMO A | `UI47-SITE-A-PROD` - Site de production | `UI47-EQ-A-PUMP` - Pompe P101, operational/high ; `UI47-EQ-A-COMP` - Compresseur C101, maintenance/critical |
| `UI47-COMP-A` - INDUSTRIE DEMO A | `UI47-SITE-A-LOG` - Site logistique | `UI47-EQ-A-CONV` - Convoyeur C201, out_of_service/medium |
| `UI47-COMP-B` - INDUSTRIE DEMO B | `UI47-SITE-B-ENER` - Site énergétique | `UI47-EQ-B-GEN` - Groupe G301, operational/low |

Six capteurs sont associés par code d'équipement : température et vibration de pompe, température du compresseur, vibration du convoyeur, température et pression d'huile du groupe. Un capteur est inactif ; ses relevés représentent un historique antérieur à sa désactivation. Unités : `°C`, `mm/s`, `bar`. Les valeurs sont plausibles pour une démonstration, sans valeur de référence de sûreté industrielle.

Chaque capteur reçoit trois mesures fixes, soit 18 lignes :

- `2026-10-14T08:00:00Z` ;
- `2026-10-15T08:00:00Z` ;
- `2026-10-16T08:00:00.123456Z`.

Les qualités good, suspect, bad et estimated sont représentées. Les fractions de seconde sont conservées en base. Les plages fictives sont de 64,2 à 86,5 °C pour les températures, de 1,8 à 4,2 mm/s pour les vibrations, et de 4,1 à 4,2 bar pour la pression.

Trois maintenances sont définies, avec marqueur explicite dans le titre :

- `UI47-MAINT-PUMP-01` : préventive terminée le 15 octobre, 45 minutes d'arrêt, coût fictif de 125 ;
- `UI47-MAINT-COMP-01` : corrective en cours depuis le 16 octobre, priorité critical ;
- `UI47-MAINT-CONV-01` : corrective planifiée au 16 octobre, priorité high, volontairement échue au contrôle du 17 octobre.

Les descriptions et techniciens indiquent le caractère fictif. Les dates administratives et d'audit sont fixes : création le 1er octobre à 08:00, modification le 16 octobre à 12:00. Aucune horloge courante ni génération aléatoire n'est utilisée par le seed.

Pour une lecture Dashboard reproductible, employer la période UTC `[2026-10-12T00:00:00Z, 2026-10-17T00:00:00Z[`. Le filtre ergonomique par entreprise n'est pas une autorisation multi-entreprises.

## Mécanisme et commandes

Le script [seed.py](../infra/development/seed.py) utilise le Python et les dépendances backend existants. Il n'importe ni les sessions ni le moteur par défaut du backend. Il valide les créations avec les schémas Pydantic, puis utilise SQLAlchemy Core sur la connexion explicitement vérifiée. Cette insertion directe permet de fixer aussi les horodatages administratifs, absents des DTO HTTP de création, et de conserver une transaction unique ; les services HTTP existants valident et commitent séparément chaque création.

La prévalidation des schémas emploie un identifiant temporaire uniquement pour vérifier le contrat d'une clé étrangère obligatoire. Cette valeur est immédiatement retirée. Les clés réellement insérées sont obtenues par les codes des parents et les identifiants attribués par la base. Tout identifiant numérique fourni dans la fixture est refusé.

Le script expose uniquement `check` et `apply`. Il ne contient ni commande de réinitialisation, ni chemin de suppression ou de mise à jour. La configuration est obligatoire et doit rester hors Git.

```powershell
$devConfig = 'D:\integration\industrial-predict\development\config.json'
& backend/.venv/Scripts/python.exe -B infra/development/seed.py check --config $devConfig
& backend/.venv/Scripts/python.exe -B infra/development/seed.py apply --config $devConfig
```

Le lancement exige PostgreSQL, FastAPI 8001 et Angular 4201 opérationnels avec la même identité. Le compte d'administration dédié sert uniquement à lire l'identifiant système du cluster pendant la précondition ; toutes les insertions utilisent `ui47_app`.

La transaction d'application revérifie l'identité, impose UTC pour les colonnes avec fuseau et verrouille les huit tables contre les écritures concurrentes pendant l'initialisation. L'attente de verrou est limitée à cinq secondes, les instructions à trente secondes. Aucun retry automatique. Toute erreur provoque l'annulation des lignes non commitées, sans nettoyage ni correction automatique. Les séquences PostgreSQL peuvent néanmoins avancer lors d'une transaction échouée ; les identifiants ne font donc pas partie du contrat reproductible.

## Idempotence et protection des données

Au premier passage, les huit tables doivent être entièrement vides. Le seed crée le jeu complet dans une transaction. Un jeu partiel ou des données étrangères avant initialisation entraînent un refus sans insertion.

Après initialisation, toutes les lignes attendues doivent correspondre exactement, y compris parents, valeurs et dates. Le second passage renvoie `unchanged`, sans INSERT, UPDATE ou DELETE. Il ne consomme pas d'identifiants supplémentaires. Les données étrangères ajoutées après un jeu complet sont ignorées et préservées. Si une ligne du jeu a été modifiée ou si une clé naturelle est ambiguë, le script refuse de poursuivre ; il ne restaure pas silencieusement les valeurs de la fixture.

Clés de résolution :

- Company, Site, Equipment, Sensor : code métier global ;
- Measurement : code capteur et instant UTC ;
- MaintenanceRecord : code équipement, titre marqué et date planifiée.

L'absence d'unicité SQL des deux dernières clés est compensée pendant le seed par les verrous transactionnels et le refus de toute correspondance multiple. Aucune contrainte SQL n'est ajoutée. Le résultat JSON comporte la version et l'empreinte SHA-256 de la fixture.

## Réinitialisation limitée, proposée uniquement

Cette procédure n'est ni implémentée dans le script ni exécutée. Elle nécessite une autorisation explicite de suppression distincte.

1. Vérifier de nouveau l'identité de développement et sauvegarder la base dédiée. Arrêter les écritures concurrentes.
2. Résoudre les lignes exactes du jeu par les codes et clés naturelles ci-dessus, puis les comparer à la fixture et au manifeste d'exécution. Le seul préfixe UI47 ne suffit pas à identifier une ligne comme supprimable.
3. Inventorier tous les descendants et références, y compris nouvelles mesures, maintenances, prédictions et recommandations. Si une donnée étrangère au jeu dépend d'une ligne du jeu, bloquer l'opération plutôt qu'autoriser une cascade.
4. Présenter un plan nominatif et des compteurs de suppression limités aux 36 lignes identifiées, puis obtenir l'autorisation avant toute suppression. Prévoir l'ordre enfants puis parents, dans une transaction, sans cascade non inventoriée, TRUNCATE ou remise à zéro des séquences.
5. Contrôler que les données étrangères restent identiques après l'opération approuvée. Si elles subsistent, le chargement initial actuel reste volontairement bloqué ; toute évolution permettant un rechargement dans une base non vide devra être validée, sans vider la base pour contourner ce refus.

Aucune commande DELETE n'est fournie et aucun scénario UI 4.7.4 n'est commencé.

## Résultats d'exécution

Le chargement réel a été effectué exclusivement dans `industrial_predict_dev`, avec `ui47_app`, après le contrôle documenté des huit tables vides. Il s'agit d'insertions SQL réelles du jeu fictif, et non d'une simulation HTTP.

| Table | Après le premier passage | Après le second passage |
| --- | ---: | ---: |
| companies | 2 | 2 |
| sites | 3 | 3 |
| equipments | 4 | 4 |
| sensors | 6 | 6 |
| measurements | 18 | 18 |
| maintenance_records | 3 | 3 |
| prediction_records | 0 | 0 |
| maintenance_recommendations | 0 | 0 |

Le premier `apply` renvoie `created`, 36 insertions. Le second renvoie `unchanged`, zéro insertion. Les instantanés complets des lignes, leurs empreintes, identifiants, horodatages et les états des huit séquences sont identiques après les deux passages. Aucun UPDATE, DELETE, TRUNCATE ou changement de schéma n'a été exécuté sur PostgreSQL.

Empreinte de la fixture chargée :

```text
5ec44cc118bb4978d7d2d9c9238d6ee1a6fa606bc14514fdec06f054db46731b
```

Les neuf clés étrangères ne présentent aucun orphelin. Aucun code dupliqué dans les entreprises, sites, équipements ou capteurs. Objets, colonnes, contraintes, index, propriétaires, ACL, rôles, appartenances et version Alembic sont identiques à la structure validée UI 4.7.2.1. Le compte applicatif reste non superutilisateur, sans DDL.

Les 60 GET ont tous répondu en 200, avec le marqueur `local-development`, directement sur 8001 et via le proxy 4201. Contrôles effectués sur les deux chemins :

- Listes des six entités créées, compteurs et références.
- Sites de l'entreprise A : deux ; sites de B : un. Pagination des sites A à une ligne par page : deux pages distinctes, total conservé.
- Recherche entreprise par code et recherche du site logistique dans l'entreprise A.
- Équipements filtrés par site : deux en production, un en logistique et un en énergie. Le contrat liste équipements ne comporte pas de filtre `company_id` ; aucun filtre fictif de ce nom n'est utilisé.
- États maintenance/critical et capteur inactive, avec les paramètres réellement supportés.
- Trois mesures par capteur ; microsecondes `.123456Z` conservées par les réponses.
- Liste paginée des mesures sur `[14 octobre 08:00 UTC, 15 octobre 08:00 UTC[` : une mesure par capteur testé, confirmant le début inclus et la fin exclue de cet endpoint.
- Une maintenance planned, une in_progress et une completed, avec les filtres serveur existants.

Pour la période Dashboard fixe, A retourne deux sites, trois équipements, quatre capteurs et douze mesures ; B retourne un site, un équipement, deux capteurs et six mesures. A présente deux maintenances ouvertes et une terminée ; B aucune. Ces contrôles vérifient le filtrage métier existant, sans démontrer une autorisation multi-entreprises.

Tests exécutés séquentiellement :

- 16 tests du seed réussis, sur SQLite en mémoire avec les modèles et schémas réels : relations avec identifiants non contigus, idempotence sans DML, données étrangères, jeu partiel, doublons, conflits, longueurs SQL, rollback et refus de cible historique.
- 10 tests du lanceur et 10 tests du proxy réussis.
- 33 tests existants de validation des schémas métier réussis, sans connexion PostgreSQL.
- Total : 69 tests réussis. Les suites Angular complètes et le build production ne sont pas relancés pour cet ajout d'outillage sans changement applicatif.
- `git diff --check`, espaces, tirets simples, liens internes et contrôle d'absence des secrets privés dans les fichiers ajoutés : conformes.

Les bases `industrial_predict` et `industrial_predict_restore_ui471_20261017t121921z` ont des manifestes intégralement identiques avant/après, y compris données, références métier, séquences et structure. PETROSEN et le site historique `id=3` sont préservés. Les lectures GET de contrôle n'ont modifié ni les lignes ni les séquences de développement.

Un contrôle de conservation du guide a initialement été interrompu par une erreur de reconstruction d'une fin de ligne dans le vérificateur. Cette comparaison a été corrigée ; aucune donnée ni fichier préexistant n'a été réparé ou écrasé pour résoudre ce problème.

## Limites et état Git final

Le jeu est fixe, petit et fictif. Il ne valide ni les calculs ML, ni les parcours de saisie POST/PATCH dans le navigateur, ni la sécurité multi-entreprises. Les valeurs de coût n'impliquent aucune devise, absente du contrat. Les dates restent fixes ; les filtres glissants du Dashboard pourront donc exclure ce jeu ultérieurement. Employer la période historique indiquée pour les démonstrations reproductibles. Le calcul courant du Dashboard, les âges et certains indicateurs d'échéance dépendent encore de l'horloge du serveur.

L'idempotence a été vérifiée sur deux exécutions PostgreSQL successives ; aucun test de charge de seeds concurrents n'est revendiqué. Les verrous restent limités à la durée de la transaction. Les avertissements `datetime.utcnow()` observés dans certaines fixtures SQLite proviennent des défauts ORM existants ; les données du seed utilisent toutes leurs dates fixes explicites. Aucun backend n'a été modifié pour les masquer.

Fichiers ajoutés :

- [demo-data.json](../infra/development/demo-data.json) ;
- [seed.py](../infra/development/seed.py) ;
- [test_seed.py](../infra/development/test_seed.py) ;
- le présent rapport.

Le [guide permanent](../infra/development/README.md) est complété par ajout d'une section seed. Ses instructions précédentes sont conservées. Les 30 autres fichiers préexistants sont identiques à leurs empreintes initiales. Aucun fichier applicatif, backend, migration, dépendance ou budget n'a été modifié pendant UI 4.7.3.

Branche finale `feature/frontend-sites`, HEAD `e8702b0`, index vide, modifications antérieures conservées. Aucun commit, push ou merge. Les preuves sont conservées hors Git sous `D:\integration\industrial-predict\development\evidence\ui-4.7.3`, notamment les deux reçus d'application, les instantanés, les contrôles GET et `final-verification.json`.

La procédure de réinitialisation reste non exécutée. Validation attendue avant UI 4.7.4.
