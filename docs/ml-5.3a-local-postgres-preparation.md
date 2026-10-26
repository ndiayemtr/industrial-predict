# ML 5.3A — Préparation PostgreSQL local P101

## 1. Périmètre et conclusion

Branche contrôlée : `feature/ml-4-p101-persistence`.
HEAD attendu et observé : `0f2ac653f31c45a4cc7cb2885c2b87649912a588`.
Au départ : arbre propre et index vide. Références : ML 5.1, ML 5.2 et les
contrats ML 3 réutilisés par le lecteur existant.

Le Compose, la configuration explicite, le lanceur isolé de migrations et le
bootstrap synthétique sont préparés. Leur exécution nécessite une autorisation
ultérieure. **Aucun moteur Docker interrogé, réseau contacté, PostgreSQL connecté,
objet SQL créé, migration appliquée ou bootstrap exécuté pendant ML 5.3A.**
Aucune prédiction calculée ou persistée ; aucune commande de ML 5.3B exécutée.

Le profil local de confiance prévu par ML 5.1 utilise explicitement SCRAM sur
transport local en clair. Il n'appelle pas les composants protégés ML 4, ne leur
ajoute aucune exception et ne prétend pas satisfaire leurs exigences TLS/HMAC.

## 2. Fichiers livrés

Douze fichiers nouveaux ; aucun fichier suivi préexistant modifié.

| Fichier | Rôle |
| --- | --- |
| `infra/p101-local/compose.yaml` | Projet, conteneur, réseau interne et volume indépendants ; publication loopback ; image épinglée, téléchargement interdit |
| `infra/p101-local/postgresql.conf` | Nom d'instance, port interne, UTC, SCRAM, ressources limitées et transport local explicite |
| `infra/p101-local/settings.example.json` | Structure publique à compléter ultérieurement hors Git ; aucune valeur privée |
| `backend/app/p101_local_demo/setup_config.py` | Configuration stricte, chemins privés, références de secrets et rendu pur HBA/variables Compose |
| `backend/app/p101_local_demo/provisioning.py` | Factory explicite, transaction, garde effective, rôles, lancement Alembic, privilèges et fermeture owner futurs |
| `backend/app/p101_local_demo/bootstrap.py` | Plan synthétique pur, empreinte, comparaison exacte et initialisation transactionnelle future |
| `backend/app/p101_local_demo/setup.py` | CLI opérateur ; aucune opération à l'import ; acquittement obligatoire avant fichiers privés ou connexion |
| `backend/local_demo_migrations/alembic.ini` | Environnement Alembic distinct, sans URL |
| `backend/local_demo_migrations/env.py` | Connexion owner fournie, garde avant DDL, transaction externe, aucun environnement DEV |
| `backend/local_demo_migrations/versions/p101_local_0001.py` | Marqueur d'instance et contraintes locales sur PredictionRecord |
| `tests/p101_local_demo/test_preparation.py` | Tests purs, statiques et doubles de transaction/identité |
| `docs/ml-5.3a-local-postgres-preparation.md` | Présent rapport |

Les quatre fichiers ML 5.2, le moteur ML 3, les migrations générales, les modules
`app/p101_postgres`, les environnements ML 4, les services génériques et Angular
restent inchangés. Aucun package ajouté.

## 3. Isolation préparée

| Élément | Choix explicite |
| --- | --- |
| Projet Compose / cluster_name | `industrial-predict-p101-local-demo` |
| Conteneur | `industrial-predict-p101-local-demo-postgres` |
| Volume neuf | `industrial-predict-p101-local-demo-data` |
| Réseau bridge interne neuf | `industrial-predict-p101-local-demo-net` |
| Base neuve | `industrial_predict_p101_local_demo` |
| Publication hôte | `127.0.0.1:55432:5432` exclusivement |
| Rôles distincts | `p101_local_admin`, `p101_local_owner`, `p101_local_writer`, `p101_local_reader` |
| Image de référence P1 | PostgreSQL 17.10, `docker.io/library/postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317` |

Le digest est repris du rapport P1, sans nouvelle consultation de registre ni
vérification Docker aujourd'hui. `pull_policy: never`, plateforme `linux/amd64`.
L'image doit déjà être disponible et son digest vérifié avant toute création ;
son absence est une condition d'arrêt, pas une autorisation de téléchargement.

Le volume n'est ni externe ni partagé avec DEV ; aucun montage de répertoire
de données DEV, aucun seed DEV, aucun montage `docker-entrypoint-initdb.d`.
La destination de stockage PG17 est `/var/lib/postgresql/data`.
Le seul secret monté par Compose est le futur fichier privé admin, via
`POSTGRES_PASSWORD_FILE`. Le HBA et le fichier PostgreSQL sont montés en lecture
seule ; il n'existe aucun healthcheck lançant automatiquement des requêtes SQL.

L'IP et le sous-réseau sont obligatoires, sans valeur implicite. La politique
accepte un IPv4 privé /24 à /28, exclut adresse réseau, broadcast et passerelle
pour le serveur, et rejette les réseaux 172.17/16, 172.18/16 et 172.19/16 recensés
par P1. **Ce contrôle n'est pas un inventaire actuel de Docker/LAN/VPN.** Il faudra
vérifier les routes et collisions réelles avant de choisir le sous-réseau.

Les noms distincts ne prouvent pas que les ressources sont absentes aujourd'hui.
Compose peut réutiliser une ressource préexistante de même nom : au premier
provisionnement, toute collision impose un arrêt et une analyse, jamais une
réutilisation silencieuse ou un nettoyage automatique. Port 55432 à recontrôler.

## 4. Configuration privée et garde de destination

`SetupSettings` refuse champs inconnus, format incorrect, host autre que
127.0.0.1, port différent de 55432, base différente, UUID nul/non canonique,
IP/réseau incohérents et date de bootstrap non canonique. `bootstrap_at` est une
valeur UTC à six décimales choisie une seule fois et conservée aux retries.

Le JSON explicite doit se trouver dans le répertoire privé déclaré, physiquement
hors du dépôt, sans redirection de chemin. Aucune lecture de `.env`, de
`DATABASE_URL`, de configuration applicative ou ORM. Les variables libpq `PG*`
sont refusées avant création d'un moteur. Les quatre noms de fichiers de secrets
sont imposés, leurs contenus ne sont pas dans Git. Ils doivent être différents,
non vides et comporter 20 à 200 caractères, sans retour de ligne interne ni NUL.
La création de secrets aléatoires forts et les ACL privées restent des opérations
ultérieures explicitement autorisées, non effectuées ici.

`check-config` est sans connexion. Toute autre opération CLI exige ensemble
`--execute` et `--instance` égal à l'UUID déclaré. Cet acquittement est une garde
opérateur locale, pas une signature ni une autorisation ML 4.

La factory n'existe qu'à l'appel explicite : URL SQLAlchemy construite par champs,
psycopg, sslmode=disable, délai 5 s, READ COMMITTED, UTC, search_path initial
pg_catalog, echo désactivé et paramètres masqués. Sur la connexion fournie, avant
DDL/DML, la garde compare les paramètres effectifs libpq et SQL : host/port/base/
rôle, absence de SSL, rôle de session et rôle effectif identiques, IP/port serveur,
cluster_name exact, UTF8, isolation, absence de p101_pilot et de memberships.
Owner/writer/reader doivent être non privilégiés ; admin est exclusivement le
superutilisateur d'initialisation du nouveau cluster.

Après migration, UUID, purpose, base, singleton et révision du marqueur doivent
correspondre ; `public.alembic_version` doit contenir uniquement p101_local_0001.
La révision ne crée aucun identifiant industriel SQL fixe.

Ces vérifications sont préparées et testées sur des doubles, pas attestées sur un
serveur. Elles ne sont pas une authentification cryptographique d'instance.

## 5. Migrations préparées

Le nouvel environnement reçoit une connexion owner déjà engagée, contrôlée et
verrouillée. Aucun moteur construit dans env.py ; mode offline et URL alternative
refusés. Les neuf sources métier sont référencées par `version_locations`, sans
réécriture et sans exécuter `backend/migrations/env.py` :

`0468ed5be8f1 → 50e5051527dc → 656260b06cdf → 572080d9e581 →
570ce155aaf8 → 783e16aa6ce3 → 675ebfea0bb5 → d6ec01cf13b6 →
09ac8101e9fe → p101_local_0001`.

Le jeu de neuf fichiers est vérifié ; le test Alembic hors base confirme une seule
tête et dix révisions. La première application exige un schéma public sans tables,
vues ou séquences, aucun local_demo et aucune installation protégée p101_pilot.
Le lanceur vise explicitement la tête locale, dans la transaction externe, avec
search_path public,pg_catalog pour les migrations générales non qualifiées.
Un retry n'est accepté qu'avec marqueur/révision concordants ; aucune adoption
d'une base métier déjà remplie. Le downgrade local est volontairement refusé.

La révision locale prépare :

- `local_demo.environment` : singleton vrai, UUID unique, purpose/base/révision
  imposés, empreinte de fixture et état/empreinte de fermeture cohérents ;
- un marqueur initial lié à l'UUID privé, bootstrap ouvert, sans données métier ;
- `uq_local_p101_target`, index UNIQUE partiel sur equipment_id, sensor_id,
  measurement_id, model_name, model_version pour anomaly/statistical_deviation/
  p101-stat-v1 ;
- `ck_local_p101_content`, CHECK ciblé : capteur/mesure non nuls, score 0/1,
  is_alert cohérent, level et horizon nuls, details objet de 6 000 octets maximum,
  schéma p101-local-demo-details-v1, synthetic booléen vrai, reason texte non vide,
  calculation/local_demo objets, UUID exact et deux empreintes hexadécimales ;
  la condition obligatoire est enveloppée dans `IS TRUE` pour refuser NULL.

Les schémas métier et leurs cascades ne sont pas modifiés à la source. Le CHECK
ne recalcule pas les hashes, n'atteste pas le calcul et ne remplace pas le futur
mapping/validateur de persistance. Il cible seulement ce profil ; aucune garantie
générique n'est revendiquée pour les autres producteurs. Aucune insertion de
PredictionRecord n'est implémentée. La syntaxe et les contraintes PostgreSQL
restent non exécutées et non certifiées aujourd'hui.

## 6. Rôles, bootstrap et reprise

L'entrée roles admin exige un schéma neuf et l'absence des trois rôles applicatifs.
Elle refuse les collisions et les secrets identiques ; aucun reset de mot de
passe ni modification de rôles existants. Les noms et secrets sont composés via
les objets SQL psycopg, jamais interpolés en texte par l'opérateur. Les quatre
secrets ne sont jamais affichés. L'opération future retire les droits PUBLIC sur
base/schéma et attribue la propriété de la base au seul owner.

Le plan `p101-local-bootstrap-v1` est pur et figé en JSON + SHA-256. Il comprend
UUID, révision, empreinte de fixture, quatre parents, dates fixes et douze mesures.
La fixture est validée par le digest ML 3 déjà approuvé :
`6c8eed59fb2c8b6328899646f93b5191a88c6698be48c51a73b414ce3560dc3a`.
Réutilisation de `validate_fixture`, `adapt_rows` et de la canonisation temporelle.
Aucun appel à evaluate(), aucune moyenne ni score recalculés dans cette étape.

Les douze valeurs prévues, dans l'ordre des 1er au 12 janvier 2026 à 08:00 UTC,
sont 65, 63, 67, 64.5, 65.5, 64.5, 65.5, 65, 65, 65, 65, 70 °C, qualité good.
available_at et fixture_id restent les métadonnées synthétiques de la référence,
absentes du schéma Measurement. Les dates parentales legacy sont explicitement
converties en UTC naïf ; les dates des mesures restent avec fuseau.

Les parents portent uniquement les codes DEMO/MLDEMO validés : entreprise, site,
pompe P101 synthétique operational/medium et capteur temperature/°C/active.
Les ids sont obtenus par INSERT RETURNING id puis utilisés dans les FK suivantes.
Il n'existe aucun identifiant SQL DEV supposé ou réutilisé.

La transaction owner future prend le verrou advisory exclusif 1010053, vérifie
marqueur et révision, puis exige les huit tables métier vides. Elle insère quatre
parents et douze mesures, relit les sources, compare exactement les parents et
reconstruit le manifeste via adapt_rows. Elle prépare les privilèges runtime et
ferme le marqueur avec son empreinte, dans la même transaction. Aucun COMMIT par
ligne, aucun DELETE, ON CONFLICT DO UPDATE, seed DEV ou recommandation.

Sur bootstrap déjà fermé, seuls un contenu exact et l'empreinte attendue sont
acceptés ; les mêmes ids SQL sont conservés et aucune réécriture n'a lieu. Un lot
partiel, supplémentaire ou divergent impose un arrêt. Une répétition de roles
impose également un arrêt pour inspection, sans écrasement automatique. Après
seal, owner est NOLOGIN : la vérification reader reste disponible, une reprise
owner exigerait une autorisation administrative distincte.

Writer/reader reçoivent SELECT sur les cinq tables source, les prédictions, le
marqueur et la version ; writer reçoit en plus INSERT sur prediction_records et
USAGE sur sa séquence. Aucun droit runtime de mutation des sources ou du marqueur,
aucun rôle privilégié/membership, aucun UPDATE/DELETE des prédictions. Le verrou
coordonne les commandes prévues ; il ne contraint pas un superutilisateur externe.
Les privilèges effectifs et la fermeture des sessions owner devront être vérifiés
sur le vrai serveur, pas seulement son attribut NOLOGIN.

L'enveloppe transactionnelle annule les erreurs avant commit, ferme la connexion
et dispose le moteur. Une erreur de commit peut laisser un état **incertain** :
aucun retry automatique et aucune promesse de rollback après perte de réponse.
Inspecter marqueur, empreinte, comptages et sources avant de choisir une reprise.

## 7. Tests réellement exécutés

Commande exécutée une fois, après revue statique et stabilisation, depuis la racine :

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
$env:PYTHONDONTWRITEBYTECODE = '1'
& backend/.venv/Scripts/python.exe -B -m pytest tests/p101_local_demo/test_preparation.py -q -p no:cacheprovider
```

**65 tests réussis en 2,81 s ; aucun échec.** Aucun ancien test ML 3/4/5.2,
suite backend complète, build ou test frontend relancé. Aucune évaluation ML.

Couverture : Compose indépendant/digest/loopback/absence de téléchargement ;
configurations DEV, implicites, chemins, UUID, dates, réseaux et secrets référencés
invalides ; acquittement CLI ; refus PG* avant factory ; garde d'identité simulée ;
transport incorrect avant SELECT ; plan exact quatre parents/douze mesures ;
immutabilité fixture, empreinte stable/liée à l'instance et à la date ; reprise
conservant les ids ; refus marqueur/empreintes/parents/FK/mesures divergents ;
graphe Alembic et contraintes inspectés sans upgrade ; imports isolés ; frontières
begin/guard/body/rollback/commit/close/dispose simulées, y compris commit incertain.

Les tests bloquent connexions SQLAlchemy/psycopg, exécution SQLAlchemy réelle,
résolution/connexion socket, processus externes et command.upgrade. Les plans et
comparaisons sont exécutés, mais **pas les fonctions opérationnelles de bootstrap,
création de rôles, migration ou génération de fichiers privés**. Aucun SQL DDL/DML
n'est exécuté, même sur une base de test. Les doubles d'identité/transaction
n'établissent aucune preuve PostgreSQL d'atomicité, privilège ou concurrence.

## 8. ML 5.3B — commandes futures, non exécutées

Toutes les lignes ci-dessous sont une procédure future à autoriser séparément.
P2/P3 protégés ML 4 ne sont pas démarrés par cette livraison.

1. Recontrôler branche/HEAD, état Git et périmètre autorisé. En lecture seule,
   vérifier moteur/contexte Docker local Linux, image/digest, absence des noms
   proposés et disponibilité de 55432. Vérifier routes Docker/LAN/VPN et disque.
   Arrêt si ambiguïté, collision, image absente ou ressource préexistante inexpliquée.
2. Faire autoriser puis créer hors Git un répertoire privé protégé par ACL Windows,
   un UUID neuf, un JSON complété à partir du modèle et quatre fichiers de secrets
   forts distincts. Vérifier ACL, chemins physiques et absence de réutilisation DEV.
   Choisir une date bootstrap fixe et un subnet/IP approuvés, sans valeur implicite.
3. Initialiser uniquement les variables opérateur suivantes, avec valeurs privées
   non reproduites dans ce rapport ; ne pas les placer dans une commande publique :

```powershell
# Variables opérateur à fournir : $P101PrivateConfig, $P101Instance, $P101ComposeVars.
# $P101ComposeVars désigne compose.vars dans le répertoire privé déclaré.
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
$env:PYTHONDONTWRITEBYTECODE = '1'
& backend/.venv/Scripts/python.exe -B -m app.p101_local_demo.setup --config $P101PrivateConfig check-config
& backend/.venv/Scripts/python.exe -B -m app.p101_local_demo.setup --config $P101PrivateConfig --execute --instance $P101Instance render
```

Render produit seulement le HBA et compose.vars privés, sans secret en clair dans
les variables Compose. Il refuse les fichiers existants divergents. Contrôler les
ACL et les montages effectifs ; absence de variables héritées `P101_LOCAL_*` qui
supplanteraient compose.vars, absence de `PG*` et de configuration Docker distante.
Ne jamais passer un fichier .env DEV. Désactiver le chargement .env implicite :

```powershell
$env:COMPOSE_DISABLE_ENV_FILE = '1'
docker compose --env-file $P101ComposeVars -f infra/p101-local/compose.yaml -p industrial-predict-p101-local-demo config --quiet
# Seulement après toutes les validations et une autorisation de création :
docker compose --env-file $P101ComposeVars -f infra/p101-local/compose.yaml -p industrial-predict-p101-local-demo up -d --pull never --no-build postgres
```

**Cette dernière commande est interdite en ML 5.3A.** Lorsqu'elle sera autorisée,
l'entrypoint officiel initialisera aussi le cluster, la base et le rôle admin :
l'autorisation devra inclure ces opérations, pas seulement la création Docker.
Contrôler écoute loopback, stockage, réseau, IP et journaux sans afficher de secrets.
Le fonctionnement du HBA custom avec l'initialisation officielle et l'adresse
source vue via Docker Desktop est un point à valider ; ne pas élargir en trust ou
ouvrir un réseau large pour contourner un refus.

4. Après autorisation des connexions et opérations SQL sur la seule instance
   identifiée, exécuter séparément et arrêter au premier échec :

```powershell
& backend/.venv/Scripts/python.exe -B -m app.p101_local_demo.setup --config $P101PrivateConfig --execute --instance $P101Instance roles
& backend/.venv/Scripts/python.exe -B -m app.p101_local_demo.setup --config $P101PrivateConfig --execute --instance $P101Instance migrate
& backend/.venv/Scripts/python.exe -B -m app.p101_local_demo.setup --config $P101PrivateConfig --execute --instance $P101Instance bootstrap
& backend/.venv/Scripts/python.exe -B -m app.p101_local_demo.setup --config $P101PrivateConfig --execute --instance $P101Instance verify
& backend/.venv/Scripts/python.exe -B -m app.p101_local_demo.setup --config $P101PrivateConfig --execute --instance $P101Instance seal
& backend/.venv/Scripts/python.exe -B -m app.p101_local_demo.setup --config $P101PrivateConfig --execute --instance $P101Instance verify
```

Après roles : vérifier absence de privilèges élevés/memberships applicatifs, owner
effectif et refus PUBLIC. Après migrate : dix révisions/tête attendue, marqueur
UUID/purpose correct, index/CHECK réellement installés, aucun p101_pilot. Après
bootstrap : exactement 1 entreprise, 1 site, 1 équipement, 1 capteur, 12 mesures,
0 prédiction et 0 maintenance/recommandation ; correspondance DEMO→ids alloués,
valeurs/dates/qualités exactes, empreinte et fermeture du marqueur. Après seal :
owner NOLOGIN et aucune session owner restante ; admin conservé seulement dans
le circuit privé de maintenance, jamais utilisé par API/Angular.

Les validations réelles négatives (mauvais serveur, mauvaise identité, droits,
rollback/concurrence et reprise après réponse perdue) restent à autoriser et à
concevoir précisément avant exécution. Aucune commande de suppression/prune,
downgrade ou remise à zéro n'est proposée. Aucun calcul ni insertion de prédiction
dans cette procédure de préparation des sources ; ML 5.4/5.5 restent séparés.

## 9. Limites et réserves conservées

Le service de persistance locale des deux prédictions, son mapping final JSON,
les conflits de contenu, les tests SQL concurrents et le raccordement API/Angular
ne sont pas implémentés ici. Les contraintes préparées et la transaction Python
ne prouvent rien sur un serveur absent. Les checks de catalogue locaux sont moins
étendus que ceux de ML 4 ; absence de certification exhaustive des fonctions,
extensions, propriétaires et ACL héritées. Les ACL Windows, le montage des secrets,
la publication Docker et l'effet du réseau internal restent à vérifier réellement.

R01–R03/R06–R07 du chemin protégé restent préparés hors base, sans validation
PostgreSQL réelle. R04 (infrastructure/PKI), R05 (émetteurs/secrets/approbations),
R08 (SQL/transactions/concurrence) et R09 (API/GET) restent ouverts. Le profil local
n'accomplit aucune de ces validations du service protégé. **TLS-01 reste ouvert** ;
aucun certificat généré, aucun HMAC ni émetteur réel créé. I01–I12 non commencés.

| Réserve | État après ML 5.3A |
| --- | --- |
| B-PRE-01 | Ouverte : opérateur local de confiance ; aucune autorisation multi-tenant |
| B-PRE-02 | Ouverte : aucun producteur générique modifié ; score P101 reste un indicateur statistique binaire, jamais une probabilité de panne |
| B-PRE-03 | Ouverte : timestamps synthétiques contrôlés, available_at absent du SQL |
| B-PRE-04 | Ouverte : FK/mapping préparés, aucune preuve de rattachement sur serveur |
| B-PRE-05 | Ouverte : CHECK local préparé, mapping et validation applicative des details de persistance encore à implémenter |
| B-PRE-06 | Ouverte : cascades générales inchangées ; aucune suppression ou politique de rétention appliquée |
| B-PRE-07 | Ouverte : lectures bornées, aucun snapshot/performance réel validé |
| B-PRE-08 | Ouverte : transaction bootstrap simulée seulement ; aucune preuve SQL d'atomicité ou de commit |
| B-PRE-09 | Ouverte : sources préparées, aucune alimentation d'historique de prédictions |
| B-PRE-10 | Ouverte : hashes de référence, sans authentification cryptographique de provenance/serveur local |
| B-PRE-11 | Ouverte : aucune route/GET/UI contactée ou modifiée |

## 10. État Git et validation

Branche et HEAD inchangés ; index vide. Douze fichiers nouveaux uniquement, aucun
fichier suivi existant modifié. Vérification d'espacement du suivi et de chacun
des nouveaux fichiers, sans indexation. Recherche de secrets/DSN : aucun secret
réel ; seules références de fichiers privés, placeholders et données synthétiques
de tests. Aucun code ML 4 ou frontend modifié, aucune ressource créée.

**Livraison en attente de validation technique ; aucun commit ni commencement
de ML 5.3B.**
