# UI 5.4 - Détail Équipement industriel

## Périmètre livré

19 octobre 2026. Branche `feature/frontend-equipments`, HEAD initial et final
`c8af42381935aca5735c0ceb7f36046ba3238fc2`. Dépôt propre avant intervention.
Référence : [conception UI 5.1, décisions EQ-01 à EQ-07](etape-ui-5.1-equipments.md).

- Fiche lazy-loaded `/equipments/:equipmentId`, en lecture seule. Ancienne route
  placeholder parallèle retirée du routing racine ; liste, Shell, Sidebar et 404
  conservés. Futures routes `new` et `:equipmentId/edit` à placer avant le détail.
  En attendant leur implémentation, ces destinations restent sur la 404 globale.
- GET Equipment via `EquipmentsApiService`, puis site réel par equipment.site_id,
  puis entreprise réelle par site.company_id. Aucune référence déduite du contexte
  de retour. Identifiants positifs sûrs et identités retournées vérifiés.
- Nom, code métier, type libre, statut/criticité en français, description,
  site et entreprise réels, création et dernière modification. Aucun identifiant
  technique affiché. Description absente : « Non renseignée ».
- Libellés métier et dates administratives partagés réutilisés. Statut et
  criticité partagent désormais leurs libellés entre liste et détail. Date sans
  fuseau : heure fournie conservée ; date avec fuseau : affichage UTC ; date
  absente ou invalide : « Non disponible ». Valeurs transport inchangées.
- Retour liste préservant company_id, site_id, status, criticality, search, page
  et page_size valides. Aucun parent implicite ajouté sur un accès direct.
  Contexte différent : notice, rattachement réel affiché et retour conservé.
- Lien vers le site réel avec contexte Sites distinct, sans reprendre les filtres
  Equipment. EQ-07 : lien « Voir les équipements » ajouté au détail Site, basé sur
  son site et son entreprise réels, indépendamment de son contexte de retour.
- Identifiant invalide sans HTTP ; 404 Equipment explicite ; réseau/5xx avec
  relance manuelle. Erreurs Site et Company distinctes : données Equipment
  conservées, et données Site conservées si seule Company échoue. Relance d'un
  parent sans recharger Equipment. Lectures obsolètes annulées à chaque changement
  d'identifiant et à la destruction du composant.
- Aucun formulaire, bouton Modifier, DELETE, transfert, descendant, compteur,
  Health Score, RUL ou appel prédictif ajouté. UI 5.5 non commencée.

## Fichiers concernés

Ajoutés :

- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.html`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.scss`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.spec.ts`
- `frontend/src/app/features/equipments/models/equipment-labels.ts`
- Ce rapport.

Modifiés :

- `frontend/src/app/app.routes.ts`
- `frontend/src/app/app.routes.spec.ts`
- `frontend/src/app/features/equipments/equipments.routes.ts`
- `frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.ts`
- `frontend/src/app/features/sites/pages/site-detail/site-detail.component.html`
- `frontend/src/app/features/sites/pages/site-detail/site-detail.component.spec.ts`
- `frontend/src/app/features/dashboard/testing/dashboard-testing.ts`

Le dernier fichier est un helper de tests de routing : simulation d'un GET
Equipment absent pour les suites Shell/Sidebar/404. Aucun changement fonctionnel
Dashboard, Companies, transport core, backend, configuration, package ou migration.

## Tests et build

- Tests ciblés : **206 réussis / 7 fichiers**, dont **54 nouveaux tests** du détail.
  Contrats HTTP, erreurs indépendantes, relances, identifiants invalides,
  incohérences de réponse, annulations Equipment/Site/Company, destruction,
  retour liste réel, contexte différent, dates avec/sans fuseau et invalides,
  texte échappé et absence de descendants/écritures/ML couverts.
- Quatre nouveaux tests de routing : fiche unique différée et réservation des
  destinations futures/inconnues. Assertion EQ-07 ajoutée aux tests Site.
- Une suite Angular complète finale : **746 réussis / 46 fichiers**, contre
  688 / 45 en UI 5.3.1. Non-régressions liste Equipment, Companies, Sites,
  Dashboard, transport, Shell, Header, Sidebar et 404 réussies.
- Un build production final : **réussi**, exécuté après la suite complète.
  Aucun fichier exécutable modifié depuis ces validations.
- Vitest maxWorkers=2 dans un fichier temporaire ignoré ; aucun timeout augmenté,
  test désactivé ou budget modifié.

Commandes depuis `frontend` :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-5.4/vitest.config.mjs --include=src/app/features/equipments/**/*.spec.ts --include=src/app/features/sites/pages/site-detail/site-detail.component.spec.ts --include=src/app/app.routes.spec.ts --include=src/app/layout/sidebar/sidebar.component.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-5.4/vitest.config.mjs
npm.cmd run build -- --configuration production --output-path=tmp/ui-5.4/production
```

| Bundle | UI 5.3.1 | UI 5.4 | Écart |
| --- | --- | --- | --- |
| Initial | 601 895 octets | 601 859 octets | -36 octets |
| Liste différée | 25 160 octets | 24 057 octets | -1 103 octets |
| Détail différé | Absent | 10 920 octets | Nouveau |
| Routes Equipment différées | 258 octets | 517 octets | +259 octets |
| Total JS/CSS émis | 811 838 octets / 33 fichiers | 823 476 octets / 35 fichiers | +11 638 octets |

Le CLI affiche **601,86 ko** initiaux, pour le budget warning de 500 ko :
avertissement connu de +101,86 ko, sous le budget d'erreur de 1 Mo.
Détail : `chunk-HKDPOVSC.js` ; liste : `chunk-QPCJE7U6.js` ; routes :
`chunk-7GM3V2LU.js`. Le code métier de détail reste différé.

## Navigateur, accessibilité et captures

Build production servi sur localhost:8098, API entièrement synthétique, sans
upstream backend. Seuls GET Companies/Sites/Equipments sont simulés ; aucune
méthode d'écriture autorisée. Dates naïves et avec offset, description multiligne,
parents réels différents du contexte de retour dans les captures.

Parcours vérifiés : détail avec contexte différent, retour aux sept paramètres
de liste, site réel, lien EQ-07 vers sa liste puis détail depuis cette liste.
Focus clavier visible sur le lien Site. Un seul h1, informations en dl/dt/dd,
libellés accessibles et liens natifs. Console sans erreur ni alerte observée.
Journal synthétique : **21 GET, 0 écriture, 0 appel ML/descendant,
0 GET liste Equipment sans site ou avec company_id**.

| Viewport CSS | Largeur document | Largeur fiche / contenu | Navigation |
| --- | --- | --- | --- |
| 1440 x 1000 | 1440 | 1119 / 1119 | Sidebar desktop |
| 1024 x 900 | 1024 | 703 / 703 | Sidebar desktop |
| 1023 x 900 | 1023 | 958 / 958 | Menu mobile |
| 768 x 1024 | 768 | 719 / 719 | Menu mobile |
| 390 x 844 | 375 | 341 / 341 | Menu mobile |
| 320 x 720 | 305 | 271 / 271 | Menu mobile |

Aucun débordement horizontal global. Sur mobile, barre verticale de 15 px,
fiche sur une colonne, bouton Retour et textes repliés dans la largeur disponible.
Serveur arrêté, viewport restauré et onglet temporaire fermé après vérification.

Preuves locales ignorées par Git, sans données réelles :

- [Tests ciblés](../frontend/tmp/ui-5.4/targeted.log), [suite complète](../frontend/tmp/ui-5.4/full-tests.log), [build](../frontend/tmp/ui-5.4/build.log)
- [Mesures responsive](../frontend/tmp/ui-5.4/responsive.json), [journal HTTP synthétique](../frontend/tmp/ui-5.4/browser-http-audit.json)
- [Desktop 1440](../frontend/tmp/ui-5.4/screenshots/equipment-detail-1440.jpg)
- [1024](../frontend/tmp/ui-5.4/screenshots/equipment-detail-1024.jpg), [1023](../frontend/tmp/ui-5.4/screenshots/equipment-detail-1023.jpg), [768](../frontend/tmp/ui-5.4/screenshots/equipment-detail-768.jpg)
- [Mobile 390](../frontend/tmp/ui-5.4/screenshots/equipment-detail-390.jpg), [mobile 320](../frontend/tmp/ui-5.4/screenshots/equipment-detail-320.jpg)
- [Mobile, parents et focus](../frontend/tmp/ui-5.4/screenshots/equipment-detail-320-parents.jpg)

## Limites et état Git

Validation HTTP et navigateur simulée ; aucune validation PostgreSQL Equipment
réelle revendiquée. Validation intégrée prévue en UI 5.7. Le fallback d'enum
inattendu ne corrige pas une éventuelle erreur de validation de réponse backend.
Les dates sans fuseau ne permettent pas de déduire un instant UTC. Pas d'audit
exhaustif de lecteur d'écran ; sémantique et clavier vérifiés. Les vérifications
de références UI ne constituent pas une autorisation multi-tenant.

13 fichiers concernés : 7 modifiés et 6 nouveaux, rapport inclus. Index vide,
branche et HEAD inchangés. `git diff --check` et contrôle des nouveaux fichiers
réussis ; liens du rapport vérifiés et empreintes des exécutables inchangées
depuis la validation. Aucun secret, dump ou artefact temporaire dans ce périmètre.
Aucun backend, PostgreSQL, Docker, package, commit, push ou merge.

**Attendre validation avant le commit UI 5.4 et avant UI 5.5.**

## Complément UI 5.4.1 - Libellés métier

Les preuves UI 5.4 ci-dessus sont conservées. La version finale harmonisée remplace
uniquement les intitulés de la fiche : « Site industriel réel » devient
« Site industriel » et « Entreprise réelle » devient « Entreprise de rattachement ».
L'assertion sémantique du test est adaptée ; les noms métier des fixtures restent
inchangés. Aucun autre texte de chargement, erreur ou contexte n'est modifié.

Comparaison SHA-256 avec le début de UI 5.4.1 : seuls le template détail, son
test et ce complément documentaire changent. Résolution Equipment -> Site ->
Company, contrats API, champs métier, routes, dates et styles strictement conservés.
Le rattachement reste indépendant du contexte de navigation.

Validation finale après ces modifications, exécutée séquentiellement :

1. **206 tests ciblés réussis / 7 fichiers**, dont les 54 scénarios du détail.
2. Une seule suite Angular complète : **746 tests réussis / 46 fichiers**.
3. Un seul build production : **réussi**, avertissement de budget connu conservé.

Les commandes UI 5.4 sont reprises avec les chemins `tmp/ui-5.4.1`. Vitest reste
limité à deux workers ; aucun test désactivé, timeout augmenté ou package ajouté.
Aucun fichier exécutable modifié après cette validation finale.

| Mesure | UI 5.4 | UI 5.4.1 |
| --- | --- | --- |
| Initial | 601 859 octets | 601 859 octets, inchangé |
| Détail différé | 10 920 octets | 10 918 octets, -2 octets |
| Total JS/CSS | 823 476 octets / 35 fichiers | 823 474 octets / 35 fichiers |

Chunk détail final : `chunk-F64K3N25.js`. Initial affiché : **601,86 ko** ;
le budget warning de 500 ko et le budget d'erreur de 1 Mo restent inchangés.

Nouveau contrôle navigateur sur le build final, API synthétique GET uniquement :
les six largeurs 1440/1024/1023/768/390/320 px ont les mêmes dimensions de document
et de fiche que UI 5.4. Un seul h1 et aucun débordement horizontal global.
Les deux libellés sont corrects ; parents réels, notice de contexte divergent,
lien Site, sept paramètres de retour et dates affichées identiques à UI 5.4.
Console sans erreur ni alerte ; journal : **3 GET Equipment/Site/Company,
aucune écriture ni appel ML**. Aucun accès FastAPI/PostgreSQL réel.
Serveur arrêté, viewport restauré et onglet fermé après vérification.

Preuves finales locales ignorées par Git :

- [Tests ciblés](../frontend/tmp/ui-5.4.1/targeted.log), [suite complète](../frontend/tmp/ui-5.4.1/full-tests.log), [build](../frontend/tmp/ui-5.4.1/build.log)
- [Mesures responsive](../frontend/tmp/ui-5.4.1/responsive.json), [journal HTTP synthétique](../frontend/tmp/ui-5.4.1/browser-http-audit.json)
- [Desktop harmonisé](../frontend/tmp/ui-5.4.1/screenshots/equipment-detail-1440.jpg)
- [Mobile harmonisé](../frontend/tmp/ui-5.4.1/screenshots/equipment-detail-390.jpg)

Bilan combiné : mêmes 13 fichiers UI 5.4 en attente, dont trois ajustés par
UI 5.4.1. Branche `feature/frontend-equipments`, HEAD `c8af423` inchangés ; index
vide. Contrôles de diff, liens documentaires et empreintes finales réussis.
Aucun commit, push, merge, changement backend ou PostgreSQL. UI 5.5 non commencée.
**Attendre validation finale avant le commit UI 5.4.**
