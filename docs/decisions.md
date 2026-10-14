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
Ces composants sont prévus sous `shared/components/` et ne sont pas encore
implémentés. UI 1.7.2 n'a pas commencé.

Ils restent standalone, stricts, accessibles, sans nouvelle dépendance ni
appel HTTP ou logique métier. La page fournit les actions projetées et traite
l'événement `retry`. `success` reste le rendu normal de la page.
Le PageHeader est distinct du Header global du Shell.
Les décisions backend D001 à D008 restent inchangées.
