# UI 9.2 - Modèles et accès GET Predictions

Date : 24 octobre 2026. Implémentation et validations terminées, en attente
de validation utilisateur. Aucun commit effectué. UI 9.3 non commencée.

## Référence et périmètre

Départ sur `main` propre, avec HEAD, main et référence locale origin/main à
`05545a88dcd45940f00c1c029d9e567a9c5a4cee`. Aucun fetch effectué ; concordance
des références locales constatée, sans vérification directe du serveur distant.
Branche créée : `feature/frontend-predictions`.

Référence fonctionnelle : [conception UI 9.1](etape-ui-9.1-predictions.md),
PRE-01 à PRE-16 validées. Cette étape couvre seulement les DTO, le transport
GET et la validation isolée de leurs contrats. Aucun composant, façade, page,
route, lien Equipment, style existant ou autre document modifié.

## Contrats implémentés

### DTO et pagination

La lecture de `backend/app/schemas/prediction_record.py` confirme **14 champs** :
equipment_id, sensor_id, measurement_id, prediction_type, score, level,
is_alert, model_name, model_version, horizon_hours, details, predicted_at,
puis id et created_at dans PredictionRecordRead. Les mentions « 15 champs »
du document UI 9.1 sont une erreur de comptage documentaire : aucun quinzième
champ n'a été ajouté, et ce document historique reste inchangé.

PredictionRead définit ces 14 propriétés obligatoires. sensor_id,
measurement_id, level, is_alert, model_name, model_version, horizon_hours et
details sont nullables. Les autres propriétés ne le sont pas. PredictionType
est l'union exacte `anomaly | failure_risk | health_score | rul`.
PredictionPage réutilise `Page<PredictionRead>` du core, sans nouvelle pagination.

details utilise JsonObject/JsonValue récursifs, sans `any`. La racine doit être
un objet ou null ; les valeurs imbriquées peuvent être objets, tableaux,
chaînes, booléens, nombres finis ou null. Les valeurs undefined, fonctions,
BigInt, symboles, objets non JSON, tableaux creux et cycles sont rejetés.
La traversée itérative accepte les objets profonds et les sous-objets partagés
sans modifier le JSON reçu. Aucune limite de 10 000 caractères ou de six
niveaux n'est appliquée au transport : ces limites restent exclusivement des
choix de présentation future et ne limitent pas le volume réseau ou le backend.

### Requête et temporalité

Seule opération publique : `PredictionsApiService.list(query)`.
Seul endpoint : `GET /api/v1/equipments/{equipment_id}/predictions`.
Observable froid : rien n'est envoyé avant abonnement. Aucun corps de requête.
Les erreurs locales de validation sont émises par l'Observable comme TypeError.

equipment_id est obligatoire et placé dans le chemin. Whitelist query exacte :
page, page_size, prediction_type, level, is_alert, start_time, end_time.
company_id, site_id et les autres clés supplémentaires ne sont jamais transmis.
Les paramètres optionnels undefined sont omis ; aucune valeur par défaut
fabriquée n'est envoyée. Les métadonnées de réponse sont contrôlées avec les
défauts backend documentés page=1 et page_size=20 en cas d'omission.

- Identifiants et pagination : entiers JavaScript sûrs, equipment_id/page >=1,
  page_size de 1 à 100 ; aucune coercition de chaîne ou booléen.
- level filtre : chaîne libre, de 1 à 50 points de code Unicode, conservée
  exactement, espaces compris ; aucun enum de niveau inventé.
- is_alert : true et false transmis explicitement ; absence distincte de false.
  null ne constitue pas une valeur valide de filtre query.
- Période predicted_at `[start_time, end_time]` : bornes inclusives, égalité
  permise y compris pour des chaînes avec offsets différents représentant le
  même instant ; inversion rejetée avant HTTP. Une seule borne est autorisée.
- Réutilisation du comparateur pur `measurementInstant` existant, sans copie
  du parseur ni import de service/façade Measurements ou Maintenance.
  `validatePredictionPeriod` adapte uniquement la comparaison `>` ; le helper
  Measurements rejetant l'égalité et sa convention de fin exclusive sont exclus.
- Calendrier, offset explicite et précision maximale de six décimales sont
  validés. Pas de conversion via Date, d'arrondi à la milliseconde, de Z ajouté,
  de normalisation, de changement d'offset ou de réécriture des chaînes ISO.

### Réponse et erreurs

Le HTTP reçoit `unknown`, puis vérifie la structure avant d'exposer PredictionPage :
items tableau, total/page/page_size/pages entiers sûrs, compteurs non négatifs,
pages cohérent avec ceil(total/page_size), page et taille correspondant à la
requête, nombre d'items compatible avec taille/total et absence d'items hors plage.
Une page hors plage vide avec total non nul reste valide. Une page vide avec
total=0 et pages=0 reste valide. Aucune exigence de remplissage exact de chaque
page n'est ajoutée, compte tenu des lectures items/COUNT backend distinctes.

Chaque ligne est vérifiée : présence des 14 clés, types et nullabilité,
identifiants positifs sûrs, equipment_id identique à celui de la requête,
prediction_type exact, score fini, horizon fini strictement positif ou null,
JSON générique valide, predicted_at et created_at calendaires avec offset.
Les chaînes temporelles, scores, métadonnées, ordre serveur et champs nullables
restent inchangés. Le scope et la pagination sont capturés à l'abonnement :
une mutation ultérieure de l'objet query ne change pas la validation en cours.

Les niveaux de réponse restent libres, y compris inconnus, vides ou dépassant
50 caractères : le schéma Read les déclare `str | None` sans la contrainte de
longueur du filtre query. Aucun niveau ou score n'est recalculé. Le score
générique n'a pas de plage métier imposée : une valeur finie n'établit ni une
probabilité ni une échelle sur 100. La provenance et les détails du producteur
sont transmis sans interprétation ; aucune présentation n'est encore implémentée.

Les erreurs HTTP sont propagées comme HttpErrorResponse avec statut et corps
d'origine. Aucun retry, cache, élargissement du périmètre, résultat vide de
remplacement, polling ou génération automatique. La désinscription annule le GET.
Il n'existe aucune méthode de détail, d'écriture, RUL ou Health Score dans ce service.

Durcissements frontend explicites par rapport au schéma backend générique :
entiers sûrs et positifs pour les IDs, nombres finis, dates obligatoirement avec
offset et contrôles de cohérence de Page. Le backend ne garantit pas toutes
ces contraintes dans ses types Pydantic/SQL ; une réponse incompatible devient
une erreur de contrat, sans correction silencieuse. Aucun contrat backend modifié.

## Fichiers créés

Sous `frontend/src/app/features/predictions/` :

- `models/prediction.model.ts` : unions et DTO 14 champs, JSON et Page.
- `models/prediction-page-query.model.ts` : equipment_id et sept paramètres GET.
- `data-access/predictions-api.service.ts` : GET unique et validation défensive.
- `data-access/predictions-api.service.spec.ts` : tests typés et HttpTestingController.
- `utils/prediction-time.ts` : validation de période inclusive.
- `utils/prediction-time.spec.ts` : contrat temporel inclusif et instants précis.

Septième fichier : le présent rapport. Aucun fichier préexistant modifié.
Configuration Vitest à deux workers réutilisée depuis le fichier local ignoré
`frontend/tmp/ui-8.8/vitest.config.mjs` ; aucun package ou fichier de configuration
suivi ajouté ou modifié.

## Tests et build effectivement exécutés

Commandes depuis `frontend/`, exécutées séquentiellement sur les sources finales :

```powershell
node node_modules/@angular/cli/bin/ng.js test --watch=false --include=src/app/features/predictions/**/*.spec.ts --runner-config=tmp/ui-8.8/vitest.config.mjs --progress=false
node node_modules/@angular/cli/bin/ng.js test --watch=false --runner-config=tmp/ui-8.8/vitest.config.mjs --progress=false
node node_modules/@angular/cli/bin/ng.js build --configuration production --progress=false
```

| Validation | Résultat exact |
| --- | --- |
| Tests ciblés finaux | **218 réussis, 2 fichiers**, 0 échec ; durée Vitest 4,81 s |
| Suite Angular complète, une seule exécution | **2 130 réussis, 74 fichiers**, 0 échec ; durée Vitest 35,61 s |
| Build production, une seule exécution | **Réussi**, génération en 12,063 s |
| Bundle initial | **605 998 octets, 606,00 kB**, transfert estimé 153,92 kB |
| Avertissement budget | Dépassement initial existant de **106,00 kB** au-dessus de 500 kB ; aucun autre avertissement signalé |

La taille exacte est la somme des neuf fichiers initiaux listés par le build,
mesurés dans `frontend/dist/industrial-predict-ui/browser`. Elle est identique
à la référence historique UI 8.8 de 605 998 octets. La feature n'est pas encore
raccordée à une page/route ; ses nouvelles capacités ne sont pas accessibles
depuis l'interface et leur transport inutilisé n'ajoute pas de chunk Predictions.
Budgets inchangés : initial 500 kB/1 MB, composant 4/8 kB.

Avant le résultat ciblé final : une compilation a échoué car une constante de
test `URL` masquait le constructeur natif ; renommée ENDPOINT avant la suite
complète. La tentative suivante a compilé, puis rencontré EPERM sur le cache
temporaire Vitest Windows, avant l'exécution des tests. La relance avec accès
autorisé a donné les 218 réussites ci-dessus. La suite complète et le build
n'ont pas été répétés ; aucun code exécutable modifié après leur validation.

Couverture : quatre types, 14 clés exactes et suppression de chacune, null vs
false vs absence, paramètres seuls/combinés/omis, whitelist et Unicode,
pagination et pages vides/hors plage, offsets équivalents et microsecondes,
calendriers/dates naïves/inversions invalides, scores et horizons non finis,
IDs invalides, niveaux inconnus, rattachement étranger, JSON générique profond
et volumineux, mutation query, corps HTTP d'erreur 401/403/404/422/500/503,
erreur réseau et annulation. Les tests interdisent les requêtes autres que GET
et les endpoints de calcul/recommandation ; aucun accès HTTP réel n'est utilisé.

La sémantique inclusive serveur est vérifiée par lecture de
`PredictionRepository` (`>=` et `<=`) et les tests HTTP prouvent que les deux
bornes sont transmises sans altération. Les fixtures ne prouvent pas une
comparaison SQL exécutée ou l'état réel de DEV : cette recette reste UI 9.6.

Journaux locaux ignorés : `frontend/tmp/ui-9.2/targeted-tests.log`,
`full-tests.log`, `build.log`. Aucun journal, bundle ou artefact de cache ajouté
au périmètre Git.

## Risques conservés et limites

| Risque UI 9.1 | Situation après UI 9.2 |
| --- | --- |
| B-PRE-01 | Authentification, autorisation de ressource et isolation multi-tenant toujours absentes ; le contrôle equipment_id frontend ne sécurise pas l'API ni une production SaaS |
| B-PRE-02 | Score/level génériques backend inchangés ; pas d'échelle ou de probabilité déduite par le transport |
| B-PRE-03 | Offsets et période validés côté client seulement ; bornes inclusives et égalité conservées, défauts backend non corrigés |
| B-PRE-04 | FK équipement/capteur/mesure indépendantes inchangées ; seule l'appartenance de la ligne à l'équipement demandé est vérifiée ici |
| B-PRE-05 | JSON backend non discriminé et non borné ; validation des valeurs JSON sans limite artificielle de présentation ; risque réseau volumineux conservé |
| B-PRE-06 | Cascades de suppression backend inchangées ; aucun DELETE ajouté |
| B-PRE-07 | OFFSET/COUNT distincts et index simples inchangés ; pagination client bornée sans chargement exhaustif |
| B-PRE-08 | Risques d'inférence/persistance/artefacts POST RUL inchangés ; aucun appel à ces endpoints |
| B-PRE-09 | Alimentation historique et absence de persistance du POST Health Score inchangées ; aucune génération automatique ni diagnostic « modèle absent » à partir d'une liste vide |
| B-PRE-10 | Données historiques invalides et provenance incomplète possibles ; contrat défensif ne répare pas les données backend |
| B-PRE-11 | Aucun GET détail ou latest exposé ; service limité à la liste existante |

PRE-02/03 pour la chaîne Entreprise -> Site -> Équipement, PRE-04 pour l'URL,
PRE-08 pour la présentation selon provenance, PRE-09 pour le rendu JSON,
PRE-10 pour les états d'écran, PRE-11/12 pour navigation/accessibilité et
PRE-14 pour l'orchestration de façade restent à implémenter aux étapes prévues.
Ils ne sont pas présentés comme livrés par ce seul transport. Aucun test visuel,
clavier ou lecteur d'écran, ni recette DEV revendiqué ici.

Aucun accès PostgreSQL/Docker, calcul ML, test backend, package nouveau,
appel HTTP réel ou donnée fictive persistée. Les données de test restent des
fixtures locales HttpTestingController.

## État Git final

- Branche : `feature/frontend-predictions`.
- HEAD, main et origin/main local restent à `05545a88dcd45940f00c1c029d9e567a9c5a4cee`.
- Sept fichiers nouveaux non suivis : six fichiers Predictions et ce rapport.
- Aucun fichier suivi préexistant modifié ; index vide.
- `git diff --check` et contrôle des nouveaux fichiers sans erreur d'espaces.
- Aucun commit, push, merge ou rebase ; UI 9.3 non commencée.

Validation utilisateur attendue avant commit ou poursuite.
