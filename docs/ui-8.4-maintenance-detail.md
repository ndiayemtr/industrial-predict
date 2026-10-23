# UI 8.4 et UI 8.4.1 - Fiche détail et harmonisation Maintenance

Date : 23 octobre 2026. Branche : `feature/frontend-maintenance`. HEAD de départ et final : `161bf88`.

## Périmètre livré

Route lazy `/maintenance/:maintenanceId`, en lecture seule, selon [MAIN-01 à MAIN-16](etape-ui-8.1-maintenance.md). La liste conserve sa route et ouvre le détail par le titre cliquable de l’intervention. La colonne visible #ID est supprimée ; l’identifiant réel reste dans le modèle et la route. Aucune colonne Actions n’est ajoutée. Aucun formulaire, DTO ou appel d’écriture, aucune transition de statut et aucun bouton Equipment -> Maintenance (réservé à UI 8.5).

Le détail utilise le service et les modèles UI 8.2 inchangés : `GET /api/v1/maintenance/{maintenance_id}`, sans paramètres de liste. Les 18 champs sont affichés une seule fois comme données du dossier :

- Intervention : `id`, `title`, `maintenance_type`, `status`, `priority`.
- Description et diagnostic : `description`, `failure_code`, `root_cause`, `action_taken`.
- Intervenant : `technician`.
- Dates métier : `planned_at`, `started_at`, `completed_at`.
- Ressources : `cost`, `downtime_minutes`.
- Suivi : `created_at`, `updated_at`.
- Rattachement : `equipment_id`.

Les enums reprennent les libellés français de la liste, sans état exprimé uniquement par une couleur. `null` est signalé comme non renseigné, une chaîne vide comme « Texte vide » ; zéro reste `0`. Les textes multilignes sont préservés. Aucun arrondi, devise ou calcul de durée n’est ajouté. Le type prédictif est explicitement une classification déclarée, sans preuve d’une prédiction IA.

## Dates, références et erreurs

Les ISO sources sont affichés intégralement dans des éléments `code`, avec un `time[datetime]` conservant la valeur reçue. Pour une date avec offset validée par le service, le helper précis existant affiche UTC, sans `Date` ni reconstruction `toISOString()`. Exemple testé : `2026-10-23T17:30:00.123456+05:30` devient `23/10/2026 à 12:00:00.123456 UTC`, tout en conservant la source. Une date administrative naïve reste inchangée et porte la mention « fuseau non fourni ». Aucun Z n’est ajouté et UTC n’est pas supposé.

La chaîne résolue est Maintenance -> Equipment -> Site -> Company. Chaque GET vérifie l’identité retournée ; chaque clé parent est contrôlée avant le GET suivant. Les paramètres URL ne servent jamais à reconstituer cette chaîne. Le lien Equipment apparaît seulement après résolution de cet équipement ; ses paramètres utilisent uniquement les parents connus de cette référence et `page=1&page_size=20`. Le site et l’entreprise peuvent ensuite compléter ce contexte. Aucun filtre Maintenance n’est transféré.

Une erreur parent laisse les 18 champs et les références déjà résolues affichés, avec une erreur distincte. Les parents suivants restent non résolus. Un contexte de retour différent déclenche une information, sans remplacer les références réelles. Les identifiants invalides sont bloqués sans HTTP. Les 404 dossier, erreurs réseau et réponses invalides ont des états distincts, sans fausse fiche vide. Relance manuelle uniquement pour réseau/5xx ; les relances de références ne rechargent pas le dossier. `switchMap` annule les lectures du dossier et de ses parents devenues obsolètes.

## Navigation et styles

Les liens liste -> détail -> liste préservent exclusivement les clés appliquées : `company_id`, `site_id`, `equipment_id`, `maintenance_type`, `status`, `priority`, `search`, `start_time`, `end_time`, `page`, `page_size`. Les valeurs répétées, fractions, offsets et fragments restent conservés ; les brouillons de formulaire ne sont pas transmis. Aucun `returnUrl` ou autre destination externe n’est utilisé.

Réutilisation de `PageHeader`, `LoadingState`, `ErrorState`, du mixin `navigation-action` et de `_buttons.scss` pour l’action secondaire de retour, les transitions, le focus et la préférence de mouvement réduit. Le lien Equipment possède aussi un focus visible et une hauteur minimale de 44 px. Aucun changement dans les modules Measurements, Sensors ou Equipment. Le focus des liens de titre rejoint le sélecteur existant de Maintenance List, sans contournement du budget SCSS.

## Fichiers cumulés UI 8.4 et UI 8.4.1 : 12

| Fichier | Changement |
| --- | --- |
| [maintenance.routes.ts](../frontend/src/app/features/maintenance/maintenance.routes.ts) | Route détail lazy, liste conservée |
| [maintenance.routes.spec.ts](../frontend/src/app/features/maintenance/maintenance.routes.spec.ts) | Shell, titre, navigation active, routes hors périmètre |
| [maintenance-list.component.ts](../frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.ts) | RouterLink et extraction du contexte autorisé |
| [maintenance-list.component.html](../frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.html) | Titre cliquable, libellé accessible, six colonnes sans ID |
| [maintenance-list.component.scss](../frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.scss) | Focus clavier des titres et largeur adaptée à la suppression de la colonne ID |
| [maintenance-list.component.spec.ts](../frontend/src/app/features/maintenance/pages/maintenance-list/maintenance-list.component.spec.ts) | Titre accessible, six colonnes, aller-retour, filtres, brouillon et pagination |
| [maintenance-detail.component.ts](../frontend/src/app/features/maintenance/pages/maintenance-detail/maintenance-detail.component.ts) | Nouveau composant et état de lecture/références |
| [maintenance-detail.component.html](../frontend/src/app/features/maintenance/pages/maintenance-detail/maintenance-detail.component.html) | Titre renforcé, badges, six sections regroupées, 18 champs et références |
| [maintenance-detail.component.scss](../frontend/src/app/features/maintenance/pages/maintenance-detail/maintenance-detail.component.scss) | Tokens, action partagée, grilles et repli mobile |
| [maintenance-detail.component.spec.ts](../frontend/src/app/features/maintenance/pages/maintenance-detail/maintenance-detail.component.spec.ts) | Contrats, présentation, erreurs, références et annulation |
| [_buttons.scss](../frontend/src/styles/_buttons.scss) | Ajout de `.maintenance-back` aux sélecteurs partagés, y compris mouvement réduit |
| [ui-8.4-maintenance-detail.md](ui-8.4-maintenance-detail.md) | Présent rapport |

## Finitions UI 8.4.1

- Retour : conventions déjà conformes en UI 8.4, conservées sans style parallèle. `navigation-action` et `_buttons.scss` assurent le bouton secondaire, son focus, ses transitions et le repli. Le libellé reste « Retour à la liste des interventions ». La destination `/maintenance` est explicite, y compris en accès direct, sans dépendre de `history.back()` ni d’une URL externe.
- Liste : le titre est l’unique lien de détail de chaque ligne, avec un libellé accessible « Consulter l’intervention : … ». Les six colonnes sont Titre, Type, Statut, Priorité, Date planifiée, Date de création. ID et Actions ne sont pas des colonnes visibles.
- Titre réel du dossier : titre de niveau 2 renforcé, sur la largeur de sa section, sans dupliquer le champ.
- Statut et priorité : mêmes classes et règles de badges textuels que la liste, mêmes couleurs, fond, bordures et padding ; la ligne de texte hérite du contexte de chaque présentation.
- Compacité : six sections au lieu de sept. Technicien, création et dernière modification sont regroupés sous Informations de suivi. Espacements entre sections et champs réduits de 24 à 16 px. Les dates peuvent partager la grille desktop ; le repli mobile reste sur une colonne. Diagnostic, dates, coût/indisponibilité et références gardent leurs sections distinctes. Tous les textes explicatifs et ISO sources restent visibles.

Aucun changement de contrat GET, de filtre, de modèle ou de logique de rattachement n’est nécessaire à cette finition.

## Validation finale réellement exécutée

Après stabilisation de UI 8.4.1, le 23 octobre 2026 :

| Contrôle | Résultat consolidé |
| --- | --- |
| Tests ciblés Maintenance + routes application + sidebar | **419 réussis, 7 fichiers** |
| Suite Angular complète, une seule exécution pour cette finition | **1 870 réussis, 71 fichiers** |
| Build production, une seule exécution pour cette finition | **Réussi** |
| `git diff --check`, espaces des nouveaux fichiers et liens locaux | **Réussis** |

Commandes depuis `frontend` :

```text
npx ng test --watch=false --include='src/app/features/maintenance/**/*.spec.ts' --include='src/app/app.routes.spec.ts' --include='src/app/layout/sidebar/sidebar.component.spec.ts' --runner-config=tmp/ui-8.4.1/vitest.config.mjs
npx ng test --watch=false --runner-config=tmp/ui-8.4.1/vitest.config.mjs
npx ng build --configuration production
```

Configuration temporaire Vitest à deux workers, sans changement suivi de configuration ou package. Preuves locales ignorées : [tests ciblés](../frontend/tmp/ui-8.4.1/targeted-tests.log), [suite complète](../frontend/tmp/ui-8.4.1/full-tests.log), [build](../frontend/tmp/ui-8.4.1/build.log).

Couverture cumulée : lazy route et Shell ; IDs invalides sans HTTP ; 404/réseau/401/403/422/5xx ; contrat invalide et champ manquant ; 18 champs et enums ; null/chaîne vide/zéro ; coût non fini et minutes invalides ; dates avec offset/microsecondes et dates administratives naïves ; références absentes, incohérentes ou inaccessibles ; conservation du dossier ; relances manuelles et annulation des réponses obsolètes ; lien Equipment uniquement après résolution ; whitelist de retour, paramètres répétés et fragment ; titre accessible sans colonne ID/Actions ; badges ; technicien regroupé avec les dates de suivi ; accès direct et retour sans historique ; liste -> détail -> retour avec brouillon non appliqué ; absence de requête autre que GET.

### Références historiques UI 8.4

La première validation UI 8.4, avant cette finition, a produit **416 tests ciblés**, **1 867 tests complets**, un build réussi, un initial de **605,86 kB** et un détail de **16,20 kB**. Ce sont des résultats historiques distincts, remplacés comme référence finale par ceux ci-dessus. Les journaux de cette première phase restent dans `frontend/tmp/ui-8.4`.

### Bundles et budgets

| Mesure brute | HEAD de départ | UI 8.4 initiale | UI 8.4 + UI 8.4.1 final |
| --- | ---: | ---: | ---: |
| Bundle initial | 605 752 octets | 605 860 octets | **605 860 octets (605,86 kB)** |
| Chunk Maintenance List | 47 213 octets | 43 989 octets | **43 974 octets (43,97 kB)** |
| Chunk Maintenance Detail | absent | 16 196 octets | **16 404 octets (16,40 kB)** |
| Ensemble JS/CSS produit | 1 085 916 octets | 1 103 026 octets | **1 103 219 octets** |

UI 8.4.1 ne change pas l’initial : +208 octets dans le détail, -15 dans la liste, soit +193 octets JS/CSS par rapport à UI 8.4. Le cumul depuis HEAD est de +108 octets d’initial et +17 303 octets JS/CSS. La répartition des chunks partagés évolue aussi : le poids du seul chunk liste ne représente pas le total chargé.

CSS local compilé/minifié avec Sass/esbuild, saut de ligne inclus : détail **1 767 octets** contre 1 558 en UI 8.4 ; liste **3 952 octets** contre 3 961. Mesures hors saut de ligne : 1 766 et 3 951 octets. Ces mesures sont distinctes du style encapsulé embarqué dans les chunks. Les badges ne sont pas déplacés artificiellement vers une feuille globale.

Budgets inchangés : initial avertissement 500 kB/erreur 1 MB ; composant avertissement 4 kB/erreur 8 kB. Aucun nouvel avertissement SCSS. Seul l’avertissement initial existant reste présent : dépassement de 105,86 kB. Les styles partagés ne changent plus entre UI 8.4 et UI 8.4.1 ; l’ajout `.maintenance-back` reste celui nécessaire à UI 8.4.

## Revue navigateur et responsive consolidée

Build production servi sur `127.0.0.1:8098` avec fixtures synthétiques et GET uniquement, sans proxy FastAPI, DEV ou PostgreSQL. Aucune donnée métier réelle n’est consultée ni écrite. Les fixtures, captures et traces restent dans `frontend/tmp/ui-8.4.1`, ignoré par Git. Cette revue ne constitue pas une validation intégrée DEV.

Les deux pages sont contrôlées aux six cibles :

| Cible CSS | Obtenu | Document : largeur utile / scrollWidth | Détail |
| --- | ---: | ---: | --- |
| 1440 | 1440 | 1420 / 1420 | Navigation ouverte, titre renforcé et grilles à deux colonnes |
| 1024 | 1024 | 1004 / 1004 | Navigation ouverte, bouton et badges contenus |
| 1023 | 1023 | 1003 / 1003 | Navigation repliée |
| 768 | 768 | 748 / 748 | Grilles à deux colonnes, retour dans l’en-tête |
| 390 | 389 et 391 | 369 / 369 et 371 / 371 | Une colonne ; réserve sur la cible exacte |
| 320 | 320 | 300 / 300 | Une colonne, titre multiligne et bouton retour de 44 px |

Les 18 champs et six sections sont présents à toutes ces largeurs. Le bouton retour mesure 44 px de hauteur, avec padding 8/16 px, arrondi 8 px, bordure, police 600 et focus bleu visibles. Les conteneurs Shell, liens, dates et codes ne débordent pas globalement. Le tableau reste un défilement local sur petits écrans : 960 px dans 250 px à 320, document 300/300. Il comporte toujours six colonnes, sans ID ni Actions.

Mesures : [détail](../frontend/tmp/ui-8.4.1/responsive-detail.json) et [liste](../frontend/tmp/ui-8.4.1/responsive-list.json). Captures détail enregistrées et examinées : [1440](../frontend/tmp/ui-8.4.1/screenshots/maintenance-detail-1440.png), [1024](../frontend/tmp/ui-8.4.1/screenshots/maintenance-detail-1024.png), [1023](../frontend/tmp/ui-8.4.1/screenshots/maintenance-detail-1023.png), [768](../frontend/tmp/ui-8.4.1/screenshots/maintenance-detail-768.png), [389](../frontend/tmp/ui-8.4.1/screenshots/maintenance-detail-389.png), [391](../frontend/tmp/ui-8.4.1/screenshots/maintenance-detail-391.png), [320](../frontend/tmp/ui-8.4.1/screenshots/maintenance-detail-320.png). Autres vues : [suivi et références regroupés](../frontend/tmp/ui-8.4.1/screenshots/maintenance-detail-1440-tracking.png), [titre de liste et focus desktop](../frontend/tmp/ui-8.4.1/screenshots/maintenance-list-1440-title-focus.png), [titre et focus mobile](../frontend/tmp/ui-8.4.1/screenshots/maintenance-list-320-title-focus.png), [focus du retour mobile](../frontend/tmp/ui-8.4.1/screenshots/maintenance-detail-320-back-focus.png).

La cible exacte 390 reste non atteinte du fait de l’arrondi du navigateur. Les captures incluent ses marges et parfois ses barres propres ; les mesures du DOM applicatif servent à distinguer ces éléments d’un débordement de page.

Parcours navigateur réellement exécuté sur fixtures : accès par titre avec Entrée -> intervention 976 -> retour avec Entrée. Les trois résultats, la page 2/taille 1, le type préventif, le statut planifié, la priorité basse, la recherche « Intervention », le début `2026-10-23T14:00:00.000001+02:00`, la fin `2026-10-24T00:00:00.999999Z` et le fragment `history` sont préservés. Tab/Maj+Tab donnent un focus visible aux liens de titre, retour et Equipment. L’ouverture directe de la fiche 1000 fournit une destination retour `/maintenance` sans historique ni contexte imposé.

Preuves : [navigation](../frontend/tmp/ui-8.4.1/navigation.json) et [journal GET brut synthétique](../frontend/tmp/ui-8.4.1/http-preview.json). Le détail GET reçoit uniquement son identifiant de chemin, et les GET liste uniquement equipment_id et les filtres/pagination autorisés. Les 404, erreurs réseau et références invalides sont couvertes par les tests Angular actuels. Les vérifications navigateur d’erreur parent et de 404 de la première UI 8.4 restent des preuves historiques, sans être revendiquées comme nouvellement rejouées dans cette finition.

## Réserves conservées et état Git

- B-MAIN-01 à B-MAIN-09 restent ouverts : chronologie et validations Pydantic/SQL, nombres non finis/précision, workflow, intégrité/concurrence, dates administratives, sécurité tenant, volumes et politique monétaire/audit.
- Les dates administratives naïves n’autorisent aucune garantie UTC. Les nombres restent les nombres JSON reçus ; aucune précision décimale comptable ou devise n’est garantie.
- Aucun accès PostgreSQL ni validation HTTP FastAPI réelle dans cette étape. Le seed strict et les autres réserves historiques ne sont ni corrigés ni requalifiés comme réussis.
- Authentification et isolation multi-tenant absentes : le contrôle frontend des références ne remplace pas une autorisation backend.
- Les tests HTTP Angular sont simulés ; les GET navigateur utilisent uniquement le serveur de fixtures. La recette DEV appartient à une étape ultérieure autorisée.
- Le dialogue natif d’abandon n’est pas revalidé pour les formulaires historiques ; aucun formulaire ni écriture n’est ajouté ici.
- UI 8.5 non commencée. Les écritures et transitions restent hors MVP, y compris MAIN-08/MAIN-09.

Seuls les 12 fichiers listés sont concernés : sept fichiers existants modifiés, quatre fichiers détail nouveaux et ce rapport nouveau. Les modifications non commitées de UI 8.4 sont conservées et complétées ; UI 8.4.1 ajoute uniquement Maintenance List SCSS au périmètre cumulé. Modèles/API, backend, SQL, Docker, packages et budgets inchangés. Index vide, HEAD `161bf88` inchangé. Aucun commit, push, merge ou rebase. Captures, serveur synthétique et journaux restent ignorés. En attente de validation avant commit.
