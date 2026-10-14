# Décisions techniques

## D001 - API

FastAPI est utilisé pour le backend.

## D002 - Base de données

PostgreSQL est la base principale.

## D003 - ORM

SQLAlchemy est utilisé avec Alembic pour les migrations.

## D004 - Architecture

Séparation :

Route
→ Service
→ Repository

## D005 - Multi-tenant

Les données doivent être isolées par `company_id`.

## D006 - Dashboard

Les agrégations complexes sont effectuées au niveau Repository.

## D007 - Machine Learning

Les composants ML doivent rester découplés des routes API.

## D008 - Tests

Toute nouvelle fonctionnalité importante doit être accompagnée de tests automatisés.

## D009 - Matrice frontend et limites de compatibilité

La fondation livrée utilise Angular 21.2.25 standalone, Nebular 17.0.0 et
Angular CDK 21.0.6. Les versions directes correspondantes sont exactes dans
`frontend/package.json` et enregistrées dans `package-lock.json`.
CLI/build : 21.2.26 ; TypeScript : 5.9.3 ; RxJS : 7.8.2 ; Zone.js : 0.16.3 ;
animations : 21.2.25. L'environnement vérifié le 14 octobre 2026 est
Node.js 24.21.0 et npm 11.19.0.

Le CDK 21.0.6 est conservé pour les exports privés
`_VIEW_REPEATER_STRATEGY` et `_DisposeViewRepeaterStrategy` utilisés par
Nebular 17.0.0. Le CDK 21.2.14 avait provoqué l'échec de compilation lié à
`_VIEW_REPEATER_STRATEGY` ; le retour ciblé à 21.0.6 a résolu cet import.
Ce choix correspond à la combinaison validée du projet, et ne garantit pas
la compatibilité de toute version Angular/CDK 21 ou d'une version future.

Zone.js et les animations Angular sont conservés pour la compatibilité
initiale Nebular. Les imports privés CDK et Sass Nebular constituent une dette
de maintenance : toute migration doit réexaminer les peer dependencies,
exports, thème, build, tests, accessibilité et rendu navigateur.
Une suppression du correctif ou une mise à jour doit être explicitement
validée ; aucun remplacement de Nebular n'est décidé implicitement.
Les installations doivent respecter les peers, sans `--force` ni
`--legacy-peer-deps`.

## D010 - Correction Sass Nebular reproductible par postinstall

`frontend/scripts/apply-nebular-sass-fix.mjs` est un script Node.js sans
dépendance supplémentaire, exécuté par `postinstall`. Il remplace uniquement
quatre expressions `if()` dépréciées par `if(sass(...): ...; else: ...)` :
trois dans `styles/global/_breakpoints.scss` et une dans
`styles/global/typography/_typography.scss` de `@nebular/theme@17.0.0`.

Le script vérifie la version exacte, l'unicité des expressions et l'empreinte
SHA-256 du contenu source avec normalisation des fins de ligne. Il contrôle
les deux fichiers avant d'écrire, accepte les expressions déjà corrigées
(idempotence) et échoue explicitement si le contenu ou la version est inattendu.
Les seules écritures concernent ces deux fichiers Sass installés ; le script
versionné rend la correction reproductible après `npm ci --strict-peer-deps`
avec scripts d'installation activés. Aucun patch manuel isolé n'est retenu.

La syntaxe exige Dart Sass **>= 1.95.0** ; la version installée constatée est
1.97.3. `verify-nebular-breakpoints.mjs` contrôle les fichiers attendus,
les limites des breakpoints, la typographie et le thème ; il traite la
dépréciation `if-function` comme une erreur, sans masquer globalement les warnings.
Des tests du script contrôlent également les cas d'échec et l'idempotence.

L'approche patch-package@8.0.1 a été abandonnée dans les étapes précédentes
à cause des vulnérabilités signalées et de son usage interne de
`npm install --force`. Elle ne constitue plus le mécanisme du projet.
Lors d'une migration Nebular ou Sass, vérifier le correctif amont et les
invariants avant d'adapter ou retirer le script.

## D011 - Un seul thème Nebular et styles ciblés

Le thème clair personnalisé `industrial-predict` hérite du thème par défaut et utilise
les tokens SCSS du projet. Seul ce thème est émis. Les styles globaux
incluent les mixins nécessaires au layout, à la sidebar, aux cards et à la
typographie ; ils ne rechargent pas tous les styles Nebular ni de CSS précompilé.
Toute extension de composants doit ajouter uniquement les styles nécessaires
et mesurer son impact sur le bundle, sans modifier les budgets pour masquer
une régression. Les chemins Sass internes restent liés à Nebular 17.0.0.

## D012 - Présentation shared et périmètre UI 1.7

Les contrats de PageHeader, LoadingState, EmptyState et ErrorState sont validés
en UI 1.7.1 et documentés dans `frontend-architecture.md` et `ui-design.md`.
Lors de cette décision en UI 1.7.1, ces composants étaient prévus sous
`shared/components/` et n'étaient pas encore implémentés. UI 1.7 est désormais
terminée et commitée dans `e3a2a2c` ; les contrats et responsabilités restent inchangés.

Ils restent standalone, stricts, accessibles, sans nouvelle dépendance ni
appel HTTP ou logique métier. La page fournit les actions projetées et traite
l'événement `retry`. `success` reste le rendu normal de la page.
Le PageHeader est distinct du Header global du Shell.
Les décisions backend D001 à D008 restent inchangées.

## D013 - Politique responsive centralisée et panneau mobile accessible

Décision validée pour UI 1.8.2 : desktop à largeur CSS **>= 1024 px**,
mobile/tablette à largeur CSS **< 1024 px**. À 1024 exactement, le mode desktop
est conservé. Le Shell centralise la détection et les transitions ; les styles
du Header suivent sa classe de mode plutôt qu'un second seuil indépendant.

Nebular 17.0.0 reste la source de l'état expanded/collapsed. Son mode responsive
natif n'est pas activé : le mode compacted cible notamment `nb-menu`, alors
que l'application utilise sa propre navigation. Les API publiques existantes
de Sidebar et des styles ciblés du Shell permettent la superposition mobile,
sans patch Nebular ni dépendance supplémentaire.

La Sidebar mobile est fermée initialement et ne compresse jamais le contenu
à l'ouverture. Le panneau ouvert utilise un dialogue modal, `CdkTrapFocus`
du CDK 21.0.6 déjà installé et un arrière-plan inert/aria-hidden. Le bouton
interne, Échap et le clic sur le fond extérieur ferment le panneau ; le focus
revient au toggle en l'absence de navigation. Après `NavigationEnd`, la
fermeture reste coordonnée avec la politique existante de focus du contenu,
y compris ses exceptions pour fragments et interactions. Les navigations
annulées n'entraînent pas cette fermeture.

Le franchissement vers mobile ferme la Sidebar ; le retour desktop l'ouvre
et retire la modalité et le fond. L'état manuel est conservé lors de changements
de largeur au sein d'un même mode. Les listeners et callbacks de rendu sont
nettoyés avec le cycle de vie Angular.

Le Header mobile donne priorité au bouton et au titre ; l'identité secondaire
et les emplacements Notifications/Profil non fonctionnels sont masqués.
Le design desktop et les tokens existants sont préservés.

Validation : 116 tests Angular, 5 tests de correctif Sass, build réussi,
tests navigateur autour de 1024 px et zoom réel 100/200/400 % confirmé
manuellement par l'utilisateur. **Lecteur d'écran réel non testé**.
L'avertissement initial 504,68 ko contre 500 ko est documenté, sans relever
les budgets. UI 1.8.4 est désormais clôturée : commit `12a18c3`, fusion `acd872b`.

## D014 - Dashboard frontend V1 : périmètre et consommation du contrat existant

Décision validée à l'issue d'UI 2.1 et enregistrée en UI 2.1.1 le 14 octobre
2026, sur `feature/frontend-dashboard`. **Conception uniquement : UI 2.2 n'est
pas commencée.** Les décisions D001 à D013 restent applicables.

| Identifiant | Décision V1 validée |
| --- | --- |
| DASH-01 | Utiliser uniquement les agrégats de `GET /api/v1/dashboard`. Aucun Health Score, RUL ou prédiction de panne ; ne pas inventer d'alertes ou de KPI. Les API ML existantes restent hors périmètre V1. |
| DASH-02 | Cartes KPI, tableaux, répartitions et barres CSS légères ; aucune bibliothèque graphique supplémentaire. Réutiliser le thème et les composants partagés. |
| DASH-03 | Différer l'affichage monétaire tant qu'aucune devise commune n'est définie. `maintenance.cost` reste dans le DTO cible ; `currency` vaut actuellement `null`. Aucun symbole de devise supposé. |
| DASH-04 | Alimenter le sélecteur d'équipement après choix du site, car la liste CRUD équipements ne filtre pas par entreprise. Le service API Dashboard conserve le support d'`equipment_id` sans `site_id`, autorisé par le backend. |
| DASH-05 | Initialiser à sept jours glissants en UTC (168 heures), avec fin fixée au moment de l'application du préréglage. Transmettre deux instants avec fuseau et conserver `[start_time, end_time)`. Les bornes appliquées restent fixes jusqu'à une nouvelle application ; aucune fenêtre glissante par timer. |
| DASH-06 | Consommer l'URL relative `/api/v1`. Prévoir le proxy Angular en développement vers `http://127.0.0.1:8000` (port backend confirmé par l'utilisateur) et un reverse proxy en production. Ni proxy ni configuration de production créés en UI 2.1.1. |

Ces choix ne changent ni le contrat backend, ni les versions, ni les budgets,
ni le correctif Sass. Les agrégats restent calculés par le backend ; la
présentation distingue « État actuel », « Sur la période » et « Au calcul ».
La sélection d'entreprise ne remplace pas une autorisation : la route actuelle
ne vérifie pas les droits d'un utilisateur sur les entreprises.

Le contrat, l'architecture cible, les références, états et risques sont décrits
dans [frontend-architecture.md](frontend-architecture.md), les cinq sections
visuelles dans [ui-design.md](ui-design.md) et le plan UI 2.2 à UI 2.8 dans
[roadmap.md](roadmap.md). Leur implémentation nécessite les missions suivantes.
