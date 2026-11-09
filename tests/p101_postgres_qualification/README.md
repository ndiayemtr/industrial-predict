# P101-DEV-3D-RUNNER-1 — préparation fermée de la première campagne

Ce lot ajoute uniquement de nouveaux fichiers de qualification et une définition
de build **incomplète et désactivée**. Il ne rend pas opérationnels les migrations,
INSERT ou lectures métier. Aucun Docker, PostgreSQL, téléchargement ou build.
L'objectif produit (analyse persistée et visible dans Angular DEV) reste ultérieur.

## Composants livrés

- `plans.py` : plan fermé des 14 publications, vérification des sources par le
  garde existant puis contrôle supplémentaire des références B2B/P101 ; descriptions
  AST inertes des upgrades, contrôles de déclarations de base vide et catalogue.
- `scenario.py` : fixture synthétique figée, plans SQL paramétrés, construction du
  résultat par `app.p101_dev.adapter.evaluate_snapshot`, normalisation/comparaison
  exhaustive d'une paire relue, répétition **en mémoire uniquement**.
- `runner.py` : CLI `report` assainie, liste explicite des sources embarquables et
  empreintes diagnostiques. Les actions `build`, `migrate`, `scenario`, `verify`
  refusent inconditionnellement, avant configuration d'un transport.
- `fixture.json` : dix températures quotidiennes non constantes précédant une
  cible à 70 °C ; snapshot rétrospectif, qualité good et provenance synthétique.
- `infra/p101-qualification-runner/Dockerfile.in` : modèle volontairement non
  constructible sans base approuvée et artefacts complets.
- `infra/p101-qualification-runner/dependencies.json` : versions de référence et
  blocages explicites ; **ce fichier n'est pas un lock reproductible complet**.

## Runner et dépendances

Le contexte futur doit être assemblé uniquement depuis `runner.SOURCE_PATHS`,
sans copier le dépôt complet, secrets, .env, .git, venv, API, Angular, writer ou
outils DEV. `source_manifest()` lit cette liste fermée et calcule les hashes
UTF-8/LF ; cela ne constitue pas une approbation ou une archive immuable.

Références locales : CPython 3.12.10, client PostgreSQL attendu 17.10,
OpenSSL de référence 3.0.16. Paquets épinglés dans le dossier de préparation :
pandas 3.0.6, numpy 2.5.3, python-dateutil 2.9.0.post0, six 1.17.0,
tzdata 2026.3, cryptography 50.0.2, cffi 2.1.1 et pycparser 3.12.
La dépendance pandas est imposée par l'évaluateur existant : aucun second moteur
de calcul n'est introduit pour alléger artificiellement le runner.

Le transport INFRA-3 est embarqué inchangé pour les métadonnées SQL/TLS. Le
collecteur X.509 existant nécessite cryptography ; la bibliothèque standard
suffit au transport. Aucun SDK Docker nécessaire dans le conteneur. Pytest
9.1.1 est utilisé côté développement, pas requis dans l'image finale proposée.

Manquent : digest d'une base contenant Python/psql et leurs bibliothèques système,
artefacts linux/amd64, fermeture transitive vérifiée, hashes des wheels,
`requirements.lock` intégral avec hashes, archive approuvée des sources et preuve
de reproductibilité. Aucune version flottante n'est proposée comme substitution.
Le modèle utilise `--no-index --no-deps --require-hashes` et un wheelhouse local ;
son contexte ne contient aujourd'hui ni ces wheels ni le lock final. Il ne doit
pas être présenté comme une image prête à construire. Aucun paquet n'a été installé.

La politique future reste : réseau bridge interne neuf, volume PostgreSQL neuf,
aucun port publié, racines RO, utilisateurs non root, limites explicites et aucun
socket Docker. La livraison des secrets/TLS doit être revue avec le profil B2B,
qui refuse actuellement les mounts supplémentaires. Aucun compose ni ressource
réelle n'est créé dans ce lot ; aucun subnet n'est implicitement approuvé.

## État réel de l'exécuteur

`prepare_migrations(campaign, expected_campaign=...)` compare la campagne à un
inventaire fourni séparément, réutilise les exclusions B2B et appelle uniquement
`general_migrations.inspect_sources()`. Les fichiers de révision ne sont jamais
importés. Les 14 empreintes, parents et chemins sont contrôlés avant de retourner
un plan `Offline`. L'inventaire injecté n'est pas une autorisation authentifiée.

Chaîne obligatoire depuis une base vide :

```text
0468ed5be8f1 → 50e5051527dc → 656260b06cdf → 572080d9e581
→ 570ce155aaf8 → 783e16aa6ce3 → 675ebfea0bb5 → d6ec01cf13b6
→ 09ac8101e9fe → 12e2fc65f372 → 4b7e2a91c6d0
→ b2b_0001_sessions → b2b_0002_analyze → p101_0001_operations
```

Le nouveau plan ne modifie pas le snapshot fermé B2B ni ses opérations signables.
`request_migration_execution()` refuse toujours, y compris avec connexion,
callback, déclaration d'approbation ou `enabled=True` injectés. Aucun chargement
Alembic alternatif, interpréteur AST exécutable ou accès SQL n'est fourni. Les
gardes, env.py, INI et révisions publiées restent inchangés. Aucun create_all,
dump, stamp, migration au démarrage ou récupération automatique.

Avant activation séparément revue : autorité couvrant la destination et les
14 publications, racines de confiance indépendantes, registre durable de non-rejeu,
release immuable et stratégie de chargement sans TOCTOU, transport RW lié à TLS,
profil pré-bootstrap qualifié et baseline complète du catalogue approuvée.
SQLAlchemy/Alembic et leurs dépendances devront être verrouillés si le futur
chargeur les emploie ; ils ne sont pas nécessaires au CLI fermé livré ici.

Séquence future réservée au lanceur qualifié :

1. Vérifier identité Docker, TLS, serveur, base, instance, cluster, rôle et ACL.
2. Sur la connexion possédée par le lanceur, vérifier une base réellement vide
   avant DDL, y compris relations/séquences, schémas utilisateur, types, routines,
   extensions et absence de table/version Alembic. Aucun nettoyage automatique.
3. Ouvrir une transaction DDL externe unique, search_path contrôlé, appliquer
   strictement les 14 upgrades ; aucune connexion ou commit par révision.
4. Vérifier catalogue complet : colonnes/defaults, PK/UNIQUE/CHECK/FK et leurs
   définitions/actions/différabilité/validation, indexes, séquences, fonctions,
   corps et search_path, triggers/flags, ownership/ACL et révision finale.
5. Acquitter le commit puis confirmer depuis une connexion indépendante.

`EMPTY_SQL`, `CATALOG_SQL`, `TRIGGERS_SQL`, `FUNCTIONS_SQL` sont des requêtes
préparatoires non exécutées. Elles ne constituent pas encore un collecteur complet.
`review_empty_declaration` ne traite que des faits injectés. Le comparateur de
catalogue exige toutes les sections et un digest de baseline fourni indépendamment,
ainsi que les noms/flags P101 attendus. Aucun baseline n'est généré à partir de
la base observée pour auto-approuver son état. Il manque encore les collecteurs
de colonnes/indexes/séquences/ACL et le relevé réel de référence. Un dictionnaire
synthétique passant la comparaison ne prouve aucune installation PostgreSQL.

## Premier scénario P101

Le plan de seed contient 15 INSERT paramétrés : entreprise, site, équipement,
capteur et onze mesures. Les ids industriels sont tous issus des futurs
`RETURNING id`, représentés par des références symboliques. Aucun id SQL présumé,
max(id), rattachement historique ou backfill.

Après seed explicitement autorisé et vérifié, le futur lanceur doit relire et
verrouiller les sources exactes, confirmer leur contenu et leur isolation, puis
calculer dans la transaction autorisée avec l'évaluateur existant. Le présent
`prepare_operation` calcule depuis la fixture déclarée et les ids fournis : il
n'effectue pas cette relecture SQL et n'atteste aucune provenance réelle.
L'acteur est un snapshot explicitement synthétique, sans assertion d'authentification
OIDC ni grant B2B. Un futur scénario avec utilisateur réel demande le fournisseur
d'identité/autorisation approprié ; il n'est pas déduit du journal.

`pair_plan` décrit une seule transaction SERIALIZABLE :

1. Préallouer l'id de prédiction via sa séquence historique, sans INSERT de prédiction.
2. Insérer le journal complet, récupérer son id technique par RETURNING.
3. Insérer la prédiction portant l'id préalloué et p101_operation_id = journal.id.
4. Forcer la validation des contraintes différées puis un seul COMMIT.

Les détails et leur SHA-256 viennent du producteur canonique existant. Aucune
modification/suppression, ligne pending ou UPDATE de finalisation. Journal et
prédiction conservent score, alerte, modèle, mesure cible et timestamps concordants.

`PAIR_SQL` prépare une relecture par clé avec LEFT JOIN et LIMIT 2 : une absence,
un journal orphelin ou un doublon ne peut devenir une paire complète valide.
`normalize_pair_observation` traite explicitement les timestamps JSON avec fuseau
et le score flottant SQL ; il ne remplit ni ne répare les champs absents.
`review_pair` compare tous les champs, le texte canonique exact, les empreintes,
le contenu des détails et les références réciproques. Il exige des identifiants
de connexion distincts, mais ceux-ci restent des déclarations injectées : le futur
lecteur doit établir lui-même sa liaison TLS/SQL et son identité avant la requête.

Le transport INFRA-3 refuse ces INSERT et cette requête métier. Il n'est pas
élargi dans ce lot. `request_scenario_execution()` reste fermé. L'exécution SQL,
le commit acquitté et la connexion indépendante ne sont donc **pas opérationnels**.

`OfflineScenario` est un stockage en mémoire réservé aux tests de protocole
logique : état `simulated_commit_confirmed` ou `uncertain`. Les pertes d'acquittement
avant/après commit simulé conservent le refus de réessayer dans cet objet. Une
absence ne prouve pas un rollback et la relecture ne change pas l'état incertain.
Un nouvel objet/processus ne possède pas cet historique : aucun non-rejeu durable
ou résistance au redémarrage n'est revendiqué. Le registre B2B existant ne couvre
pas automatiquement cette nouvelle opération P101.

## Validation et suite

Tests uniquement des nouveaux composants, avec réseau, drivers, Docker/subprocess
et commandes Alembic interdits par fixtures. Aucune révision importée/exécutée,
aucun test de conteneur ou serveur réel. Les comparaisons de catalogue et de paire
emploient des observations synthétiques. Ni contraintes, ni concurrence, ni
durabilité PostgreSQL ne sont qualifiées par ces tests.

```powershell
& backend/.venv/Scripts/python.exe -B -m pytest tests/p101_postgres_qualification/test_runner.py -q -p no:cacheprovider
```

Prochain lot concret : revue des nouveaux plans et du dossier de dépendances,
puis verrouillage des artefacts et définition de l'autorité/du transport RW/lecteur
indépendant. Une éventuelle activation du chargeur devra être un lot distinct
explicitement revu. Ce lot ne modifie ni DEV, Angular, API, writer, migrations,
transport INFRA-3, politiques B2B ni OIDC. Aucun commit ou push.
