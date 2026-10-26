# ML 5.2 — Adaptateur local SQL → ML 3 P101

Date : 25 octobre 2026. Statut : implémentation hors base, soumise à validation
technique avant tout commit.

## 1. Référence et périmètre

Dépôt `D:/projets/industrial-predict`, branche
`feature/ml-4-p101-persistence`, HEAD attendu et conservé
`a6d87cd716d8a5a3a31ba74c19c3aea47322e074`. Arbre propre et index vide vérifiés au
départ. Référence fonctionnelle : [ML 5.1](ml-5.1-local-functional-pilot.md).

Le nouveau package prépare la chaîne **lignes Measurement SQL → manifeste validé
→ evaluate ML 3 → paire Computed**, sans persistance. Aucun moteur/session créé,
accès PostgreSQL/HTTP, infrastructure Docker, migration, bootstrap, insertion,
PredictionRecord, index d'unicité, API locale ou configuration Angular ajouté.
Aucun secret/certificat généré, entraînement, package installé, commit/push/merge/
rebase. Les seules évaluations sont synthétiques et nécessaires aux tests ciblés.

Les producteurs ML 3, détecteur statistique, contrats ML 4 et service P101 protégé
restent inchangés. ML 5.3–5.5 ne sont pas commencés.

## 2. Fichiers créés

Six fichiers nouveaux, aucun fichier suivi préexistant modifié :

| Fichier | Fonction |
| --- | --- |
| `backend/app/p101_local_demo/__init__.py` | Package opt-in sans initialisation de configuration ou infrastructure |
| `backend/app/p101_local_demo/contracts.py` | Destination locale, erreurs stables, lignes sources, mapping SQL, contexte et résultat figés |
| `backend/app/p101_local_demo/reader.py` | Cinq Tables Core de lecture, contrôles de transport/identité, SELECT bornés et adaptation pure |
| `backend/app/p101_local_demo/processing.py` | Validation du contexte, appels ML 3 et validation de la paire complète |
| `tests/p101_local_demo/test_adapter.py` | 83 cas unitaires/statiques, lignes/transport/catalogue simulés et test d'import neuf |
| `docs/ml-5.2-local-sql-ml-adapter.md` | Ce rapport |

Les modèles Company, Site, Equipment, Sensor et Measurement ont été lus, ainsi que
les Tables Core existantes. Leurs imports ORM passent par core.database : le
nouveau lecteur déclare donc une MetaData indépendante et seulement les colonnes
nécessaires à ses SELECT. Aucune PK/FK ou table serveur n'est créée par ces
déclarations. Un test AST compare les colonnes sélectionnées aux attributs des
modèles existants sans importer ces modèles. Aucune Table PredictionRecord n'est
nécessaire à cette sous-étape.

## 3. Fonctions et contrats réutilisés

- ML 3 `evaluate` et `validate_proposal`, appelant le StatisticalAnomalyDetector
  existant ; aucune réimplémentation de la décision statistique.
- ML 3 `utc_instant`, `manifest_sha256`, `finite_value`, Computed, Abstained et
  ses onze codes, Statistics et identités ASSET.
- Constantes pures `FIXTURE_SHA256` et `CALCULATION_REVISION` de ML 4.2A. Aucun
  import de app.p101_postgres, core.config, core.database, modèles ou services.
- Fixture existante `tests/p101_anomaly/fixtures/p101-temperature-v1.json`, fournie
  explicitement à l'adaptateur. Le package ne cherche ni ne charge automatiquement
  un fichier de configuration, de fixture ou de secret.

L'empreinte canonique de fixture reste
`6c8eed59fb2c8b6328899646f93b5191a88c6698be48c51a73b414ce3560dc3a` ; la révision
de calcul attendue reste `b6b4d521b9c9456c160433e9343efd48d3c0168d`. Une révision
déclarée n'est pas une authentification cryptographique du code d'exécution.

## 4. Configuration et lecture SQL préparées

### Destination locale explicite

`LocalDestination` impose le host littéral 127.0.0.1, port client 55432, base
industrial_predict_p101_local_demo, rôle p101_local_reader ou p101_local_writer,
adresse serveur IP canonique explicitement fournie, port serveur 5432, UUID
d'instance canonique non nul et révision locale au préfixe p101_local_. Aucun
défaut DEV ni mot de passe n'est contenu dans ce contrat. Les ports sont ceux du
profil ML 5.1 ; toute autre topologie exige une évolution revue du contrat.

`validate_transport` inspecte une connexion **déjà fournie** : URL et paramètres
effectifs psycopg doivent correspondre à la destination, driver postgresql+psycopg,
sslmode disable et ssl_in_use false. C'est exclusivement le profil local en clair
de ML 5.1 sur hôte de confiance ; aucun TLS/HMAC du service protégé n'est désactivé.
Toute variable PG* est refusée. DATABASE_URL est ignorée : elle n'est jamais une
source de connexion. Une connexion absente ou contradictoire est refusée avant
le premier SELECT.

L'appelant futur doit avoir déjà ouvert sa transaction. Le package n'appelle ni
connect/create_engine/sessionmaker, ni begin/commit/rollback ; il ne possède pas
le cycle de vie de la connexion. Aucune factory de connexion réelle ou CLI n'est
créée dans ML 5.2.

### Identité effective, puis sources

`read_rows(connection, destination)` effectue uniquement des SELECT :

1. Garde d'identité : base, session_user/current_user, adresse/port serveur,
   READ COMMITTED, UTF8, marqueur local_demo.environment, instance/purpose/base,
   bootstrap_closed vrai, révisions marqueur/Alembic concordantes, absence du
   schéma protégé p101_pilot, rôle limité sans membership ni propriété d'objet,
   SELECT sur sources et absence de leurs privilèges de mutation table/colonne.
2. Quatre lectures ciblées par les codes industriels P101, limitées à deux lignes
   chacune pour détecter les parents absents ou ambigus ; validation de la chaîne
   avant toute lecture des mesures.
3. Lecture du seul sensor_id validé, ordre timestamp/id, limite 13. Cette ligne
   de débordement permet de refuser un jeu supérieur à douze lignes sans transfert
   illimité. Aucun filtre good ni période ne masque une mesure invalide/excédentaire.

Le marqueur et la révision locale sont **un contrat de lecture à matérialiser
ultérieurement**, pas un schéma existant attesté. Le futur marqueur devra fournir
singleton, instance_uuid, purpose, database_name, bootstrap_closed, schema_revision ;
public.alembic_version devra exposer la révision locale approuvée. Aucun fichier
de migration n'est préparé ou appliqué ici. Une absence/incohérence provoque un
refus, sans adoption ou création automatique.

La garde simple n'est pas un audit de catalogue équivalent à ML 4 : authenticité
du transport en clair, définitions du marqueur, immutabilité de ses droits et
snapshot des sources devront être traités dans le provisionnement/contrat de
transaction futur. L'absence de commandes d'écriture dans le package ne remplace
pas la vérification des droits effectifs sur un vrai serveur.

## 5. Contrat d'entrée et reconstruction du manifeste

`SqlRows` regroupe cinq tuples de mappings : companies, sites, equipments, sensors,
measurements. Les quatre premiers doivent contenir exactement un parent ; le
dernier exactement douze mesures. Les ids sont des INTEGER PostgreSQL positifs,
distincts pour les mesures, jamais des booléens ni des ids fixés par le scénario.
Des ids identiques dans des tables différentes ne sont pas supposés interdits.

`adapt_rows(rows, reference)` est pure et vérifie :

- Fixture de référence épinglée, douze identités DEMO-M-001 à 012 ; aucun JSON
  arbitrairement modifié ne devient une nouvelle référence autorisée.
- Company/Site/Equipment/Sensor aux codes ASSET, FK réelles cohérentes, pompe
  synthétique operational/medium, capteur temperature/°C/active. Le statut
  d'équipement active est refusé, conformément à la compatibilité Angular ML 5.1.
- Douze timestamps uniques correspondant aux instants attendus, UTC normalisé à
  six décimales ; les datetime naïfs sont refusés. Les objets datetime avec fuseau
  et chaînes ISO à offset explicite sont acceptés puis canonisés.
- Valeurs SQL int/float finies, sans booléen, chaîne ou null ; qualité good et
  sensor_id réel correspondant. Aucun remplacement, interpolation ou imputation.

Chaque observation est construite avec **value et quality des lignes SQL,
timestamp de la ligne SQL canonisé et unit du capteur SQL**. Le JSON sert à
associer fixture_id et à fournir available_at et synthetic, absents des tables.
Les codes logiques proviennent du contrat ASSET après validation des codes et
rattachements réellement fournis. Le manifeste reconstruit doit retrouver
l'empreinte canonique de fixture ; une température SQL modifiée est donc refusée,
et n'est jamais corrigée par sa température JSON.

Sortie intermédiaire `AdaptedMeasurements` : manifest_json immutable contenant
les nombres issus de SQL, et `SqlIdentityMap` figé pour les quatre parents et les
douze correspondances (fixture_id, id SQL). Les lignes d'entrée ne sont pas
modifiées et l'ordre d'entrée des mesures n'est pas imposé.

`available_at` reste attesté par le scénario synthétique : aucune preuve SQL de
disponibilité temporelle industrielle n'est inventée. Ces fonctions refusent les
données hors scénario ; elles ne constituent pas une extraction généraliste.

## 6. Calcul et sortie publique

`process_rows(rows, reference, context)` réadapte et valide toujours les lignes
brutes avant calcul ; le seul type d'une dataclass ne vaut pas validation.
`CalculationContext` exige run_id UUID canonique, prepared_at à offset explicite
au moins égal aux deux cutoffs, révision de calcul épinglée et deux cutoffs exacts
dans l'ordre des cibles. Aucun appel à l'horloge ou découverte Git automatique.

`read_and_evaluate(connection, destination, reference, context)` compose le parcours :
contexte/fixture valides, garde/SELECT simulables, adaptation puis process_rows.
Aucun appel automatique à l'import, aucune écriture et aucun résultat fictif en
cas d'erreur.

Appels evaluate :

| Cible | Cutoff UTC | Dix références | Résultat obtenu dans les tests |
| --- | --- | --- | --- |
| DEMO-M-011, 65 °C | 2026-01-11T08:01:00.000000Z | DEMO-M-001 à 010 | score 0, is_alert false |
| DEMO-M-012, 70 °C | 2026-01-12T08:01:00.000000Z | DEMO-M-002 à 011 | score 1, is_alert true |

Les tests obtiennent moyenne 65 °C, écart-type d'échantillon 1 °C et seuil 3 °C.
La référence de 012 inclut 011 disponible dans le passé ; aucune cible n'est sa
propre référence. Score = indicateur d'anomalie statistique binaire, sans probabilité
de panne, apprentissage ou artefact entraîné.

La sortie `ComputedPair` contient les deux objets Computed ML 3 originaux, dans
l'ordre 011/012, et le mapping SQL séparé. Les propositions conservent leurs ids
logiques ; aucun id de prédiction ou champ de persistance n'est attribué.
validate_proposal est réutilisée, puis sont contrôlés cibles, références,
empreintes, contexte et cohérence Statistics/détails. Les onze Abstained, tout
objet absent/incomplet/dupliqué ou Computed incohérent provoquent une erreur
explicite pour l'ensemble du lot. Aucun premier résultat partiel n'est retourné.

Erreurs `LocalDemoError` à code stable : DESTINATION_REJECTED,
SQL_SNAPSHOT_REJECTED, FIXTURE_MISMATCH, CALCULATION_CONTEXT_REJECTED,
COMPUTED_PAIR_REQUIRED. Les exceptions du driver/calcul ne sont pas réexposées
avec leurs paramètres, DSN ou valeurs sensibles.

## 7. Tests réellement exécutés

Après revue statique et stabilisation, une seule passe ciblée :

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
backend/.venv/Scripts/python.exe -B -m pytest tests/p101_local_demo -x -q -p no:cacheprovider
```

**Résultat : 83 tests réussis en 9,15 s, aucun échec.** Aucun test backend complet,
ML 4 ou frontend relancé. Les évaluations ML 3 sont uniquement celles du nouveau
parcours synthétique et des cas unitaires nécessaires.

| Couverture | Preuve hors base |
| --- | --- |
| Nominal | Six SELECT observés sur un double, douze mesures vers deux vrais appels evaluate synthétiques ; scores, références, statistiques et mapping attendus |
| Sources invalides | Mesure manquante/excédentaire, qualité/unité/valeur modifiée, doublons, dates naïves/incohérentes, nombres non finis, bool/string/null, mauvais ids/codes/parents/statuts refusés avant evaluate |
| Référence | Modifier simultanément le JSON et la valeur SQL ne légitime pas la nouvelle fixture ; empreinte épinglée refusée |
| Mapping | Ordre inversé et ids SQL différents acceptés avec correspondance correcte ; aucune dépendance aux ids des fixtures de tests |
| Contexte | Cutoffs manquants/inversés/incorrects, mauvaise révision, mauvais UUID ou date de préparation refusés |
| Sorties ML | Chacun des onze codes d'abstention sur la deuxième cible annule la paire ; None, cible dupliquée, statistiques/références/empreinte incohérentes refusés |
| Immutabilité | Entrées inchangées ; identité des Computed retournés conservée ; copies details modifiables sans modifier la proposition ; champs figés |
| Destination | Déclarations DEV/protégées/distantes ou implicites, transport/rôle/version/UUID incorrects et mauvais marqueur refusés avant lecture des sources |
| Lecture SQL | Compilation dialecte PostgreSQL, paramètres bornés, SELECT uniquement, absence de filtre quality/période cachant des données |
| Import neuf | Sous-processus Python sans core.config/core.database/models/services/protected imports ; constructeur moteur, connexion et ouverture .env interdits, aucun réseau |
| Erreurs | Exceptions contenant une sentinelle fictive remplacées par les erreurs stables sans fuite de leur texte |

Les tests interdisent Engine.connect/raw_connection, Connection.execute/
exec_driver_sql, Session.execute/flush/commit, psycopg.connect et connexions/
résolutions socket. Les SELECT du lecteur sont enregistrés par une classe simulée,
sans connexion SQLAlchemy réelle. Le sous-processus d'import est aussi instrumenté
contre les effets de bord ; les modèles sont lus uniquement via AST.

**Ces tests ne valident aucun serveur PostgreSQL, privilège réel, transaction,
snapshot, catalogue ou disponibilité d'infrastructure.** Aucune persistance,
atomicité d'écriture, unicité concurrente ou intégration Angular n'est revendiquée.

## 8. Suite et protections conservées

ML 5.3–5.5 devront préparer puis faire autoriser séparément : nouvelle instance,
connexion/factory et configuration privée explicites ; migration générale/locale
et contrat du marqueur ; bootstrap des quatre parents/douze mesures ; verrou/
immutabilité des sources ; insertion transactionnelle, unicité et résolution
des retries ; API reader/GET puis proxy et validation Angular.

Avant le premier SELECT réel, vérifier la destination Docker/SQL, les deux ports,
le rôle, le marqueur, les privilèges et la révision installée, sur la seule instance
locale indépendante. Les limites 13/2, le rendu des requêtes et les types psycopg
doivent être confrontés au vrai serveur. L'adaptateur ne crée rien pour satisfaire
sa garde si un prérequis manque.

ML 4 et ses protections TLS/HMAC/catalogue/registre sont intégralement conservés,
sans exception ajoutée. Le profil local en clair ne résout pas TLS-01, R04–R05,
R08–R09 ni les validations serveur restantes de R01–R03/R06–R07. Les tests I01–I12
du service protégé restent non commencés. La démonstration n'est pas un déploiement
industriel ni une preuve de séparation multi-tenant.

| Réserve | État après ML 5.2 |
| --- | --- |
| B-PRE-01 | Ouverte : destination locale contrôlée hors base ; aucune autorisation multi-tenant |
| B-PRE-02 | Ouverte : score P101 binaire validé, producteurs génériques inchangés |
| B-PRE-03 | Ouverte : dates/cutoffs validés sur fixture, available_at absent du SQL réel |
| B-PRE-04 | Ouverte : rattachements simulés contrôlés, aucune preuve des FK/verrous réels |
| B-PRE-05 | Ouverte : propositions ML 3 validées ; aucun mapping JSON de persistance nouveau |
| B-PRE-06 | Ouverte : cascades et conservation d'historique non modifiées |
| B-PRE-07 | Ouverte : aucune mesure réelle de snapshot, pagination ou performance |
| B-PRE-08 | Ouverte : aucun commit ni service d'écriture implémenté dans cette étape |
| B-PRE-09 | Ouverte : raccordement de lecture préparé, aucune alimentation de l'historique |
| B-PRE-10 | Ouverte : empreintes déclarées contrôlées, provenance/identité serveur non attestées |
| B-PRE-11 | Ouverte : aucune nouvelle route, API ou GET exécuté |

## 9. État Git final

Branche et HEAD conservés ; index vide. Six fichiers nouveaux uniquement, aucun
fichier suivi préexistant modifié. Contrôles finaux conformes : six ajouts attendus,
`git diff --check` et contrôle `git diff --no-index --check` de chaque nouveau
fichier sans erreur d'espacement ; recherche de motifs de secrets/DSN sans résultat,
valeurs des tests fictives et onze réserves ouvertes conservées. Aucune indexation
ni aucun commit.

**En attente de validation technique avant tout commit. Aucune persistance ou
infrastructure de ML 5.3–5.5 n'est autorisée implicitement par cette livraison.**
