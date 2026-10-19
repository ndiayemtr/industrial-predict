# UI 5.3 - Liste et filtres Equipements

## Perimetre et etat de depart

19 octobre 2026. Branche `feature/frontend-equipments`, HEAD conserve :
`ff3fed32545a9713a8793e927df91b490dc8310a`. Depot initialement propre.
Conception : [UI 5.1 et arbitrages EQ-01 a EQ-07](etape-ui-5.1-equipments.md).
Le transport UI 5.2 est reutilise sans modification.

- Feature lazy-loaded sur `/equipments`, avec titre, Shell, Sidebar et 404 preserves.
- `/equipments/:equipmentId` conserve son placeholder existant. Aucun detail,
  formulaire, bouton de creation, DELETE, transfert, descendant ou calcul ML ajoute.
- Selection explicite entreprise puis site, sans selection par defaut. Catalogues
  serveur par pages de 50, chargement supplementaire et deduplication. Lectures
  ciblees pour les references d'URL hors premiere page. Un lien avec seulement
  site_id retrouve son entreprise reelle puis complete l'URL.
- Verification entreprise puis site et appartenance avant chaque GET Equipment.
  Une paire incoherente ou une reference indisponible bloque la liste. Un retour
  contenant des equipements d'un autre site est egalement refuse.
- Changement d'entreprise : annulation, retrait des resultats, site et recherche
  effaces, page 1 ; statut et criticite conserves. Changement de site : page 1,
  recherche deja appliquee conservee, brouillon jamais applique implicitement.
- Recherche explicite par nom/code/type, bouton ou Entree ; statut et criticite
  avec libelles francais ; pagination serveur, tailles 20/50/100 et taille d'URL
  valide 1..100. Aucun tri local ni filtre API company_id.
- URL : company_id, site_id, search, status, criticality, page, page_size ;
  normalisation des entrees invalides avec notice, preservation des parametres
  tiers et du fragment. Les liens de detail portent le contexte applique.
- Etats selection attendue, chargement, vide, aucun resultat, erreur avec relance
  manuelle pour reseau/5xx, page hors plage avec retour explicite aux resultats.

## Fichiers concernes

Modifies :

- `frontend/src/app/app.routes.ts`
- `frontend/src/app/app.routes.spec.ts`
- `frontend/src/app/layout/sidebar/sidebar.component.spec.ts`

Ajoutes :

- `frontend/src/app/features/equipments/equipments.routes.ts`
- `frontend/src/app/features/equipments/equipments-list.facade.ts`
- `frontend/src/app/features/equipments/equipments-list.facade.spec.ts`
- `frontend/src/app/features/equipments/models/equipments-state.model.ts`
- `frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.ts`
- `frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.html`
- `frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.scss`
- `frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.spec.ts`
- Ce rapport.

Aucun changement du code Companies, Sites, Dashboard, transport core, backend,
Docker, migrations, packages ou fichiers de configuration sensibles.

## Validation Angular et bundle

- Tests cibles : **117 reussis, 5 fichiers** (Equipment, routing et Sidebar).
- Une validation complete finale : **681 reussis, 45 fichiers**, contre
  637 / 43 en UI 5.2. Les 44 nouveaux tests couvrent references explicites et
  paginees, contexte hors page, URLs invalides et retour, filtres exacts,
  brouillon de recherche, annulations, erreurs, vide et page hors plage.
- Suites Companies, Sites, Dashboard, transport partage, Shell et 404 reussies.
  Les URLs existantes de detail Equipment restent couvertes par les tests root.
- Un build production final : reussi. Aucun fichier executable modifie depuis.
- Initial : **601 606 octets (601,61 ko)**, contre 601 509 en UI 5.2, soit **+97 octets**.
  Avertissement existant du budget initial de 500 ko : depassement de 101,61 ko.
  Budget d'erreur de 1 Mo non atteint ; aucun budget modifie.
- Chunks differes : liste `chunk-TTYL4FXT.js`, **24 630 octets** ; routes
  `chunk-KKUHEBZ5.js`, **258 octets**. Total JS/CSS emis : 33 fichiers,
  811 019 octets, contre 31 / 786 034, soit +24 985 octets.

Commandes depuis `frontend` :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-5.3/vitest.config.mjs --include=src/app/features/equipments/**/*.spec.ts --include=src/app/app.routes.spec.ts --include=src/app/layout/sidebar/sidebar.component.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-5.3/vitest.config.mjs
npm.cmd run build -- --configuration production --output-path=tmp/ui-5.3/production
```

Configuration temporaire Vitest : maxWorkers=2, aucun timeout ou test desactive.
Preuves locales ignorees par Git : [tests cibles](../frontend/tmp/ui-5.3/targeted.log),
[suite complete](../frontend/tmp/ui-5.3/full-tests.log),
[build](../frontend/tmp/ui-5.3/build.log).

## Navigateur isole et captures

Build production servi sur le port local 8098 avec donnees entierement synthetiques,
aucun proxy backend et refus de toute methode autre que GET. Entreprises et sites
sur deux pages de references ; quatre equipements de demonstration et un site
avec 45 equipements pour la pagination. Ce controle ne constitue pas une nouvelle
validation FastAPI/PostgreSQL reelle.

Parcours verifies : selection manuelle des parents, site de deuxieme page,
pagination page 1 puis 2, recherche par Entree, filtres combines et aucun resultat,
changement d'entreprise avec retrait du site/recherche/resultats. Journal du
serveur : **34 GET, 0 ecriture, 0 GET Equipment sans site ou avec company_id**.
Console du contexte final : aucune erreur ni alerte observee.

Dimensions CSS reelles controlees, avec captures et mesures DOM :

| Viewport | Largeur document | Tableau visible / contenu | Navigation |
| --- | --- | --- | --- |
| 1440 x 1000 | 1425 | 1071 / 1071 | Sidebar desktop |
| 1024 x 900 | 1009 | 655 / 655 | Sidebar desktop |
| 1023 x 900 | 1008 | 911 / 911 | Menu mobile |
| 768 x 1024 | 753 | 671 / 671 | Menu mobile |
| 390 x 844 | 375 | 325 / 608 | Menu mobile |
| 320 x 720 | 305 | 255 / 608 | Menu mobile |

L'ecart de 15 px correspond a la barre verticale du navigateur. Aucun debordement
horizontal global. Sur mobile, tableau defilant dans sa region accessible, champs
sur une colonne et pagination repliee. Libelles explicites, controles natifs,
liens detail au clavier et focus visible. Fleche droite verifiee sur la region
du tableau a 320 px : defilement local et contour de focus presents.

Captures locales (JPEG, donnees synthetiques, non versionnees) :

- [Desktop 1440](../frontend/tmp/ui-5.3/screenshots/equipments-1440.jpg)
- [Desktop, tableau et focus](../frontend/tmp/ui-5.3/screenshots/equipments-1440-results.jpg)
- [1024](../frontend/tmp/ui-5.3/screenshots/equipments-1024.jpg)
- [1023](../frontend/tmp/ui-5.3/screenshots/equipments-1023.jpg)
- [768](../frontend/tmp/ui-5.3/screenshots/equipments-768.jpg)
- [Mobile 390](../frontend/tmp/ui-5.3/screenshots/equipments-390.jpg)
- [Mobile 390, resultats](../frontend/tmp/ui-5.3/screenshots/equipments-390-results.jpg)
- [Mobile 320](../frontend/tmp/ui-5.3/screenshots/equipments-320.jpg)
- [Mobile 320, tableau et focus](../frontend/tmp/ui-5.3/screenshots/equipments-320-results.jpg)
- [Mesures responsive](../frontend/tmp/ui-5.3/responsive.json)
- [Journal HTTP synthetique](../frontend/tmp/ui-5.3/browser-http-audit.json)

## Limites et etat Git final

- Validation navigateur sur API simulee ; aucune ecriture ni operation PostgreSQL.
  La validation integree reelle Equipment reste prevue en UI 5.7.
- Fiche detail encore en preparation ; UI 5.4 non commencee. Aucun lien de Site
  ajoute a cette etape, conformement au decoupage UI 5.1.
- Pas de preuve de lecteur d'ecran ou d'audit exhaustif d'accessibilite ; controles
  semantiques automatises et clavier navigateur effectues.
- Verifier les parents dans l'UI ne remplace pas une autorisation multi-tenant.
  Authentification/autorisation et secrets historiques restent les dettes connues,
  sans modification ni nouvelle exposition dans cette etape.
- `git diff --check` et controle des nouveaux fichiers : reussis. Index vide,
  3 fichiers suivis modifies et 9 nouveaux fichiers, dont ce rapport ; aucun
  secret, dump, package, capture ou fichier temporaire dans ces 12 fichiers.
- Branche et HEAD inchanges ; aucun commit, push, merge, rebase ou suppression.
  Serveur de previsualisation arrete, viewports restaures et onglets temporaires fermes.

**Attendre validation avant le commit UI 5.3 et avant UI 5.4.**

## Complement UI 5.3.1 - Finitions UX

Les resultats UI 5.3 ci-dessus sont conserves comme preuves historiques.
Les resultats de reference apres finitions sont ceux de cette section.

Seuls le template `equipments-list.component.html`, son fichier de tests
`equipments-list.component.spec.ts` et ce complement documentaire ont change
depuis la validation UI 5.3. Comparaison SHA-256 effectuee avec l'etat initial
de UI 5.3.1. Aucun changement de facade, verification des parents, transport,
styles, routing ou valeurs equipment_type.

- Aide entreprise masquee apres verification de l'entreprise selectionnee ;
  aide site masquee apres verification du site et de son appartenance. Les aides
  restent presentes si une selection manque, est indisponible ou incoherente.
- Attribut aria-describedby retire avec chaque aide masquee, sans reference
  accessible vers un element absent. Les aides reviennent apres deselection.
- Compteurs harmonises : `0 equipement`, `1 equipement`, `2 equipements` (avec
  accents dans l'interface), dans les resultats et la pagination. Le resultat
  vide comporte maintenant son compteur explicite. Convention conditionnelle
  des templates Sites/Companies reutilisee, avec singulier pour zero et un.
- Sept tests ajoutes, assertions existantes completees : parents valides,
  manquants, 404 et incoherents ; compteurs 0/1/2/21 ; filtres et URL inchanges.

Validation executee sequentiellement, sans modification executable ensuite :

1. Tests cibles Equipment, routing et Sidebar : **124 reussis / 5 fichiers**.
2. Tests Angular complets : **688 reussis / 45 fichiers**. Suites Companies,
   Sites, Dashboard, transport et Shell toujours reussies.
3. Build production : **reussi**, avertissement initial de 500 ko conserve.

Commandes identiques a UI 5.3 avec les chemins `tmp/ui-5.3.1` pour le runner
Vitest (maxWorkers=2), les journaux et la sortie de production.

| Mesure | UI 5.3 | UI 5.3.1 | Ecart |
| --- | --- | --- | --- |
| Bundle initial | 601 606 octets | 601 895 octets | +289 octets |
| Chunk liste differe | 24 630 octets | 25 160 octets | +530 octets |
| Total JS/CSS emis | 811 019 octets / 33 fichiers | 811 838 octets / 33 fichiers | +819 octets |

Le CLI affiche 601,89 ko pour l'initial et 25,16 ko pour la liste differee
`chunk-2UULKMSX.js`. Aucun budget ou package modifie.

Controle navigateur du nouveau build sur le serveur synthetique GET uniquement :
1440, 1024, 1023, 768, 390 et 320 px CSS, aux memes hauteurs que UI 5.3.
Largeurs du document et du tableau identiques aux mesures precedentes : aucun
debordement horizontal global, defilement local du tableau sur mobile. Sur les
six dimensions, aides masquees, compteur `1 equipement` et filtres/contexte URL
conserves. Verification supplementaire de `0 equipement`, `2 equipements`, puis
du retour des aides lors des deselections. Console sans erreur ni alerte.
Journal synthetique : **15 GET, aucune ecriture ni requete Equipment sans site**.
Serveur arrete, viewport restaure et onglet temporaire ferme apres validation.

Preuves locales ignorees par Git :

- [Tests cibles UI 5.3.1](../frontend/tmp/ui-5.3.1/targeted.log)
- [Tests complets UI 5.3.1](../frontend/tmp/ui-5.3.1/full-tests.log)
- [Build UI 5.3.1](../frontend/tmp/ui-5.3.1/build.log)
- [Mesures des six largeurs](../frontend/tmp/ui-5.3.1/responsive.json)
- [Journal HTTP synthetique](../frontend/tmp/ui-5.3.1/browser-http-audit.json)
- [Capture desktop](../frontend/tmp/ui-5.3.1/screenshots/equipments-1440.jpg)
- [Capture mobile](../frontend/tmp/ui-5.3.1/screenshots/equipments-390.jpg)

Etat final : branche `feature/frontend-equipments`, HEAD `ff3fed3` inchanges,
travaux UI 5.3 preexistants preserves, index vide. `git diff --check` et controle
des fichiers nouveaux reussis. Aucun backend, PostgreSQL, Docker, package, commit,
push ou merge ; aucun secret ou artefact temporaire ajoute aux fichiers a livrer.
UI 5.4 non commencee. **Attendre validation avant le commit UI 5.3.**
