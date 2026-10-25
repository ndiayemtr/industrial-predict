# ML 4.2B-2.1 — Préparation et durcissement du sandbox P101

Date : 25 octobre 2026. Statut : code local et tests hors base, soumis à validation
technique avant tout commit ou provisionnement.

## 1. Référence et périmètre

Dépôt `D:/projets/industrial-predict`, branche
`feature/ml-4-p101-persistence`, HEAD de départ et final inchangé
`e268bb761268c9609c866168ff044dffaf7ee525`. Arbre propre et index vide vérifiés
avant les changements. Aucun commit, push, merge ou rebase.

Références contractuelles inchangées :
[ML 4.1](ml-4.1-p101-persistence-design.md),
[ML 4.2A](ml-4.2a-p101-persistence-contracts.md),
[ML 4.2B-1](ml-4.2b1-p101-persistence-implementation.md),
[ML 4.2B-2.0](ml-4.2b2-p101-sandbox-readiness.md).

R01, R02, R03, R06 et R07 disposent de composants préparés et de contrôles hors
base. Leur fonctionnement PostgreSQL réel n'est pas certifié. Aucune connexion
PostgreSQL/HTTP, migration appliquée, exécution serveur de DDL/DML, ressource
Docker/base/rôle créée, image téléchargée, certificat ou secret réel généré.
Aucun entraînement, joblib, nouveau package ou changement frontend. Les services
ML génériques, routes, neuf révisions générales et producteurs ML 3/ML 4.2A sont
inchangés. ML 4.2B-2.2, I01–I12 PostgreSQL et ML 5 ne sont pas commencés.

## 2. Fichiers modifiés et créés

Treize fichiers concernés : six modifiés, sept nouveaux, dont ce rapport.

| Statut | Fichier | Rôle |
| --- | --- | --- |
| Modifié | `backend/app/p101_postgres/runtime.py` | CA SHA-256, bootstrap_uuid obligatoires, politique et manifeste de release renforcés |
| Modifié | `backend/app/p101_postgres/session.py` | Vérification des octets CA avant construction du moteur lazy |
| Modifié | `backend/app/p101_postgres/guard.py` | Contrôles de catalogue supplémentaires ; séparation identité writer / installation |
| Modifié | `backend/p101_migrations/env.py` | Délégation à l'entrée admin typée, suppression du callback booléen |
| Modifié | `tests/p101_postgres/conftest.py` | Fausse CA en fichier texte temporaire et interdictions supplémentaires d'exécution réelle |
| Modifié | `tests/p101_postgres/test_guard_repository_migration.py` | Instantanés enrichis, conservation des vérifications B-1, adaptation de l'entrée Alembic |
| Nouveau | `backend/app/p101_postgres/administration.py` | Contrat d'approbation admin, transport owner, lanceur et environnement gardés |
| Nouveau | `backend/app/p101_postgres/bootstrap.py` | Plans purs de rôles/privilèges/données et entrée owner future de bootstrap |
| Nouveau | `backend/app/p101_postgres/catalog.py` | Définitions et colonnes attendues, validations fermées |
| Nouveau | `backend/p101_core_migrations/alembic.ini` | Environnement indépendant réutilisant les neuf sources générales |
| Nouveau | `backend/p101_core_migrations/env.py` | Entrée Alembic générale sandbox, sans réglages applicatifs |
| Nouveau | `tests/p101_postgres/test_sandbox_hardening.py` | Soixante cas unitaires/statiques supplémentaires |
| Nouveau | `docs/ml-4.2b21-p101-sandbox-hardening.md` | Ce rapport |

Aucune nouvelle révision générale ou pilote n'est créée. La source de
`p101_0001_registry.py` est inchangée ; seule son entrée d'exécution administrative
change. Les dossiers de préparation et clés métier ML 4.2A ne sont pas réécrits.

## 3. R01 — Chemin général de migration indépendant

`migration_config` construit uniquement un Config Alembic : connexion fournie,
SandboxConfig, AdminApproval et AdminApprovalVerifier sont injectés explicitement.
`run_migrations` est une fonction opérationnelle future, jamais appelée avec une
connexion réelle ici. Aucun moteur/connexion n'est construit à l'import ; aucun
chargement de settings, core.database, DATABASE_URL, .env ou lanceur DEV.

L'ini `p101_core_migrations` pointe son `script_location` vers son propre env et
son `version_locations` vers les sources générales existantes. L'entrée commune
refuse l'offline, une configuration/scope non approuvés, les overrides de chemins,
une cible autre que la révision exacte, une connexion déjà engagée et tout écart
de transport/identité owner. Le chemin des sources générales et l'ensemble exact
des neuf fichiers sont vérifiés ; leurs octets font partie du manifeste approuvé.

Avant toute DDL : approbation authentifiée, CA et fichiers approuvés, connexion
owner TLS vérifiée côté client, puis SELECT d'identité effective. Pour le schéma
général, les schémas dédiés doivent être vides de tables/vues/séquences ; le lanceur
est volontairement limité au premier bootstrap et ne reprend pas automatiquement
une installation partielle. Il fixe ensuite le search_path de migration à
public,pg_catalog pour réutiliser les révisions non qualifiées inchangées.

Chaîne : 0468ed5be8f1 → 50e5051527dc → 656260b06cdf → 572080d9e581 →
570ce155aaf8 → 783e16aa6ce3 → 675ebfea0bb5 → d6ec01cf13b6 → 09ac8101e9fe.
Version générale dans `public.alembic_version` ; cible pilote p101_0001 et version
dans `p101_pilot.alembic_version`. La migration pilote exige la bonne révision
générale et l'absence préalable du schéma p101_pilot, avant sa création.

Le contexte de transaction appartient au lanceur admin ; l'approbation est
revérifiée avant sa sortie. Aucun test n'a exécuté context.run_migrations,
command.upgrade ou upgrade/downgrade. La transaction Alembic réelle et la prise en
compte du contexte externe restent à vérifier sur PostgreSQL autorisé.

## 4. R02 — Contrat administratif distinct

`AdminApproval` est figé et porte : UUID canonique d'approbation, action fermée,
empreinte SHA-256 du plan, empreinte de politique, expiration UTC et HMAC-SHA256.
Les actions sont distinctes : migration générale, migration pilote et bootstrap
de données. Les plans de migration lient les révisions et le schéma de version ;
le bootstrap lie son contenu canonique complet. La politique lie destination,
instance, bootstrap_uuid, rôles, CA, révision et empreintes de fichiers.

`AdminApprovalVerifier` exige une clé explicite d'au moins 32 octets et un jeton
du type exact, vérifie scope/contenu/politique/expiration/signature puis les octets
CA et release. Aucun émetteur, clé par défaut ou callback permissif. L'ancien
`p101_authorize_migration` retournant un booléen n'est plus accepté ; les attributs
sont `p101_admin_approval` et `p101_admin_verifier`.

L'approbation métier `ExecutionApproval`, le dossier ML 4.2A et un booléen ne sont
pas des approbations admin. Le domaine de payload admin est distinct ; la vraie
clé admin devra être distribuée séparément de la clé métier. HMAC reste un secret
partagé, pas une signature asymétrique séparant les pouvoirs d'émission et de
vérification. L'émetteur réel et ses secrets ne sont pas provisionnés ici.

La connexion owner doit être fournie par une future étape autorisée. Son URL et
les paramètres effectifs psycopg doivent correspondre au host/port/base/owner,
avec sslmode verify-full, CA explicite, TLS actif et options exactement
`-c search_path=pg_catalog -c timezone=UTC`. Aucune variable PG* n'est acceptée.
Le SELECT effectif vérifie adresse/port serveur, base, session_user=current_user
owner, TLS et encodage UTF8. Les deux ports (publié et interne) restent distincts.

## 5. R03 — Préparation reproductible du bootstrap

### Plans purs

`role_creation_plan` produit trois instructions CREATE ROLE aux noms validés,
NOLOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS et
NOINHERIT, sans mot de passe. Des rôles déjà présents ne doivent pas être adoptés :
les CREATE ordinaires échoueront. **Ce plan n'est pas exécuté par les tests ni par
bootstrap_data** : son application future relève d'un administrateur de bootstrap
explicitement autorisé. Attribution de propriété de la base, activation LOGIN,
secrets neufs et fermeture finale de l'accès owner restent des opérations séparées.

`privilege_plan` prépare, après migrations, le retrait de PUBLIC et des droits
writer/reader sur base, schémas, tables, séquences et fonctions pilote, puis les
GRANT minimaux : CONNECT/USAGE ; SELECT sources/historique ; SELECT versions,
marqueur et registre pour writer ; INSERT prédictions/registre pour writer ;
USAGE de la séquence résolue et EXECUTE lock_sources pour writer. Les privilèges
par défaut tables/fonctions sont aussi restreints pour l'owner. Aucun GRANT de
mutation des mesures, recommandations, ni UPDATE/DELETE historique.

La séquence vient de pg_get_serial_sequence et son nom doit satisfaire le format
public autorisé ; aucune séquence ni aucun id SQL ne sont supposés dans le plan.
Les droits de colonne/memberships et droits effectifs réels devront encore être
contrôlés. Le dispositif suppose des rôles neufs, et non le recyclage d'anciens
comptes contenant des droits cachés.

`build_bootstrap_plan` accepte uniquement le manifeste synthétique épinglé par
FIXTURE_SHA256, les douze identités ordonnées DEMO-M-001 à 012 et une date de
préparation postérieure à leur disponibilité. Il produit un plan figé en JSON
canonique avec empreinte. `validate_bootstrap_plan` reconstruit ce plan : contenu,
identités, empreintes ou bootstrap_uuid altérés sont refusés.

Le périmètre comporte les quatre parents P101, leurs codes contractuels, une
pompe au nom contenant « synthétique », un capteur temperature/°C et les douze
mesures good. Aucun id SQL alloué, aucune prédiction ni recommandation n'est
préchargé. La préparation ne calcule aucune prédiction et n'appelle aucun seed DEV.

### Entrée opérationnelle future, non exécutée

`bootstrap_data` reçoit une connexion owner neuve et le plan, exige une approbation
BOOTSTRAP valide et le transport explicite, puis ouvre une transaction unique.
Avant DML : identité owner, deux versions, installation SQL attendue, verrou
advisory exclusif 1010042 et tables sources/historique/maintenance/registre/marqueur
vides. Aucun nettoyage, upsert ou adoption d'un contenu existant n'est prévu.

Il prépare ensuite les INSERT des parents avec RETURNING id et rattache chaque
enfant aux ids retournés, puis les douze mesures. Le marqueur porte instance_uuid,
bootstrap_uuid, base, purpose, rôles et révisions ; provisioning_closed passe de
false à true après application du plan de privilèges. La fermeture exige une ligne
modifiée et une approbation encore valide. Les timestamps parents historiquement
sans fuseau sont des UTC convertis explicitement en naïf ; les mesures gardent
un instant avec fuseau.

Cette fonction n'a jamais été appelée dans les tests nominaux, même avec une
fausse session réalisant ces étapes. Seul son refus sans approbation est exercé
avant accès à une connexion ; son corps est revu statiquement. Le bootstrap réel,
son rollback/commit, la fermeture owner et une relecture indépendante restent à
valider. Aucune relance automatique après erreur : un échec au voisinage du commit
admin doit être considéré comme incertain et inspecté séparément, sans nettoyage.

`available_at` n'est pas stocké dans measurements : sa preuve reste le manifeste
synthétique attesté. Cela ne démontre pas la disponibilité temporelle de données
industrielles réelles. Le provisionneur privilégié doit respecter le verrou
exclusif et rester arrêté après fermeture ; SHARE seul ne bloque pas une insertion
administrative de nouvelle mesure.

## 6. R06 — Contenu de la CA lié à la politique

Deux nouveaux champs SandboxConfig sont obligatoires, sans valeur par défaut :
`tls_root_sha256` et `bootstrap_uuid`. Le digest CA doit être hexadécimal SHA-256
valide et non nul. `verify_ca` exige un fichier absolu, non redirigé par résolution
de chemin, borné à 64 Kio, lisible et dont les octets correspondent au digest.
Une modification au même chemin est refusée. Une nouvelle empreinte déclarée
modifie la politique et invalide les anciennes approbations admin et métier.

Contrôle lors des vérifications d'approbation, avant la factory lazy et avant le
transport admin ; l'approbation est également revérifiée avant les commits métier
et admin. Cela ne valide ni la syntaxe X.509, ni la chaîne réelle, les SAN, la
validité temporelle, les permissions de fichiers ou l'authentification du serveur.
Les ACL privées et la prévention de remplacements concurrents du fichier entre
vérification et ouverture TLS restent nécessaires au provisionnement. Aucun
certificat réel n'est créé ; les tests écrivent seulement du texte explicitement
fictif et non utilisable comme CA.

Le manifeste RELEASE_PATHS contient désormais 35 chemins : les 21 précédents,
trois modules nouveaux, deux fichiers d'entrée générale et les neuf révisions
générales. L'autorité devra attester le futur commit revu et ces octets précis ;
le HEAD actuel ne doit pas être présenté comme contenant ces changements locaux.

## 7. R07 — Contrôles SQL supplémentaires

Les vérifications B-1 sont conservées et complétées :

- Identité : bootstrap_uuid et database_name du marqueur comparés à la politique.
- Contraintes registre : noms/types/validité/différabilité/FK NO ACTION existants,
  colonnes et colonnes référencées ordonnées, définition pg_get_constraintdef exacte
  attendue, expressions CHECK hexadécimales et limites d'octets. Une contrainte
  supplémentaire est refusée, même avec un autre nom.
- Marqueur : PK et cinq CHECK attendus, définitions, validité et non-différabilité.
- Triggers : liste exacte des trois triggers utilisateur, table/fonction/schéma,
  activation, différabilité et flags de lignes/événements/timing. tgtype attendu
  31 pour BEFORE ROW INSERT/UPDATE/DELETE, 29 pour AFTER ROW ; aucun argument,
  prédicat WHEN ou liste de colonnes inattendu.
- Fonctions : quatre fonctions exactes, corps SHA-256, propriétaire, SECURITY
  DEFINER et search_path existants ; langage plpgsql, type de routine, volatilité,
  signatures/résultats et bénéficiaires EXECUTE attendus ; pas de délégation à un
  non-owner. Le writer n'exécute directement que lock_sources. Le contrôle owner
  du bootstrap tient compte des privilèges inhérents du propriétaire, sans ouvrir
  ceux du writer.
- Objets : tables pilote/version et PredictionRecord, propriétaires, schéma
  pilote propriétaire, types/ordre/nullabilité des colonnes, absence de RLS ou
  table/vue/séquence pilote inattendue. Les 14 champs restent inchangés.

`check_installation` extrait les contrôles de catalogue utilisables avant le
marqueur ; `check_destination` conserve en plus la garde complète writer.
Les définitions SQL ne sont normalisées que pour les espaces hors littéraux,
sans accepter des expressions sémantiquement différentes ou retirer leurs casts.
Les contrôles ne constituent pas un audit exhaustif de tous les objets du cluster.

**Limite importante :** les rendus exacts de pg_get_constraintdef,
pg_get_function_result, les noms automatiques de CHECK, les types renvoyés par
psycopg et les privilèges de catalogue sont supposés d'après les sources et les
instantanés fabriqués. Ils devront être confrontés à PostgreSQL réel. Tout écart
provoquera un refus ; une éventuelle adaptation exige revue du rendu serveur,
pas une désactivation du contrôle pour faire passer un test.

## 8. Tests réellement exécutés

La suite ciblée est `tests/p101_postgres` : conservation/adaptation des 70 cas
B-1 et ajout de 60 cas. Le fixture de configuration construit ses empreintes
à partir des sources locales et crée uniquement un fichier texte de fausse CA.

Première commande ciblée sans basetemp : erreurs de préparation de tmp_path,
interrompue pour isoler le problème ; aucune réussite globale revendiquée.
Un diagnostic ciblant `test_complete_simulated_guard_snapshot` a confirmé
**1 erreur de setup en 12,25 s**, causée par l'impossibilité de créer le répertoire
temporaire pytest par défaut. Aucun changement de code ou de contrôle de sécurité
n'a été fait pour contourner ce diagnostic.

Passe complète avec répertoire neuf dédié dans le workspace ignoré par Git :

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
backend/.venv/Scripts/python.exe -B -m pytest tests/p101_postgres -x -q -p no:cacheprovider --basetemp=backend/.venv/p101-b21-unit-tmp
```

Résultat final : **130 tests réussis en 20,26 s, aucun échec**. Le dossier temporaire
de cette passe est réservé à ces fixtures et supprimé après contrôle de son chemin.
Aucune suite backend complète, build ou ancien ensemble ML 3/4.2A complet relancé.
Les préparations synthétiques nécessaires aux tests existants sont conservées ;
aucun calcul industriel réel ou entraînement n'a été lancé.

Les tests bloquent Engine.connect/raw_connection, Connection.execute/exec_driver_sql,
Session.execute/flush/commit, psycopg.connect, les connexions/résolutions socket,
Alembic command.upgrade et Operations.execute. Les requêtes des gardes sont
observées sur des objets fabriqués ; les anciens tests de repository compilent
ou enregistrent des instructions, sans serveur exécutant ces instructions.
Aucun corps nominal de migration ou bootstrap DDL/DML n'est exécuté.

Couverture nouvelle : approbation admin nominale/invalide/absente/expirée, séparation
de domaines, refus d'un callback booléen, chemins Alembic non autorisés, transport
owner incohérent/implicite, CA remplacée et politique modifiée, bootstrap_uuid,
définitions/colonnes/ACL/triggers/objets de catalogue altérés, plan exact des
quatre parents et douze mesures, refus des variantes de fixture et absence d'ids
préalloués. Lecture AST des révisions/env et des ordres de garde avant DDL.

**Les simulations ne prouvent ni TLS serveur, ni DDL PostgreSQL valide, ni droits
effectifs, ni atomicité, concurrence, rollback ou commit réels. Aucun I01–I12
PostgreSQL n'est déclaré réussi.**

## 9. Traitement consolidé R01–R09 et prérequis ML 4.2B-2.2

| Réf. | État après cette étape | Validation ou prérequis restant |
| --- | --- | --- |
| R01 | Lanceur/env indépendants préparés, neuf sources inchangées réutilisées | Appliquer uniquement après autorisation sur base vide ; vérifier versions, transaction Alembic et schéma effectif |
| R02 | Contrat admin signé et vérificateur typé, scope/plan/politique/expiration contrôlés | Émetteur réel, clé admin indépendante, connexion owner verify-full et autorisations nominatives à provisionner |
| R03 | Plans rôles/privilèges/données et entrée bootstrap préparés ; aucune exécution | Création/activation privée des rôles, propriété base, bootstrap réel, droits de colonne, fermeture owner et relecture à valider |
| R04 | Inchangé : aucune infrastructure créée ou interrogée dans cette étape | Image/digest approuvés, moteur Docker Linux, volume/réseau/port/IP indépendants, outil PKI fonctionnel et certificats à préparer |
| R05 | Aucun émetteur métier réel ou circuit de secrets ajouté | Distribution séparée des clés admin/métier, attestation commit/octet, expiration/rotation et résolution après commit incertain à organiser |
| R06 | Digest des octets CA exigé et lié aux approbations ; remplacement testé hors base | Chaîne X.509, SAN, validité, ACL et remplacement concurrent à contrôler sur fichiers privés réels |
| R07 | Catalogue comparé plus strictement et bootstrap_uuid lié | Vérifier les rendus PostgreSQL, owners, ACL et objets réels ; ne pas assimiler les instantanés à une preuve d'installation |
| R08 | Toujours non validé sur PostgreSQL | Syntaxe PL/pgSQL/DDL, normalisation JSON, catalogue, privilèges, verrous, contraintes différées, rollback et concurrence I01–I12 |
| R09 | Aucun changement de route/GET ou configuration applicative | Harnais reader/API distinct, autorisation HTTP future, dépendance DB sandbox explicite avant I10 ; aucune API DEV contactée |

Avant toute étape ML 4.2B-2.2 : validation technique et éventuel commit explicitement
autorisé ; autorisations distinctes de provisionnement, fichiers privés et PKI,
connexion admin, création/activation des rôles, DDL général/pilote, bootstrap
synthétique puis tests PostgreSQL. Le choix réseau, serveur et certificats doit
être approuvé avant la première connexion ; aucun apprentissage permissif de
destination, rollback destructif automatique ou fallback DEV.

Après déploiement futur autorisé, vérifier d'abord identité/TLS/schéma sans lancer
le service métier, puis bootstrap et droits, puis seulement les tests I01–I12
nominativement autorisés, avec inventaires avant/après. Une anomalie de garde
arrête la procédure et demande une correction revue, sans relance des écritures.

## 10. Réserves B-PRE-01 à B-PRE-11

| Réserve | État |
| --- | --- |
| B-PRE-01 | Ouverte : séparation admin/métier locale renforcée, aucune autorisation multi-tenant SaaS démontrée |
| B-PRE-02 | Ouverte : contrats P101 bornés inchangés, producteurs et scores génériques non durcis |
| B-PRE-03 | Ouverte : UTC/cutoffs contractuels ; disponibilité SQL non stockée et GET réel non testé |
| B-PRE-04 | Ouverte : bootstrap/rattachements préparés ; sources et verrous réels non vérifiés |
| B-PRE-05 | Ouverte : JSON canonique et borné en mémoire, équivalence SQL/JSON non prouvée |
| B-PRE-06 | Ouverte : protections P101 jamais installées ; cascades générales inchangées, aucun nettoyage DEV |
| B-PRE-07 | Ouverte : aucune mesure de snapshot, pagination, charge ou performance |
| B-PRE-08 | Ouverte : service métier dédié conservé ; transactions réelles non démontrées, chemin RUL/joblib inchangé |
| B-PRE-09 | Ouverte : aucune alimentation réelle de l'historique, aucune orchestration générale |
| B-PRE-10 | Ouverte : provenance CA/bootstrap/release renforcée hors base ; schéma/versions/identités serveur non attestés |
| B-PRE-11 | Ouverte : aucun nouvel endpoint ni GET ; détail/latest existants inchangés |

## 11. État Git final

Branche et HEAD inchangés ; index vide. Six fichiers suivis modifiés et sept
nouveaux uniquement dans le pilote, ses entrées administratives, ses tests et ce
rapport. Les révisions générales, services/routes génériques, ML 3/ML 4.2A,
frontend et configurations DEV sont inchangés. Contrôles finaux conformes :
`git diff --check` et contrôle `git diff --no-index --check` de chaque nouveau
fichier sans erreur d'espacement ; recherche de motifs de secrets/DSN sans
résultat et lecture des valeurs fictives de test ; onze réserves ouvertes
présentes. Le répertoire temporaire dédié aux fausses CA a été supprimé après
vérification de son chemin dans le workspace. Aucune indexation ni aucun commit.

**En attente de validation technique. Aucune autorisation d'infrastructure ou
d'écriture PostgreSQL n'est déduite de cette livraison.**
