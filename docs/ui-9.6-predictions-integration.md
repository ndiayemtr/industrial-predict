# UI 9.6 — Recette intégrée Predictions sur PostgreSQL DEV

Date de recette : **25 octobre 2026**. Branche `feature/frontend-predictions`,
HEAD `b92ab9e406d037dc8505b0e90dd2c0eb52d9cc6b`, dépôt propre avant recette.
Sections utiles du guide DEV et des documents UI 9.1 à UI 9.5 consultées.

**Résultat : lectures vides et navigations conformes dans le périmètre observé ;
couverture DEV partielle.** La table `prediction_records` existe mais contient
**0 ligne**. Aucune prédiction créée pour compléter les preuves. Les huit tables
métier et leurs 40 lignes sont identiques avant/après. Les captures XHR restent
indisponibles : les GET indépendants ne sont pas présentés comme trafic Angular.

## Identité effective et limites d'exécution

Les services permanents étaient déjà disponibles. Aucun démarrage ou arrêt de
service, aucune instance Angular supplémentaire, aucune opération Docker.
Seuls les ports DEV 4201, 8001 et 5434 ont été utilisés ; aucun accès aux ports
historiques 4200, 8000 ou 5433.

| Élément | Vérification effective |
| --- | --- |
| Angular | `http://127.0.0.1:4201`, GET `/__dev/identity` conforme via le proxy |
| FastAPI | `http://127.0.0.1:8001`, même diagnostic conforme directement |
| PostgreSQL | Connexion à `127.0.0.1:5434`, base effective `industrial_predict_dev` |
| Rôle SQL effectif | `ui47_app`, non superutilisateur ; privilèges élevés exclus par le contrôleur d'identité existant |
| PostgreSQL effectif | `17.10 (Debian 17.10-1.pgdg13+1)` |
| Révision | `09ac8101e9fe` en HTTP et dans `alembic_version` |
| Marqueurs | Mode HTTP `local-development`, en-tête d'environnement conforme, instance comparée à la configuration privée ; OID SQL 16384 et cluster nommé `industrial-predict-development` conformes |

Les diagnostics ont précédé les lectures métier. Le collecteur HTTP a revalidé
les identités directe et proxy ; chaque instantané SQL a vérifié l'identité de
sa connexion avant inventaire. Aucune configuration privée, URL de connexion,
valeur de secret ou valeur privée du marqueur d'instance publiée.

Aucun POST/PATCH/DELETE, calcul RUL/Health Score, seed, migration, reset,
nettoyage ou écriture PostgreSQL. Aucun changement frontend/backend exécutable,
contrat API, dépendance ou budget. Les collecteurs temporaires ignorés ne font
pas partie de l'application ni de la livraison. Aucune suite Angular ou build
relancé, aucun commit, push, merge ou rebase. UI 9.7 non commencée.

## Inventaire PostgreSQL avant/après

Instantanés collectés respectivement à **09:40:54.821235 UTC** et
**09:46:55.414152 UTC**, dans des transactions distinctes :

```sql
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL TIME ZONE 'UTC';
SET LOCAL DateStyle = 'ISO, YMD';
SET LOCAL extra_float_digits = 3;
-- Identité, inventaire, COUNT et SELECT ordonnés par id.
ROLLBACK;
```

`transaction_read_only = on` et `transaction_isolation = repeatable read`
effectivement relus. La connexion impose également
`default_transaction_read_only=on`. Les huit tables proviennent de la whitelist
de l'outillage DEV et sont toutes présentes dans le catalogue public ;
`alembic_version` est contrôlée séparément, hors compte des tables métier.

| Table | Avant | Après | Empreinte de table SHA-256, identique avant/après |
| --- | ---: | ---: | --- |
| companies | 2 | 2 | `457092dde2badcab01a07d9158093f9b8d7ddcc952e2b3c2fa903de188a2ab90` |
| sites | 4 | 4 | `9d80b1a639ad2f095fc508363aa66788983e0b59e763fa552ae17fbd02e76850` |
| equipments | 6 | 6 | `8b9d6efae46c3323e7ba2ff8c6e731654d5380926255f40f43abf3498b70849c` |
| sensors | 7 | 7 | `c56118ba0daf587d422bb2dffa0b810983ddfa6124e59f647b40ccfa7d06b8c1` |
| measurements | 18 | 18 | `39cd781a0ee9b034e61fe77cb0e552c302f151c4187fd223761c7a8c5f28429b` |
| maintenance_records | 3 | 3 | `3b67f85c5455fa36a89d0ae60546785dc7e519b8083f96e7d2bce58622d8791c` |
| prediction_records | 0 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| maintenance_recommendations | 0 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| **Total métier** | **40** | **40** | **0 ajout, 0 suppression, 0 modification de ligne** |

Les 40 lignes ont été comptées et relues ; leur nombre n'a pas été présumé à
partir des rapports historiques. Les deux tables vides ont la SHA-256 du texte
vide, résultat normal et non une empreinte de ligne inventée.

Méthode reproductible : chaque ligne est obtenue par
`SELECT t.id, to_jsonb(t)::text ... ORDER BY t.id`, avec les paramètres de
sérialisation ci-dessus. SHA-256 UTF-8 de ce texte pour chaque ligne. Empreinte
de table : SHA-256 de la concaténation ordonnée de `id:empreinte_ligne` suivi
d'un saut de ligne. Empreinte globale : SHA-256 des entrées
`table:compteur:empreinte_table` suivies d'un saut de ligne, par nom de table.
Cette méthode porte sur toutes les colonnes métier lues, sans modifier les
valeurs ni ajouter un offset aux dates administratives naïves.

Empreinte globale avant **et** après :

```text
0e7650ab8cda04a6e3d23b6de6e172cadd90d922e29904c9703f077722b07442
```

Les ensembles d'IDs, toutes les empreintes par ligne, les compteurs et les
empreintes de table sont égaux. Les colonnes Predictions, les rattachements
Equipment/Site/Company et les valeurs du capteur 1 comparées sont également
inchangés. Conclusion limitée aux deux instantanés, sans prétendre à un journal
de toutes les transactions concurrentes éventuelles.

### Écart historique du capteur 1 conservé

Valeurs réelles avant/après : description `Capteur fictif` et `updated_at`
`2026-10-20T22:11:55.315993`, sans offset ajouté. Le fichier de seed attend
`Capteur fictif.` et `2026-10-16T12:00:00`. Empreinte de la ligne, identique
avant/après et à celle documentée lors de UI 8.6 :

```text
91a8dcf3ba8902082532cecb9f932f6df1f58719f2cd7056ecf10db408c2d899
```

Le seed strict reste historiquement non conforme. Ni son application ni son
contrôle exécutable ne sont lancés ; aucune correction ou nouvelle conformité
revendiquée. La comparaison utilise seulement les valeurs et le JSON versionné.

## Disponibilité réelle de Predictions et rattachements

`prediction_records` est présente dans les deux instantanés. Le catalogue
confirme **14 colonnes** : id, equipment_id, sensor_id, measurement_id,
prediction_type, score, level, is_alert, model_name, model_version,
horizon_hours, details, predicted_at, created_at. Les colonnes de score/horizon
sont double precision, les deux dates timestamp with time zone, details JSON.
Les huit colonnes nullables correspondent au DTO UI 9.2. Cela confirme le
schéma constaté, pas la conformité d'une instance DTO inexistante.

Rattachements vérifiés par jointures sur les références effectivement présentes :

| Equipment | Code | Site | Company |
| ---: | --- | ---: | ---: |
| 1 | UI47-EQ-A-PUMP | 1 | 1 |
| 2 | UI47-EQ-A-COMP | 1 | 1 |
| 3 | UI47-EQ-A-CONV | 2 | 1 |
| 4 | UI47-EQ-B-GEN | 3 | 2 |
| 5 | UI5-EQ-TEST-001 | 1 | 1 |
| 6 | UI57-EQ-20261020-01 | 1 | 1 |

Aucune prédiction, donc aucun type, équipement producteur, intervalle de
prédiction, niveau ou jeu de détails réel à inventorier dans cette table.

## GET HTTP indépendants et comparaisons SQL

**33 GET Predictions indépendants exécutés, 33 contrôles conformes** :
30 vers FastAPI 8001 et 3 via le proxy Angular 4201. Ces appels utilisent
uniquement `/api/v1/equipments/{id}/predictions`, sur les six équipements
existants ci-dessus. Aucune redirection suivie, aucune mutation ni endpoint ML.
Les paramètres sont limités à la whitelist du GET.

**26 réponses 200**, chacune comparée à un COUNT et à un SELECT paginé SQL
exécutés dans une transaction explicitement REPEATABLE READ READ ONLY. La
comparaison porte sur l'ensemble du Page : items, total, page, page_size, pages.
Pour chaque cas valide : `items=[]`, `total=0`, `pages=0`, pagination demandée
conservée (défauts 1/20 si omise).

| Groupe exécuté | Cas | Résultat réel et limite |
| --- | --- | --- |
| Périmètres | GET sans filtre pour chacun des IDs 1 à 6 | 6 réponses 200 vides, SQL correspondant vide |
| Pagination | page 2/taille 20, page 999/taille 1, page 1/tailles 1 et 100 | 4 réponses conformes ; pages au-delà de 0 acceptées. Aucun cas hors plage avec total positif disponible |
| Types | anomaly, failure_risk, health_score, rul séparément | 4 réponses 200 ; aucun enregistrement réel d'un de ces types |
| Niveau | critical et chaîne libre `  niveau DEV 日本  ` | 2 réponses 200 ; acceptation de chaîne libre, effet de filtrage non discriminable sur table vide |
| Alerte | true et false séparément, comparés au GET sans filtre | URLs effectivement distinctes ; réponses toutes vides. Différence entre lignes false/true/null non démontrable ici |
| Temps | début seul, fin seule, deux bornes identiques, mêmes instants avec offsets différents | 4 réponses 200 conformes au SQL ; pas de ligne sur une borne à examiner |
| Combinés | page 2/taille 1, rul, critical, false, période à six décimales | Réponse vide conforme au SQL, AND exécuté sur toutes les conditions |
| Proxy permanent | défaut pour Equipment 1, false pour Equipment 4 (Company 2), health_score/false/bornes égales avec offsets pour Equipment 1 | 3 réponses 200 conformes aux mêmes lectures SQL |

**7 réponses 422 attendues**, avec tableau `detail`, pour page=0, page_size=101,
type inconnu, niveau vide, niveau de 51 caractères, alerte invalide et date
invalide. Elles ne sont pas présentées comme comparaisons de lignes SQL.

Exemple sans filtre, réellement reçu sur P101 :

```json
{"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0}
```

### Couverture temporelle exacte

Les requêtes ont effectivement transmis et accepté :

- `2026-10-25T12:00:00.123456Z` comme début et fin identiques.
- Début `2026-10-25T14:00:00.123456+02:00` et fin
  `2026-10-25T12:00:00.123456Z`, deux chaînes distinctes pour le même instant.
- Période combinée de `2026-10-01T02:00:00.000001+02:00` à
  `2026-10-25T12:00:00.999999Z`.

Le SQL comparatif emploie `predicted_at >= CAST(:start_time AS timestamptz)` et
`<= CAST(:end_time AS timestamptz)`, avec ORDER BY predicted_at DESC puis id DESC,
LIMIT et OFFSET. Aucune convention de fin exclusive transposée. L'acceptation
de l'égalité, des offsets explicites et des six décimales est prouvée en HTTP.
L'inclusion effective d'une ligne à la borne, la discrimination à la microseconde,
le tri de plusieurs lignes et la restitution de leurs dates ne sont **pas**
prouvés en DEV sur ces résultats vides. Aucun enregistrement synthétique ajouté.

## Observations Angular réelles

Parcours exécutés dans le navigateur sur le seul environnement permanent 4201,
sans interception par des fixtures :

1. Sidebar → Prédictions : vraie page, état Sélection attendue, aucune fiche
   Equipment liée tant que le contexte est incomplet.
2. Sélection explicite Company 1, Site 1 puis Equipment 1. Aux étapes partielles,
   attente et absence de lien fiche ; équipement désactivé avant le site.
   Après résolution, noms/code de la chaîne réelle et **0 prédiction / Aucune
   prédiction enregistrée** pour Pompe de circulation P101.
3. Prédictions → Equipment : Retour aux prédictions seul. Ouverture directe de
   `/equipments/1` sans origine : Voir les prédictions seul après résolution de
   Site/Company. Son action retourne aux IDs 1/1/1 avec page 1, taille 20.
4. Type RUL, niveau critical et alerte Non appliqués par les contrôles : URL
   avec `prediction_type=rul&level=critical&is_alert=false`, état Aucun résultat.
5. Ouverture directe avec ces filtres, page 2, taille 1 et les deux instants
   équivalents +02:00/Z à six décimales. Les chaînes originales demeurent dans
   la période appliquée et dans le contexte `pre_`.
6. Saisie d'un brouillon de niveau non appliqué, puis lien Equipment :
   `pre_level=critical`, pas le brouillon. Retour contextuel seul, autres actions
   présentes, aucun bouton Voir simultané. Retour : page 2, taille 1, filtres
   appliqués et chaînes temporelles restaurés, niveau critical. Focus main-content.
7. Rechargement du navigateur : même contexte validé et mêmes chaînes restaurés.
8. Contexte contradictoire Company 2 / Site 1 / Equipment 1 : erreur
   « Ce site ne correspond pas à l’entreprise sélectionnée. », aucune ligne
   de résultat et aucun lien fiche Equipment.

Aucun warn/error console relevé sur ces parcours. Les huit contrôles visuels
utilisateur approuvés en UI 9.5 sont réutilisés ; pas de répétition complète de
la recette ergonomique ou du responsive. Capture réelle de l'état vide obtenue :
`frontend/tmp/ui-9.6/dev-empty.png`. Elle montre le contexte P101, l'aide des
bornes inclusives, la pagination et le message vide, sans donnée de prédiction
fabriquée. Onglet fermé, viewport et visibilité réinitialisés, services laissés
actifs. Les observations sont enregistrées séparément des réponses HTTP.

## Distinction des preuves et limites

| Catégorie | Preuve disponible |
| --- | --- |
| XHR Angular réellement capturés | **Indisponibles** : l'outil navigateur expose DOM, captures et console, mais aucun journal réseau/XHR. Ses capacités listées sont pageAssets et webmcp, sans enregistreur HTTP. Aucun proxy de capture ou instrumentation applicative ajouté |
| GET HTTP indépendants | 33 requêtes réelles, URL/paramètres/status/body enregistrés dans http-sql.json ; ne proviennent pas d'une capture du navigateur |
| PostgreSQL | 3 transactions explicites READ ONLY/REPEATABLE READ : avant, comparaisons HTTP/SQL, après ; données et schéma lus réellement |
| Angular réel | Sélections, états vides, filtres, URLs, liens, exclusivité, retour et rechargement constatés dans le DOM ; une capture réelle |
| Tests Angular isolés | Références historiques UI 9.5 : 642 ciblés, 2 376 complets sur 84 fichiers, 163 ciblés après finition ; **aucune exécution UI 9.6** |
| Build | Référence historique UI 9.5 : réussi avant finition, initial 606 501 octets ; **aucun build ni mesure de bundle UI 9.6** |

L'absence de GET historique avant validation complète ou sur contexte
contradictoire reste couverte par l'implémentation et les tests HTTP isolés
historiques. La recette observe les états Angular de blocage, mais **ne certifie
pas cette absence par une trace XHR réelle**, faute de capture réseau. Les
requêtes indépendantes n'ont transmis ni company_id ni site_id au GET Predictions.
Leur conformité ne démontre pas à elle seule l'ensemble du trafic Angular.

Impossible à prouver avec les données DEV présentes : comparaison d'une ligne
API aux 14 valeurs SQL, rendu réel des quatre types, scores/provenance/échelles,
niveaux et alertes nullables, séparation de predicted_at et created_at sur une
ligne, détails JSON/métadonnées réels, cohérence RUL, comportement de troncature,
tri de lignes et pagination à total positif, effet sélectif des filtres et
appartenance de lignes retournées. Ces scénarios restent couverts seulement par
les fixtures isolées déjà validées en UI 9.2 à UI 9.5 ; aucun résultat de fixture
n'est présenté comme un enregistrement PostgreSQL. Aucun 404 d'équipement
inexistant ni incident serveur n'a été provoqué pour cette recette.

## Réserves B-PRE conservées

| Réserve | Situation après recette |
| --- | --- |
| B-PRE-01 | Authentification, autorisation de ressource et isolation multi-tenant absentes ; bloque la production SaaS. Identité DEV et cascade UI ne constituent pas une sécurité multi-tenant |
| B-PRE-02 | Scores et niveaux backend génériques inchangés ; aucune interprétation d'une valeur réelle possible ici, règles prudentes UI 9.4 conservées |
| B-PRE-03 | Validation temporelle backend non durcie ; égalité/offsets acceptés, mais inclusion de lignes aux bornes non prouvée sur table vide |
| B-PRE-04 | Intégrité Equipment/Sensor/Measurement backend partielle ; références réelles Equipment/Site/Company vérifiées, aucun lien descendant ajouté |
| B-PRE-05 | JSON backend générique sans limite de taille ; limites UI 10 000 caractères/six niveaux uniquement visuelles, aucun JSON réel à auditer ici |
| B-PRE-06 | Cascades de suppression backend inchangées ; aucun DELETE ni test destructif |
| B-PRE-07 | OFFSET/COUNT distincts, concurrence et index inchangés ; pas de mesure de volume ni garantie de snapshot API, comparaisons SQL isolées seulement |
| B-PRE-08 | Risques des POST RUL et artefacts inchangés ; aucun calcul, POST ou chargement ML déclenché |
| B-PRE-09 | Historique réellement vide constaté ; aucune génération automatique ou déduction de modèle absent, mécanisme d'alimentation non testé |
| B-PRE-10 | Données/provenance historiques potentiellement invalides ou incomplètes ; 14 colonnes constatées, aucune ligne pour auditer les valeurs |
| B-PRE-11 | Aucun GET détail/latest ou écran détail autonome ajouté ; détails locaux de liste non exercés sur données DEV |

## Preuves locales et état Git

Preuves locales **ignorées par Git**, sous `frontend/tmp/ui-9.6/` :

- `before.json`, `after.json` : identités sans secrets, compteurs, SHA-256 par
  table et par ligne, schéma Predictions, rattachements et écart Sensor 1.
- `integrity-comparison.json` : comparaison complète, all_equal true et listes
  ajout/suppression/modification vides pour chacune des huit tables.
- `http-sql.json` : les 33 cas indépendants, réponses et résultats SQL comparés.
- `angular-observations.json` : observations DOM/URLs, réserve XHR explicite.
- `dev-empty.png` : état vide DEV réel. `audit.py` et `http_sql.py` : collecteurs
  temporaires GET/SELECT uniquement, sans démarrage de service ni import de
  session applicative ; aucun de ces fichiers n'est une source applicative livrée.

Seul nouveau fichier proposé : `docs/ui-9.6-predictions-integration.md`.
Branche et HEAD inchangés, index vide. `git diff --check`, contrôle des espaces
du rapport et absence de secrets/artefacts de livraison vérifiés. Aucun fichier
frontend/backend suivi modifié, aucun nouveau package, migration ou seed.
Aucune donnée modifiée, restaurée ou nettoyée ; intégrité avant/après démontrée
par les compteurs et empreintes. Aucun commit, push, merge ou rebase.

Validation utilisateur attendue sur cette recette partielle et ses réserves.
UI 9.7 non commencée.
