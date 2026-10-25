# ML 3 — Calcul pur et tests du pilote P101

Date : 25 octobre 2026. Statut : implémentation locale à valider techniquement,
sans commit. Contrat : [ML 2](ml-2-p101-anomaly-design.md) ; audit conservé :
[ML 1](ml-1-existing-prediction-audit.md).

## 1. Référence et périmètre effectivement réalisé

Départ vérifié dans `D:/projets/industrial-predict` : branche
`docs/ml-2-p101-anomaly-design`, HEAD
`34fe615f310ddc3055e9705037bcd3fa27a1e96b`, index et arbre propres.
Branche créée depuis ce HEAD : `feature/ml-3-p101-anomaly-core`.
Main reste à `85d4bf0f1a03bbb841b5c2deebb8f12786c22dca`.

Le pilote réalise un calcul statistique pur sur une fixture synthétique de P101.
Il sélectionne dix observations passées, prépare leurs statistiques puis appelle
le `StatisticalAnomalyDetector` existant. Il n'appelle ni base, session SQLAlchemy,
API, service de persistance, joblib, modèle supervisé ou forêt. Aucun entraînement,
RUL, risque de panne, Health Score ou recommandation. Aucun nouvel endpoint,
package, changement frontend ou modification du détecteur existant.

Les tests ciblés autorisés ont été exécutés avec le Python déjà installé dans
`backend/.venv`. La suite backend complète n'a pas été lancée. Aucun accès PostgreSQL
ou HTTP, opération SQL, migration, commit, fetch, push, merge ou rebase.

## 2. Fichiers et architecture

Six fichiers ajoutés ; aucun fichier suivi préexistant modifié :

| Fichier | Rôle |
| --- | --- |
| `backend/app/anomaly_detection/p101_contracts.py` | Identité DEMO fixe, version de méthode, onze codes fermés, dataclasses figées Observation/Statistics/LogicalPrediction/Computed/Abstained |
| `backend/app/anomaly_detection/p101_canonical.py` | Parsing UTC strict, décimales canoniques, JSON UTF-8 déterministe, empreintes SHA-256 et borne des détails |
| `backend/app/anomaly_detection/p101_core.py` | Validation, sélection causale, abstention priorisée, moyenne/variance, adaptation au détecteur, proposition logique et validation de sortie |
| `tests/p101_anomaly/fixtures/p101-temperature-v1.json` | Exactement les douze observations ML 2, avec identité complète répétée, UTC, disponibilité, qualité, unité et marqueurs synthétiques |
| `tests/p101_anomaly/test_core.py` | T01–T20 paramétrés et cas complémentaires ; protection contre réseau/imports DB/HTTP/joblib/apprentissage pendant les tests du pilote |
| `docs/ml-3-p101-anomaly-core.md` | Ce rapport et les preuves de validation |

L'identité autorisée est une correspondance en lecture seule :
DEMO-COMP-001 / MLDEMO-COMP-P101 → DEMO-SITE-001 / MLDEMO-SITE-P101 →
DEMO-EQ-001 / MLDEMO-EQ-P101 → DEMO-SEN-001 / MLDEMO-SEN-P101-TEMP.
Elle ne contient aucune clé SQL. Le calcul ne découvre aucune configuration DEV.

### Contrats publics

- `evaluate(manifest, target_id, *, cutoff, prepared_at, run_id, code_revision=None)`
  reçoit un manifeste mémoire et un contexte explicite. Il ne lit ni fichier,
  horloge, Git ou réseau. Résultat discriminé par status computed/abstained.
- Computed porte une LogicalPrediction, la liste ordonnée des dix ids de référence,
  Statistics, dataset_sha256 et reference_sha256. La proposition est figée et ses
  détails sont conservés en JSON sérialisé ; la propriété details retourne une copie.
- Abstained porte code, cible, cutoff UTC si parsable, ids concernés, explication
  bornée et version. prediction est null ; aucun champ score/is_alert.
- `validate_proposal` vérifie le contrat logique, les objets JSON fermés, les
  références, leur empreinte, les statistiques recalculées sur ces dix points et
  l'accord score/alerte. Il ne complète aucun DTO SQL.
- `canonical_bytes` et `manifest_sha256` normalisent un manifeste canonisable ;
  une température invalide ne reçoit pas d'empreinte inventée. Ces fonctions
  lèvent ValueError pour une valeur/température non canonisable.
- `bounded_details` sérialise un objet déjà validé et refuse un dépassement :
  maximum 6 000 octets UTF-8, chaînes <= 240 caractères, six niveaux de conteneurs,
  JSON strict sans NaN/inf. Les tailles par champ et la fermeture des objets sont
  contrôlées par le parseur/validateur, pas par le seul sérialiseur générique.

## 3. Sélection temporelle, calcul et abstention

Le parseur rejette globalement une structure corrompue, une propriété inattendue,
des ids/types interdits, une date naïve ou une précision supérieure à six décimales.
Les dates sont normalisées en UTC à six décimales, sans arrondi silencieux.
Une disponibilité antérieure au timestamp de mesure est également INVALID_INPUT.
L'ordre d'entrée des lignes n'est pas utilisé pour établir leur antériorité.

Pour une cible à T, le périmètre utile est la cible et les observations disponibles
à C dans [T−10 jours ; T]. La référence doit correspondre exactement aux dix jours
T−10…T−1, à 08:00 UTC. L'observation courante est exclue. Aucune autre observation
plus ancienne ne remplace un trou ou une valeur invalide. Les points disponibles
après C ne sont pas utilisés ; un créneau interne manquant produit GAP_OR_CADENCE.
En début de série, moins de dix points et un début connu postérieur à T−10j donnent
INSUFFICIENT_HISTORY. Les timestamps identiques/ids répétés utiles donnent
DUPLICATE_OBSERVATION, sans départage par id ou valeur.

Les validations respectent la priorité ML 2 : INVALID_INPUT, INCONSISTENT_PARENT,
UNIT_MISMATCH, DUPLICATE_OBSERVATION, TARGET_UNAVAILABLE, INSUFFICIENT_HISTORY,
GAP_OR_CADENCE, INVALID_VALUE, INVALID_QUALITY, ZERO_STD, NONFINITE_STATISTIC.
Les chaînes numériques/booléens/collections en guise de valeur sont INVALID_INPUT ;
une valeur absente/null/NaN/infinie est INVALID_VALUE dans la cible/référence.
Une unité autre que °C et une qualité autre que good ne sont jamais converties.

La moyenne et la variance échantillonnale viennent de `statistics.mean` et
`statistics.variance` sur les dix valeurs de référence, puis racine carrée de la
variance. La variance et les autres résultats doivent être finis ; std nulle donne
ZERO_STD avant appel du détecteur. Le détecteur reçoit une seule ligne avec la
valeur cible et ces statistiques, `threshold_std=3.0`. Sa comparaison stricte
`abs(value−mean) > 3×std` est conservée, sans arrondi préalable ni epsilon.

Les tests vérifient indépendamment les dix valeurs et les ids utilisés, la formule
somme/carrés/division par neuf et les statistiques pandas sur les **mêmes dix points
passés**. Un espion vérifie aussi la ligne réellement transmise au détecteur.

## 4. Fixture, empreintes réelles et résultats

Fixture : schema_version `p101-temperature-fixture-v1`, dataset_id
`p101-temp-synthetic-v1`. Températures dans l'ordre :
65 ; 63 ; 67 ; 64,5 ; 65,5 ; 64,5 ; 65,5 ; 65 ; 65 ; 65 ; 65 ; 70 °C.
Ids DEMO-M-001 à DEMO-M-012, du 1er au 12 janvier 2026 à 08:00:00Z,
available_at le même jour à 08:01:00Z, qualité good et synthetic=true.
Le test T01 vérifie les douze valeurs, dates, disponibilités et appartenances.
Aucune mesure historique ni aucun id SQL DEV n'est repris.

Canonisation effectivement exécutée : UTF-8 sans BOM, clés triées, JSON compact,
chaînes NFC, dates UTC à six décimales, valeurs numériques converties en chaînes
décimales normalisées dans le manifeste canonique (mais numériques dans le calcul
et les détails). Observations triées par timestamp/id. L'empreinte de référence
porte sur un objet observations contenant les dix observations complètes, y compris
parents, qualité, unité et disponibilité. Ces empreintes sont vérifiées pendant
les tests contre des encodages/attentes indépendants.

Empreinte SHA-256 réelle du manifeste canonique complet :

`6c8eed59fb2c8b6328899646f93b5191a88c6698be48c51a73b414ce3560dc3a`

| Cible | Références | μ °C | s °C | Écart °C | Seuil °C | Résultat |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| DEMO-M-011 | DEMO-M-001…010 | 65 | 1 | 0 | 3 | computed, score 0, is_alert false |
| DEMO-M-012 | DEMO-M-002…011 | 65 | 1 | 5 | 3 | computed, score 1, is_alert true |

Empreintes SHA-256 réelles des références :

- Cible 011 : `bd7a43412110a9aaf977ae856dd24afbe056ca1f1d97d33572bff4eb687d9d5c`.
- Cible 012 : `289c1bd2a3e4123f07657155d491b86917482c2d424090bb36e2137e0c6c4372`.

La sortie pure a également été relue en mémoire pour consigner ces preuves, avec
run_id de test `00000000-0000-4000-8000-000000000001`, prepared_at fixe
2026-02-01T00:00:00Z et cutoff de la cible à 08:01 UTC. Aucun résultat enregistré
dans une table ou un fichier de données. Les détails logiques sérialisés font
respectivement 2 830 et 2 819 octets UTF-8, avant le futur enrichissement SQL.

Le score est uniquement un indicateur binaire de dépassement statistique, sans
probabilité de panne. Les dix points initiaux ne produisent pas de faux résultats
normaux : leurs évaluations s'abstiennent faute d'historique suffisant.

## 5. Proposition logique, provenance et compatibilité ML 4

La proposition conserve prediction_type anomaly, model_name statistical_deviation,
model_version p101-stat-v1, score 0/1, is_alert cohérent, level/horizon_hours null,
predicted_at = timestamp cible UTC. Les attributs equipment_fixture_id,
sensor_fixture_id et measurement_fixture_id sont des identités logiques explicites.
Aucun id, equipment_id/sensor_id/measurement_id SQL ou created_at n'est inventé.

Les détails sont fermés et versionnés, avec caractère synthétique, run, motif,
parents logiques, cible, dix mesures, moyenne/std/écart/seuil/multiplicateur, cutoff,
prepared_at et empreintes. Ils sont destinés à devenir les détails du DTO final
après mapping autorisé en ML 4 ; la proposition n'est pas un PredictionRecordRead
persisté et ne doit pas être envoyée telle quelle au frontend.

Écarts intentionnels au schéma final ML 2, sans modification de son document :

- Les ids SQL sont absents des détails et remplacés par les identités logiques ;
  ML 4 doit résoudre/vérifier les ids avant construction du DTO à 14 champs.
- idempotency_key est absente : elle dépend de l'instance bac à sable et d'une
  révision d'implémentation validée encore indisponibles. Aucune clé factice.
- producer.code_revision est null par défaut avec revision_status pending_commit.
  Une révision fournie doit être un SHA de 40 caractères minuscules et porte
  requires_validation : sa forme ne prouve ni son existence ni sa correspondance
  aux sources. Aucun SHA documentaire n'est injecté par défaut.
- Ces états de provenance sont une extension du contrat **logique provisoire** ;
  ils ne doivent pas être acceptés comme preuve finale de persistance.

Après un commit de code explicitement autorisé, un processus de livraison devra
vérifier le SHA réel du commit contenant ces modules et la fixture, l'absence de
modifications locales, le succès des tests pertinents et la correspondance au code
exécuté. Il fournira cette révision au préparateur ; aucun SHA auto-référentiel
n'est codé dans le fichier qu'il identifie. La validation complète et la suppression
de l'état provisoire appartiennent au raccordement ML 4, pas à ce calcul pur.

Le futur service ML 4 devra aussi attribuer created_at, valider le contrat SQL,
recontrôler la borne JSON après enrichissement et maîtriser atomiquement registre
unique/prédictions. `PredictionService.create` conserve son commit interne et n'est
pas appelé ici. Aucune destination, autorisation d'écriture ou idempotence SQL n'est
simulée comme déjà réalisée.

## 6. Tests et preuves d'exécution

Ordre respecté : lecture statique des API → implémentation ciblée → tests ML 3 →
régression anomaly_detection sans entraînement → durcissements ciblés et tests ML 3
justifiés par les changements → analyse documentaire/Git.

Commandes exécutées depuis la racine, sans cache pytest ni écriture bytecode :

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
backend/.venv/Scripts/python.exe -m pytest tests/p101_anomaly -q -p no:cacheprovider
backend/.venv/Scripts/python.exe -m pytest tests/anomaly_detection -q -p no:cacheprovider --ignore=tests/anomaly_detection/test_isolation_forest_detector.py --ignore=tests/anomaly_detection/test_sensor_detector.py
```

| Validation | Résultat |
| --- | --- |
| Premier passage ML 3 | 69 réussis, 1 échec sur valeurs finies extrêmes |
| Après correction numérique | 70 réussis, aucun échec |
| Régression existante sans entraînement | 38 tests et 51 sous-cas réussis, aucun échec |
| Dernier passage ML 3 après durcissements | 73 réussis en 1,60 s, aucun échec |

L'échec initial révélait le chemin `statistics.stdev(..., xbar=mean)` sur ±1e308,
qui levait une AttributeError interne au lieu d'une abstention. Le chemin corrigé
calcule la variance sans xbar fourni, contrôle sa finitude puis prend sa racine ;
les dépassements sont transformés en NONFINITE_STATISTIC avant détecteur. Le cas
reste couvert. Aucun changement au détecteur commun n'a été nécessaire.

Les tests test_isolation_forest_detector et test_sensor_detector existants ont été
exclus explicitement car leurs scénarios entraînent des modèles, interdit dans ML 3.
Ce n'est donc pas une validation de toute la suite anomaly_detection. Les autres
tests sélectionnés couvrent schémas, statistique, z-score, vote, synthèse et explication.
Les ultimes modifications ne touchent que les nouveaux modules du pilote ; aucune
relance de ces tests existants n'était nécessaire après leur succès.

### Correspondance T01–T20

| Cas contractuel | Preuve implémentée |
| --- | --- |
| T01 | Fixture exacte, témoin normal, copie des entrées inchangée, références 001…010 |
| T02 | Saut positif, références 002…011, dix valeurs explicites, formule manuelle et pandas indépendantes |
| T03 | Cible 60, écart 5, alerte vraie |
| T04 | Cibles 62/68, égalité au seuil 3 sans alerte |
| T05 | Évaluation de chacun des dix premiers points : INSUFFICIENT_HISTORY |
| T06 | Référence constante, cible identique/différente : ZERO_STD sans détecteur |
| T07 | Référence/cible null, NaN, ±inf, chaîne, booléen, liste/dict et valeur absente ; aucun détecteur |
| T08 | suspect/estimated/bad/missing/inconnue dans référence et cible |
| T09 | Doublon id, instant, offsets équivalents et duplication intégrale |
| T10 | Créneau interne supprimé et décalage d'une seconde |
| T11 | °F, K, C et Celsius refusés |
| T12 | Mauvais ids entreprise/site/équipement/capteur ; manifeste non synthétique |
| T13 | Ajout/modification de valeurs futures : statistiques/décision/référence inchangées ; empreinte globale différente |
| T14 | Référence arrivée après cutoff : abstention ; nouveau cutoff permet une nouvelle proposition |
| T15 | Cible postérieure au cutoff ou non encore disponible |
| T16 | Changement de la cible et espion sur l'entrée effective du détecteur, sans modifier la référence |
| T17 | Permutation, offsets équivalents, microsecondes préservées ; dates naïves/trop précises refusées, cadence décalée refusée |
| T18 | Octets canoniques attendus littéralement, valeurs 65/65.0, tri des lignes/clés, hashes calculés par hashlib indépendamment |
| T19 | Proposition sans id/created_at SQL, états et JSON borné, champs inconnus/reférence altérée refusés, métadonnées de révision provisoires |
| T20 | Seuils exacts et flottants immédiatement voisins via nextafter, comparaison stricte |

Cas complémentaires : priorités combinées, onze codes fermés, statistiques non
finies, date provoquant un débordement de calendrier, manifeste global non
canonisable et JSON non objet. Les tests n'importent pas l'application API ni les
fixtures SQL communes ; une garde d'import et de connexion pendant les tests du
pilote refuse les chemins DB/HTTP/joblib/sklearn/services/ML annexes.

## 7. Limites et réserves conservées

Un manifeste globalement non canonisable, par exemple NaN dans une observation
future, donne INVALID_INPUT avant appel du détecteur : on ne peut pas attester
l'identité d'un dataset invalide avec son empreinte canonique contractuelle. L'invariance
temporelle est prouvée pour les extensions/modifications **valides** du manifeste ;
les critères qualité/statistiques de points futurs valides n'alimentent pas la
référence. Cette distinction précise le contrôle structurel global prévu par ML 2.

La variance peut être non représentable pour des entrées finies extrêmes ; le
pilote s'abstient. La cadence est volontairement quotidienne exacte. La qualité,
la disponibilité et les parents sont des informations synthétiques du manifeste,
pas une preuve de provenance authentifiée. Le faible jeu construit pour ces seuils
ne mesure ni performance industrielle ni risque de panne. La validation de sortie
ne remplace pas l'autorisation de ressource ou la transaction SQL.

| Réserve | État ML 3 |
| --- | --- |
| B-PRE-01 | Ouverte : aucune authentification/autorisation multi-tenant ; contrôle logique DEMO uniquement |
| B-PRE-02 | Ouverte globalement : contrat binaire borné du pilote seulement, producteurs existants inchangés |
| B-PRE-03 | Ouverte backend : UTC/cutoff du calcul pur testés, aucune route durcie |
| B-PRE-04 | Ouverte SQL : parents logiques contrôlés, aucun mapping/FK composé ajouté |
| B-PRE-05 | Ouverte globalement : JSON logique fermé/borné testé ; stockage générique inchangé |
| B-PRE-06 | Ouverte : aucune politique de cascade/conservation modifiée |
| B-PRE-07 | Ouverte : aucune mesure de charge, transaction de lecture ou pagination modifiée |
| B-PRE-08 | Ouverte : POST RUL/artefacts/idempotence existants non modifiés et non appelés |
| B-PRE-09 | Ouverte : calcul pur disponible, aucune alimentation d'historique ou orchestration ajoutée |
| B-PRE-10 | Ouverte : provenance du pilote explicitement provisoire, aucune donnée historique réparée |
| B-PRE-11 | Ouverte : aucune nouvelle route détail/latest ; consultation future via GET existant |

## 8. État Git et suite

Branche de travail `feature/ml-3-p101-anomaly-core`, HEAD inchangé
`34fe615f310ddc3055e9705037bcd3fa27a1e96b`. Index vide ; six fichiers nouveaux
non indexés listés section 2 ; aucun fichier suivi existant modifié. Main inchangée.
Contrôle `git diff --check` et vérification des six nouveaux fichiers contre NUL
réussis sans erreur d'espacement, sans indexation ni commit. Aucun import SQL,
HTTP, joblib ou sklearn et aucun appel fit dans les trois modules du pilote.

Les contrats/documents ML 1 et ML 2 sont conservés. ML 4 n'est pas commencé ;
aucune infrastructure ou garantie de persistance n'est mise en place ici.
**Attente de validation technique consolidée avant toute demande de commit.**
