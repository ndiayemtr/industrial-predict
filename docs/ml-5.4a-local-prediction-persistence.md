# ML 5.4A — Calcul et persistance locale P101 préparés

## 1. Référence, périmètre et résultat

Branche vérifiée : `feature/ml-4-p101-persistence`.
HEAD attendu et conservé : `810877715edbaf84c18d7f8bca1eeac7a9db41be`.
Arbre propre et index vide au départ. Références : ML 5.1, ML 5.2, ML 5.3A,
contrats ML 3 et migration locale `p101_local_0001`.

Le traitement futur Measurement PostgreSQL → ML 3 → deux Computed → deux
PredictionRecord est implémenté et testé hors base. **Aucune connexion PostgreSQL,
lecture des fichiers privés réels, insertion réelle, commande Docker, migration,
modification de données ou exécution du nouveau lanceur n'a eu lieu ici.** Les
seuls calculs effectués sont les évaluations synthétiques des tests ciblés.

Les preuves SQL d'initialisation ML 5.3B restent celles de l'étape précédente ;
elles ne valent pas validation réelle du nouveau service de persistance.

## 2. Fichiers créés

Cinq nouveaux fichiers, aucun fichier préexistant modifié :

| Fichier | Responsabilité |
| --- | --- |
| `backend/app/p101_local_demo/prediction_mapping.py` | Validation pure du lot, clés et contenu canoniques, mapping, reconstruction des lignes existantes, contrats de résultat/erreur |
| `backend/app/p101_local_demo/prediction_persistence.py` | Table Core indépendante, garde writer, verrou, lecture/calcul, comparaison et INSERT groupé dans une transaction fournie |
| `backend/app/p101_local_demo/run_predictions.py` | CLI explicite distinct de setup ; aucun effet à l'import, acquittement obligatoire |
| `tests/p101_local_demo/test_predictions.py` | Tests synthétiques purs et simulations de transactions sans PostgreSQL |
| `docs/ml-5.4a-local-prediction-persistence.md` | Présent rapport |

Aucun changement au moteur ML 3, aux producteurs génériques, à PredictionService,
aux modules protégés ML 4, aux migrations, à Angular, à Docker ou aux secrets.
Aucun package ajouté.

## 3. Réutilisation et contrats publics

`read_and_evaluate` ML 5.2 reste l'unique raccordement SQL → evaluate : douze lignes
Measurement réellement lues et validées, adaptation du manifeste, puis les deux
évaluations ML 3. Aucun remplacement silencieux d'une valeur SQL par le JSON.
Le JSON approuvé reste la référence d'intégrité et des métadonnées synthétiques.

`prepare_predictions(pair, destination, reference, context, created_at)` est pur :
il exige deux Computed distincts, jamais une abstention, avec cibles 011/012,
contexte commun, versions et révision approuvées, références temporelles et
empreintes exactes. Le mapping des douze ids Measurement est complet, entier,
positif et sans doublons ; aucun identifiant SQL industriel n'est inventé.
Le résultat est un tuple de deux PredictionPlan immuables. `sql_values()` fournit
une nouvelle copie des treize valeurs à insérer ; l'id reste alloué par PostgreSQL.

La validation réutilise validate_context, validate_fixture, project_content et
les validations de proposition ML 3 transitivement appelées par ce dernier.
build_key/IdempotencyTuple et canonical_projection sont réutilisés comme fonctions
pures de ML 4.2A. Aucune DestinationDeclaration sandbox fictive ni autorisation
ML 4 n'est construite pour le profil local.

`persist_in_transaction` exige une connexion writer déjà transactionnelle et
ne possède aucun commit ou rollback interne. `run_predictions` est l'entrée
opérationnelle : SetupSettings et CalculationContext typés, configuration privée
explicitement fournie, une seule transaction fraîche via la factory existante.
Le résultat n'est rendu qu'après la sortie réussie du contexte transactionnel.

PersistenceResult expose `inserted` ou `identical_retry` et les quatorze champs
des deux lignes. Les dates sont représentées en UTC à six décimales dans le
résultat JSON ; les valeurs destinées à SQL sont des datetime avec fuseau.
Les copies retournées ne permettent pas de modifier les propositions ML 3.

## 4. Mapping des quatorze champs

| Champ PredictionRecord | Origine et validation |
| --- | --- |
| id | Entier réel obtenu par RETURNING ; conservé lors d'un retry |
| equipment_id | Mapping SQL validé du P101 synthétique |
| sensor_id | Mapping SQL validé du capteur température |
| measurement_id | Correspondance réelle de DEMO-M-011 ou DEMO-M-012 |
| prediction_type | anomaly, proposition ML 3 validée |
| score | 0/1, booléen refusé en tant que nombre ; Float SQL 0.0/1.0 accepté à la relecture |
| level | null |
| is_alert | Booléen strict correspondant au score |
| model_name | statistical_deviation |
| model_version | p101-stat-v1 |
| horizon_hours | null |
| details | Enveloppe locale bornée décrite ci-dessous |
| predicted_at | Date canonique de la cible, 11 ou 12 janvier 2026 à 08:00 UTC |
| created_at | UTC de la première tentative persistée, non antérieur à prepared_at ; valeur originale conservée au retry |

Le CLI utilise le même instant UTC de début pour prepared_at et created_at des
deux lignes. Ce n'est pas une horloge serveur ni une preuve de l'instant du commit.
La comparaison des lignes existantes valide aussi id, created_at, la cardinalité,
les noms des quatorze champs et la cohérence du contexte commun du lot.

details contient exactement schema_version=`p101-local-demo-details-v1`,
synthetic=true, reason, calculation et local_demo. calculation conserve les
détails ML 3 inchangés, dont producer.revision_status. local_demo contient
instance_uuid, adapter_version=`p101-local-persistence-v1`, idempotency_key,
content_sha256 et sql_mapping (quatre parents et douze correspondances).

bounded_details vérifie l'enveloppe finale : 6 000 octets UTF-8, six niveaux de
conteneurs, chaînes de 240 caractères maximum et nombres finis. Le CHECK SQL
local impose aussi son sous-ensemble de forme, champs non nuls et score cohérent ;
la validation applicative demeure nécessaire et plus restrictive.

Le score est un indicateur statistique binaire, sans probabilité de panne,
entraînement ou modèle appris. Attentes synthétiques testées : 011 → 0/false,
012 → 1/true.

## 5. Transaction, destination et droits

Le lanceur utilise exclusivement p101_local_writer via la factory explicite ML
5.3A : aucune URL globale, aucun .env DEV, aucun ORM ou import de modèle applicatif.
Les gardes existantes conservent les vérifications de transport, base, IP/port,
cluster, rôle effectif, UTF8 et READ COMMITTED. Les deux requêtes d'identité
réutilisent la correction host(inet_server_addr()).

La garde writer additionnelle exige : rôle writer et révision locale exacts,
identité ML 5.2 et sources immuables pour ce rôle, bootstrap fermé, empreinte de
fixture attendue et empreinte de bootstrap bien formée, owner NOLOGIN sans session
restante, SELECT/INSERT sans UPDATE/DELETE sur les prédictions, marqueur immuable,
index UNIQUE local valide et CHECK local validé.

Ces contrôles de catalogue locaux vérifient présence/état des objets approuvés,
pas une certification exhaustive de leurs définitions et des propriétaires comme
le profil ML 4. Les sources restent soumises à la validation effective ML 5.2.

Ordre prévu dans l'unique transaction :

1. Garde de destination puis garde writer.
2. Verrou advisory exclusif 1010053, commun au provisionnement local.
3. Lecture et validation des douze mesures, deux appels ML 3 via read_and_evaluate.
4. Validation du lot et construction des deux mappings complets.
5. Lecture bornée à trois prédictions pour détecter un état excédentaire.
6. Zéro ligne : un seul INSERT multi-lignes avec RETURNING des quatorze champs,
   puis validation complète des lignes retournées, avant commit.
7. Deux lignes : comparaison stricte et retour des lignes originales, sans écriture.
8. Toute autre cardinalité ou divergence : rejet ; sortie transactionnelle avec rollback.
9. Un seul commit à la sortie normale du contexte ; succès exposé seulement ensuite.

Le profil est volontairement limité à deux prédictions dans cette base locale.
Une autre ligne/version/équipement dans prediction_records entraîne un refus,
sans suppression, adoption ou réparation automatique. Le service ne contacte
aucune route, ne produit aucune recommandation et ne modifie aucune mesure.

## 6. Retry, conflits et concurrence

La clé p101-idempotency-v1 reprend UUID d'instance, fixture/référence, cible,
dates, cutoff, méthode et révision. Run_id, prepared_at, created_at et ids SQL
alloués n'en font pas partie. Le contenu métier canonique inclut en revanche les
rattachements SQL sources et la version du raccordement, en plus du contenu
logique projeté. Unicode NFC, nombres et dates sont canonisés par les fonctions
existantes, JSON compact à clés triées et SHA-256.

Les détails d'une tentative antérieure sont reconstruits en Computed et validés
contre la fixture approuvée. Les clés et contenus sont recalculés ; les chaînes
canoniques sont comparées, pas seulement les hashes. Les empreintes stockées,
le reason, l'enveloppe, les ids et toutes les métadonnées doivent correspondre.
Les deux lignes stockées doivent partager leur contexte initial et created_at.

Un nouveau run_id ou prepared_at n'altère pas le contenu métier : un retry
identique retourne les ids, created_at et détails initiaux sans UPDATE. Un
changement de cutoff, référence, rattachement, score ou métadonnée n'est jamais
adopté silencieusement. Les valeurs stockées invalides sont rejetées.

L'index UNIQUE partiel existant reste le filet SQL sur equipment_id, sensor_id,
measurement_id, model_name, model_version pour anomaly/statistical_deviation/
p101-stat-v1. Aucun ON CONFLICT DO NOTHING/UPDATE. Une erreur SQLSTATE 23505
produit un code stable et annule le lot ; aucune nouvelle connexion automatique.
Une éventuelle reprise nécessite une nouvelle transaction autorisée et gardée.

Si le traitement est terminé mais que la sortie transactionnelle échoue, le
résultat est classé COMMIT_UNCERTAIN_INSPECT_BEFORE_RETRY. Aucun succès ni rollback
garanti n'est affirmé après perte de réponse ; la relecture des deux clés naturelles
reste nécessaire. Le lanceur ne relance jamais automatiquement une insertion.

Le verrou ne couvre que les acteurs coopérants. Un administrateur ou writer qui
l'ignore n'est pas neutralisé par ce code. Les privilèges runtime empêchent les
mutations des mesures ; une maintenance privilégiée exigerait une autre autorisation.

## 7. Tests réellement exécutés

Une seule exécution du nouveau fichier ciblé, après revue et stabilisation :

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
$env:PYTHONDONTWRITEBYTECODE = '1'
& backend/.venv/Scripts/python.exe -B -m pytest tests/p101_local_demo/test_predictions.py -q -p no:cacheprovider
```

**56 tests réussis en 5,51 s, aucun échec.** Aucun test backend complet, test SQL
réel, test frontend ou ancienne suite ML relancé.

| Couverture | Résultat hors base |
| --- | --- |
| Calcul nominal | Lignes SQL simulées → vrai read_and_evaluate/ML 3 → scores 0 et 1, alertes false et true |
| Mapping | Treize valeurs INSERT, id via RETURNING simulé, quatorze champs contrôlés ; copie des détails ML 3 inchangée |
| Lots invalides | Incomplet, abstention, cible dupliquée, statistique/version/révision/empreinte incorrecte, non-fini et mapping invalide refusés |
| JSON et stockage | Champs manquants/excédentaires, profondeur/taille, booléens numériques, mauvaises dates, ids, hashes, UUID et contenu refusés |
| Retry | Nouveau run_id/prepared_at accepté sans INSERT ; mêmes ids, created_at et détails d'origine |
| Transaction | Une connexion, un begin, un INSERT groupé et un commit ; verrou avant lecture/calcul/insertion |
| Rollback | Échec simulé de deuxième ligne, RETURNING incomplet, UNIQUE, état partiel/dupliqué et conflit : aucun commit, état conservé |
| Commit incertain | Simulation avec commit appliqué ou absent ; pas de retry automatique ; reprise explicite testée dans les deux cas |
| Destination/droits | DEV, mauvais port, reader utilisé en écriture, acquittement absent et états de garde incorrects refusés |
| Sources/imports | Valeur SQL divergente non remplacée par JSON ; propositions et sources inchangées ; import neuf sans connexion ni import DEV/protégé |

Les fixtures bloquent les connexions SQLAlchemy/psycopg, les exécutions SQLAlchemy
réelles, les sockets et les écritures ORM. Le double utilise les vraies instructions
Core compilées PostgreSQL ; il conserve son état en mémoire et simule les frontières
commit/rollback. Un sous-processus d'import est instrumenté contre toute création
de moteur et connexion. Aucune configuration privée réelle n'est chargée.

**Les mocks ne prouvent ni atomicité PostgreSQL réelle, ni concurrence, privilèges
effectifs, comportement du pilote JSON/RETURNING ou résolution réelle d'un commit
incertain.** Ces points restent à valider avant de qualifier le parcours opérationnel.

## 8. Première exécution réelle : non autorisée dans cette étape

Après validation technique et commit séparément autorisé, la future commande sera :

```powershell
# $P101Instance est l'UUID approuvé issu de la configuration privée, jamais inventé.
& backend/.venv/Scripts/python.exe -B -m app.p101_local_demo.run_predictions --config D:/P101Private/settings.json --execute --instance $P101Instance
```

Cette commande n'a pas été exécutée. Avant son autorisation : recontrôler Git,
mémoire, Docker/port loopback, destination effective, marqueur/révision, owner fermé,
privilèges et absence d'autres prédictions. Prévoir les preuves SQL avant/après des
sources, des deux nouvelles lignes et d'un retry identique. Tester séparément les
erreurs et courses sur une instance appropriée sans altérer l'historique approuvé.
Aucun raccordement API ou Angular n'est inclus dans ML 5.4A.

## 9. Limites et réserves

La révision de calcul reste une déclaration contrôlée contre la référence revue,
pas une attestation cryptographique du code en mémoire. Le profil est local,
synthétique, à acquisition figée ; available_at et fixture_id ne sont pas des
colonnes Measurement. Les casts JSON, séquences, contraintes et interruptions
réseau ne sont pas certifiés par les tests hors base. Des trous de séquence après
rollback sont acceptables. Les rôles privilégiés demeurent hors de cette protection.

Le profil local n'affaiblit ni ne remplace les protections ML 4. TLS-01 et les
réserves R01–R09 restantes de ce chemin ne sont pas clôturées par cette livraison.

| Réserve | État après ML 5.4A |
| --- | --- |
| B-PRE-01 | Ouverte : aucune autorisation multi-tenant ; opérateur local de confiance |
| B-PRE-02 | Ouverte : score binaire du seul P101 ; producteurs génériques inchangés |
| B-PRE-03 | Ouverte : disponibilité temporelle issue d'une fixture figée, pas d'acquisition réelle |
| B-PRE-04 | Ouverte : rattachements validés par l'adaptateur ; nouvelle écriture SQL non exécutée |
| B-PRE-05 | Ouverte : JSON local validé hors base, aucune correction des schémas génériques |
| B-PRE-06 | Ouverte : cascades et conservation d'historique génériques inchangées |
| B-PRE-07 | Ouverte : aucun test réel de snapshot/performance ; refus borné d'un historique hors profil |
| B-PRE-08 | Ouverte : atomicité/rollback/retry simulés, nouvelle transaction réelle non testée |
| B-PRE-09 | Ouverte : aucun historique de prédictions alimenté pendant cette mission |
| B-PRE-10 | Ouverte : hashes et révision déclarée, sans HMAC ou attestation de provenance locale |
| B-PRE-11 | Ouverte : aucune route ni intégration de lecture API/Angular modifiée |

## 10. État Git final

Cinq fichiers nouveaux uniquement, aucun fichier suivi existant modifié, index
vide, branche et HEAD conservés. Vérification git diff --check et contrôle des
nouveaux fichiers sans indexation ; recherche de secrets/DSN sans secret réel.
Seules valeurs synthétiques et sentinelles de tests figurent dans les ajouts.

**En attente de validation technique avant tout commit et avant toute première
exécution PostgreSQL réelle du traitement de prédiction.**
