# ML 5.5A — API locale reader et page Angular Prédictions

## 1. Référence et périmètre

Branche : `feature/ml-4-p101-persistence`.
HEAD attendu et conservé : `ac8e92b58cfa97a899a27d7019c0cac522dda61d`.
Arbre propre et index vide au départ. Références : ML 5.1, ML 5.2, ML 5.3A,
ML 5.4A et les résultats SQL de ML 5.4B.

Le profil de lecture est préparé pour afficher les deux prédictions déjà
persistées, sans recalcul. La dernière preuve ML 5.4B portait sur les IDs 1 et 2,
mesures 11 et 12, scores 0 et 1, avec identical_retry. Ces constats historiques
n'ont pas été réinterrogés dans cette mission.

**Aucun serveur, HTTP, navigateur, PostgreSQL ou Docker contacté pendant ML 5.5A.
Aucune écriture de données, migration, modification de secret ou calcul ML.**
Les tests appellent les fonctions directement avec des lignes SQL simulées.

## 2. Inventaire examiné et choix de réutilisation

Les routeurs génériques companies, sites et equipment importent get_db depuis
`app.core.database`. Ce module importe settings, charge la configuration globale
avec possibilité de .env, et crée engine/SessionLocal à l'import. Le routeur
equipment importe aussi les services de santé, RUL et recommandations et expose
des POST de calcul. Importer ces routeurs avant de remplacer get_db initialise
donc déjà le chemin de connexion générique.

La réutilisation directe de ces handlers n'est pas compatible avec l'isolation
requise sans refactoriser le backend générique. Aucun remplacement global de
DATABASE_URL, de settings ou de module importé n'est employé. Les sept handlers
locaux sont minces et conservent les contrats GET nécessaires à la page.

Réutilisations effectives : FastAPI, CompanyRead, SiteRead, EquipmentRead,
PredictionRecordRead, Page, build_page, enums de filtres, configuration locale,
gardes de connexion/identité corrigées, validation des sources par adapt_rows et
de la fixture par son empreinte. Les imports app.core.enums/app.core.pagination
sont purs ; app.core.config et app.core.database sont exclus et bloqués dans le
test d'import neuf. Les schémas existants ne créent pas de moteur.

Angular reste inchangé : ReferenceDataApiService, PredictionsListFacade,
PredictionReferenceCatalog, PredictionsApiService, PredictionRead et la page
Prédictions sont réutilisés. La façade relit équipement, site et entreprise par
ID et vérifie leurs rattachements avant de demander l'historique.

PredictionRead exige quatorze clés, y compris les champs nullables. La page
affiche anomaly comme « Indice d'anomalie », sans pourcentage. La présentation
de probabilité est réservée à failure_risk et à son champ explicite ; aucun
score P101 n'est converti en probabilité.

## 3. Fichiers créés

Huit nouveaux fichiers ; aucun fichier suivi existant modifié.

| Fichier | Rôle |
| --- | --- |
| `backend/app/p101_local_demo/api_reader.py` | Validation préalable, connexion exclusivement reader, transaction read-only avec rollback et erreurs typées |
| `backend/app/p101_local_demo/api_reads.py` | SELECT Core bornés, validation du profil figé, sélection des références et historique filtré/paginé |
| `backend/app/p101_local_demo/api.py` | Factory explicite FastAPI et sept routes GET seulement |
| `backend/app/p101_local_demo/serve_api.py` | Lanceur futur sur 127.0.0.1:8001, configuration et UUID explicites, option --serve obligatoire |
| `frontend/proxy.p101.conf.json` | Proxy distinct /api/v1/** vers 127.0.0.1:8001, sans fallback DEV |
| `frontend/scripts/serve-p101.ps1` | Lanceur futur Angular existant sur 127.0.0.1:4201 avec ce proxy |
| `tests/p101_local_demo/test_api.py` | Tests hors serveur, sans client HTTP ni requête ASGI |
| `docs/ml-5.5a-local-predictions-api.md` | Présent rapport |

Les fichiers Angular src/, angular.json, package.json et proxy.conf.json
habituels restent intacts. Aucun changement aux producteurs ML, services ML 4,
migrations, conteneurs, secrets ou au serveur DEV. Aucun package ajouté.

## 4. Routes réellement enregistrées par la factory

| Méthode / chemin | Paramètres pertinents | Réponse existante réutilisée |
| --- | --- | --- |
| GET /api/v1/companies | page, page_size, search | Page[CompanyRead] |
| GET /api/v1/companies/{company_id} | ID positif | CompanyRead |
| GET /api/v1/sites | page, page_size, company_id, search | Page[SiteRead] |
| GET /api/v1/sites/{site_id} | ID positif | SiteRead |
| GET /api/v1/equipments | page, page_size, site_id, status, criticality, search | Page[EquipmentRead] |
| GET /api/v1/equipments/{equipment_id} | ID positif | EquipmentRead |
| GET /api/v1/equipments/{equipment_id}/predictions | page, page_size, prediction_type, level, is_alert, start_time, end_time | Page[PredictionRecordRead] |

Pagination : page >= 1, page_size entre 1 et 100 ; defaults 1/20, pages calculées
par le helper existant. Les catalogues Angular demandent 50 éléments par page.
Les filtres booléens conservent false ; dates avec offset et bornes inclusives,
égalité début/fin autorisée, période inversée refusée. Tri prédictions :
predicted_at DESC, id DESC, identique au repository existant.

Le profil étant figé, les SELECT de références sont bornés à deux lignes par
parent et treize mesures. Exactement un parent de chaque type et douze mesures
doivent correspondre à la fixture ; un excédent ou une divergence provoque un
refus. Aucun ID SQL n'est codé en dur. Les références inconnues renvoient 404 ;
les filtres de parent qui ne correspondent pas produisent une page vide.

L'historique est borné à trois lignes pour exiger les deux prédictions du profil.
Les quatorze champs, versions, scores/alertes, dates, rattachements et enveloppe
JSON locale sont contrôlés avant filtrage. Une donnée incohérente ne disparaît
donc pas derrière un filtre. La réponse conserve les données stockées, sans
modifier leurs IDs, created_at ou détails. Les filtres légitimes peuvent donner
une page vide ; une page hors plage conserve total/pages avec items vide.

La recherche des références est une sous-chaîne littérale insensible à la casse
sur name/code, appliquée au petit profil en mémoire. Elle n'interprète pas % et _
comme wildcards SQL, contrairement à certains repositories génériques. Les
options nécessaires à la sélection P101 restent compatibles avec Angular.

OpenAPI HTTP, Swagger, ReDoc et health ne sont pas exposés. Aucun routeur complet
n'est monté. Un middleware refuse les méthodes autres que GET, y compris
HEAD/OPTIONS, avant accès aux données. Aucune route de calcul, écriture, capteurs,
mesures, dashboard ou recommandations n'est ajoutée. Les autres pages du frontend
ne constituent pas un parcours pris en charge par cette API de démonstration.

## 5. Configuration, lecture seule et sécurité

create_app reçoit obligatoirement des SetupSettings valides avant les imports
FastAPI/schémas/lectures. L'import seul ne charge ni configuration privée, moteur
ou connexion. Le lanceur valide le JSON privé explicite, le rôle reader et
l'acquittement --serve/--instance avant de construire l'application.

Chaque requête utilise uniquement p101_local_reader. Pas de DATABASE_URL, .env,
PGSERVICE ou PG* implicite, ni d'option de rôle writer/admin. La factory reçoit
host/port/base séparément et utilise uniquement reader.password par référence
privée. Les paramètres sont masqués et echo désactivé.

SQL : postgresql+psycopg, destination locale ML 5.3A validée, sslmode=disable
explicite, UTC, READ COMMITTED, search_path pg_catalog, connect_timeout 5 secondes,
default_transaction_read_only=on dès la connexion. NullPool ferme les connexions
par requête. La transaction est annulée même après un GET réussi ; aucun commit.

Avant lecture métier : gardes existantes du transport et de l'identité effective,
cluster, base, rôle de session/effectif, IP/port serveur, marqueur/UUID/révision,
bootstrap fermé, absence du schéma protégé, rôle limité sans membership et sources
immuables. La garde locale exige aussi fixture SHA conforme, owner NOLOGIN et
SELECT sans privilèges de mutation sur prediction_records, y compris de colonne.

Les cinq tables sources sont relues et leur manifeste vérifié par adapt_rows ;
cette canonisation/empreinte n'est pas une inférence. Aucun import du moteur
p101_core, de processing, prediction_persistence ou run_predictions n'est
nécessaire à l'API. Aucun evaluate, INSERT, mise à jour ou recommandation ne peut
être déclenché par les handlers préparés.

HTTP futur : uvicorn fixé à 127.0.0.1:8001, proxy_headers=False, server_header=False,
access_log=False ; TrustedHost autorise seulement 127.0.0.1. Aucun CORS nécessaire
pour le parcours via le proxy Angular, qui garde le navigateur sur la même origine.
Il s'agit d'un profil local de confiance, sans authentification multi-utilisateur.
Le choix de transport local non TLS ne modifie aucune protection ML 4.

Erreurs : 404 référence absente, 422 requête/période invalide, 503 lecture ou donnée
persistée incohérente. Le texte des erreurs SQL, paramètres, DSN et secrets n'est
pas transmis au client. Aucun élargissement de privilèges ni réparation automatique.

## 6. Tests réellement exécutés

Commande ciblée, sans HTTP, navigateur ou serveur :

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
$env:PYTHONDONTWRITEBYTECODE = '1'
& backend/.venv/Scripts/python.exe -B -m pytest tests/p101_local_demo/test_api.py -q -p no:cacheprovider
```

Première exécution : 52 réussites et un échec du test statique de libellé Angular,
dû à la lecture du fichier UTF-8 avec l'encodage Windows implicite. Lecture du test
corrigée en UTF-8 ; aucun fichier TypeScript modifié. La revue a également séparé
les erreurs de données des erreurs de référence/filtre et ajouté deux cas ciblés.

**Dernière exécution : 55 tests réussis en 4,98 s, aucun échec.** Aucun test ML,
PostgreSQL, suite backend complète, build Angular ou test navigateur lancé.

| Couverture | Preuve hors serveur |
| --- | --- |
| Routes | Exactement sept GET, OpenAPI inspecté en mémoire, quatorze propriétés PredictionRecordRead et filtres Angular |
| Sélection | Catalogues paginés, détails par ID, rattachements Company → Site → Equipment, mauvaises références |
| Historique | Deux lignes stockées simulées, scores 0/1, alertes false/true, modèle/version et détails locaux |
| Filtres | Anomaly/autres types, niveau, alertes false/true, bornes inclusives égales, périodes invalides, pages vides/hors plage |
| Données refusées | Lot partiel/dupliqué, mauvais score/alerte/équipement/UUID, JSON non fini ou incomplet, mapping, unité ou mesure divergente |
| Reader | Destination DEV/port/host invalides, rôles non reader, PG* implicite, UUID/marqueur/rôle/port/révision effectifs incorrects |
| Transaction | Session read-only exigée, rollback/fermeture/dispose en succès et erreur ; aucun commit |
| Actualisation | Deux appels directs identiques aux handlers ; sources et réponses inchangées ; instructions SELECT uniquement |
| Méthodes | Rejet direct du middleware pour POST/PUT/PATCH/DELETE/HEAD/OPTIONS sans dispatch de dépendance |
| Imports | Sous-processus instrumenté : construction app sans moteur, réseau, imports DEV, services génériques, ML 4 ou calcul ML |
| Exécution dédiée | Proxy 8001, lanceurs loopback 8001/4201, proxy DEV 8000 conservé, acquittement de lancement obligatoire |

Les tests bloquent les connexions SQLAlchemy/psycopg, sockets et démarrage uvicorn.
Les handlers, modèles de réponse et générateurs de connexion sont appelés
directement ; aucun TestClient, client HTTP/ASGI ni socket serveur. Les méthodes
refusées du middleware sont évaluées comme coroutines sans boucle réseau.
Les fixtures de prédictions sont des lignes simulées déclarées, sans evaluate.

**Aucune preuve de connexion reader PostgreSQL réelle ni de sérialisation HTTP,
proxy effectif, rendu navigateur, liaison réelle des ports ou absence d'impact
sur une navigation réelle n'est revendiquée.** Les détails sont contrôlés comme
enveloppe et profil ; le GET ne refait pas la validation mathématique du calcul
ou l'attestation cryptographique des empreintes de contenu.

## 7. Démonstration future : procédure non exécutée

Après validation technique et commit séparément autorisé : recontrôler Git,
mémoire, disponibilité des ports 8001/4201, P101 running et publié seulement sur
127.0.0.1:55432, secrets/ACL inchangés, révision locale, owner fermé et deux
prédictions conformes. Aucune nouvelle infrastructure ou prédiction nécessaire.

Dans un premier terminal à la racine, avec les valeurs privées déjà approuvées :

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
$env:PYTHONDONTWRITEBYTECODE = '1'
# $P101Instance provient du fichier privé approuvé ; ne pas inventer un UUID.
& backend/.venv/Scripts/python.exe -B -m app.p101_local_demo.serve_api --config D:/P101Private/settings.json --instance $P101Instance --serve
```

Dans un second terminal à la racine :

```powershell
& ./frontend/scripts/serve-p101.ps1
```

Le script emploie exclusivement le CLI Angular local déjà installé, sans npx,
installation ou téléchargement automatique. Il passe le proxy dédié explicitement
et conserve les options DEV habituelles dans leurs fichiers d'origine.

Après autorisation des accès HTTP/navigateur, contrôler les sept GET, les filtres,
les statuts négatifs et les réponses à quatorze champs. Ouvrir directement
`http://127.0.0.1:4201/predictions` pour éviter la redirection racine vers le
dashboard, hors du périmètre de cette API. Sélectionner les références synthétiques
ou utiliser l'URL avec les IDs SQL réellement vérifiés, sans les supposer fixes.

Vérifier les deux lignes (normal 0/false, anomalie 1/true), le modèle/version,
les motifs synthétiques, le JSON et les dates de janvier 2026. Ne pas appliquer
un filtre temporel récent qui masquerait ces prédictions historiques. Tester
alerte true/false, pagination et actualisation. Le réseau navigateur doit rester
sur 4201 pour /api/v1, relayé vers 8001, sans requête vers les API DEV.

Les routes d'écriture doivent être absentes/refusées, sans exécuter de calcul.
Relever avant/après les comptages et empreintes des sources/prédictions via une
lecture P101 autorisée séparément : toujours douze mesures et deux prédictions,
mêmes ids, created_at et détails. Contrôler aussi l'état des deux instances DEV
par Docker uniquement. Aucun rattrapage par recalcul, seed ou nouvelle insertion.

## 8. Réserves et Git

Toutes les réserves B-PRE-01 à B-PRE-11 restent ouvertes pour le produit général.
En particulier : autorisation multi-tenant absente (01), sémantique des producteurs
génériques inchangée (02), available_at synthétique (03), nouvelles lectures/FK et
JSON à confronter au serveur (04–05), cascades inchangées (06), performance de la
relecture bornée à mesurer (07), transaction reader réelle non vérifiée ici (08),
aucune alimentation d'historique ajoutée (09), provenance non authentifiée (10),
lecture limitée au profil local sans nouvelles routes génériques détail/latest (11).
TLS-01 et les validations restantes du chemin ML 4 ne sont pas clôturées.

État final : huit fichiers nouveaux uniquement, aucun fichier suivi existant
modifié, index vide, branche et HEAD conservés. Contrôles d'espacement sur le suivi
et chacun des nouveaux fichiers sans indexation, recherche de secrets/DSN sans
secret réel. Aucun serveur, accès SQL/HTTP, changement Docker ou commit.

**En attente de validation technique avant commit et démonstration réelle.**
