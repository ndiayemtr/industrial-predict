# UI 8.6 - Recette intégrée Maintenance en lecture seule

Date : 24 octobre 2026. Branche : `feature/frontend-maintenance`. HEAD de départ et final : `b51d20e`. Dépôt propre avant la recette.

## Bilan et périmètre

Recette réelle de consultation favorable sur les données disponibles : Angular 4201 -> FastAPI 8001 -> PostgreSQL DEV sur 5434. Les listes, filtres, bornes temporelles, trois détails de 18 champs et navigations examinés concordent avec les lectures SQL. Les compteurs et empreintes des huit tables, globales et par ligne, sont identiques avant/après : **40 lignes, aucune ajoutée, supprimée ou modifiée**.

Limites explicites : aucune trace XHR brute disponible ; les GET HTTP de contrôle sont des requêtes indépendantes. La présence d’une seule intervention par équipement limite la preuve de tri et de pagination multipage. Les dates Maintenance existantes sont à la seconde et avec offset ; les cas de fractions non nulles stockées et dates administratives naïves Maintenance ne sont pas représentés. Aucun correctif n’est apporté.

Documents relus sur les points nécessaires : [guide DEV](../infra/development/README.md), [conception UI 8.1](etape-ui-8.1-maintenance.md), [liste UI 8.3](ui-8.3-maintenance-list.md), [détail UI 8.4](ui-8.4-maintenance-detail.md) et [navigation UI 8.5](ui-8.5-maintenance-navigation.md). La validation visuelle utilisateur **9/9** de UI 8.5 reste acquise ; aucune nouvelle campagne responsive n’est revendiquée.

## Identité et préconditions

Les identités `http://127.0.0.1:4201/__dev/identity` et `http://127.0.0.1:8001/__dev/identity` ont été vérifiées avant toute consultation métier et revérifiées lors du relevé final :

| Propriété | Valeur vérifiée |
| --- | --- |
| Mode | `local-development` |
| Base | `industrial_predict_dev` |
| Rôle API et connexion SQL | `ui47_app`, non superutilisateur |
| Instance | `fb3284bd-fb7b-4c22-b620-96a1564b1d0c`, conforme à la configuration privée |
| PostgreSQL | Client `127.0.0.1:5434`, version 17.10, cluster `industrial-predict-development` |
| Alembic | `09ac8101e9fe` |
| Angular / API | `127.0.0.1:4201` / `127.0.0.1:8001` |

Le dispositif existant de configuration/inspection a été réutilisé, avec validation de la base, de son OID, du marqueur d’instance, de la version, du rôle et de ses privilèges. Les secrets restent hors Git et ne sont pas affichés. Les services étaient accessibles ; aucun démarrage, arrêt ou redémarrage de service, aucune opération Docker, migration, seed ou reset.

Le serveur PostgreSQL annonce son port **interne 5432** ; le client utilise exclusivement le port DEV publié **5434**. Un premier contrôle temporaire a arrêté la sonde sur cette différence avant les lectures des tables métier, puis a été corrigé pour vérifier le port client et les marqueurs d’identité. Cette correction concerne uniquement le script diagnostic ignoré, pas l’application ou sa configuration. Aucun accès à `industrial_predict` historique ni fallback.

## État SQL avant et après

Toutes les lectures SQL directes ont lieu dans une transaction explicitement **REPEATABLE READ READ ONLY**, avec `transaction_read_only=on`, puis `ROLLBACK`. La connexion impose aussi `default_transaction_read_only=on`. Fuseau de session UTC et DateStyle ISO identiques pour les deux relevés ; cela ne modifie ni les valeurs stockées ni les dates naïves.

- Instantané initial : **2026-10-24T08:33:51.554521+00:00**.
- Instantané final : **2026-10-24T08:45:05.342333+00:00**, après fermeture du parcours Angular.

| Table métier | Avant | Après | Empreintes de toutes les lignes |
| --- | ---: | ---: | --- |
| `companies` | 2 | 2 | Identiques |
| `sites` | 4 | 4 | Identiques |
| `equipments` | 6 | 6 | Identiques |
| `sensors` | 7 | 7 | Identiques |
| `measurements` | 18 | 18 | Identiques |
| `maintenance_records` | 3 | 3 | Identiques |
| `prediction_records` | 0 | 0 | Identiques |
| `maintenance_recommendations` | 0 | 0 | Identiques |
| **Total** | **40** | **40** | **40/40 identiques** |

Le total 40 est mesuré lors de cette recette, pas repris comme hypothèse d’une étape précédente.

### Empreintes reproductibles

Chaque ligne est lue par `SELECT id, to_jsonb(t)::text FROM public.<table> t ORDER BY id`. L’ensemble des colonnes réelles est couvert, y compris nulls, textes, nombres, enums et dates. Les noms de colonnes sont relevés dans leur ordre ordinal, y compris pour les tables vides.

```text
empreinte_ligne = SHA256(UTF8(texte JSONB PostgreSQL de la ligne))
empreinte_table = SHA256(JSON canonique {columns: [...], rows: [[id, empreinte_ligne], ...]})
empreinte_globale = SHA256(JSON canonique [[table, count, empreinte_table], ...])
```

JSON canonique : clés triées, séparateurs compacts, échappement ASCII explicite. Lignes triées par id ; ordre des tables : companies, sites, equipments, sensors, measurements, maintenance_records, prediction_records, maintenance_recommendations. La même représentation est employée avant/après.

| Table | SHA-256 avant | Même SHA-256 après |
| --- | --- | --- |
| `companies` | `ce2d6cc33d689ee73b25f266c0da1fbdee81593ce7aa59ba0f64a799ab3e45a8` | Oui |
| `sites` | `99f7056e03baa51f933168977b5a1537d2a56c7ff82e0c3d1109d7fd108bae07` | Oui |
| `equipments` | `8cab5adf983f2e9d4ac66f904f2e51d7a17ccde0a75148bf3eda6b45c68e27e1` | Oui |
| `sensors` | `9c10dd334869f1cda4915aa40099c907b112e849556bc64af88b3194a442d9ce` | Oui |
| `measurements` | `d3baf62462089d456fde6f3d56036b2708d96ba566c403ea3dd70c8b0e992846` | Oui |
| `maintenance_records` | `328a0cee1d5d76781e1e1773f4ef41cf9c54e7d74618eb5b82bd57c70597efc4` | Oui |
| `prediction_records` | `70122079bccfa0bdc90b769bf92a5ba4abcab0be7e3457e0748a190834d43b56` | Oui |
| `maintenance_recommendations` | `248b3bcd2bd8b5f3563e4816b8d3b50385993d96d0e03c8f6d13a719a5456a5a` | Oui |

Empreinte globale avant **et** après :

```text
6e8c453e35f65f1fba4605874e8105d5b936c677577130f97cc4991fea06e2ab
```

Comparaison des ensembles d’identifiants et de chaque empreinte de ligne : **0 ajout, 0 suppression, 0 modification**, sans aucune variation inattendue.

Preuves locales ignorées : [instantané initial](../frontend/tmp/ui-8.6/before.json), [instantané final](../frontend/tmp/ui-8.6/after.json), [comparaison d’intégrité](../frontend/tmp/ui-8.6/integrity-comparison.json). Elles contiennent les empreintes par ligne et la représentation des colonnes permettant leur reproduction. Aucun dump SQL n’est ajouté au dépôt.

### Capteur ID 1 et seed

Le capteur ID 1 conserve notamment `description = "Capteur fictif"` et `updated_at = "2026-10-20T22:11:55.315993"`, sans offset ajouté. Son empreinte complète, identique avant/après :

```text
91a8dcf3ba8902082532cecb9f932f6df1f58719f2cd7056ecf10db408c2d899
```

L’écart préexistant et la réserve historique du seed check strict sont conservés. Le seed et son contrôle ne sont ni corrigés ni relancés ; aucune conformité nouvelle n’est affirmée.

## Données Maintenance disponibles

Trois interventions, toutes créées à `2026-10-01T08:00:00+00:00` en SQL, une par équipement :

| ID | Equipment -> Site -> Company | Type | Statut | Priorité | Coût / minutes déclarées |
| --- | --- | --- | --- | --- | --- |
| 1 | Pompe P101 : 1 -> 1 -> 1 | preventive | completed | medium | 125 / 45 |
| 2 | Compresseur C101 : 2 -> 1 -> 1 | corrective | in_progress | critical | null / null |
| 3 | Convoyeur C201 : 3 -> 2 -> 1 | corrective | planned | high | null / null |

Les titres `UI47-MAINT-PUMP-01 - Contrôle préventif`, `UI47-MAINT-COMP-01 - Inspection corrective` et `UI47-MAINT-CONV-01 - Révision planifiée` proviennent des données existantes ; aucun code ou dossier n’est créé par l’UI.

## Preuves HTTP et comparaisons SQL

**36 GET HTTP de contrôle ont répondu 200**, via le proxy Angular 4201 avec contrôle de l’en-tête `X-Industrial-Predict-Environment: local-development` :

- 27 GET liste paginée, toujours avec `equipment_id` 1, 2 ou 3.
- 3 GET détails `/api/v1/maintenance/1`, `/2`, `/3`.
- 6 GET références : Equipment 1/2/3, Site 1/2, Company 1.

Les 27 réponses liste concordent avec les valeurs de l’instantané SQL : ids, total, page, taille, nombre de pages et ordre attendu. Les 18 champs de chacun des trois détails concordent également. Les nombres sont comparés sans arrondi ; les dates aware peuvent être équivalentes sous `Z` et `+00:00`, mais les chaînes sources sont conservées. Une date naïve n’est jamais assimilée arbitrairement à UTC.

Preuve : [requêtes, réponses et comparaisons API/SQL](../frontend/tmp/ui-8.6/http-sql-comparison.json).

**Ces 36 GET sont indépendants des XHR du navigateur.** Aucune capture XHR brute n’a été obtenue avec les outils disponibles. Les URL Angular et états DOM réellement observés sont conservés dans [30 étapes navigateur](../frontend/tmp/ui-8.6/browser-steps.json) ; ce sont des URL de pages et des états rendus, pas des traces réseau XHR. Les comparaisons SQL sont une troisième catégorie de preuve. Les tests Angular historiques constituent une quatrième catégorie, simulée et non réexécutée ici.

Aucun GET Maintenance global, endpoint non paginé par équipement ou endpoint temporel spécialisé n’est utilisé dans les contrôles HTTP. La mesure réseau directe de l’absence de GET avant validation des parents ou sur période invalide reste une limite de cette recette ; le blocage visuel réel et les tests simulés historiques sont distingués ci-dessous.

## Liste, filtres et pagination réellement consultés

1. Ouverture `/maintenance` sans contexte : aucune entreprise/site/équipement sélectionné, Site et Equipment désactivés, état Sélection attendue.
2. Sélection explicite Entreprise A id 1, puis Site de production id 1 : l’équipement reste sans sélection et la liste reste en attente. Après sélection de Pompe P101 id 1, une intervention est affichée avec total 1, page 1/1.
3. Type Préventive + statut Terminée + priorité Moyenne, puis recherche `PUMP-01` : dossier 1 conservé. Le texte saisi reste en brouillon avant Entrée ; l’URL ne reçoit `search` qu’après validation explicite.
4. Recherche `UI86-NO-MATCH`, puis priorité Basse dans un périmètre sans dossier correspondant : états Aucun résultat réels, sans création de donnée.
5. Compresseur id 2 : Corrective + En cours + Critique + recherche `UI47-TEMP`, qui vise le code de panne réel ; dossier 2 affiché.
6. Convoyeur id 3, Site logistique id 2 : Corrective + Planifiée + Haute ; dossier 3 affiché, références distinctes correctement restaurées.

| Filtre | Valeurs avec dossier réel vérifié | Valeur absente du jeu |
| --- | --- | --- |
| maintenance_type | preventive, corrective | predictive : GET réel vide, affichage positif uniquement simulé |
| status | completed, in_progress, planned | cancelled : GET réel vide, affichage positif uniquement simulé |
| priority | medium, critical, high | low : état vide réel API et UI, affichage positif uniquement simulé |
| search | titre PUMP-01, code de panne UI47-TEMP ; combinaison avec trois enums | terme sans correspondance : vide réel |

Pagination : taille 20 puis taille 1 via contexte URL valide, total 1 et pages 1 concordants avec SQL. Une ouverture volontaire à page 2/taille 1 reçoit items vides, total 1, pages 1. L’UI affiche Page hors plage et temporairement « Page 2 sur 1 » ; Revenir aux résultats restaure page 1, sans perdre filtres, période ou fragment. Aucun correctif n’est nécessaire pour ce comportement de récupération observé.

Une seule ligne par périmètre ne permet pas de démontrer un tri sur plusieurs lignes ni le départage par id en cas d’égalité de created_at, ou une vraie navigation entre deux pages non vides. La concordance constatée avec l’ordre SQL attendu ne remplace pas ces scénarios simulés. Aucun nouvel enregistrement n’est ajouté pour les fabriquer.

Le rendu initial sans choix automatique et l’attente après choix partiels sont observés. L’absence de requête Maintenance avant le dernier parent est couverte par les tests simulés historiques ; faute de capture XHR, elle n’est pas présentée ici comme une mesure réseau réelle.

## Dates, bornes et précision

Le filtre porte sur **created_at**, début inclus et fin exclue. Cas réels HTTP/API comparés à SQL et corroborés dans Angular :

| Cas | Période | Résultat pour Equipment 1 |
| --- | --- | --- |
| Début inclus | [2026-10-01T08:00:00Z, 2026-10-01T08:00:00.000001Z) | Dossier 1 |
| Fin exclue | [2026-10-01T07:59:59.999999Z, 2026-10-01T08:00:00Z) | Vide |
| Début unilatéral après création | start=2026-10-01T08:00:00.000001Z | Vide, GET de contrôle |
| Fin unilatérale après création | end=2026-10-01T08:00:00.000001Z | Dossier 1, GET de contrôle |
| Offset source | [2026-10-01T10:00:00.000000+02:00, 2026-10-01T10:00:00.000001+02:00) | Dossier 1 ; valeurs sources présentes dans l’URL et la période appliquée |
| Dates métier hors création | [2026-10-15T00:00:00Z, 2026-10-16T00:00:00Z) | Vide, bien que planned_at, started_at et completed_at du dossier 1 soient le 15 octobre |

Dans Angular, la modification du début en `.000001` face à une fin `.000001` reste un brouillon, sans changement de l’URL ni de la liste appliquée. Appliquer produit « Le début doit être strictement antérieur à la fin ». Aucun GET HTTP indépendant invalide n’a été envoyé pour ce contrôle. Le rejet UI est réel ; l’absence réseau de requête est prouvée par les tests simulés, pas par une capture XHR de cette session.

Après correction du brouillon, la fin modifiée `.000002` est appliquée en UTC `2026-10-01T08:00:00.000002Z`. Le début inchangé conserve exactement `2026-10-01T10:00:00.000000+02:00`. Les fractions sont à six chiffres, sans passage par JavaScript Date pour les reconstruire. La source d’une borne inchangée reste conservée ; une nouvelle valeur saisie en UTC est sérialisée comme telle.

Limites : aucun timestamp Maintenance stocké ne porte de fraction non nulle. La recette démontre des bornes à la microseconde autour d’un instant stocké à la seconde et la conservation des paramètres, pas une réponse portant une microseconde historique non nulle. Les created_at/updated_at Maintenance consultés sont aware ; aucun cas administratif naïf Maintenance réel n’est disponible. Les tests simulés existants couvrent ces données et l’interdiction d’ajouter Z ; aucune valeur existante n’est modifiée pour les créer.

## Détail : 18 champs réels comparés

Ouverture par titre pour les trois dossiers, puis ouverture directe `/maintenance/2` sans contexte. Cinq états de fiche ont été relevés : **18 champs à chaque fois**, mêmes clés que l’API et SQL, valeurs rendues concordantes. Comparaison détaillée : [DOM/API/SQL](../frontend/tmp/ui-8.6/dom-api-sql-comparison.json).

Exemple complet du dossier 1 ; les dates SQL aware sont représentées ci-dessous par leur source API équivalente avec Z, conservée dans la fiche :

| Champ | Valeur vérifiée API / SQL / DOM |
| --- | --- |
| id | 1 |
| equipment_id | 1 |
| title | UI47-MAINT-PUMP-01 - Contrôle préventif |
| maintenance_type | preventive, libellé Préventive |
| status | completed, libellé Terminée |
| priority | medium, libellé Moyenne |
| description | Intervention fictive terminée. |
| failure_code | null, Non renseigné |
| root_cause | null, Non renseigné |
| action_taken | Contrôle et lubrification simulés. |
| technician | Équipe fictive A |
| planned_at | 2026-10-15T09:00:00Z |
| started_at | 2026-10-15T09:00:00Z |
| completed_at | 2026-10-15T09:45:00Z |
| cost | 125, aucune devise |
| downtime_minutes | 45 minutes déclarées, aucune durée calculée |
| created_at | 2026-10-01T08:00:00Z |
| updated_at | 2026-10-16T12:00:00Z |

Dossier 2 : cost, downtime_minutes, completed_at et action_taken nuls sont affichés comme non renseignés, sans zéro de remplacement. Dossier 3 : started_at et completed_at sont également nuls. Aucun coût zéro, minute zéro ou texte vide n’est présent dans les trois dossiers : ces cas restent des validations simulées.

Les chaînes ISO sources restent affichées ; la représentation UTC correspond aux offsets réels. Equipment -> Site -> Company est résolu par les clés réelles : 1 -> 1 -> 1, 2 -> 1 -> 1, 3 -> 2 -> 1. La consultation directe du dossier 2 propose `/maintenance` comme retour et exige ensuite une sélection explicite. Aucune action de création, modification, suppression ou transition Maintenance n’est présente ; seuls les liens de retour et d’équipement sont observés, sans formulaire.

## Navigation et contexte

Parcours complet vérifié : Equipment Detail -> Voir les interventions -> Maintenance List -> titre -> Maintenance Detail -> Equipment Detail. Navigation au clavier : Tab depuis Voir les capteurs atteint Voir les interventions ; Entrée ouvre Maintenance. Dans la fiche Maintenance, Tab atteint le lien Equipment, avec focus visible, puis Entrée ouvre la référence réelle.

Equipment 1 est aussi ouvert avec `search=P101`, `status=operational`, `criticality=high`, page 3/taille 50. Voir les interventions utilise uniquement :

```text
/maintenance?company_id=1&site_id=1&equipment_id=1&page=1&page_size=20
```

Retour Equipment, Voir les capteurs et Modifier Equipment gardent leur ordre et leurs destinations. Modifier reste une action Equipment existante, jamais activée pendant la recette. Aucun filtre Equipment n’est repris vers Maintenance et aucune identité n’est reconstruite depuis une URL de retour. Preuve : [actions Equipment](../frontend/tmp/ui-8.6/equipment-navigation.json).

Le retour propre à Maintenance conserve les onze clés : company_id, site_id, equipment_id, maintenance_type, status, priority, search, start_time, end_time, page, page_size, plus le fragment `history`. Le cas réellement parcouru utilise les trois enums, la recherche PUMP-01, le début source avec +02:00, la fin `.000002Z`, page 1/taille 1 ; ces valeurs sont retrouvées au retour. Le lien inverse Equipment reçoit seulement ses parents réels et page 1/taille 20, sans statut/type/recherche/période Maintenance. Aucun returnUrl externe n’est utilisé.

## Réserves, références historiques et Git

B-MAIN-01 à B-MAIN-09 restent ouverts : chronologie et alignement Pydantic/SQL, validations numériques/précision, workflow, erreurs d’intégrité/concurrence, dates administratives, authentification/isolation tenant, volumes et politique monétaire/audit. Cette recette GET ne valide pas les écritures futures et ne corrige aucun de ces écarts. Le seed strict reste une réserve historique conservée.

Limites de preuve restantes : trace XHR brute absente, absence de mesure réseau directe du blocage pré-parent/période invalide ; absence de pagination multipage, tri multiligne, maintenance predictive/cancelled/low positive, coûts/minutes zéro, valeurs non finies ou textes vides, dates Maintenance naïves et fractions stockées non nulles. Les valeurs absentes ne sont pas fabriquées. Aucun écart API/SQL/DOM ou changement d’intégrité n’a été constaté dans le périmètre testé.

Références **historiques UI 8.5**, non relancées le 24 octobre : **741 tests ciblés**, **1 899 tests Angular**, **build production réussi**, initial **606,00 kB** et chunk Equipment Detail **14,79 kB**. Budgets inchangés ; avertissement initial 500 kB dépassé de 106,00 kB, pas de nouvel avertissement SCSS lors de ce build historique. La validation visuelle utilisateur 9/9 est conservée sans être présentée comme un nouvel essai.

Seul fichier à livrer : `docs/ui-8.6-maintenance-integration.md`. Les sondes READ ONLY, réponses et instantanés locaux sont dans `frontend/tmp/ui-8.6`, ignoré par Git ; aucun secret n’y est imprimé. Aucun fichier applicatif, backend, SQL, migration, Docker ou package modifié. Aucun POST, PATCH, DELETE, seed, reset, nettoyage, restauration ou écriture PostgreSQL. Aucun service n’a été redémarré. `git diff --check` et les références documentaires sont contrôlés. Branche `feature/frontend-maintenance`, HEAD `b51d20e` inchangé, index vide ; seul ce rapport est nouveau. Aucun commit, push, merge ou rebase. UI 8.7 non commencée. En attente de validation.
