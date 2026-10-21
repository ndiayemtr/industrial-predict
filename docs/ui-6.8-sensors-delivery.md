# UI 6.8 - Documentation et préparation de livraison Sensors

21 octobre 2026. Branche `feature/frontend-sensors`, HEAD de référence `a317e22`.
Branche, HEAD et dépôt propre vérifiés avant intervention. Cette étape est
strictement documentaire : aucun fichier exécutable, backend, SQL, migration,
Docker, package, lockfile ou budget modifié. Aucune requête API, opération
PostgreSQL ou Docker. Aucun commit, push, rebase ou merge ; UI 7 non commencée.

## 1. Périmètre fonctionnel livré

La [conception UI 6.1](etape-ui-6.1-sensors.md), SEN-01 à SEN-10 approuvées,
reste la référence métier. Ses constats de blocage sont historiques : B-SEN-01
est corrigé dans `4defbe9`, sans déclarer les autres dettes backend résolues.
Les rapports UI 6.1 à UI 6.7 sont conservés sans modification ni duplication
de leurs traces HTTP et SQL.

- Liste lazy `/sensors` : sélection explicite Entreprise -> Site -> Équipement,
  catalogues paginés avec chargement supplémentaire, aucun choix automatique.
  Validation des références réelles avant tout GET Sensors, sans liste globale
  de secours. Recherche explicite nom/code/type/unité, filtre active/inactive,
  pagination serveur et gestion des pages hors plage et réponses obsolètes.
- Contexte URL typé et conservé entre liste, détail et formulaires. Company_id
  et site_id restent des données UI ; seul equipment_id avec search/status/
  page/page_size est transmis au GET paginé Sensors.
- Fiche `/sensors/:sensorId` avec les dix champs réels, dates administratives
  et chaîne Sensor -> Equipment -> Site -> Company vérifiée. Une erreur parent
  est distincte d'une erreur Sensor et conserve les données du capteur.
- Création `/sensors/new` : formulaire typé partagé, parent explicite vérifié,
  nom/code/type/unité obligatoires, type/unité libres et statut initial active.
  Code unique globalement, sans précontrôle par téléchargement de tous les capteurs.
- Édition `/sensors/:sensorId/edit` : nom, code, statut et description modifiables ;
  entreprise, site, équipement, type et unité en lecture seule. Informations de
  suivi avant les actions, dates exclues des écritures.
- PATCH différentiel limité à name/code/status/description réellement modifiés,
  sans valeur restaurée ni appel sans différence. Equipment_id, sensor_type,
  unit, company_id, site_id, id et dates exclus. Description inchangée omise,
  effacement vide et retrait null explicite distincts, sans conversion implicite.
- Protections des saisies, doubles soumissions, erreurs 404/409/422 et réseau,
  résultat d'écriture incertain sans retry automatique. Après succès, fiche de
  l'id réel et confirmation unique ; récupération de navigation sans réécriture.
- Navigation **Equipment <-> Sensors** : le détail Equipment propose Voir les
  capteurs uniquement après résolution de ses parents réels. Destination
  `/sensors?company_id=...&site_id=...&equipment_id=...&page=1&page_size=20`,
  sans filtres Equipment transférés. Le lien Sensor -> Equipment utilise le
  véritable équipement, sans convertir les filtres Sensors en filtres Equipment.
- Aucun DELETE ou transfert frontend, aucune mesure, compteur temps réel,
  prédiction, Health Score ou RUL fictif. Les endpoints backend plus permissifs
  ne sont pas supprimés ou sécurisés par ces seules restrictions Angular.

Measurements reste un futur module Angular à concevoir selon le backend réel.
Les routes Mesures, Maintenance, Prédictions et Recommandations restent des
placeholders. Le Dashboard présente déjà des agrégats et le backend possède
des fonctions ML ; cela ne livre pas ces futurs écrans ni une acquisition temps réel.

## 2. Validation et preuves conservées

Ces résultats proviennent des validations antérieures. **Aucun test Angular,
backend ou build relancé en UI 6.8**, car aucun fichier exécutable n'est modifié.

| Preuve | Référence et portée |
| --- | --- |
| Tests Angular | **1 179 réussis dans 58 fichiers**, UI 6.7.2 ; 393 ciblés dans 11 fichiers, incluant les 26 nouveaux scénarios de navigation |
| Build production | **Réussi**, sources finales UI 6.7.2 |
| Bundle initial | **605 239 octets, soit 605,24 kB** ; +114 octets par rapport à UI 6.6 |
| Création réelle | POST `/api/v1/sensors` **201** depuis Angular 4201, Sensor **7**, code `UI67-SEN-20261020-01`, Equipment **1** |
| Modification réelle | PATCH `/api/v1/sensors/7` **200**, payload exactement name/status/description ; code, type, unité et equipment_id inchangés |
| Persistance PostgreSQL | Rechargement de fiche, GET et lecture SQL concordants sur industrial_predict_dev, port 5434 via FastAPI 8001 |
| Conservation | **39 lignes préexistantes préservées**, seul Sensor 7 ajouté puis modifié ; **40 lignes métier finales** |
| Intégrité | Huit tables vérifiées, neuf FK sans orphelin, codes Company/Site/Equipment/Sensor sans doublon |
| Correction SEN-08 | Clic réel Equipment -> Sensors, parents 1/1/1, page 1, taille 20 et trois capteurs 1/2/7 ; 40 lignes inchangées pendant UI 6.7.2 |
| Backend B-SEN-01 | Tests de routes/repository isolés SQLite, création/unicité globale/PATCH code identique ou différent ; référence acceptée de 132 tests réussis et un test PostgreSQL ignoré, sans nouvelle exécution ici |

La [recette réelle UI 6.7, section 9](ui-6.7-sensors-integration.md#9-reprise-ui-67-autorisée--parcours-réel-angular---api---postgresql)
conserve les payloads et réponses complets POST/PATCH, compteurs, dates et
comparaisons SQL. Sa section 10 complète SEN-08, la validation 1 179/build et
les preuves de navigation. Les mentions antérieures de lien absent ou d'API
bloquée décrivent les étapes précédentes, pas l'état final validé.

### État métier final de référence

| Table | Lignes finales |
| --- | ---: |
| companies | 2 |
| sites | 4 |
| equipments | 6 |
| sensors | 7 |
| measurements | 18 |
| maintenance_records | 3 |
| prediction_records | 0 |
| maintenance_recommendations | 0 |
| Total | 40 |

Les empreintes par id des 39 lignes initiales sont conservées pendant UI 6.7.
Les empreintes globales des huit tables et de chacune des 40 lignes sont
identiques avant/après UI 6.7.2. Aucun nouvel accès SQL en UI 6.8 : ces nombres
sont des références datées, pas une nouvelle attestation de l'état en direct.

### Simulation et contrôles navigateur

409/422 d'écriture, réseau, double clic, abandons et navigation échouée sont
couverts par HttpTestingController et fixtures isolées. Ils ne sont pas
présentés comme des écritures réelles supplémentaires ou une preuve de concurrence.
Les résultats 929, 977, 1 032, 1 092 et 1 153 des étapes précédentes restent
historiques ; la référence finale est 1 179, sans réexécution documentaire.

Responsive de référence : 1440, 1024, 1023, 768 et 320 px mesurés ; cible 390
contrôlée à 389 et 391 px du fait de l'arrondi du navigateur. Aucun débordement
global constaté, action Equipment de 44 px et focus clavier visible. Les captures
UI 6.7.2 bornées au viewport ne constituent pas toutes des captures de page entière.
Les captures, journaux et mesures cités par les rapports restent des pièces
locales ignorées par Git ; leurs liens dépendent du poste et ne sont pas des
artefacts livrés. Les rapports versionnés conservent la synthèse et les preuves
textuelles nécessaires à la revue.

## 3. Limites et dettes techniques

- **B-SEN-02 non corrigé** : divergences Pydantic/SQL sur blancs, longueurs et
  null, notamment PATCH. Les validations UI ne garantissent pas le contrat API.
- **B-SEN-03 non corrigé** : IntegrityError, courses d'unicité/FK et transactions
  repository/service. Les succès séquentiels ne prouvent pas la concurrence ni
  l'atomicité ; pas de contrôle optimiste, version ou idempotence serveur garanti.
- **Seed check strict non conforme** : Sensor 1 conserve description
  `Capteur fictif` et updated_at `2026-10-20 22:11:55.315993`. Le seed attend
  `Capteur fictif.` et `2026-10-16 12:00:00`. Écart accepté pour cette recette
  seulement, origine non attribuée avec certitude, SeedConflict maintenu.
  Aucun changement du seed, de sa logique ou des valeurs actuelles.
- **Dialogue natif d'abandon/beforeunload non vérifié manuellement** ; les tests
  simulés des gardes ne lèvent pas cette réserve navigateur.
- **Absence d'authentification et d'isolation multi-tenant**. La sélection des
  parents et les whitelists UI ne sont pas des autorisations backend. Aucune
  déclaration de préparation à la production SaaS multi-tenant.
- **Budget Angular dépassé** : warning initial 500 kB, dépassement 105,24 kB.
  Seuil d'erreur initial 1 MB, budgets composants 4/8 kB inchangés ; build réussi
  avec avertissement, aucune hausse artificielle de budget.
- **Tests PostgreSQL spécifiques non intégralement exécutés** : SQLite isolée
  et recette DEV contrôlée ne remplacent pas une suite PostgreSQL de contraintes,
  concurrence et transactions. Aucune nouvelle autorisation d'écriture implicite.
- Réserve responsive exactement 390 px, lecteur d'écran, zoom et charge non
  exhaustivement validés. Les garanties d'accessibilité restent limitées aux
  contrôles documentés.
- Secrets historiques suivis dans backend/alembic.ini et docker-compose.yml,
  déjà signalés en UI 5.8, à externaliser et renouveler séparément. Leurs valeurs
  ne sont pas recopiées ; ces fichiers sont inchangés dans la branche Sensors.

## 4. Audit documentaire et Git

Les six documents de suivi nécessitaient une synchronisation : ils annonçaient
encore Sensors comme placeholder et Équipements en attente de livraison.

| Document | Actualisation UI 6.8 |
| --- | --- |
| [README_AI.md](../README_AI.md) | Contexte courant, Sensors livré sur la branche, lien vers statut et bilan |
| [frontend/README.md](../frontend/README.md) | Parcours Sensors, références finales, limites et checklist |
| [project-status.md](project-status.md) | Branche/HEAD, périmètre, preuves et réserves courantes centralisées |
| [roadmap.md](roadmap.md) | Étapes UI 6, état Équipements intégré, séparation Measurements/IA futurs |
| [architecture.md](architecture.md) | Feature Sensors et frontières API/UI, B-SEN-01 distingué des dettes |
| [frontend-architecture.md](frontend-architecture.md) | Routes réelles, structure, façade, formulaire et interactions partagées |
| Présent rapport | Inventaire de livraison, preuves référencées et checklist de fusion |

Rapports UI 6.1 à UI 6.7 et rapports antérieurs inchangés. Les liens vers des
rapports utilisent des chemins relatifs ; les résultats détaillés restent dans
leurs rapports d'origine et le statut courant centralise les réserves.

### Comparaison locale à main

- HEAD source `a317e22` ; main et référence locale origin/main :
  `a76e49c1aea1999f5bbdefb76df7ee1fcce3b448`. Aucun fetch effectué ; ce constat
  ne garantit pas l'état distant lors d'une future fusion.
- `git rev-list --left-right --count main...HEAD` : **0 / 7**. Merge-base égal
  à main : main est ancêtre de HEAD et une fusion fast-forward est possible
  dans cet état local, après validation/commit documentaire et nouveau contrôle.
- Périmètre commité `main...a317e22` : **49 fichiers**, 6 058 insertions et
  6 suppressions : 40 frontend (dont 31 dans la feature Sensors), sept rapports,
  un repository backend et un fichier de tests backend B-SEN-01.
- La préparation documentaire ajoute six documents modifiés et ce rapport non
  suivi : **56 chemins au total** par rapport à main si elle est validée puis
  commitée sans autre changement. Le diff de travail UI 6.8 reste sept documents.

| Commit à intégrer, du plus ancien au plus récent | Objet |
| --- | --- |
| 4defbe9 | fix(backend): restore Sensor code lookup and cover CRUD |
| 9efa8fa | feat(frontend): add Sensors data models and API integration |
| b5d74e5 | feat(frontend): implement Sensors list and filters |
| e9cdf7f | feat(frontend): implement Sensor detail and navigation |
| 012cfd2 | feat(frontend): implement Sensor creation |
| 576314d | feat(frontend): implement Sensor editing |
| a317e22 | feat(frontend): complete Sensors integration and equipment navigation |

### Fichiers commités à intégrer

Inventaire exact de `git diff --name-only main...a317e22` ; le préfixe
`frontend/src/app/features/sensors/` est commun aux 31 chemins Sensors ci-dessous.

#### Feature Sensors (31 fichiers)

- `components/sensor-form/sensor-form.component.html`
- `components/sensor-form/sensor-form.component.scss`
- `components/sensor-form/sensor-form.component.spec.ts`
- `components/sensor-form/sensor-form.component.ts`
- `data-access/sensors-api.service.spec.ts`
- `data-access/sensors-api.service.ts`
- `models/sensor-page-query.model.ts`
- `models/sensor-write.model.ts`
- `models/sensor.model.ts`
- `models/sensors-state.model.ts`
- `pages/sensor-create/sensor-create-references.facade.ts`
- `pages/sensor-create/sensor-create.component.html`
- `pages/sensor-create/sensor-create.component.scss`
- `pages/sensor-create/sensor-create.component.spec.ts`
- `pages/sensor-create/sensor-create.component.ts`
- `pages/sensor-detail/sensor-detail.component.html`
- `pages/sensor-detail/sensor-detail.component.scss`
- `pages/sensor-detail/sensor-detail.component.spec.ts`
- `pages/sensor-detail/sensor-detail.component.ts`
- `pages/sensor-edit/sensor-edit.component.html`
- `pages/sensor-edit/sensor-edit.component.scss`
- `pages/sensor-edit/sensor-edit.component.spec.ts`
- `pages/sensor-edit/sensor-edit.component.ts`
- `pages/sensors-list/sensors-list.component.html`
- `pages/sensors-list/sensors-list.component.scss`
- `pages/sensors-list/sensors-list.component.spec.ts`
- `pages/sensors-list/sensors-list.component.ts`
- `sensors-list.facade.spec.ts`
- `sensors-list.facade.ts`
- `sensors.routes.spec.ts`
- `sensors.routes.ts`

#### Autres chemins (18 fichiers)

- `backend/app/repositories/sensor_repository.py`
- `docs/etape-ui-6.1-sensors.md`
- `docs/ui-6.2-sensors-data-access.md`
- `docs/ui-6.3-sensors-list.md`
- `docs/ui-6.4-sensor-detail.md`
- `docs/ui-6.5-sensor-create.md`
- `docs/ui-6.6-sensor-edit.md`
- `docs/ui-6.7-sensors-integration.md`
- `frontend/src/app/app.routes.spec.ts`
- `frontend/src/app/app.routes.ts`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.html`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.scss`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.spec.ts`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-sensors-navigation.spec.ts`
- `frontend/src/app/layout/sidebar/sidebar.component.spec.ts`
- `frontend/src/styles/_buttons.scss`
- `tests/test_sensor_crud.py`

### Revue des styles et composants partagés

Le diff transversal a été examiné :

- _buttons.scss ajoute new-sensor et sensor-edit aux actions primaires, et
  equipment-sensors aux actions secondaires et de mouvement réduit. Les règles
  hover/active/focus/transitions restent celles existantes ; pas de budget relevé.
- Les pages réutilisent _actions.scss ; ce mixin, les tokens et les quatre
  composants shared ne changent pas. Aucun fichier sous shared/ n'est modifié.
  SensorForm est partagé dans la feature Sensors seulement.
- App.routes délègue Sensors en lazy, tests routing/Sidebar adaptés au remplacement
  du placeholder ; les autres destinations restent inchangées. Equipment Detail
  ajoute uniquement son action conditionnée aux références réelles et ses tests.
- B-SEN-01 ajoute seulement get_by_code, égalité exacte sur Sensor.code sans
  filtre equipment_id. Aucun schéma, migration, dépendance ou configuration modifié.

Les chemins et ajouts de la branche ont été contrôlés pour secrets et artefacts :
aucun nouveau secret détecté par les motifs ciblés et la revue, aucun dump SQL,
capture, trace HTTP temporaire, build ou runner ajouté. Les secrets historiques
restent une dette distincte ; ce contrôle ne certifie pas tout l'historique Git.
Les 123 liens locaux des sept documents UI 6.8 sont contrôlés, ancres comprises,
sans cible absente. `git diff --check` et `git diff --check main` réussissent ;
index vide. Aucun tiret cadratin ajouté.

## 5. Checklist de fusion

- [x] Vérifier branche, HEAD et dépôt propre au départ ; conserver l'historique.
- [x] Synchroniser les six documents nécessaires, distinguer Sensors des futurs modules.
- [x] Conserver 1 179 tests, build et bundle sans relance ; distinguer HTTP réel,
  SQL et simulations, maintenir toutes les réserves ouvertes.
- [x] Comparer commits/chemins à main et examiner styles/routing/composants communs.
- [x] Contrôler liens locaux, secrets/artefacts et diff documentaire ; index vide.
- [ ] Obtenir validation de UI 6.8 et du diff des sept documents.
- [ ] Sur autorisation distincte, indexer explicitement les sept documents,
  vérifier diff indexé/stat/check et créer le commit documentaire final.
- [ ] Avant fusion autorisée, dépôt propre, fetch origin et revérification des
  HEAD source/main/origin/main, ascendance et éventuelle divergence. Refaire la
  revue et les validations appropriées si des sources exécutables ont changé.
- [ ] Confirmer l'acceptation des réserves de recette ; seed strict ne devient
  pas conforme par fusion, et sécurité/budget/concurrence restent des dettes.
- [ ] Obtenir autorisation explicite de fusion. Privilégier ff-only si l'ascendance
  reste confirmée ; arrêter en cas de divergence ou conflit non évalué.
- [ ] Après fusion autorisée, vérifier HEAD, log et dépôt propre, préserver la
  branche source. Publication distante uniquement sur autorisation séparée.

## 6. État Git et point d'arrêt

HEAD `a317e22` inchangé sur feature/frontend-sensors. Six documents modifiés
et un rapport ajouté pour UI 6.8, index vide, diff contrôlé. Aucun fichier exécutable
modifié, aucun package ajouté. Aucune opération PostgreSQL/Docker, aucun commit,
push, rebase ou merge. Aucun début UI 7. Validation attendue avant toute suite.
