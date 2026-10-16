# UI 3.1 - Analyse fonctionnelle et technique Companies

## État actuel - suivi documentaire UI 3.8

Mise à jour du 16 octobre 2026 : UI 3.1 à UI 3.7.1 sont terminées et validées,
Companies MVP est implémenté sur `feature/frontend-companies`. UI 3.8 est en
finalisation documentaire avant validation de livraison dans `main`, au HEAD
initial `ac2dc3a` (rapport UI 3.7.1 commité, dépôt propre avant édition).

Les sections 1 à 9 et le contexte d'analyse ci-dessous conservent la conception
historique UI 3.1, validée dans `d6d31ec`. Leurs mentions « proposé »,
« non créé », « à valider » et « UI 3.2 non commencée » décrivent l'état du
15 octobre 2026, pas l'état courant. La section 10 distingue ce qui est réellement
livré des intentions initiales ; le [statut actuel](project-status.md) et
l'[architecture réalisée](frontend-architecture.md#companies-mvp---architecture-implémentée-ui-3)
font référence pour la livraison.

## Statut, périmètre et méthode de l'analyse historique UI 3.1

Analyse du 15 octobre 2026, sur `feature/frontend-companies`, HEAD initial
`b7aac19` (`docs: synchronize Dashboard V1 delivery status and UI 3 roadmap`).
Le répertoire de travail est propre avant intervention. UI 2 est livrée ;
`/companies` affiche encore le placeholder partagé.

Lors de l'analyse UI 3.1, ce document est une proposition soumise à validation. Aucun composant, service,
formulaire ou parcours Companies décrit comme cible ci-dessous n'est implémenté
par UI 3.1. UI 3.2 n'est pas commencée.

Méthode : lecture du code et des tests versionnés, sans exécuter de requête
d'écriture, de migration ou de test susceptible d'utiliser PostgreSQL. Aucun
appel réel CRUD, contrôle navigateur Companies ou test de suppression n'est
revendiqué. Les comportements déduits des contraintes SQL sont distingués des
réponses explicitement gérées par les routes.

Références projet lues : [README_AI.md](../README_AI.md),
[project-status.md](project-status.md), [roadmap.md](roadmap.md),
[architecture.md](architecture.md), [frontend-architecture.md](frontend-architecture.md),
[ui-design.md](ui-design.md) et [decisions.md](decisions.md).
D004, D005, D008 à D013 et les contraintes de D014 restent applicables ;
aucune nouvelle décision architecturale n'est enregistrée à ce stade.

## 1. Sources vérifiées

| Couche | Fichiers examinés |
| --- | --- |
| Enregistrement API | `backend/app/main.py`, `backend/app/api/routes/companies.py` |
| Contrats | `backend/app/schemas/company.py`, `backend/app/schemas/pagination.py` |
| Traitement | `backend/app/services/company_service.py`, `backend/app/repositories/company_repository.py`, `backend/app/core/pagination.py` |
| Persistance | `backend/app/models/company.py`, `site.py`, `equipment.py`, `sensor.py`, `measurement.py`, `maintenance_record.py`, `prediction_record.py`, `maintenance_recommendation.py` |
| Migrations | `backend/migrations/versions/0468ed5be8f1_create_companies_table.py`, `50e5051527dc_create_sites_table.py` et migrations des clés étrangères descendantes |
| Connexion et sécurité | `backend/app/core/database.py`, dépendances des routes et montage FastAPI ; `frontend/src/app/app.config.ts`, routes Angular |
| Tests backend associés | `tests/pagination_filters/test_routes.py`, son README et la fixture `tests/dashboard/support.py` ; tests de périmètre Dashboard consultés comme contrôle de cohérence, pas comme preuve d'autorisation |
| Références Angular | `frontend/src/app/core/api/reference-data-api.service.ts` et tests, `core/models/page.model.ts`, `core/models/reference-data.model.ts`, `core/http/api-config.ts` |
| Conventions UI | `app.routes.ts`, navigation centralisée, Header, Shell/focus, DashboardFacade, DashboardFilters, composants partagés et `src/styles/_tokens.scss` |

Les chemins backend abrégés de la ligne Persistance sont tous sous
`backend/app/models/`. Les chemins Angular abrégés sont sous `frontend/src/app/`.

## 2. Contrat backend actuel

### 2.1 Endpoints

Préfixe réel `/api/v1`, ajouté dans `main.py`. Les routes de collection sont
déclarées sans slash final. Aucun endpoint PUT, archivage, restauration, export,
suppression en lot ou aperçu d'impact n'est défini pour Company.

| Méthode et URL | Entrée | Succès | Erreurs explicitement prévues |
| --- | --- | --- | --- |
| `GET /api/v1/companies` | Query `page`, `page_size`, `search` facultatifs | 200, `Page<CompanyRead>` | 422 pour paramètres invalides |
| `GET /api/v1/companies/{company_id}` | Identifiant entier dans le chemin | 200, `CompanyRead` | 404 `Company not found` ; 422 si non entier |
| `POST /api/v1/companies` | JSON `CompanyCreate` | 201, `CompanyRead` | 409 si code déjà trouvé par le service ; 422 si corps invalide |
| `PATCH /api/v1/companies/{company_id}` | Identifiant entier et JSON `CompanyUpdate` | 200, `CompanyRead` | 404 si absent ; 409 si code déjà affecté à une autre entreprise ; 422 si validation échoue |
| `DELETE /api/v1/companies/{company_id}` | Identifiant entier ; aucun corps requis | 204, sans corps | 404 si absent ; 422 si identifiant non entier |

Le paramètre de chemin n'a pas de contrainte `gt=0` dans ces routes : un entier
négatif ou nul est recherché, puis retourne normalement 404 si absent. Ce n'est
pas le contrat des filtres Dashboard, qui impose des identifiants positifs.
Les GET sont de lecture ; POST/PATCH/DELETE committent en base.

Les erreurs 404/409 gérées ont la forme `{ "detail": "..." }`. Le conflit
est formulé `Company with code 'CODE' already exists.`. La validation FastAPI
422 utilise `detail` comme liste d'erreurs avec localisation, message et type ;
ne pas la typer comme une simple chaîne. Aucun 400 métier n'est défini ici.
Les routes n'émettent pas de 401/403 démontré : cela traduit une lacune de
sécurité, pas une garantie d'accès autorisé.

Les routes ne capturent que `ValueError` pour transformer un conflit en 409 et
effectuer `rollback()`. Une violation SQL, une course à l'unicité entre deux
POST/PATCH, une panne de base ou un échec de cascade peuvent donc provoquer une
erreur non gérée, potentiellement 500. Ne pas garantir un 409 pour tout doublon
concurrent, ni afficher une trace SQL comme message utilisateur.

### 2.2 Champs et nullabilité

| Champ | Création | PATCH | Réponse et contrainte SQL |
| --- | --- | --- | --- |
| `id` | Non prévu | Non prévu | Entier, clé primaire générée ; non modifiable via les schémas |
| `name` | `string`, obligatoire | `string` ou `null`, facultatif | `string`, NOT NULL, `VARCHAR(150)` |
| `code` | `string`, obligatoire | `string` ou `null`, facultatif | `string`, NOT NULL, `VARCHAR(50)`, index unique |
| `description` | `string` ou `null`, défaut `null` | `string` ou `null`, facultatif | `string` ou `null`, TEXT, aucune longueur maximale définie |
| `created_at` | Non prévu | Non prévu | Date JSON sous forme de chaîne, obligatoire |
| `updated_at` | Non prévu | Non prévu | Date JSON sous forme de chaîne, obligatoire |

`CompanyCreate` hérite de `CompanyBase`. Il n'y a ni `min_length`, ni
`max_length`, ni suppression des espaces, ni règle de casse dans ces schémas.
Un nom/code vide ou composé d'espaces n'est donc pas refusé par une validation
métier explicite. Les limites 150/50 viennent de SQL, pas de Pydantic : un texte
trop long peut dépasser la validation HTTP puis échouer à la persistance.
Ne pas prétendre que ces cas retournent proprement 422.

Le service recherche l'unicité par égalité SQL du code brut, sans normalisation
ni comparaison insensible à la casse explicite. Le nom n'est pas unique.
Ne pas imposer majuscules, alphabet ASCII ou unicité insensible à la casse
comme s'il s'agissait de règles backend validées.

PATCH utilise `model_dump(exclude_unset=True)` : champ absent = inchangé ;
`description: null` = effacement volontaire. `name: null` et `code: null` sont
acceptés par le schéma mais incompatibles avec NOT NULL en base. `{}` est accepté
par le schéma et ne signifie pas une remise à zéro. Aucun contrôle de version,
ETag, `If-Match` ou prévention des écrasements concurrents n'est implémenté.

Les horodatages SQL sont `DateTime` sans fuseau, alimentés par `datetime.utcnow`
et `onupdate` pour la modification. Le contrat n'assure donc pas de suffixe `Z`
ou de décalage dans les chaînes JSON Company. Conserver les chaînes de transport ;
ne pas ajouter silencieusement `Z`, ni étiqueter une conversion locale comme UTC
prouvé. Ce point diffère du contrat temporel Dashboard.

Exemples de structure, non issus d'une opération réelle :

```json
{ "name": "Entreprise exemple", "code": "EXEMPLE", "description": null }
```

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "pages": 0
}
```

Une réponse `CompanyRead` contient exactement les champs métier documentés :
`id`, `name`, `code`, `description`, `created_at`, `updated_at`. Elle ne contient
ni liste de sites, ni comptage de sites/actifs, ni état actif/inactif, ni contact,
adresse, logo, devise ou indicateur prédictif.

### 2.3 Pagination et recherche

| Paramètre | Contrat vérifié |
| --- | --- |
| `page` | Entier >= 1, défaut 1 |
| `page_size` | Entier de 1 à 100, défaut 20 |
| `search` | Chaîne facultative, longueur HTTP de 1 à 100 avant trim |

Le service retire les espaces aux extrémités de `search` ; une chaîne composée
d'espaces devient une absence de filtre. Une chaîne vide fournie explicitement
viole `min_length=1` : l'omettre lorsque la recherche est vide.
Le repository filtre par `name ILIKE '%recherche%' OR code ILIKE '%recherche%'`.
La description n'est pas recherchée. `%` et `_` ne sont pas échappés : ils
conservent la sémantique des jokers SQL ; ne pas promettre une recherche littérale
exacte ni une recherche insensible aux accents.

Tri fixe par `id` croissant ; pas de paramètre de tri ni de filtre métier
additionnel disponible. L'offset vaut `(page - 1) * page_size` ; le total est
calculé avec le même filtre et `pages = ceil(total / page_size)`, ou 0 si vide.
Une page au-delà de la dernière retourne 200, `items: []`, total/pages conservés,
pas 404. La lecture des lignes et du total n'assure pas un snapshot commun face
aux modifications concurrentes. Ne jamais filtrer seulement la page chargée en
présentant le résultat comme une recherche globale.

### 2.4 Relations et suppression

Cardinalité réelle : une Company peut avoir **zéro à plusieurs sites**, même si
la description métier générale évoque une entreprise possédant des sites.
`Site.company_id` est obligatoire et référence `companies.id` avec
`ON DELETE CASCADE`. La relation ORM Company.sites utilise
`cascade="all, delete-orphan"`. Aucun refus explicite « entreprise non vide »
n'existe dans le service ou la route DELETE.

Conséquences attendues d'une suppression selon modèles et migrations :

```text
Company
  - Sites
    - Équipements
      - Capteurs - Mesures
      - Maintenances
      - Recommandations persistées
      - Prédictions persistées (également liées aux capteurs/mesures)
```

Les relations ORM assurent plusieurs cascades descendantes ; les clés étrangères
SQL des descendants, y compris PredictionRecord, portent `ON DELETE CASCADE`.
Il s'agit d'une suppression définitive, sans corbeille, restauration, archivage,
prévisualisation atomique, audit métier de suppression ou confirmation serveur.
L'état réel des contraintes d'une instance PostgreSQL n'a pas été inspecté ici ;
la cascade complète n'a pas été exécutée pour la prouver.

`GET /api/v1/sites?company_id=ID&page=1&page_size=20` permet de consulter les sites
et leur total. La route spécialisée `/sites/company/{company_id}` renvoie aussi
une liste non paginée, mais n'est pas recommandée pour cette UI. Même un total
de sites égal à zéro n'est pas une protection contre une création concurrente.
Le comptage client n'est ni une autorisation ni un verrou de suppression.

**Recommandation : exclure DELETE du MVP frontend.** Une confirmation seule
n'apporte pas les garanties manquantes. Prévoir sa conception pour une étape
conditionnelle après validation du périmètre destructif et des protections
backend ; ne pas exposer un bouton désactivé laissant croire à une disponibilité
imminente décidée. Ne pas appeler DELETE pendant UI 3.1.

### 2.5 Couverture existante et lacunes

`tests/pagination_filters/test_routes.py` teste les vraies routes, services et
repositories avec session de test substituée : défauts, structure Page, bornes
422, pages multiples, page hors limites, ordre stable, recherche nom/code,
espaces et absence de résultat. La fixture utilise SQLite en mémoire par défaut ;
une configuration PostgreSQL de test est possible, distincte de la base métier.

La recherche des sources de tests versionnées ne révèle pas de suite dédiée
Company couvrant POST, GET détail, PATCH, conflits concurrents, null explicite,
limites SQL et cascade DELETE complète. Les validations des autres schémas
métier ne prouvent pas celles de Company. Les tests Dashboard de cohérence
company/site/equipment démontrent un filtrage, pas une autorisation utilisateur.
Ces lacunes restent des tests backend à proposer séparément, sans les ajouter
ni lancer de suite utilisant PostgreSQL dans cette étape documentaire.

## 3. Sécurité et périmètre de livraison

Les cinq routes Companies dépendent uniquement de `get_db`. Le montage FastAPI
ne fournit pas de dépendance d'authentification globale démontrée ; aucune
identité utilisateur, appartenance d'entreprise ou politique RBAC n'est vérifiée
dans ce parcours. Les routes Angular n'ont pas de guard d'authentification et
`provideHttpClient()` n'ajoute pas d'intercepteur d'identité. Aucun mécanisme
externe éventuel ne peut être déduit du dépôt.

D005 exprime un objectif d'isolation par `company_id`, pas une garantie déjà
réalisée. La liste est globale, et l'identifiant de détail/modification/suppression
n'est pas restreint aux entreprises d'un utilisateur. Masquer une action dans
Angular ne sécurise pas l'API. Ni lecture ni écriture ne doivent être présentées
comme prêtes pour une production SaaS multi-tenant.

Le MVP proposé vise l'environnement local/interne contrôlé déjà utilisé pour
Dashboard. L'exposition en production nécessite un chantier distinct, validé,
d'authentification, autorisation serveur par ressource et tests d'accès croisés.
Le report de DELETE ne ferme pas les accès directs à l'endpoint existant.

## 4. Conception fonctionnelle proposée

### 4.1 MVP

| Parcours | Contenu et comportement proposés |
| --- | --- |
| Liste `/companies` | PageHeader « Entreprises », action « Créer une entreprise », tableau Nom, Code, Description et actions nommées Consulter/Modifier ; texte « Non renseignée » pour description null/vide. Aucune colonne de statut ou nombre de sites inventée. Pagination serveur de 20 lignes, précédent/suivant, page et total réels. |
| Recherche | Champ « Rechercher par nom ou code », maximum 100 caractères, application explicite par formulaire/Entrée et bouton Rechercher ; effacer omet search et revient page 1. Pas de tri ou filtre non fourni. Texte d'aide sur les jokers `%`/`_` si ces caractères sont utilisés. |
| Détail `/companies/:companyId` | Nom/code/description, identifiant, création et modification en lecture seule ; retour liste et Modifier. Pas de KPI, onglets factices ni chargement de tous les actifs. Les dates sans fuseau restent présentées avec la réserve « Horodatage serveur sans fuseau explicite ». |
| Création `/companies/new` | Formulaire Nom, Code, Description ; Créer et Annuler. Nom/code obligatoires. POST uniquement au submit valide, résultat 201 puis navigation vers le détail de l'id renvoyé. Annonce « Entreprise créée ». Aucun id prédéfini. |
| Modification `/companies/:companyId/edit` | Charger le détail avant le formulaire ; champs modifiables identiques, Enregistrer et Annuler ; PATCH des seuls champs changés. Après succès, navigation détail et annonce « Entreprise modifiée ». Un formulaire inchangé n'envoie pas de PATCH. |

L'id figure dans le détail ; la liste privilégie nom/code sans faire de l'id
une information métier principale. Ne pas présenter une troncature comme un
contenu complet : le détail garde la description entière et respecte ses sauts
de ligne avec CSS, sans interpréter de HTML fourni par l'utilisateur.

Le contexte liste appliqué (`page`, `page_size`, `search`) est conservé en query
params, pour pagination, retour navigateur et retour depuis un détail/formulaire.
Ne réutiliser qu'un contexte interne typé, pas une URL de redirection arbitraire.
Valider les paramètres Router, omettre search vide ; une URL invalide retrouve
des valeurs UI sûres (page 1, taille 20), sans prétendre corriger une donnée API.

### 4.2 Validation formulaire proposée, à valider

- Nom : obligatoire et non blanc ; maximum 150 caractères, en cohérence avec SQL.
- Code : obligatoire et non blanc ; maximum 50 caractères ; conserver la casse
  et les caractères autorisés implicitement par le contrat, sans regex inventée.
- Proposition UX : retirer les espaces de début/fin du nom/code à la soumission,
  appliquer la validation sur la valeur ainsi normalisée ; c'est une politique
  frontend plus stricte, pas une validation backend existante.
- Description facultative, sans maximum métier inventé. Conserver le texte
  saisi ; un champ vidé intentionnellement en création envoie null, et en
  modification envoie `description: null` si la valeur a changé.
- Ne jamais envoyer `name: null` ou `code: null` depuis le formulaire, tout en
  représentant cette possibilité dans le DTO de transport PATCH fidèle à l'API.
- Afficher « Le nom est obligatoire », « 150 caractères maximum »,
  « Le code est obligatoire », « 50 caractères maximum » près du champ concerné.
  Un 409 affiche « Ce code est déjà utilisé par une autre entreprise » sur Code.
- Pas de précontrôle d'unicité via la recherche : elle est partielle, paginée
  et non atomique. L'enregistrement serveur reste l'autorité.

Les limites de longueur Angular doivent être testées avec Unicode : les
comptages JavaScript en unités UTF-16 ne sont pas strictement identiques aux
caractères PostgreSQL. Ne pas transformer cela en règle métier ASCII implicite.

### 4.3 États, erreurs et suites d'opérations

La liste charge sa première page à l'entrée : contrairement au Dashboard, elle
ne nécessite pas une entreprise sélectionnée. Un service injecté seul ne lance
pas de GET. États de lecture : `loading`, `success`, `empty`, `error` ; état
initial local `idle` possible avant le premier déclenchement.

- `LoadingState` et `aria-busy` sur les résultats ; recherche et contexte restent
  visibles, pas de focus déplacé à chaque réponse.
- `EmptyState` avec « Aucune entreprise » si total 0 sans recherche, action Créer ;
  « Aucun résultat » si recherche appliquée, action Effacer la recherche.
- Si items vide mais total > 0 et page hors limites, proposer/recharger la dernière
  page valide une seule fois, sans boucle face aux écritures concurrentes ; ne pas
  annoncer que la base est vide. Détail 404 = entreprise introuvable, pas empty.
- `ErrorState` pour les erreurs de lecture ; Réessayer relance la dernière requête
  appliquée (pas un texte de recherche encore en édition). Réseau/5xx : relance
  manuelle ; 422 query : corriger les paramètres ; 404 détail : retour liste.
- 422 de formulaire : associer les erreurs `body.name/code/description` aux champs
  connus, avec résumé accessible pour les autres ; ne pas afficher du HTML serveur.
- Enregistrement : état distinct `idle/saving/success/error`, valeurs conservées,
  double submit bloqué. Pas de mutation optimiste ni de retry automatique.
- Réseau/500 après POST ou PATCH : le résultat peut être incertain après commit.
  Ne pas réutiliser aveuglément le bouton Réessayer du composant d'erreur pour
  refaire une écriture. Inviter à vérifier la liste ou recharger le détail ;
  après vérification, nouvelle soumission explicite. Aucun idempotency-key fourni.
- 404 pendant PATCH : signaler la disparition, conserver la saisie, proposer
  retour liste ; ne pas recréer silencieusement l'entreprise.
- Après succès, utiliser le DTO renvoyé et recharger les lectures aux entrées
  suivantes ; aucun calcul local du total. Prévenir l'abandon d'une saisie modifiée
  via un mécanisme local simple à valider, sans modifier la politique du Shell.

### 4.4 Fonctionnalités reportées

Suppression, archivage/restauration, export/import, actions de masse, tri serveur,
filtres statut/secteur/pays, champs contact/adresse/logo/devise, compteurs d'actifs,
édition des sites, rôles et permissions, audit d'activité, mise à jour temps réel,
prévention robuste des conflits et sécurité SaaS multi-tenant. Les informations
non disponibles ne seront ni inventées ni déduites de la seule page de résultats.
Le détail peut être enrichi ultérieurement de sites paginés via l'API existante,
après validation ; cela n'est pas requis pour consulter Company dans le MVP.

## 5. Architecture Angular proposée

### 5.1 Structure cible, non créée

Chemins relatifs à `frontend/src/app/`. Chaque composant prévu comporte
`.ts`, `.html`, `.scss`, `.spec.ts`. Aucun module Angular classique nécessaire.

```text
features/companies/
  companies.routes.ts
  models/company-write.model.ts
  models/companies-state.model.ts
  data-access/companies-api.service.ts + .spec.ts
  companies-list.facade.ts + .spec.ts
  pages/companies-list/companies-list.component.*
  pages/company-detail/company-detail.component.*
  pages/company-form/company-form-page.component.*
  components/company-form/company-form.component.*
  companies.routes.spec.ts
```

Ne pas extraire de composant table, paginator partagé, formulaire générique ou
store global avant besoin démontré. La liste et le détail restent des pages ;
un même formulaire de présentation sert création et modification. La page de
formulaire porte les appels et les états, le formulaire émet une valeur validée.

### 5.2 DTO et accès HTTP

Réutiliser sans modification structurelle `CompanyRead` existant dans
`core/models/reference-data.model.ts`, `Page<T>` et `ReferencePageQuery` dans
`core/models/page.model.ts`. `SiteRead` et `EquipmentRead` héritent actuellement
de CompanyRead : ne pas déplacer/renommer ce dernier pendant UI 3 sans nécessité.

Proposition de contrats de transport (spécification, pas du code ajouté) :

```typescript
interface CompanyCreate {
  name: string;
  code: string;
  description?: string | null;
}
interface CompanyUpdate {
  name?: string | null;
  code?: string | null;
  description?: string | null;
}
```

`CompanyRead` garde id numérique, name/code chaînes, description nullable et
dates chaînes. Le modèle de formulaire est distinct du PATCH nullable et
n'autorise pas le null pour nom/code. Le service ne normalise pas silencieusement
le DTO ; la normalisation UX validée appartient au formulaire/page.

`CompaniesApiService` :

- `list(query): Observable<Page<CompanyRead>>` délègue à
  `ReferenceDataApiService.getCompanies(query)` pour ne pas dupliquer le GET liste.
- `getById(id): Observable<CompanyRead>` : GET détail.
- `create(body: CompanyCreate): Observable<CompanyRead>` : POST.
- `update(id, body: CompanyUpdate): Observable<CompanyRead>` : PATCH, omissions
  et null explicites préservés. Pas de `delete()` prévu dans le MVP.
- Base `API_PREFIX` existante, HTTP relatif `/api/v1`, proxy déjà configuré.
  Observables sans souscription interne, sans retry automatique ou appel au
  constructeur, sans nouvelle dépendance ou modification de `app.config.ts`.

Une délégation de lecture ne crée pas de cache global : le service de références
actuel n'en possède pas. Les tests devront vérifier un seul GET et la propagation
des erreurs, sans dupliquer tous les tests déjà présents du service de références.

### 5.3 État et concurrence

`CompaniesListFacade`, fournie localement à la page, reprend la convention
Dashboard : signals en lecture seule, union discriminée d'états, snapshot des
paramètres appliqués, `switchMap` pour recherche/pagination/actualisation et
`takeUntilDestroyed` pour nettoyage. Les paramètres Router appliqués sont la
source de vérité ; ne pas déclencher deux GET via URL et submit en parallèle.
La recherche explicite évite un debounce ou une requête à chaque frappe.

Détail et page de formulaire : état local typé, lecture de `paramMap` avec
annulation des GET obsolètes quand l'id change. Pas de façade générique imposée
aux trois écrans. Les écritures utilisent un verrou de soumission ou `exhaustMap`,
pas un `switchMap` autorisant une seconde écriture après annulation côté client.
Quitter une page ne garantit jamais l'annulation d'une transaction serveur.

Le PATCH différentiel limite les écrasements de champs non modifiés, sans
garantir de résolution des modifications concurrentes. Proposer un rechargement
explicite du détail pour vérifier une valeur ; ne pas utiliser updated_at comme
verrou serveur qui n'existe pas.

### 5.4 Routing et navigation

Proposition : une branche `companies` avec `loadChildren` dynamique vers
`companies.routes.ts`, sous le Shell existant, et des pages `loadComponent` :

| Route UI proposée | Métadonnée `pageTitle` / titre de document |
| --- | --- |
| `/companies` | Entreprises |
| `/companies/new` | Créer une entreprise |
| `/companies/:companyId/edit` | Modifier une entreprise |
| `/companies/:companyId` | Détail entreprise |

Conserver `NAVIGATION_ITEMS` comme source du chemin et libellé de section.
Dans le mapping d'`app.routes.ts`, générer pour Companies un objet avec
`loadChildren` à la place du chargeur placeholder, sans conserver simultanément
`loadComponent` sur ce même objet. Conserver la branche Dashboard et les autres
routes. Dans la branche Companies, placer `new` avant `:companyId` ; garder la
wildcard globale en dernière position, sans wildcard locale capturant trop large.

Le Header lit déjà les métadonnées de la route primaire la plus profonde ;
aucune modification du Header ou de la Sidebar n'est nécessaire. Chaque titre
de document utilise le suffixe `| Industrial Predict AI`. Valider l'id numérique
positif et sûr côté page avant GET, avec erreur dédiée si invalide ; tester le
changement d'id sur la même instance et les URLs Companies inconnues profondes.
`/companies/new` ne doit jamais devenir un GET détail pour l'id « new ».
Une URL structurellement inconnue doit conserver la 404 globale et son marqueur
`isNotFound`, sans sélection Sidebar trompeuse ; un id valide absent reçoit le
traitement 404 métier local. Aucune nouvelle entrée de navigation n'est ajoutée.

### 5.5 Composants réutilisés, accessibilité et responsive

- Standalone, OnPush, TypeScript strict, entrées signal et sorties typées selon
  les conventions existantes ; Reactive Forms déjà installé.
- PageHeader par page pour l'unique h1, description et actions ; titres de
  section h2. LoadingState, EmptyState et ErrorState réutilisés sans en changer
  les contrats ; icône décorative locale `companies` déjà disponible.
- Labels associés aux inputs ; required, aria-invalid, aria-describedby et
  erreurs explicites. Ordre clavier naturel, véritables liens RouterLink pour
  naviguer, boutons type submit/button pour agir. Libellés contextualisés pour
  les actions de chaque ligne, pas seulement une icône.
- Sur submit invalide, marquer les champs et placer explicitement le focus sur
  le premier champ invalide/résumé après action utilisateur ; sur recherche ou
  réception HTTP, conserver le focus. Sur navigation, laisser la politique du
  Shell agir, sans autofocus concurrent. Annonce unique de succès et résultats,
  éviter de cumuler alert et live region pour le même message.
- Tableau avec caption et th scope=col ; pagination dans nav avec nom accessible,
  boutons indisponibles correctement désactivés et compteurs réels. À 320 px,
  cellules et actions se replient, chaînes longues peuvent se couper ; aucun
  débordement horizontal global ni cible interactive minuscule.
- Tokens existants : surface blanche, fond gris clair, texte principal/secondaire,
  bleu d'action, bordure et espacements centralisés. Pas de CSS Nebular complet,
  de nouveau thème ou module UI volumineux ; ne pas inventer de token inexistant.
- Valider 1440/1024/1023/768/390/320 px, hauteur 900 px ; focus clavier, skip link,
  navigation mobile et zoom réel 100/200/400 %. Les validations du Dashboard ne
  prouvent pas celles des nouvelles pages. Lecteur d'écran réel toujours non testé.

Une confirmation de suppression, si autorisée ultérieurement, restera locale à
Companies : dialogue nommé, conséquence irréversible et nom/code explicites,
action Annuler prioritaire, confinement du focus et restauration au déclencheur,
Échap = annuler, submit unique. Le CDK installé peut être réutilisé ; aucun
nouveau composant modal transversal n'est justifié avant cette décision.

## 6. Impact sur le Dashboard et les références

Le Dashboard ne doit subir aucun changement de calcul, de filtre ou de chargement.
La réutilisation de CompanyRead et du GET liste n'impose pas de refonte du service
de références. Après création/modification, les nouvelles lectures de références
retournent les données réelles ; aucune invalidation de cache n'est nécessaire
dans le service actuel, qui n'en a pas.

DashboardFilters conserve néanmoins une liste locale pendant sa durée de vie :
une écriture dans un autre onglet ne la met pas à jour automatiquement. Le retour
au Dashboard remonte normalement ses composants et recharge ses références ;
aucun bus global, polling ou sélection automatique de la société créée n'est
proposé. Toute amélioration de synchronisation multi-onglet est reportée.

Une suppression externe peut rendre obsolètes une sélection et ses descendants ;
le Dashboard gère déjà le 404 de périmètre. Une suppression future modifierait
également tous ses agrégats, d'où son exclusion du MVP. Les tests des références,
filtres, états Dashboard et du routing doivent continuer à réussir.

Dette connue conservée : bundle initial de référence **565,38 ko**, budget warning
**500 ko**, Angular Forms partagé avec Nebular. Le module Companies doit rester
différé ; mesurer initial et chunks métier indépendamment, sans noms hashés
imposés, sans relever les budgets et sans importer les pages dans le Shell.

## 7. Découpage proposé, à valider avant développement

Tous les chemins ci-dessous sont relatifs à `frontend/src/app/`, sauf mention.
Aucune de ces sous-étapes n'est commencée par la présente analyse.

| Étape | Objectif et fichiers envisagés | Dépendances | Critères d'acceptation et tests |
| --- | --- | --- | --- |
| UI 3.2 | DTO d'écriture et `features/companies/data-access/companies-api.service.*`, `models/company-write.model.ts` | Validation UI 3.1 | Réutiliser CompanyRead/Page et GET liste existants ; GET détail, POST, PATCH corrects ; payload partiel/null fidèle ; tests HTTP URL/méthodes/corps/erreurs 404/409/422/500/réseau, aucune requête à l'injection, aucun retry d'écriture ni DELETE MVP. |
| UI 3.3 | Liste, recherche, pagination ; `companies-list.facade.*`, modèles d'états, `pages/companies-list/`, `companies.routes.ts`, adaptation ciblée `app.routes.ts` et tests | UI 3.2 | Première page à l'entrée, URL et contexte appliqués uniques, recherche globale nom/code et omission vide, reset page 1, page hors limites, courses annulées, erreurs/vide/chargement accessibles ; Sidebar/titres/focus/404 et lazy loading préservés ; aucun faux tri. Actions vers pages non encore livrées non exposées. |
| UI 3.4 | Détail ; `pages/company-detail/`, routes et tests | UI 3.3 | DTO complet, description null, textes longs et dates sans fuseau traités honnêtement ; ids invalides bloqués, changement d'id, 404 et retry lecture, retour contexte ; pas de requêtes d'actifs supplémentaires ni indicateur inventé. |
| UI 3.5 | Création ; `components/company-form/`, `pages/company-form/`, routes et tests | UI 3.4 et validation des règles formulaire | Champs/validations accessibles, un POST par submit, 201 puis détail, saisie conservée sur erreurs, 409 et 422 localisés, issue incertaine réseau/500 sans relance aveugle ; Annuler et abandon de saisie cohérents ; la route statique new précède l'id. |
| UI 3.6 | Modification avec le même formulaire et page, tests complémentaires | UI 3.5 | Chargement préalable, PATCH différentiel, null pour effacement description seulement, inchangé sans requête, double submit bloqué, erreurs/404 et absence de verrou serveur explicites ; succès puis détail et non-régression création. |
| UI 3.7 | Validation intégrée du MVP, suites existantes et éventuels tests manquants | UI 3.6 | Liste/recherche/pagination, détail et écritures sur environnement de test explicitement autorisé, jamais production par défaut ; distinguer backend réel et mocks ; responsive, clavier/focus, zoom réel et console, absence de fuite inter-pages et de régression Dashboard ; mesurer bundle initial/différé. |
| UI 3.8 | Documentation finale et préparation livraison ; documents de statut/roadmap/architecture/design selon code livré | UI 3.7 validée | Contrat et limites cohérents, métriques mesurées, contrôles et résultats réels/simulés tracés ; validation avant toute opération Git de livraison. Aucun commit automatique. |

Suppression : étape conditionnelle distincte **hors MVP**, à numéroter après
validation d'un chantier de sécurité et de suppression sûre. Elle nécessite
preuves de cascade sur base de test, politique de droits, gestion d'impact et
concurrence, confirmation accessible, 204/404/erreurs et résultat incertain testés.
Elle ne doit pas être activée implicitement à la fin d'UI 3.6.

Pour chaque sous-étape de code : build production, tests Angular existants et
nouveaux pertinents avec `npm test -- --watch=false`, contrôles/tests Sass du
projet, `npm ls --all`, `npm audit`, `git diff --check`. Aucun backend ou budget
modifié pour faire réussir ces contrôles. Aucun test de mutation sur PostgreSQL
de développement sans autorisation explicite et données de test convenues.

## 8. Décisions et questions à valider

1. Valider le MVP liste/recherche/détail/création/modification pour usage local
   contrôlé, avec DELETE absent de l'UI et sécurité SaaS reportée comme blocage
   de production. Le CRUD backend non protégé reste accessible directement.
2. Valider les contraintes UX nom/code non blancs, limites 150/50 et trim de
   soumission, sans prétendre qu'elles sont déjà garanties par le backend.
3. Valider la recherche explicite nom/code, page de 20, contexte URL et absence
   de tri, filtres supplémentaires ou recherche de description.
4. Valider les trois pages (liste, détail, formulaire mutualisé), routes proposées,
   DTO/read réutilisés et façade locale limitée à la liste, sans store global.
5. Valider l'affichage prudent des horodatages sans fuseau et le report d'un
   contrat Company UTC explicite ; ne pas changer le backend dans UI 3.
6. Choisir avant UI 3.5 le mécanisme minimal de confirmation d'abandon de saisie
   et l'environnement autorisé pour tester les écritures ; proposer une protection
   de navigation locale, sans infrastructure générique de dialogue.
7. Planifier séparément le durcissement backend : validations Pydantic/SQL
   cohérentes, null NOT NULL, conflits concurrents, autorisation multi-entreprises
   et suppression. Ce sont des lacunes constatées, pas des modifications autorisées.

## 9. Bilan UI 3.1

Capacités confirmées par les sources : CRUD Company, recherche serveur nom/code,
pagination complète et lien avec les sites. Limites majeures : suppression
destructive en cascade, autorisation non implémentée sur le parcours, validation
incomplète et horodatages sans fuseau explicite. Le MVP proposé n'invente ni
champ, ni KPI, ni fonction ML et conserve le Dashboard livré.

Les 220 tests Angular et le build réussis sont les références historiques de la
livraison Dashboard ; ils ne sont pas relancés en UI 3.1 documentaire. Contrôles
de cette étape : cohérence avec les sources, périmètre documentaire, tirets
simples, `git diff --check` et état Git. Aucun code, dépendance, donnée PostgreSQL,
budget, Shell ou Dashboard modifié pendant UI 3.1. La validation avant UI 3.2
était l'action attendue à cette date ; elle a depuis permis l'implémentation.

## 10. Réalisation Companies MVP et écarts au plan initial

Liste/recherche serveur/pagination, détail, création et modification sont
implémentés (`07d2bc3`, `84f7f18`, `a1e332e`, `d8e6c48`, `ab99551`). Les DTO,
service API, façade locale et formulaire partagé existent ; routes différées
sous le Shell, contexte page/page_size/search conservé, aucune nouvelle entrée
Sidebar. Le Dashboard garde son contrat et aucun backend n'est modifié.

| Intention UI 3.1 | Réalisation observée et limite |
| --- | --- |
| Actions Consulter/Modifier dans la liste | Le nom est un lien de consultation ; Modifier se trouve dans le détail chargé. Aucun bouton d'édition directe par ligne. |
| Route création « Créer une entreprise » | Route `/companies/new`, titre réel « Nouvelle entreprise » ; édition : « Modifier l’entreprise ». |
| Page hors limites : récupération éventuelle | Action manuelle vers une page disponible, sans relance automatique ni boucle de rattrapage. |
| Description facultative | Création : intacte omise, vide volontaire null, autre texte conservé ; édition : PATCH des seuls changements, vide volontaire null. |
| Longueurs Unicode à vérifier | Validateur sur nom/code trimés, 150/50 points de code Unicode ; pas de restriction ASCII. |
| Protection d'abandon à choisir | CanDeactivate local, confirmation native de saisie modifiée, beforeunload ; navigation bloquée pendant saving. Couvert par tests, dialogue natif non validé manuellement. |
| Annonce de succès | Toast NbToastrService global après succès et texte persistant sur le détail ; NbToastrModule.forRoot configuré dans app.config.ts et mixin toast ajouté au thème. La proposition initiale sans changement d'app.config.ts a donc évolué. |
| Validation intégrée et zoom | UI 3.7 : lectures FastAPI réelles, POST/PATCH simulés, 24 contrôles responsive au zoom nominal 100 % ; zoom réel Companies 200/400 % et lecteur d'écran réel non validés. |

Les lectures réelles concernent PETROSEN, la recherche et le détail ; la
pagination multipage et les écritures sont simulées. Aucun POST/PATCH réel
PostgreSQL réalisé dans la validation. DELETE reste exclu à cause de la cascade,
les autorisations multi-entreprises ne sont pas démontrées et les horodatages
Company ne sont pas déclarés UTC sans fuseau explicite. Le module n'est pas prêt
pour une production SaaS multi-tenant.

Le [rapport UI 3.7.1](ui-3.7.1-test-stability.md), commité dans `ac2dc3a`,
consigne trois suites complètes séquentielles à 348/348, build production et
contrôles Sass réussis. Le défaut initial 404 n'est pas reproduit ; les timeouts
sous concurrence conduisent à recommander des validations séquentielles, sans
correctif spéculatif des tests. Ces résultats restent historiques en UI 3.8.

Bundle actuel mesuré : 600,89 ko pour un budget d'avertissement de 500 ko,
dont +32,48 ko après intégration de NbToastrService, inclus dans le total.
Le lazy loading reste effectif ; aucun budget relevé. Les observations, tests
simulés et limites sont détaillés dans le
[bilan Companies](project-status.md#companies-mvp---validation-historique-ui-37).
UI 3.8 finalise uniquement les documents avant validation de livraison ; aucun
commit, push, merge ou début d'UI 4 effectué dans cette étape.
