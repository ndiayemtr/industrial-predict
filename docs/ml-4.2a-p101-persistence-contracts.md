# ML 4.2A — Contrats de persistance P101 hors base

Date : 25 octobre 2026. Statut : implémentation locale en attente de validation
technique, sans commit. Références : [ML 2](ml-2-p101-anomaly-design.md),
[ML 3](ml-3-p101-anomaly-core.md), [ML 4.1](ml-4.1-p101-persistence-design.md).

## 1. Référence et périmètre

Départ vérifié : dépôt `D:/projets/industrial-predict`, branche
`feature/ml-4-p101-persistence`, HEAD
`a002e99ff3ac2adca71225ec4c24caf9f7a13a43`, index et arbre propres.
La branche et le HEAD sont conservés ; aucune nouvelle branche nécessaire.

La préparation du futur lot de deux prédictions est implémentée exclusivement en
mémoire. Aucun service transactionnel opérationnel, modèle ORM, factory de session,
requête SQL, endpoint ou mécanisme de connexion n'est ajouté. Aucun accès
PostgreSQL/HTTP, provisionnement, migration, table, package, frontend, entraînement,
joblib, commit, push, merge ou rebase. Seules les évaluations synthétiques et
revalidations nécessaires aux tests ciblés ont été exécutées. Aucun calcul sur
donnée industrielle réelle ; ML 4.2B et ML 5 ne sont pas commencés.

## 2. Fichiers ajoutés et réutilisation

Six fichiers nouveaux ; aucun fichier suivi préexistant modifié :

| Fichier | Fonction |
| --- | --- |
| `backend/app/p101_persistence/__init__.py` | Package pur, sans initialisation de service ni infrastructure |
| `backend/app/p101_persistence/contracts.py` | Modèles typés figés, identités, politique, déclaration d'autorisation, provenance, projections, erreurs et résultat |
| `backend/app/p101_persistence/canonical.py` | Encodage canonique des clés/contenus, SHA-256 et comparaison logique de retry |
| `backend/app/p101_persistence/preparation.py` | Validation du lot, comparaison au manifeste/politique/déclaration et mapping conceptuel |
| `tests/p101_persistence/test_contracts.py` | Tests unitaires sans base/réseau, avec évaluations synthétiques ML 3 |
| `docs/ml-4.2a-p101-persistence-contracts.md` | Ce rapport |

Réutilisés sans modification : les dataclasses Computed/Abstained/LogicalPrediction,
`validate_proposal`, `bounded_details`, `canonical_bytes`, `manifest_sha256`,
`utc_instant` et `decimal_text` de ML 3. Les tests utilisent `evaluate` sur la fixture
existante de douze observations ; le code de préparation ne lance pas evaluate ou
un détecteur. StatisticalAnomalyDetector n'est ni reconstruit ni modifié. Les
services ML existants, schémas SQL, routes et documents contractuels restent inchangés.

## 3. Contrats publics

Les modèles sont des dataclasses frozen. Leur construction représente une donnée,
pas une validation implicite : les frontières publiques réalisent les contrôles
et retournent un résultat typé ou lèvent ContractError pour les utilitaires.

| Contrat | Sens et limites |
| --- | --- |
| TargetIdentity | Deux valeurs fermées : DEMO-M-011 et DEMO-M-012 |
| DestinationDeclaration | UUID déclaré, hôte/port, base/rôle proposés et purpose sandbox ; aucune preuve de connexion |
| ProvenanceAttestation | Révision du calcul, empreinte fixture, UUID de revue et marqueur attested à comparer à la politique |
| PreparationPolicy | Destination attendue, UUID de revue accepté, révision/fixture du pilote v1 épinglées |
| AuthorizationTarget / AuthorizationDeclaration | Déclaration de destination et de contenu : deux identités, cutoffs, empreintes de référence/contenu, révision et dataset |
| IdempotencyTuple / LogicalIdempotencyKey | Composants versionnés et leur projection canonique ; aucune réservation SQL |
| CanonicalProjection | Octets représentés par une chaîne JSON canonique et digest SHA-256 réel calculé en mémoire |
| SqlDependent | Champ SQL explicitement non résolu, éventuellement rattaché à une identité logique |
| DetailsDraft / PredictionReadPlan | Détails candidats et quatorze champs conceptuels, distincts d'un DTO SQL final |
| PreparedTarget / PreparationDossier | Lot ordonné et immutable, destination/provenance/déclaration, projections et manifeste canonique figé |
| ValidatedPreparation / RejectedPreparation | status validated_offline avec dossier, ou rejected avec erreurs typées et dossier=null |

Fonctions publiques :

- `prepare_batch(proposals, manifest, *, policy, provenance, authorization)` :
  valide le lot hors base et retourne ValidationResult. Les propositions doivent
  être un tuple de deux véritables Computed ; aucune coercition d'un dictionnaire.
- `validate_destination` : contrôle la forme/cohérence d'une **déclaration** ;
  n'effectue ni résolution DNS, ni connexion, ni vérification des privilèges.
- `project_content(computed)` : construit la projection métier sans données de
  tentative ou identifiants SQL. Cette fonction n'approuve pas une provenance.
- `target_key(computed, destination)` : construit la clé d'une instance déclarée,
  après contrôle du contrat logique et de la révision de calcul attendue.
- `build_key(IdempotencyTuple)` : utilitaire de clé versionnée, contrôlant les
  types, paramètres, identités, formats d'empreintes et dates. Il peut distinguer
  une future version de méthode ; cela ne l'autorise pas dans le pilote v1.
- `canonical_projection` : encodage pur avec limites de taille et profondeur.
- `compare_retry(existing_key, existing_content, candidate_key, candidate_content)` :
  IDENTICAL_RETRY, CONTENT_CONFLICT ou DIFFERENT_KEY ; vérifie les digests et les
  octets canoniques fournis, sans lecture/écriture d'un registre.

Les douze ValidationCode sont propres à la préparation : INVALID_INPUT,
ABSTENTION_REFUSED, INCOMPLETE_BATCH, DUPLICATE_TARGET, INVALID_PROPOSAL,
IDENTITY_MISMATCH, VERSION_MISMATCH, INVALID_FINGERPRINT, UNATTESTED_PROVENANCE,
DESTINATION_MISMATCH, AUTHORIZATION_MISMATCH et JSON_LIMIT. Les **onze** codes
d'abstention ML 3 sont conservés sans ajout. Les erreurs ne recopient pas les valeurs
d'entrée, DSN ou textes de déclaration dans leur message ; seulement code et champ.

## 4. Validation du lot et de sa provenance

La préparation refuse : toute Abstained, tuple incomplet, cible dupliquée/étrangère,
proposition partielle, objet imitant un Computed, autre équipement/capteur,
type/modèle/version incompatible, score/alerte incohérents, dates non conformes,
nombre non fini, JSON inconnu/dupliqué ou hors limites. Les deux propositions
doivent partager le même run_id et prepared_at ; leurs cutoffs respectifs restent
ceux de leurs observations différentes.

Le validateur ML 3 vérifie les invariants de la proposition et les dix références.
La préparation vérifie aussi l'enveloppe Computed : Statistics, reference_ids,
dataset_sha256 et reference_sha256 doivent correspondre exactement aux détails.
Une enveloppe détachée de sa proposition n'est pas acceptée.

La politique v1 reste épinglée sur la révision de calcul déjà validée :
`b6b4d521b9c9456c160433e9343efd48d3c0168d`.
L'empreinte canonique de fixture attendue, déjà calculée en ML 3, est :
`6c8eed59fb2c8b6328899646f93b5191a88c6698be48c51a73b414ce3560dc3a`.
Ces références ne désignent pas le HEAD documentaire actuel comme une implémentation
de calcul. Le manifeste reçu est effectivement canonisé/haché pendant les tests et
comparé à cette empreinte ; aucune fixture dérivée n'est substituée sous le même v1.

La révision/empreinte du dossier de provenance doivent correspondre à cette
politique ; l'UUID de revue doit être celui accepté et attested doit être le booléen
true, pas l'entier 1. code_revision=null/pending_commit est refusé. Le statut
requires_validation de la proposition originale est conservé ; il ne devient pas
une preuve authentifiée par lui-même.

La validation pure vérifie la **concordance de données d'attestation fournies**.
Elle ne consulte pas Git, ne contrôle pas un signataire, ne prouve pas l'existence
d'une revue et n'authentifie pas une autorisation. Le chargement d'une politique
de confiance et le contrôle externe des preuves restent obligatoires en ML 4.2B.
Un appelant capable de fabriquer politique et attestation concordantes ne reçoit
toujours aucun droit d'écriture par cette fonction.

Après contrôle de l'empreinte complète du manifeste, chaque cible est reliée à sa
mesure synthétique : valeur, qualité, unité, timestamp et available_at doivent
correspondre. Références exactes 001…010 pour 011 et 002…011 pour 012 ; leurs
empreintes sont recalculées depuis les observations complètes du manifeste et
comparées aux Computed. Cutoffs fixés au 11/12 janvier à 08:01 UTC. Modifier ce
cutoff peut produire une nouvelle clé via l'utilitaire, mais la préparation v1 le
refuse : un autre scénario nécessite un contrat/politique explicitement validé.

La déclaration d'autorisation doit ensuite correspondre à la destination attendue,
au dataset, à la révision et aux deux projections de contenu/références/cutoffs.
Elle est conservée comme donnée à vérifier, jamais comme credential d'écriture.
PreparationDossier expose toujours trois propriétés non paramétrables :
`destination_verified=false`, `write_authorized=false`, `persistence_ready=false`.

## 5. Canonisation et idempotence logique

Le tuple porte schema_version p101-idempotency-v1, UUID d'instance déclarée,
dataset_sha256, codes équipement/capteur, cible logique et timestamp, cutoff UTC,
type/modèle/version, code_revision du calcul, reference_sha256 et paramètres
10 observations / ddof 1 / cadence 86 400 s / multiplicateur 3 / comparaison stricte.

L'encodage est UTF-8 sans BOM, JSON compact à clés triées, chaînes et clés NFC,
UTC à six décimales. Tous les nombres de la projection de hachage sont normalisés
en chaînes décimales sans notation exponentielle ni zéros finaux superflus.
Booléens et null conservent leur type JSON. Les champs cutoff_utc/predicted_at et
bornes temporelles sont normalisés explicitement ; la primitive du manifeste ML 3
ne normalisait automatiquement que timestamp/available_at. Une collision de clés
après NFC est refusée, ainsi qu'une valeur non finie, un type non JSON ou une
profondeur excessive. Le contenu métier reste numérique dans le candidat details.

Projection de contenu versionnée p101-business-content-v1 : champs déterministes de
prédiction, identités logiques et détails métier du calcul, dont cible, références,
statistiques, paramètres, provenance de calcul et empreintes. run_id, prepared_at
et revision_status provisoire en sont retirés. created_at et ids SQL alloués n'y
figurent jamais. La clé ne contient pas davantage ces champs de tentative/SQL.

Limites : clé canonique <= 4 096 octets, contenu canonique <= 16 384 octets. Les
digests sont calculés par hashlib SHA-256 ; les comparaisons de retry utilisent
**aussi les octets canoniques**, et non le digest seul. Un contenu fourni avec un
digest incorrect ou une représentation non canonique est refusé.

- Même clé et même contenu : retry logique identique, même avec nouveau run_id et
  prepared_at. Les candidats de détails conservent leurs métadonnées de tentative
  distinctes ; le futur stockage devra retourner les métadonnées de première écriture.
- Même clé et contenu différent : conflit de contenu, sans remplacement implicite.
- Version/cutoff/référence/révision/instance différents : clé différente, aucun retry
  déclaré identique. La validité d'une nouvelle version reste une décision de politique.

**Aucun hash Python ne réserve une clé ou ne garantit l'unicité sous concurrence.**
Deux processus peuvent produire la même préparation. UNIQUE PostgreSQL, verrous,
transaction, contrôle du contenu stocké et résolution d'un commit incertain restent
entièrement à réaliser en ML 4.2B selon ML 4.1.

## 6. Mapping conceptuel et bornes des détails

PredictionReadPlan contient exactement les quatorze noms de champs Read :
id, equipment_id, sensor_id, measurement_id, prediction_type, score, level,
is_alert, model_name, model_version, horizon_hours, details, predicted_at, created_at.

Pour id, equipment_id, sensor_id, measurement_id et created_at, la valeur est un
objet SqlDependent explicitant le champ et, si applicable, son identité DEMO.
Ce ne sont ni des entiers SQL, ni des dates fictives, ni des nulls présentés comme
un DTO final valide. Aucun import de PredictionRecord, du DTO SQL applicatif ou
d'une session n'est requis. Aucun objet ORM n'est créé.

Les autres champs sont fixés/validés : anomaly, statistical_deviation, p101-stat-v1,
score 0/1, alerte booléenne correspondante, level/horizon null et predicted_at UTC
de l'observation cible. Le test nominal retrouve les scores 0 pour 011 et 1 pour 012
depuis le calcul synthétique existant.

DetailsDraft contient une copie JSON candidate : métadonnées provisoires de statut
retirées, code_revision fournie et contrôlée contre la politique, vraie clé **logique**
calculée pour l'UUID déclaré. Les parents et mesures portent toujours leurs identités
logiques ; les ids SQL des références/cibles sont absents. Les objets de proposition
ML 3 originaux ne sont jamais mutés. La conversion finale devra remplacer/compléter
les identités aux emplacements du schéma SQL ML 2, notamment les ids équipement,
capteur, cible et dix références ; les identités logiques de parents supplémentaires
du brouillon ne sont pas automatiquement des propriétés autorisées du JSON SQL final.

Le JSON logique d'entrée est borné à 6 000 octets avant parsing ; propriétés JSON
dupliquées et NaN/inf sont refusés. `validate_proposal` ferme ensuite sa structure.
Les limites de chaînes et profondeur de ML 3 sont réutilisées. Après ajout de la clé,
le candidat doit rester <= 4 976 octets, laissant un budget explicite de 1 024 octets
pour les treize futurs mappings SQL (deux parents, une cible, dix références).
Ce budget ne constitue pas une validation des détails enrichis réels : ML 4.2B
devra fermer leur schéma, vérifier les vrais ids et réappliquer la limite totale
6 000 octets/six niveaux. Aucune valeur SQL fictive n'est utilisée pour tester la taille.

## 7. Tests réellement exécutés

Après revue statique et stabilisation du code, un seul lancement ciblé a été effectué :

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
backend/.venv/Scripts/python.exe -m pytest tests/p101_persistence tests/p101_anomaly -q -p no:cacheprovider
```

Résultat : **126 tests réussis en 4,98 s**, aucun échec. Cela comprend 53 cas
unitaires de préparation ML 4.2A et les 73 tests de calcul pur ML 3, repris en
régression parce que leurs contrats et validateurs sont directement réutilisés.
Aucune suite backend complète ni test transactionnel/PostgreSQL/HTTP n'a été lancé.
Les tests purs utilisent une garde de réseau/imports et un contrôle AST des nouveaux
modules ; aucune fixture SQL commune n'est importée. Les valeurs d'hôte, port,
UUID et rôle des tests sont fictives et déclaratives, jamais utilisées pour connecter.

| Couverture | Preuves unitaires |
| --- | --- |
| Lot nominal | Deux véritables Computed, ordonnés, scores 0/1, 14 champs conceptuels et trois indicateurs de non-autorisation false |
| Refus d'entrée | Abstained, zéro/une/trois propositions, doublon, dict/null partiel |
| Identité et version | Autre équipement/capteur/cible ; type RUL, nom de modèle et méthode v2 refusés |
| Provenance | Marqueur false ou entier 1, mauvaise révision/empreinte/revue, provenance pending_commit refusés |
| Empreintes | Enveloppe Computed modifiée, manifeste différent, déclaration avec empreinte invalide ou contenu divergent |
| Canonisation | Ordre des propriétés/lignes, NFC, chiffres 65/65.0, UTC/offset, booléens/nulls et digest attendu calculé indépendamment par hashlib |
| Retry et conflit | Nouveau run/prepared_at : mêmes clés/contenus ; contenu divergent : conflit ; digest falsifié : refus |
| Changement d'identité de calcul | Version/cutoff/référence/révision/instance modifiés : autre clé ; cutoff hors contrat v1 refusé au lot |
| JSON et nombres | NaN/±inf, taille d'entrée excessive, chaîne/projection trop grande, profondeur excessive et propriétés dupliquées refusés |
| Destination déclarée | Base DEV, rôle DEV, forme d'hôte inadmissible, port booléen, UUID invalide et destination différente de la déclaration refusés |
| Immutabilité | Contexte initial égal à sa copie, sortie frozen, copies de détails indépendantes, proposition ML 3 conservant son statut initial |
| Isolation statique/dynamique | Aucun import DB/config/services/HTTP/joblib/sklearn ni appel connect/commit/flush/fit/execute dans le nouveau package ; garde des connexions/résolution DNS pendant les tests |

Les tests de ML 4.1 I01–I12 ne sont pas revendiqués comme exécutés : seules leurs
parties conceptuelles sans base (validation et mapping) sont préparées ici.

## 8. Correspondance ML 4.1 et préparation ML 4.2B

| Conception ML 4.1 | Réalisation ML 4.2A / reste à faire |
| --- | --- |
| Lot de deux computed sans abstention | Contrat et rejet hors base implémentés |
| Validation des dix références et du manifeste | Réutilisation ML 3, liaison au manifeste canonique v1 et contrôle d'enveloppe implémentés ; rapprochement SQL absent |
| Provenance attestée | Concordance politique/données de revue implémentée ; vérification externe de Git/signataire/dossier de confiance à ajouter |
| Tuple p101-idempotency-v1 et contenu déterministe | Implémentés ; aucune réservation ni lecture de registre |
| Retour des 14 champs | Plan conceptuel typé ; DTO SQL final, vrais ids et created_at encore non résolus |
| Garde effective PostgreSQL | Déclaration seulement ; transport, session_user/current_user, marqueur et privilèges non vérifiés |
| Transaction/rollback/commit incertain | Aucune implémentation opérationnelle dans cette sous-étape |
| Registre UNIQUE et protections inverses | Aucun modèle ORM, DDL, trigger ou migration créé |

Avant ML 4.2B : autoriser explicitement son périmètre, le bac à sable et les connexions,
valider la politique externe et les preuves de code/fixture, produire le mapping
des douze mesures, créer les objets sandbox autorisés et implémenter la transaction
unique/contrainte concurrente décrite par ML 4.1. Revalider la destination réelle
contre la déclaration et recalculer/refuser les clés si l'instance ne correspond
pas ; ne pas simplement réétiqueter un dossier existant. Vérifier les contenus et
mappings existants au retry, conserver les premières dates et ids, puis réaliser
I01–I12 sur PostgreSQL isolé. Aucune de ces étapes n'est commencée ici.

## 9. Limites et réserves B-PRE

Les dataclasses et digests ne constituent ni une autorisation, ni une signature,
ni un verrou concurrent. Le pilote v1 est volontairement épinglé à la fixture et
révision validées ; une autre fixture ou méthode nécessite une nouvelle politique
et des tests. L'empreinte SHA-256 porte sur une représentation canonique déterminée,
pas sur une attestation d'origine réelle. Aucun endpoint n'expose ce validateur.

| Réserve | État après ML 4.2A |
| --- | --- |
| B-PRE-01 | Ouverte : aucune authentification/autorisation multi-tenant ni garde effective de session |
| B-PRE-02 | Ouverte globalement : binaire et finitude contrôlés pour la préparation P101 seulement |
| B-PRE-03 | Ouverte backend : UTC/cutoffs vérifiés hors base, routes existantes inchangées |
| B-PRE-04 | Ouverte SQL : identités DEMO vérifiées, aucun rapprochement/FK SQL nouveau |
| B-PRE-05 | Ouverte globalement : JSON de préparation borné ; enrichissement SQL réel encore à valider |
| B-PRE-06 | Ouverte : aucune conservation/cascade/contrainte inverse modifiée |
| B-PRE-07 | Ouverte : aucune pagination, isolation de lecture ou performance mesurée |
| B-PRE-08 | Ouverte : chemins RUL/artefacts et services commitants inchangés et non appelés |
| B-PRE-09 | Ouverte : aucune alimentation d'historique, aucun service opérationnel |
| B-PRE-10 | Ouverte : concordance de provenance déclarée seulement, pas de vérification externe ni réparation historique |
| B-PRE-11 | Ouverte : aucun nouvel endpoint détail/latest ; GET historique non appelé |

## 10. État Git et livraison

Branche `feature/ml-4-p101-persistence`, HEAD conservé
`a002e99ff3ac2adca71225ec4c24caf9f7a13a43`. Les six fichiers de la section 2 sont
ajoutés localement sans indexation ; aucun fichier suivi préexistant modifié.
Index vide, aucun commit. Contrôles finaux réussis : seul ce périmètre apparaît dans
git status, aucun diff de fichier suivi, git diff --check et comparaison des six
nouveaux fichiers contre NUL sans erreur d'espacement. Aucun import/accès SQL,
réseau ou entraînement identifié dans le package. Aucun relancement de tests supplémentaire.

**Rapport et implémentation en attente de validation technique avant tout commit.
ML 4.2B et ML 5 non commencés.**
