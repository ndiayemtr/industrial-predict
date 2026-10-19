# UI 5.1 - Conception du module Équipements industriels

19 octobre 2026. **Conception validée : arbitrages EQ-01 à EQ-07 approuvés par l’utilisateur.**
Branche contrôlée : `feature/frontend-equipments`, HEAD `667fe5b978aeda5cebf2d7cabf62497c987e8da4`.
`main` et la référence locale `origin/main` pointent au même commit. Dépôt propre
avant rédaction. Aucune création de branche nécessaire, aucun fetch effectué.

Ce document distingue le contrat constaté, les conventions déjà livrées et les
décisions MVP approuvées. UI 5.2 est autorisée séparément pour la couche de données
uniquement ; aucune écriture métier réelle n’est autorisée.
Aucun changement applicatif/backend, package, commit, push ou merge.

## 1. Méthode, sources et état de départ

Analyse statique des sources et tests versionnés ; contrôle local des schémas
Pydantic uniquement, sans import du serveur, moteur SQL ou connexion PostgreSQL.
Aucun appel API, lancement Docker, migration, seed ou test de suppression.

Sources principales :

- [Modèle Equipment](../backend/app/models/equipment.py),
  [migration initiale](../backend/migrations/versions/656260b06cdf_create_equipments_table.py),
  [migration criticality](../backend/migrations/versions/675ebfea0bb5_add_equipment_criticality.py).
- [Schémas Equipment](../backend/app/schemas/equipment.py),
  [énumérations](../backend/app/core/enums.py),
  [routes Equipment](../backend/app/api/routes/equipment.py),
  [montage API](../backend/app/main.py),
  [service](../backend/app/services/equipment_service.py),
  [repository](../backend/app/repositories/equipment_repository.py).
- [Contrat Page](../backend/app/schemas/pagination.py),
  [construction de pagination](../backend/app/core/pagination.py),
  [tests de filtres](../tests/pagination_filters/test_routes.py),
  [tests de schémas](../tests/business_validation/test_schemas.py).
- [Architecture frontend](frontend-architecture.md), [règles visuelles](ui-design.md),
  [architecture générale](architecture.md), [décisions existantes](decisions.md),
  [conception Sites](etape-ui-4.1-sites.md) et [bilan Sites](ui-4.7.5-sites-closure.md).

Les routes actuelles `/equipments` et `/equipments/:equipmentId` sont des
placeholders, sans module CRUD Équipements implémenté. Les intentions antérieures
Health Score, RUL, onglets capteurs/mesures/prédictions/documents sont des cibles
produit ; elles ne constituent pas des fonctionnalités déjà livrées ou un périmètre
MVP automatiquement approuvé. Le suivi global décrit encore l'état préparatoire
de Sites ; le présent document consigne le contexte Git réel sans réécrire cet historique.

## 2. Contrat backend Equipment constaté

### Champs et contraintes

| Champ | Schémas API | Persistance et conséquence UI |
| --- | --- | --- |
| id | EquipmentRead uniquement | Entier technique, clé primaire ; liens/états internes, pas un champ de saisie |
| name | Requis en création ; facultatif nullable en PATCH | VARCHAR(150), NOT NULL ; aucune contrainte Pydantic de longueur ou de texte non blanc |
| code | Requis en création ; facultatif nullable en PATCH | VARCHAR(100), NOT NULL, index unique global, toutes entreprises/sites confondus |
| equipment_type | Requis en création ; facultatif nullable en PATCH | VARCHAR(100), NOT NULL ; texte libre, aucun catalogue ou enum de types |
| description | Facultative, chaîne ou null ; défaut null en création | TEXT nullable ; aucun maximum métier explicite |
| status | Enum en création, défaut operational ; facultatif nullable en PATCH | VARCHAR(50), NOT NULL, défaut ORM operational ; pas de machine à états dans le service |
| criticality | Enum en création, défaut medium ; facultatif nullable en PATCH | VARCHAR(20), NOT NULL ; défaut ORM et défaut serveur de migration medium, index |
| site_id | Entier requis en création ; facultatif nullable en PATCH | FK NOT NULL vers sites.id, ON DELETE CASCADE ; service vérifie le site fourni |
| created_at / updated_at | datetime en lecture seulement | DateTime sans fuseau explicite, datetime.utcnow et onupdate ; jamais envoyés dans les formulaires |

EquipmentRead contient ces dix champs, sans company_id, nom du site, nom de
l'entreprise, fabricant, série, localisation, date d'installation, compteurs de
capteurs, dernière maintenance ou résultat ML. Ne pas inventer ces propriétés.

Le code est recherché par égalité avant écriture, sans trim ou changement de
casse backend. Aucune unicité métier insensible à la casse n'est garantie.
Les colonnes status/criticality sont des chaînes SQL, sans contrainte CHECK
d'énumération dans les migrations examinées ; la validation d'enum est portée
par Pydantic. Une valeur historique hors vocabulaire peut donc faire échouer la
validation de réponse ; ne pas promettre qu'un fallback frontend corrige ce cas.

Contrôle local Pydantic exécuté en UI 5.1 : création sans status/criticality
produit operational/medium ; PATCH vide produit `{}` avec exclude_unset ; null
explicite accepté en PATCH pour les champs non nullable SQL. La création accepte
name vide, name de 151 caractères, code/type de 101 caractères et site_id=0 au
niveau schéma. Elle refuse status=inactive, criticality=urgent et null pour ces
deux enums. **Ces acceptations de schéma ne démontrent aucune acceptation SQL.**

### Statuts et criticités réellement supportés

| Champ | Valeur transport exacte | Libellé français proposé |
| --- | --- | --- |
| status | operational | Opérationnel |
| status | maintenance | En maintenance |
| status | out_of_service | Hors service |
| criticality | low | Faible |
| criticality | medium | Moyenne |
| criticality | high | Élevée |
| criticality | critical | Critique |

Ne pas envoyer les libellés, une majuscule ou des espaces dans ces enums.
Le service autorise toutes les transitions entre valeurs valides ; aucune règle
« maintenance exige une intervention ouverte » ou « hors service désactive les
capteurs » n'est implémentée. Criticité et statut ne représentent pas un Health
Score ni une prédiction de panne. Les éventuelles règles supplémentaires restent
des évolutions métier hors MVP, sans validation arbitraire frontend.

### Endpoints montés sous /api/v1

| Méthode / chemin | Contrat constaté |
| --- | --- |
| GET `/equipments` | Page[EquipmentRead] ; page >= 1 (défaut 1), page_size 1..100 (défaut 20), site_id >= 1 facultatif, status/criticality enums facultatifs, search longueur 1..100 facultative ; 200 ou 422 de validation |
| GET `/equipments/{equipment_id}` | EquipmentRead ou 404 ; entier de chemin sans ge=1 explicite, 422 si conversion impossible |
| GET `/equipments/site/{site_id}` | Liste non paginée ; à ne pas utiliser pour remplacer la pagination UI |
| POST `/equipments` | EquipmentCreate ; 201 EquipmentRead, 409 sur ValueError avec rollback, 422 Pydantic |
| PATCH `/equipments/{equipment_id}` | EquipmentUpdate, model_dump(exclude_unset=True) ; 200 EquipmentRead, 404 si absent, 409 sur ValueError avec rollback, 422 Pydantic |
| DELETE `/equipments/{equipment_id}` | 204 sans corps ; 404 si absent ; suppression définitive avec descendants concernés |

Le GET liste **ne possède aucun filtre company_id ni equipment_type dédié**.
Le type est couvert par search, pas par un catalogue de types récupérable.
Les filtres site/status/criticality et search se combinent par ET. Search fait
un OU sur name/code/equipment_type avec ILIKE `%search%` ; trim côté service,
chaîne blanche devenue absence de filtre, jokers `%` et `_` non échappés.
Pas de recherche description ni d'insensibilité aux accents garantie.

Tri fixe id ASC ; aucune API de tri. Page contient items/total/page/page_size/pages,
pages=0 si total=0. Une page hors plage peut être vide avec total positif : pas
de recalage automatique ni de 404. Items et total sont deux lectures séparées,
sans garantie de snapshot immuable sous concurrence. Un site inexistant filtré
peut renvoyer une liste vide : ce vide ne prouve pas que le parent existe.

### Erreurs et capacités que le backend ne garantit pas

Le service vérifie le site puis le code en création ; il vérifie site_id et code
seulement s'ils sont fournis en PATCH. Deux causes connues de 409 textuel :
site absent et code Equipment déjà utilisé. Pas de code métier structuré pour
les distinguer sûrement ; ne pas reprendre « tout 409 cible Code » de Companies.
Un PATCH du code courant n'est pas un conflit avec l'équipement lui-même.

Omission conserve la valeur ; description vide et description:null sont distincts.
site_id:null échoue à la vérification de site ; name/code/type/status/criticality
null peuvent atteindre une contrainte SQL NOT NULL. Les courses d'unicité/FK et
autres IntegrityError ne sont pas traduites systématiquement en 409/422.
Aucun verrou de version, ETag, idempotence, contrôle de transition ou handler
général d'intégrité ne doit être prétendu. Aucun correctif backend en UI 5.1.

Des routes prédictives existent sous Equipment : GET predictions/recommendations,
POST health-score/rul/recommendations. Ce ne sont pas des champs CRUD Equipment.
Leurs POST de calcul/génération peuvent persister des résultats ; ne jamais les
appeler automatiquement à l'ouverture d'une fiche ou d'un filtre CRUD.

## 3. Relations et équipements ayant des descendants

Relation constatée : **Company -> Site -> Equipment -> Sensor -> Measurement** ;
MaintenanceRecord, PredictionRecord et MaintenanceRecommendation référencent aussi
Equipment. Un équipement peut avoir zéro descendant : aucune création de capteur
ou maintenance n'est requise pour le créer.

Sources : [Company](../backend/app/models/company.py),
[Site](../backend/app/models/site.py), [Sensor](../backend/app/models/sensor.py),
[Measurement](../backend/app/models/measurement.py),
[MaintenanceRecord](../backend/app/models/maintenance_record.py),
[PredictionRecord](../backend/app/models/prediction_record.py),
[MaintenanceRecommendation](../backend/app/models/maintenance_recommendation.py).

- company_id se résout par Equipment.site_id puis Site.company_id. Ne jamais
  utiliser l'entreprise du contexte de retour comme parent réel de la fiche.
- Suppression : cascades ORM sur capteurs/maintenances/recommandations et FK SQL
  en cascade, y compris mesures via capteurs et prédictions via équipement,
  capteur ou mesure. Pas de corbeille, archivage ou endpoint d'estimation d'impact.
  Ce constat est statique, sans essai destructif ni garantie testée de cascade.
- Changement de site : le backend le permet vers tout site existant, sans vérifier
  l'entreprise, les descendants ou les droits. Capteurs, mesures et maintenances
  restent attachés au même équipement ; leur périmètre déduit du site change,
  potentiellement vers une autre entreprise. Aucun journal métier de transfert
  ou réaffectation explicite des historiques n'est fourni.
- Modification des autres champs : conserve les relations par id ; status,
  equipment_type et criticality ne déclenchent dans EquipmentService ni mutation
  des capteurs/maintenances, ni recalcul ML. Ne pas faire croire qu'un statut
  maintenance ouvre une intervention, ou qu'un retour operational la termine.

MVP approuvé : fiche métier seule, sans chargement automatique des descendants,
sans faux compteurs à zéro, sans onglets inactifs présentés comme fonctionnels.
Un développement ultérieur pourrait utiliser GET `/sensors?equipment_id=...`,
GET `/maintenance?equipment_id=...` et GET `/measurements?sensor_id=...`.
Il n'existe pas de filtre Equipment direct sur cette dernière liste : agréger
tous ses capteurs et mesures demande un contrat/périmètre distinct, pas un fan-out
silencieux. Aucun CRUD de descendants ni action de génération ML dans ce MVP approuvé.

## 4. Périmètre MVP et décisions approuvées

Les sept arbitrages sont officiellement validés. Les restrictions ci-dessous
portent sur le MVP frontend ; les capacités backend constatées restent inchangées.

| Référence | Décision approuvée | Portée et limites |
| --- | --- | --- |
| EQ-01 | Liste après sélection explicite entreprise puis site ; site obligatoire, aucune sélection automatique | Pas de vue tous sites d'une entreprise ni de pagination locale fusionnant plusieurs sites. Conserver status/criticality valides au changement de parent ; entreprise changée efface site/recherche et revient page 1 |
| EQ-02 | Aucun DELETE dans l'UI ou le service Angular, sans action désactivée | Toute future suppression reste un chantier distinct avec impact, permissions et autorisation spécifiques |
| EQ-03 | Aucun déplacement de site, même dans la même entreprise ; site_id exclu du PATCH MVP | Site et entreprise en lecture seule en édition. Un futur transfert nécessite une nouvelle décision métier et de sécurité |
| EQ-04 | Fiche CRUD sans listes embarquées de descendants ni indicateurs ML | Consultation des capteurs/mesures/maintenances et ML hors MVP ; aucun faux compteur |
| EQ-05 | Type en texte libre ; statut et criticité éditables avec les enums et libellés décrits | Pas de catalogue fictif, règle de transition ajoutée ou synchronisation automatique de maintenance |
| EQ-06 | Création avec défauts visibles présélectionnés operational/medium, conformes à l'API | Les futurs formulaires montrent ces valeurs. Le transport peut omettre les propriétés facultatives pour laisser appliquer les défauts backend, sans les injecter ou modifier silencieusement |
| EQ-07 | Lien Voir les équipements depuis Site et lien vers le Site réel depuis Equipment | Intégration aux étapes d'écran prévues ; aucun élargissement Companies ni réalisation de ces liens en UI 5.2 |

Hors MVP approuvé : import/export, actions groupées, documents, géolocalisation,
historique d'audit, archivage, calculs ML, édition des descendants, modification
backend, RBAC et sécurisation multi-tenant. Le backend existant ne porte aucune
authentification/autorisation utilisateur ou tenant sur ces routes ; filtres et
vérification de parent ne sont pas des protections d'accès. Une restriction UI
de suppression/transfert ne sécurise pas les endpoints directs.

## 5. Parcours et propositions d'interface

### Liste, recherche et filtres

Selon EQ-01, PageHeader « Équipements industriels », action « Nouvel
équipement », puis Entreprise obligatoire, Site obligatoire, recherche « Nom,
code ou type », Statut (Tous ou enum), Criticité (Toutes ou enum), taille de page.
Tableau proposé : Nom lié au détail, Code, Type, Statut, Criticité. Le site et
l'entreprise sélectionnés figurent au-dessus ; pas de GET parent par ligne.
Description intégrale réservée au détail pour limiter la largeur du tableau.

1. Départ sans contexte : catalogue d'entreprises seulement ; invitation initiale,
   aucun GET Equipment. Choisir une entreprise charge ses sites paginés.
2. Choisir un site exige de vérifier Site.company_id contre l'entreprise choisie.
   Le company_id UI n'est **jamais envoyé comme filtre Equipment** ; la requête
   Equipment contient site_id et les seuls filtres backend reconnus.
3. Catalogues par pages de 50, chargement supplémentaire explicite, déduplication,
   conservation des pages reçues après erreur. Référence d'URL hors catalogue :
   lecture ciblée par id plutôt que conclure à son absence.
4. Entreprise changée : annuler les anciennes lectures, vider le site/la recherche,
   revenir page 1 et suspendre les résultats. Site changé : revenir page 1.
   Recherche, statut, criticité, taille changés : revenir page 1. Les filtres
   transversaux status/criticality valides peuvent être conservés au changement
   de parent ; comportement approuvé dans EQ-01.
5. Recherche sur bouton ou Entrée, aucune requête à la frappe ; Effacer retire
   seulement search. Pagination serveur, choix 20/50/100 ; accepter aussi une
   taille d'URL valide 1..100, comme Sites. Aucun tri inventé.
6. États distincts : sélection attendue, chargement, aucun équipement, aucun
   résultat filtré, page indisponible avec total positif, erreur. Pas de pagination
   visible pour total=0 ; récupération de page manuelle, sans boucle automatique.

URL proposée : `/equipments?company_id=...&site_id=...&status=...&criticality=...&search=...&page=1&page_size=20`.
L'URL appliquée porte le snapshot, pas le brouillon de recherche. Normaliser les
entiers positifs sûrs, tailles, search trimée <=100 et enums ; notice avant lecture
pour un contexte invalide, jamais de périmètre implicite plus large. Paire
entreprise/site incohérente en liste : bloquer les équipements et demander une
sélection cohérente. site_id seul en lien profond : résoudre site puis entreprise,
sans choisir arbitrairement la première option. Aucun returnUrl externe.

### Détail

PageHeader, Retour liste et Modifier après chargement. Fiche : nom, code, type,
statut, criticité, description (ou Non renseignée), site et entreprise résolus
par leur parent réel, dates administratives disponibles. Labels métier nom/code
sans affichage technique d'id ; chaînes de transport inchangées.

Lecture Equipment puis Site puis Company ; erreurs de référence séparées, données
Equipment conservées même si le parent n'est plus lisible. Id invalide : erreur
locale sans HTTP ; Equipment absent : 404 dédiée, aucune fiche vide/recréation.
Contexte liste différent du parent réel : notice, parent réel affiché, retour
au contexte de liste conservé. Lien vers Site approuvé par EQ-07 ; utiliser un
contexte de retour Site distinct des filtres Equipment si nécessaire.

Ne pas afficher « Aucun capteur » ou « Aucune maintenance » faute de les avoir
lus. Un enum inattendu reçu ne devient pas silencieusement operational/medium :
affichage d'indisponibilité explicite et soumission bloquée jusqu'à traitement
cohérent, sans nouvelle valeur métier inventée.

### Création et modification

Formulaire Equipment propre à la feature, partagé par deux pages d'orchestration.
Création : Entreprise (contexte UI), Site, Nom, Code métier, Type d'équipement,
Statut, Criticité, Description. Site prérempli depuis une liste valide, mais
vérifié avec son entreprise avant POST ; aucun identifiant implicite. Sans site
disponible : invitation à créer un site via un lien existant, pas de création
imbriquée. Les sélections/chargements n'effacent jamais une saisie métier.

Édition, selon EQ-03 : site et entreprise en lecture seule ; dates de suivi
hors FormGroup ; seuls nom/code/type/status/criticality/description éditables.
PATCH construit par comparaison des valeurs brutes initiales/courantes, pas par
dirty ; champs revenus à l'origine exclus, aucun PATCH vide. Whitelist au service
également : ni site_id/company_id, ni id, dates ou données des descendants.

Après POST 201/PATCH 200 : navigation vers l'id retourné et un seul toast Nebular
après navigation réussie, plus confirmation role=status indépendante sur le
détail. Navigation refusée après succès : lien de récupération, aucune nouvelle
écriture ni faux toast. Annuler création revient à la liste, Annuler édition au
détail, avec contexte validé et protection des modifications réelles.

## 6. Validation UX, erreurs et accessibilité proposées

- Nom/code/type non blancs ; limites respectives **150/100/100 points de code
  Unicode**. Ne pas recopier la limite Code=50 de Sites. Création : trim de ces
  textes, casse conservée ; édition : valeurs intactes préservées, espaces inclus
  dans les limites des champs modifiés, comme Sites. Aucune regex ASCII.
- site_id positif sûr et référence vérifiée, appartenant à l'entreprise choisie
  en création. company_id est un contexte/sélecteur UI, absent du payload Equipment.
- Statut/criticité : enums exacts, jamais null ni chaîne vide. Défauts visibles
  selon EQ-06 ; aucune normalisation d'une valeur inconnue ou d'un champ intact.
- Description sans maximum inventé : intacte omise en POST/PATCH lorsque pertinent,
  effacement manuel transmis comme chaîne vide, bouton Retirer comme null ;
  espaces, sauts de ligne et Unicode conservés. Pas de conversion vide/null implicite.
- Aucun id/date/nom de parent/filtre/compteur dans le corps. Aucune prévalidation
  d'unicité présentée comme définitive ; erreur serveur possible malgré validation UX.

| Situation | Traitement proposé |
| --- | --- |
| GET réseau/5xx | Erreur explicite, relance manuelle avec le snapshot ; ne pas changer les filtres |
| Parent 404 | Référence indisponible ; création/édition bloquée, saisies conservées ; pas de transfert de secours |
| Equipment 404 en PATCH | Conserver la saisie, signaler la disparition, aucun POST de remplacement |
| Écriture 409 | Conflit générique, vérifier site et code ; aucun parsing de detail libre ni attribution automatique à Code |
| Écriture 422 | Champs body connus seulement, messages frontend sûrs, focus premier champ ; autres contraintes dans le résumé ; site_id reconnu uniquement en création |
| Réseau/5xx après écriture | Résultat incertain : vérifier liste/fiche et acquitter avant une nouvelle soumission explicite ; aucun retry automatique |
| 401/403 éventuels | Accès refusé sans assimilation à un vide ; leur gestion défensive ne prouve pas une sécurité existante |

Verrou saving, contrôles/actions désactivés et navigation bloquée pendant l'appel.
CanDeactivate avec confirm et beforeunload sur changements réels ; revenir aux
valeurs initiales permet de quitter sans alerte. Ces protections n'annulent pas
une transaction déjà reçue et ne constituent pas une clé d'idempotence.

Un h1, PageHeader et composants LoadingState/EmptyState/ErrorState ; labels,
aides/erreurs associées, aria-invalid/aria-busy, caption/en-têtes du tableau,
statut/criticité lisibles en texte sans dépendre seulement de la couleur. Focus
premier champ invalide ; focus main/titres/Sidebar du Shell conservés. Tableau
à défilement local si nécessaire, actions repliables, aucun débordement global
à 320 px. Desktop Shell >=1024 px, sans seuil concurrent.

Le formateur administratif existant conserve les composantes d'un ISO sans
fuseau ; offsets explicites convertis en UTC, fractions masquées uniquement à
l'affichage. Ne pas ajouter de Z ni interpréter implicitement en heure navigateur.
Lecteur d'écran réel, zoom 200/400 % et dialogue natif à valider séparément :
les preuves Companies/Sites ne les valident pas pour Equipment.

## 7. Réutilisation et architecture Angular proposées

| Existant examiné | Réutilisation et limite |
| --- | --- |
| [Types core](../frontend/src/app/core/models/reference-data.model.ts) | EquipmentRead, EquipmentStatus, EquipmentCriticality, SiteRead, CompanyRead déjà présents ; aucune duplication des DTO de lecture |
| [ReferenceDataApiService](../frontend/src/app/core/api/reference-data-api.service.ts) | getCompanies/getSites/getSiteById/getCompanyById/getEquipmentById déjà présents ; réutiliser pour parents et détail |
| getEquipments(siteId, query) | GET paginé existant limité à page/page_size/search ; **ne transmet actuellement ni status ni criticality**, même avec propriétés supplémentaires TypeScript |
| [SitesApiService](../frontend/src/app/features/sites/data-access/sites-api.service.ts) | Pattern de délégation liste et whitelist PATCH, sans DELETE ; pas d'import métier de la feature Sites |
| [SitesListFacade](../frontend/src/app/features/sites/sites-list.facade.ts) | Façade locale signals/snapshot/switchMap, références vérifiées et annulation ; adapter aux deux parents, ne pas partager son état |
| [Formulaire Sites](../frontend/src/app/features/sites/components/site-form/site-form.component.ts) et [Companies](../frontend/src/app/features/companies/components/company-form/company-form.component.ts) | Reprendre validation Unicode, focus, description et protections ; ne pas importer leurs formulaires/types/SCSS internes : Equipment a un autre contrat et Code=100 |
| [businessReferenceLabel](../frontend/src/app/shared/utils/business-reference-label.ts) et [dates](../frontend/src/app/shared/utils/datetime-display.ts) | Réutilisation directe, sans nouvelle conversion métier |
| Shared, Shell, Router, NbToastrService | Providers et thème existants ; pas de forRoot supplémentaire, package, store global ou CRUD universel |

Pour supporter les filtres sans dupliquer le GET : proposer un type core
EquipmentPageQuery étendant ReferencePageQuery avec status?/criticality?, puis
une extension rétrocompatible du second paramètre getEquipments. Ajouter
explicitement ces deux HttpParams, omettre les filtres vides ; signature actuelle
et appels Dashboard restent valides. Tests de non-régression obligatoires sur le
service partagé et les paramètres Dashboard. Aucun changement effectué ici.

EquipmentListQuery de feature ajoute site_id au type paginé ; company_id reste
dans le contexte UI séparé. EquipmentsApiService.list délègue à ce transport,
getById peut déléguer au GET détail core existant, create/update portent les DTO
d'écriture propres. EquipmentUpdate MVP est le sous-ensemble de l'API sans site_id
selon EQ-03 approuvée ; documenter explicitement cette différence, sans faire
croire que le backend refuse un déplacement. Whitelist des six champs éditables.

Structure proposée, aucun fichier créé hors de ce rapport :

```text
features/equipments/
  equipments.routes.ts
  equipments-list.facade.ts
  models/equipment-write.model.ts
  models/equipment-list-query.model.ts
  models/equipments-state.model.ts
  data-access/equipments-api.service.ts
  pages/equipments-list/
  pages/equipment-detail/
  pages/equipment-create/
  pages/equipment-edit/
  components/equipment-form/
```

Routes proposées sous le Shell :

| Ordre | URL | Composant / comportement |
| --- | --- | --- |
| 1 | `/equipments` | EquipmentsListComponent, pathMatch full |
| 2 | `/equipments/new` | EquipmentCreateComponent, canDeactivate |
| 3 | `/equipments/:equipmentId/edit` | EquipmentEditComponent, canDeactivate |
| 4 | `/equipments/:equipmentId` | EquipmentDetailComponent |

`loadChildren` vers EQUIPMENT_ROUTES, puis `loadComponent` pour chaque page.
Adapter le [routing racine](../frontend/src/app/app.routes.ts) : remplacer le
placeholder de liste et retirer son ancienne route détail parallèle, sans deux
définitions concurrentes. new/edit avant l'id ; chemins imbriqués inconnus vers
404 globale ; neuf liens Sidebar conservés et section Équipements active.
Titres proposés : Équipements industriels, Nouvel équipement industriel,
Modifier l'équipement, Détail de l'équipement. Pas d'action descendant anticipée.

## 8. Tests prévus et critères d'acceptation

Les [tests pagination/filtres backend](../tests/pagination_filters/test_routes.py)
couvrent Equipment par site, status, criticality, nom/code/type, combinaisons,
pagination et enums invalides. Les tests métier existants couvrent enums/defaults
et PATCH vide, sur schémas ; ils ne prouvent pas une cascade ou autorisation.
Pas de suite dédiée de service CRUD Equipment trouvée dans les tests examinés.
Ne pas étendre la validation PostgreSQL passée de Sites au futur module Equipment.

| Niveau | Critères à vérifier avant livraison |
| --- | --- |
| Transport | GET paginé exact, site_id/status/criticality/search indépendants et combinés ; company_id jamais transmis ; réponses et erreurs intactes ; POST whitelist, PATCH différentiel, absence de DELETE conformément à EQ-02 |
| Références | Entreprise/site hors première page, pages dédupliquées et reprise après erreur, couple incohérent, site inexistant, aucune sélection implicite, pas de GET Equipment avant scope valide |
| Liste | idle/loading/vide/aucun résultat/page hors plage/error/success ; contexte URL/back, recherche explicite type comprise, resets de page et annulation des réponses obsolètes |
| Détail | Parent réel et contexte divergent, erreurs Equipment/Site/Company distinctes, ids invalides sans HTTP, dates sans fuseau/Z/offset/fractions/invalides, aucun faux compteur ou appel de calcul ML |
| Formulaire | Unicode 150/100/100, noms/types blancs, casse/espaces préservés selon mode, enums/defaults, null/omission/vide description, site vérifié, site non modifiable conformément à EQ-03, dates hors FormGroup |
| Écriture | Une requête par action, aucun PATCH inchangé/restauré, code global, 409 générique pour deux causes connues, 422 champs/texte/champs inconnus/balisage, 404 sans recréation, réseau/5xx incertain sans retry |
| Navigation | new avant id, disparition des placeholders concernés, 404 intacte, Shell/titres/Sidebar/focus, retours filtrés, liens Site approuvés, toast unique après navigation, récupération après navigation refusée |
| Abandon | Refuser/accepter via Annuler et navigation, saisie conservée après refus, beforeunload et saving ; scénario natif navigateur distinct des mocks confirm |
| Non-régression | Companies/Sites et leurs écritures, Dashboard et paramètres/getEquipments/références, dates, Shell/Sidebar/404 et utilitaires partagés |
| Visuel/accessibilité | 1440/1024/1023/768/390/320 px, clavier/menu mobile, longs textes/tableau/toasts, annonces/focus ; zoom et lecteur d'écran réels consignés avec leurs limites |

Prévoir d'abord HttpTestingController et fixtures entièrement isolées. Le
simulateur Sites actuel ne couvre pas Equipment : ne pas l'utiliser avec fallback
vers FastAPI. Si un outil navigateur Equipment est nécessaire, cadrer ses routes,
son absence d'upstream et ses tests avant de lui soumettre quoi que ce soit.

Lors d'une future intégration réelle séparément autorisée : vérifier les identités
du [DEV permanent](../infra/development/README.md), Angular 4201 -> FastAPI 8001
-> PostgreSQL 5434 / industrial_predict_dev. Préparer des données Equipment
dédiées, préserver le seed et les essais Sites ; garder les corps HTTP, comparer
aux lectures SQL et tester rechargement, POST 201/PATCH 200 et refus contrôlés.
Aucun DELETE, transfert, reset ou écriture réelle autorisé par la présente conception.

## 9. Découpage validé, exécution par étapes

| Étape | Livraison prévue | Condition d'acceptation |
| --- | --- | --- |
| UI 5.2 | DTO d'écriture/requêtes et EquipmentsApiService ; extension ciblée du transport de références | EQ-01/EQ-02/EQ-03 approuvées ; HttpTestingController, filtres exacts, whitelist, non-régression Dashboard ; aucun écran anticipé |
| UI 5.3 | Liste différée, références entreprise/site, recherche et filtres/pagination | Aucun scope implicite, paramètres et états conformes, annulations, navigation/back et six largeurs vérifiés |
| UI 5.4 | Détail métier et parents réels ; liens Site selon EQ-07 approuvée | 404/erreurs parents distinctes, dates et contexte, aucun faux agrégat/onglet ; conserver les anciennes URLs de détail |
| UI 5.5 | Création et EquipmentForm partagé | Validation 150/100/100 et enums, site vérifié, POST exact, protections/notifications/erreurs et responsive |
| UI 5.6 | Édition et PATCH différentiel | Aucun déplacement conformément à EQ-03, aucun PATCH vide/champ intact, valeurs brutes et relations préservées, suivi hors formulaire |
| UI 5.7 | Validation intégrée et non-régression | Distinguer preuves simulées/réelles, plan d'écritures séparément approuvé, persistance et erreurs, abandon natif, accessibilité et limites documentées |
| UI 5.8 | Documentation et préparation Git | Bilan des choix/écarts, résultats de référence, dettes et checklist ; aucun commit/fusion/publication sans demande explicite |

Pour chaque future implémentation : suite Angular complète et build production
séquentiels, contrôles Sass/npm pertinents et diff --check. Consigner date/HEAD,
résultats et tailles initiales/différées sans reprendre les chiffres antérieurs
comme nouvelle exécution. Pas de skip/retry ou hausse de budget pour masquer un échec.

## 10. Limites conservées et clôture UI 5.1

Référence précédente : 583 tests Angular réussis avec deux workers et build
production réussi, bundle initial 601,51 ko pour un budget warning de 500 ko.
Ces suites/build ne sont pas relancés ici ; le contrôle local Pydantic est distinct.
Le dialogue natif d'abandon reste une réserve Sites, pas une validation Equipment.
Les secrets historiques déjà suivis nécessitent externalisation/rotation dans
un chantier distinct ; aucune valeur lue pour ce document, affichée ou ajoutée.

Autres risques : absence d'authentification/autorisation multi-tenant, erreurs
SQL non structurées, concurrence sans version/idempotence, coût des catalogues
volumineux, enums historiques hors contrat, fuseaux non garantis et impact
métier des changements de type/statut/criticité. Aucun engagement de production SaaS.

Seul fichier proposé par UI 5.1 : `docs/etape-ui-5.1-equipments.md`, non indexé.
Branche et HEAD inchangés, index vide ; aucun changement exécutable ou backend,
aucune écriture PostgreSQL, aucun package, commit, push ou merge.
**UI 5.1 validée et commit documentaire autorisé. UI 5.2 autorisée pour les
modèles, le transport et leurs tests uniquement ; attendre validation avant son commit
et avant UI 5.3.**
