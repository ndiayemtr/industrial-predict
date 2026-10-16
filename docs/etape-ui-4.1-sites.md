# UI 4.1 - Analyse et conception Sites industriels

Date : 16 octobre 2026. Statut : conception fonctionnelle validée par
l'utilisateur ; autorisation de commit documentaire en attente.
Aucune implémentation UI 4.2 commencée. La validation de la conception ne
constitue ni une livraison des fonctionnalités ni une autorisation d'implémentation.

## 1. Point de départ et méthode

`main` propre au commit `54dd1285a3b854bfbf8590bbedfb96e342d41bb8`, identique à
`origin/main` après `git fetch origin` (0 commit d'écart). Branche
`feature/frontend-sites` créée depuis cette base. `main` n'est pas modifiée.

Analyse statique des sources, migrations et tests présents. Une vérification
locale des seuls schémas Pydantic a été exécutée, sans import du serveur,
connexion à une base ou appel HTTP. Aucun test applicatif complet ni build
relancé : les 386 tests Angular, le build production et l'audit npm sans
vulnérabilité restent les résultats historiques de la livraison précédente.
Voir le [statut du projet](project-status.md) et le
[rapport des filtres de dates](dashboard-date-precision.md).

## 2. Contrat backend constaté

### Sources examinées

- [Modèle Site](../backend/app/models/site.py),
  [migration Sites](../backend/migrations/versions/50e5051527dc_create_sites_table.py),
  [schémas Pydantic](../backend/app/schemas/site.py).
- [Routes Sites](../backend/app/api/routes/sites.py),
  [montage FastAPI](../backend/app/main.py),
  [service](../backend/app/services/site_service.py),
  [repository](../backend/app/repositories/site_repository.py).
- [Schéma Page](../backend/app/schemas/pagination.py) et
  [construction de pagination](../backend/app/core/pagination.py).
- [Tests pagination/filtres](../tests/pagination_filters/test_routes.py) et
  [base de tests isolée](../tests/dashboard/support.py).

### Champs et validation

| Champ | Contrat Pydantic | Persistance / conséquence pour l'UI |
| --- | --- | --- |
| `id` | Entier dans SiteRead, absent des schémas d'écriture | Clé primaire ; affichage en lecture seule |
| `name` | Chaîne obligatoire en création ; optionnelle et nullable en PATCH | VARCHAR(150), NOT NULL ; pas de validation Pydantic de longueur ou de texte non blanc |
| `code` | Chaîne obligatoire en création ; optionnelle et nullable en PATCH | VARCHAR(50), NOT NULL, index unique global |
| `description` | Chaîne ou null, facultative, défaut null | TEXT nullable, aucun maximum métier explicite |
| `company_id` | Entier obligatoire en création ; optionnel et nullable en PATCH | FK NOT NULL vers companies.id ; service vérifie l'existence de l'entreprise |
| `created_at`, `updated_at` | datetime dans SiteRead uniquement | DateTime sans timezone explicite ; valeurs produites par datetime.utcnow, updated_at avec onupdate |

SiteRead retourne les sept champs ci-dessus, sans nom d'entreprise imbriqué,
adresse, localisation, pays, coordonnées, statut ou nombre d'équipements.
Un site appartient à une entreprise et peut avoir zéro à plusieurs équipements :
aucune contrainte n'impose la présence d'un équipement.

La vérification Pydantic locale confirme l'acceptation des chaînes vides,
d'un nom de 151 caractères, d'un code de 51 caractères, de company_id=0 en
création, d'un PATCH vide et de null explicite pour name/code/company_id en
PATCH. Cela ne signifie pas que SQL accepte ces écritures. Le frontend devra
éviter les entrées manifestement incompatibles sans présenter ses validations
comme un durcissement de l'API. Les champs non prévus ne constituent pas des
fonctionnalités d'écriture supportées.

### Endpoints effectivement montés sous /api/v1

| Méthode et chemin | Entrées | Succès et erreurs explicitement gérées |
| --- | --- | --- |
| GET `/sites` | page=1 minimum 1 ; page_size=20 entre 1 et 100 ; company_id facultatif minimum 1 ; search facultatif de 1 à 100 caractères | 200 Page[SiteRead] ; 422 si paramètres invalides |
| GET `/sites/{site_id}` | Entier de chemin, sans contrainte ge=1 explicite | 200 SiteRead ; 404 `Site not found` ; 422 si conversion impossible |
| GET `/sites/company/{company_id}` | Entier de chemin | 200 liste non paginée, ordonnée par id ; pas de contrôle explicite d'existence de l'entreprise |
| POST `/sites` | SiteCreate : name, code, company_id, description facultative | 201 SiteRead ; 409 sur ValueError du service ; 422 de validation Pydantic |
| PATCH `/sites/{site_id}` | SiteUpdate ; seuls les champs fournis sont appliqués avec exclude_unset=True | 200 SiteRead ; 404 si site absent ; 409 sur ValueError ; 422 de validation |
| DELETE `/sites/{site_id}` | Entier de chemin | 204 sans corps ; 404 si absent ; suppression définitive en cascade |

La route `/sites/company/{company_id}` ne remplace pas la liste paginée pour
l'UI. Le segment supplémentaire évite toute collision avec le GET détail.

Pagination : `items`, `total`, `page`, `page_size`, `pages`, où pages vaut
ceil(total/page_size), ou 0 si total=0. Une page trop haute retourne items vide
avec total éventuellement positif, sans 404 et sans recalage automatique.

Recherche : nom OU code via ILIKE `%search%`, combiné avec company_id par ET.
Le service retire les espaces périphériques ; une recherche uniquement blanche
devient l'absence de filtre. `%` et `_` restent des jokers SQL, non échappés.
Aucune promesse d'insensibilité aux accents, de recherche sur la description
ou de recherche littérale. Tri fixe `id ASC`, aucun paramètre de tri disponible.
Items et total utilisent les mêmes filtres, mais deux lectures séparées ne
garantissent pas un instantané immuable en présence d'écritures concurrentes.

Le GET liste n'exige pas company_id et ne vérifie pas l'existence d'une
entreprise filtrée : une entreprise inexistante peut produire une page vide.
L'UI ne devra pas traduire ce vide en preuve d'existence du parent.

### Unicité, intégrité et erreurs

Le code Site est unique dans toute la table, et non par entreprise : deux sites
de deux entreprises différentes ne peuvent partager un même code identique.
Le service recherche le code par égalité, sans trim ni changement de casse.
Aucune unicité fonctionnelle insensible à la casse n'est définie ; ne pas
promettre que deux variantes de casse entrent nécessairement en conflit.

POST vérifie l'entreprise puis l'unicité du code. PATCH vérifie company_id s'il
est fourni, puis le code s'il est fourni, en excluant le site courant du conflit.
Il autorise donc techniquement un changement de rattachement vers toute
entreprise existante. Il n'y a pas de vérification d'autorisation utilisateur.
L'omission conserve une valeur ; description:null l'efface. company_id:null
échoue à la vérification d'existence et donne 409. name/code:null peuvent
atteindre une contrainte SQL NOT NULL.

Les routes POST/PATCH interceptent ValueError, font rollback et renvoient
409 avec detail textuel. Deux causes différentes sont présentes :

```text
Company with id '<id>' does not exist.
Site with code '<code>' already exists.
```

Pas de code d'erreur métier structuré distinguant ces causes. Ne pas reprendre
le mapping Companies « tout 409 cible Code ». Les IntegrityError SQL ne sont
pas interceptées ici, ni par un handler global dans app.main : course entre
vérification et insertion, longueur SQL excessive, FK supprimée entre contrôle
et commit ou null interdit peuvent devenir des erreurs serveur. Le code ne
garantit pas leur traduction en 409/422. Ne pas modifier ce backend en UI 4.

### Suppression et changement de rattachement

La [relation Site/Equipment](../backend/app/models/site.py) utilise
`cascade="all, delete-orphan"` ; la FK Equipment.site_id utilise ON DELETE CASCADE.
Les [équipements](../backend/app/models/equipment.py),
[capteurs](../backend/app/models/sensor.py),
[mesures](../backend/app/models/measurement.py),
[maintenances](../backend/app/models/maintenance_record.py),
[prédictions](../backend/app/models/prediction_record.py) et
[recommandations](../backend/app/models/maintenance_recommendation.py) possèdent
les relations/FK de cascade correspondantes. Supprimer un Site peut donc
supprimer équipements, capteurs, mesures, maintenances, prédictions et
recommandations associés. La FK Site.company_id est aussi en cascade si
l'entreprise est supprimée. Aucun archivage, corbeille ou endpoint d'estimation
de l'impact n'est présent dans ce contrat.

Décision MVP validée : exclure DELETE de l'UI et de SitesApiService, sans bouton
désactivé ni promesse d'ajout. Cela ne protège pas l'endpoint backend existant.
Le transfert d'entreprise est interdit dans le MVP frontend : les équipements
resteraient rattachés au même Site et changeraient indirectement de périmètre
d'entreprise. Un futur transfert exige une décision métier et de sécurité.

### Horodatages et autorisation

Le producteur utilise datetime.utcnow mais les colonnes et le contrat de sortie
n'imposent pas de fuseau explicite. Ne pas ajouter UTC à un ISO sans fuseau et
ne pas le parser dans le fuseau du navigateur. Réutiliser
[formatAdministrativeDateTime](../frontend/src/app/shared/utils/datetime-display.ts) :
`JJ/MM/AAAA à HH:mm`, fractions masquées à l'affichage ; composantes conservées
si absence de fuseau ; conversion UTC et suffixe UTC si Z/offset explicite ;
`Non disponible` pour absence ou valeur invalide. DTO et payload restent intacts.

Trois notions distinctes :

1. Filtre ergonomique : company_id réduit les résultats demandés par l'UI.
2. Cohérence métier : le service vérifie l'existence du parent à l'écriture ;
   la FK protège sa référence. Le Dashboard a ses propres contrôles de cohérence
   de périmètre, qui ne s'appliquent pas automatiquement aux routes Sites.
3. Autorisation : aucune dépendance d'identité, rôle ou tenant sur les routes
   Sites ; app.main ne monte pas de protection globale. GET détail, PATCH et
   DELETE ciblent directement l'id, sans scope d'entreprise de l'utilisateur.

Le filtrage ne constitue donc pas une protection multi-tenant. Aucune garantie
d'accès autorisé par entreprise ni préparation à une production SaaS multi-tenant
n'est revendiquée. Aucun guard Angular proposé ne pourrait corriger cette absence.

### Couverture backend existante et limites de preuve

Les tests pagination_filters traversent routes/services/repositories avec une
base isolée SQLite par défaut, PostgreSQL de test facultatif. Ils couvrent pour
Sites structure/defaults, limites de pagination, pages hors plage, ordre id,
recherche nom/code, filtre company_id et recherche combinée, espaces et vides.
Les recherches dans les tests Python présents n'ont pas trouvé de suite dédiée
SiteCreate/SiteUpdate/SiteService pour POST/PATCH/DELETE, unicité concurrente ou
cascade Sites. Ces comportements sont ici déduits du code et des contraintes,
pas présentés comme testés de bout en bout sur PostgreSQL. Les tests d'isolation
du Dashboard vérifient un filtrage/cohérence, pas une autorisation d'utilisateur.

## 3. Frontend Companies examiné et réutilisation

Références : [routes différées](../frontend/src/app/features/companies/companies.routes.ts),
[service API](../frontend/src/app/features/companies/data-access/companies-api.service.ts),
[DTO d'écriture](../frontend/src/app/features/companies/models/company-write.model.ts),
[façade de liste](../frontend/src/app/features/companies/companies-list.facade.ts),
[liste](../frontend/src/app/features/companies/pages/companies-list/companies-list.component.ts),
[détail](../frontend/src/app/features/companies/pages/company-detail/company-detail.component.ts),
[formulaire de présentation](../frontend/src/app/features/companies/components/company-form/company-form.component.ts)
et [page de formulaire](../frontend/src/app/features/companies/pages/company-form/company-form-page.component.ts).
Leurs tests HTTP, façade, routing, pages et formulaires ont été examinés, avec
les [règles frontend](frontend-architecture.md) et [règles visuelles](ui-design.md).
Les indications pré-livraison UI 3.8 dans ces documents sont historiques ; le
statut de livraison actuel est celui de project-status.md. Les décisions
[D001 à D014 et le suivi Companies](decisions.md) restent inchangés.

| Existant | Réutilisation recommandée |
| --- | --- |
| Shell, navigation centralisée, focus main et lien d'évitement | Garder l'entrée Sites et son match de section ; remplacer seulement sa route placeholder lors de l'implémentation |
| PageHeader, LoadingState, EmptyState, ErrorState, tokens et thème Nebular | Réutilisation directe, sans nouveau système de design |
| core SiteRead, Page, ReferencePageQuery | Réutiliser les types déjà présents ; SiteRead étend actuellement CompanyRead pour les champs communs, pas de DTO de lecture à dupliquer |
| ReferenceDataApiService.getSites(companyId, query) | Réutiliser pour la liste filtrée ; conserve pagination/recherche et évite de modifier le Dashboard |
| ReferenceDataApiService.getCompanies(query) | Réutiliser pour le sélecteur paginé d'entreprises |
| Patterns Companies façade/signals/switchMap | Reprendre la structure dans Sites, sans importer sa façade ou son état métier |
| CompanyFormComponent | Ne pas réutiliser directement : entrées/types/identifiants DOM/erreurs Companies et absence de company_id ; créer SiteFormComponent |
| NbToastrService et overlay applicatif existants | Réutiliser le provider global et la confirmation persistante, sans nouvelle configuration forRoot |
| Formateur administratif | Réutiliser tel quel, aucun nouveau formatage à inventer |

Companies conserve URL appliquée page/page_size/search, validation des ids sûrs,
recherche explicite, distinction total=0/page hors plage, annulation des lectures,
PATCH différentiel, absence de PATCH sans changement, verrou saving,
CanDeactivate/beforeunload et vérification après écriture d'issue incertaine.
Ces principes sont adaptés à Sites. Ne pas extraire maintenant une façade CRUD,
un formulaire universel ou un store global. Les styles locaux peuvent suivre
les mêmes tokens sans importer un SCSS interne Companies dans Sites.

## 4. MVP fonctionnel validé

| Sujet | Décision ou contrainte retenue |
| --- | --- |
| Liste | Sélection explicite d'une entreprise, sans entreprise par défaut ; pas de GET Sites avant sélection valide |
| Vue toutes entreprises | Hors premier MVP, bien que GET /sites sans company_id existe ; réduit complexité et réutilise getSites existant |
| Code Site | Unicité globale, toutes entreprises confondues, conformément au backend |
| Recherche/pagination | Serveur, nom/code, saisie explicite, page 1 et 20 lignes par défaut ; pas de tri UI inventé |
| Création | Entreprise obligatoire, sélection explicite ou préremplissage vérifié depuis Companies ; nom/code/description |
| Modification | Nom/code/description uniquement ; entreprise affichée en lecture seule, aucun company_id dans PATCH |
| Navigation | Liste/détail/formulaire Sites ; lien Voir les sites depuis le détail Companies ; lien vers l'entreprise depuis le détail Sites |
| Suppression/transfert | Exclus pour cascade et changement de périmètre des descendants |
| Conflit 409 d'origine inconnue | Résumé prudent, sans attribution automatique au champ Code ; conserver la saisie et inviter à vérifier entreprise et unicité du code |
| Sécurité | Absence d'autorisation multi-entreprises backend signalée comme limite ; le filtre frontend ne protège pas l'accès aux données |

Exclusions supplémentaires : géolocalisation/carte, statut, compteurs/KPI,
inventaire d'équipements embarqué, import/export, actions groupées, gestion des
droits, modifications backend et création d'entreprise dans le formulaire Site.
Sans entreprise disponible : expliquer « Créez d'abord une entreprise » et
proposer un lien vers la création Companies, sans création imbriquée automatique.

### Champs et validations UX retenus

- Création : company_id entier positif sûr et entreprise chargée/existante ;
  nom et code non blancs après trim, respectivement 150 et 50 points de code
  Unicode ; préserver casse, accents et autres écritures, sans regex ASCII.
- Aide Code : « Code unique parmi tous les sites, quelle que soit l'entreprise. »
  L'UI n'effectue pas de prétendue prévalidation définitive d'unicité.
- Description facultative, aucun maximum inventé ; préserver le contenu.
  En création omettre si intacte, null si effacement volontaire ; en modification
  envoyer uniquement une différence effective, vide volontaire vers null.
- Ne jamais envoyer name/code/company_id null. DTO transport PATCH fidèle au
  schéma nullable, mais payload du formulaire limité aux champs autorisés MVP.
- Ne pas envoyer id, dates, nom d'entreprise, paramètres de retour ou filtres.
  Dates de suivi textuelles en édition seulement, après les champs et avant les
  boutons, hors FormGroup et hors détection des modifications.
- Préserver les anciennes valeurs intactes, y compris espaces et null ; ne pas
  normaliser des champs non modifiés simplement en ouvrant l'édition.

## 5. Parcours et maquettes textuelles

### Liste /sites

```text
Sites industriels                         [Nouveau site]
Entreprise (obligatoire) [Sélectionnez une entreprise v]
[Charger davantage d'entreprises] si une autre page existe
Rechercher par nom ou code [                    ] [Rechercher] [Effacer]
Sites de <nom entreprise> - <total> résultat(s)
Nom (lien détail) | Code | Description
[Précédent]            Page n - 20 sites par page          [Suivant]
```

Sans sélection : état idle « Sélectionnez une entreprise pour consulter ses
sites », distinct d'une liste vide. Le bouton Nouveau site peut ouvrir un
formulaire avec sélecteur vide ; il ne crée pas avec une entreprise implicite.
Après sélection valide : page 1, recherche remise à vide sur changement
d'entreprise, GET avec company_id ; l'URL appliquée porte company_id, page,
page_size et search non vide. La recherche et son effacement conservent
l'entreprise et reviennent à la page 1. Pas de requête à chaque frappe.
Jokers %/_ signalés. Aucun filtre local des seules lignes affichées.

Chargement des entreprises distinct du chargement Sites : erreurs et relances
séparées. Un sélecteur ne doit pas supposer que la première page contient tout
le catalogue : charger les pages suivantes à la demande, dédupliquer par id et
conserver une sélection valide. Un company_id d'URL hors des options déjà
chargées exige une lecture de référence par id, pas une conclusion « absent ».
Aucune sélection automatique de la première entreprise, même si elle est seule.

### Détail /sites/:siteId

```text
Détail du site                  [Retour à la liste des sites] [Modifier]
Informations du site
Nom / Code / Identifiant
Entreprise : <nom - code> [Voir l'entreprise]
Description intégrale
Création : JJ/MM/AAAA à HH:mm
Dernière modification : JJ/MM/AAAA à HH:mm
Dates affichées selon les informations horaires du serveur.
```

L'id du chemin est validé avant HTTP. Le GET Site détermine le company_id réel ;
un paramètre de retour différent ne remplace jamais cette valeur. Lire la
référence entreprise une fois pour le libellé/lien, sans N+1 par ligne dans la
liste filtrée. Une erreur de libellé entreprise n'efface pas le Site chargé :
afficher l'identifiant et une erreur de référence relançable si approprié.
404 Site reste une erreur métier locale ; URL de route inconnue va à la 404 globale.

### Création /sites/new et édition /sites/:siteId/edit

```text
Nouveau site OU Modifier le site
Entreprise (obligatoire) [sélecteur en création / texte en édition]
Nom *         [                                      ]
Code *        [                                      ]
Description   [                                      ]
Informations de suivi (édition seulement)
Créé le : ...                     Modifié le : ...
[Créer le site OU Enregistrer les modifications] [Annuler]
```

Création : pas de GET Site ; charger les entreprises et vérifier le parent
prérempli éventuel. Un changement d'entreprise avant envoi ne perd pas les autres
saisies, compte comme modification et doit rester explicite. Édition : GET Site
avant de révéler les champs ; pas de transfert d'entreprise proposé. Aucun PATCH
si valeurs inchangées ou revenues à l'origine. Pendant saving, verrouiller
champs et actions, empêcher doubles soumissions et navigation d'abandon.
CanDeactivate et beforeunload reprennent le principe Companies, sans prétendre
annuler une transaction déjà traitée par le serveur.

Succès POST/PATCH : toast unique « Site créé avec succès. » ou « Site modifié
avec succès. », navigation vers l'id renvoyé, GET détail et confirmation
persistante role=status « Site créé. » / « Site modifié. ». Aucun toast en cas
d'erreur, d'absence de différence ou de requête annulée.

### Retours et navigation Companies/Sites

- Retour liste Sites conserve le snapshot appliqué company_id/page/page_size/search,
  pas la recherche encore en cours de saisie. Annuler création revient à cette
  liste ; annuler édition revient au détail, après protection d'abandon.
- Accès direct sans contexte : retour vers /sites?company_id=<parent réel>&page=1,
  page_size=20 après chargement du Site ; sinon /sites sans sélection implicite.
- Depuis le détail Companies, Voir les sites ouvre /sites?company_id=<id>&page=1.
  Préserver le contexte de liste Companies par paramètres dédiés company_page,
  company_page_size et company_search, distincts des filtres Sites. Aucun
  returnUrl libre ni redirection externe. Ce lien n'impose pas un état de façade
  partagé. Le détail Sites offre Voir l'entreprise vers le parent réel ; seuls
  les paramètres Companies validés lui sont transmis.
- Les paramètres numériques doivent être des entiers positifs sûrs, page_size
  entre 1 et 100 ; recherche trimée et limitée à 100. Paramètres invalides
  normalisés avec notice avant requête, company_id invalide retiré sans choisir
  une autre entreprise. Une entreprise 404 doit être signalée explicitement.
- Si contexte filtré et parent réel du Site divergent, conserver le retour à la
  liste d'origine mais afficher le parent réel, avec notice de divergence.
  Ne pas faire passer cette comparaison ergonomique pour une autorisation.

## 6. États, erreurs et accessibilité

Liste : idle/loading/empty/success/error ; total=0 signifie vide ou aucun résultat
selon search. Items vide et total positif signifie page indisponible, avec
action manuelle vers une page disponible, sans boucle automatique. Détail :
loading/success/error. Formulaire : loading/load-error/idle/saving/success/error,
avec état distinct de disponibilité de la référence entreprise.

| Cas | Message et action proposés |
| --- | --- |
| Référence entreprise non choisie | Sélectionnez une entreprise ; pas de GET Sites ni POST |
| Parent 404 lors de sa vérification | Cette entreprise n'existe pas ou n'est plus disponible ; changer la sélection, aucune écriture |
| total=0 sans recherche | Aucun site pour cette entreprise ; proposer Nouveau site |
| total=0 avec recherche | Aucun site ne correspond à cette recherche ; Effacer conserve l'entreprise |
| GET Site 404 | Site introuvable ; retour liste, pas de formulaire vide ni recréation |
| GET réseau/5xx | Chargement impossible ; Réessayer manuellement avec le snapshot |
| Écriture 409 | Conflit : vérifiez que l'entreprise existe et que le code est unique parmi tous les sites ; saisie conservée et résumé focalisable |
| Écriture 422 | Erreurs associées aux champs connus via detail.loc, résumé des autres contraintes ; focus premier champ invalide |
| PATCH 404 | Ce site n'existe plus ; saisie conservée, pas de POST de substitution |
| Écriture réseau/5xx | Enregistrement non confirmé ; vérifier liste/fiche avant une nouvelle soumission explicite, sans retry automatique |
| 401/403 éventuels d'un futur déploiement | Accès refusé, sans relance ni assimilation à une liste vide ; aucune preuve que ces protections existent actuellement |

Pour 409, ne pas déduire automatiquement un champ à partir d'un detail libre ni
inventer un code d'erreur. Afficher un résumé générique et proposer vérification
du parent/code ; aucun HTML brut du serveur. Un durcissement backend ultérieur
serait un chantier séparé. Après erreur de résultat incertain, conserver la
saisie et le verrou de nouvelle soumission jusqu'à vérification explicitement
confirmée par l'utilisateur, comme Companies. Pas d'idempotence serveur,
de verrou de version ou de fusion concurrente prétendus.

PageHeader unique h1, sections h2, caption et en-têtes de tableau, liens réels
pour naviguer et boutons pour agir. Labels et aides associés, aria-invalid,
résumé d'erreurs et aria-live appropriés ; ne pas multiplier les annonces.
Conserver le focus de recherche sur les changements d'URL internes à la page,
le focus main géré par le Shell lors d'une nouvelle page et le focus premier
champ erroné. Les états busy ne doivent pas masquer les erreurs comme des vides.

Thème clair/tokens existants ; actions repliables, description longue avec
sauts de ligne, champs min-width:0, une colonne mobile. Prévoir liste lisible à
320 px sans débordement global, comme Companies, plutôt qu'ajouter des colonnes
non disponibles au contrat. Shell desktop à partir de 1024 px inchangé.
Vérifier clavier, Tab/Shift+Tab, Espace/Entrée, Échap du menu, restauration du
focus, zoom réel 200/400 % et lecteur d'écran réel. Les preuves historiques
Dashboard ne valident pas automatiquement Sites ou Companies.

## 7. Architecture Angular recommandée

```text
features/sites/
  sites.routes.ts
  sites-list.facade.ts
  models/site-write.model.ts
  models/sites-state.model.ts
  data-access/sites-api.service.ts
  pages/sites-list/
  pages/site-detail/
  pages/site-form/
  components/site-form/
  styles/_site-actions.scss
```

Routes proposées sous le Shell : /sites (liste, pathMatch full), /sites/new,
/sites/:siteId/edit, /sites/:siteId, dans cet ordre. loadChildren pour Sites,
loadComponent pour les pages ; titres et data.pageTitle cohérents, canDeactivate
sur les deux routes de formulaire. Ne pas ajouter de lien Sidebar supplémentaire.

Flux liste : page et URL -> SitesListFacade locale -> SitesApiService ->
ReferenceDataApiService.getSites. La façade expose des signals en lecture seule,
un snapshot immutable et switchMap/takeUntilDestroyed pour les lectures.
Page détail et page de formulaire gardent leurs états locaux et leur propre
gestion des identifiants/réponses obsolètes. Aucun polling ni store global.

SitesApiService : list(companyId, query), getById, create, update ; aucun delete.
SiteCreate reflète name/code/company_id requis, description facultative nullable.
SiteUpdate reflète les quatre champs facultatifs nullables du backend, mais la
page de formulaire construit un PATCH de name/code/description seulement.
Les horodatages restent des strings dans SiteRead et ne sont jamais réécrits.

Pour vérifier/précharger une entreprise par id sans importer un service de la
feature Companies dans Sites, prévoir dans UI 4.2 une lecture de référence
getCompanyById dans core/ReferenceDataApiService (GET /companies/{id} existant),
avec son test HTTP. Ce serait un ajout frontend de transport, pas un nouvel
endpoint backend. Les chargements de référence ne doivent jamais réinitialiser
un formulaire déjà modifié. Pas d'import CompaniesListFacade/CompanyFormComponent
ou de dépendance circulaire. Le lien Companies -> Sites reste un RouterLink.

## 8. Scénarios de tests à prévoir avant livraison

| Niveau | Scénarios nécessaires |
| --- | --- |
| Transport | Chemins GET/POST/PATCH exacts, params company_id/page/page_size/search, omission des facultatifs, dates brutes inchangées, erreurs conservées, aucune méthode DELETE |
| Références | Parent au-delà de la première page, chargement paginé/déduplication, id d'URL vérifié, 404/réseau, aucune première entreprise choisie automatiquement, aucune requête Sites sans parent valide |
| Liste/façade | idle, loading, vide sans/avec recherche, succès, page hors plage, normalisation URL, retour page 1 au changement entreprise/recherche, filtre ET recherche, jokers, snapshot immuable, annulations et retry manuel |
| Détail | Id invalide sans HTTP, 404/422/réseau/5xx, changement d'id et destruction, parent réel divergent du contexte, échec du libellé sans perte du détail |
| Formulaire | Nom/code blancs et limites Unicode 150/50, description longue/null/omission, entreprise obligatoire en création et immuable en édition, dates textuelles hors FormGroup/PATCH, absence de suivi en création |
| Écriture | Un POST/PATCH par action, aucun PATCH inchangé ou revenu à l'origine, aucun company_id en PATCH MVP, 409 parent et code distincts du mapping Companies, 422 champs/résumé, 404 sans recréation, issue incertaine sans retry |
| Navigation | Routes new avant id, titres/Shell/Sites actif, protection d'abandon acceptée/refusée, beforeunload, contexte des deux listes, retours profonds sans URL externe, toast unique et confirmation persistante |
| Non-régression | Dashboard et ses références/dates, Companies et ses filtres/écritures, 404/Shell/Sidebar, utilitaire de dates sans fuseau/Z/offset/fractions/valeurs invalides |
| Visuel et accessible | 1440/1024/1023/768/390/320 px, longs textes, formulaire et toasts, focus/clavier, erreurs annoncées, menu mobile, zoom réel et lecteur d'écran si disponibles ; consigner les limites sinon |

Lors d'une future validation intégrée, distinguer lectures FastAPI réelles,
simulations HTTP Angular/navigateur et écritures réellement persistées. Les
POST/PATCH de Companies n'ont pas été validés de bout en bout ; ce précédent
ne valide pas ceux de Sites. Ne pas écrire dans la base de développement pour
prouver cette conception. Les tests backend de cascade/intégrité nécessiteraient
une base de test isolée et un périmètre séparément autorisé.

Exécuter les suites Angular complètes puis le build production séquentiellement,
contrôles Sass pertinents, audit npm et diff --check ; consigner les résultats
réels sans réattribuer les 386 tests historiques à une nouvelle exécution.
Mesurer initial et différé : dette de départ 600,89 ko pour un budget initial
de 500 ko, sans relèvement ni dépendance nouvelle. Le lazy loading réduit le
chargement initial potentiel mais ne garantit pas une taille inchangée : mesurer.

## 9. Risques et suivi de la conception validée

Le périmètre fonctionnel de la section 4 est validé. L'architecture recommandée
et le découpage prévisionnel restent le cadre de préparation des étapes
suivantes, sans autorisation de les commencer. Les décisions existantes sont
préservées ; aucune nouvelle entrée D015 n'est ajoutée dans cette finalisation.

Risques persistants : API sans autorisation tenant, contraintes Pydantic/SQL
différentes, conflit 409 non structuré, courses FK/unicité non traduites,
modification concurrente sans version serveur, issue d'écriture incertaine,
catalogue d'entreprises volumineux, dates sans garantie de fuseau, budget initial
déjà dépassé et validations réelles d'accessibilité encore incomplètes.
Les créations/modifications/suppressions simultanées externes peuvent invalider
un parent ou une page : ne pas écraser la saisie ni élargir implicitement le scope.

## 10. Découpage prévisionnel, sous réserve de validation

| Étape | Livrable proposé |
| --- | --- |
| UI 4.2 | DTO d'écriture, SitesApiService, lecture core entreprise par id et tests HTTP, sans écran complet |
| UI 4.3 | Routes différées, liste avec sélection d'entreprise, recherche, pagination et façade locale |
| UI 4.4 | Détail Site, dates lisibles, liens parent et Companies -> Sites, contextes de retour |
| UI 4.5 | Création et SiteForm partagé, validation, protection d'abandon et succès Nebular |
| UI 4.6 | Modification différentielle, entreprise immuable, suivi lecture seule et erreurs d'écriture |
| UI 4.7 | Validation intégrée, responsive/accessibilité, non-régression et mesure bundle, preuves réelles/simulées séparées |
| UI 4.8 | Documentation finale, bilan des limites et préparation de livraison avant autorisation Git |

UI 4.1 s'arrête à cette conception. Aucun fichier applicatif, contrat,
dépendance, budget ou donnée PostgreSQL modifié. Aucun commit, push ou merge.
La prochaine action est l'autorisation du commit documentaire. Toute
implémentation UI 4.2 nécessitera ensuite une demande distincte.
