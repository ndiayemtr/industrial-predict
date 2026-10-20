# UI 5.6 - Modification d'un équipement industriel

## Périmètre livré

20 octobre 2026. Branche feature/frontend-equipments, HEAD 70d2a0f. Dépôt propre avant intervention. Référence : [conception UI 5.1 et décisions EQ-01 à EQ-07](etape-ui-5.1-equipments.md). Aucun commit, push ou merge réalisé.

- Route lazy-loaded /equipments/:equipmentId/edit avant le détail, avec garde canDeactivate. Action Modifier affichée après succès du GET Equipment ; Shell, Sidebar et 404 conservés.
- EquipmentForm réutilisé avec un mode édition, sans changement des défauts ou du trim de création. GET de l'équipement, puis du site réel et de son entreprise réelle, indépendamment du contexte de retour.
- Entreprise et site présentés en texte de lecture seule. Aucun sélecteur ni transfert, même dans la même entreprise. Les contrôles de parents hérités du mode création sont désactivés et exclus du diff.
- Dates affichées en lecture seule hors du modèle FormGroup, avec le formateur administratif partagé.
- Diff calculé à partir des six valeurs brutes initiales/courantes, jamais des seuls indicateurs dirty. Un champ restauré est exclu ; aucun PATCH vide ou formulaire inchangé. La page recalcule le diff et le service existant applique sa whitelist.
- Casse, espaces et Unicode préservés. Limites des textes modifiés : nom 150, code/type 100 points de code, espaces compris, sans texte blanc. Les textes historiques inchangés restent intacts, y compris lorsqu'ils dépassent ces limites. Pas de catalogue de types ni règle de transition de statut ajoutés.
- Description inchangée omise, effacement manuel transmis vide, retrait explicite transmis null. Aucun site_id, company_id, id, horodatage ou descendant dans le PATCH.
- Chargement et reprise GET manuelle ; lectures obsolètes annulées au changement d'identifiant. Parents absents/incohérents : enregistrement bloqué, saisie préservée, aucune référence de secours issue de l'URL. Une relance des références ne réinitialise pas le brouillon.
- Double soumission et navigation pendant saving bloquées. Garde d'abandon et beforeunload basées sur les modifications réelles ; restauration des valeurs autorisant la sortie sans confirmation.
- Erreurs PATCH 404/409/422/réseau/serveur : saisies conservées, messages locaux sûrs, focus du premier champ 422 connu. Un 409 reste générique ; site_id/company_id et champs 422 inconnus ne sont pas associés aux champs éditables. Aucun POST de remplacement après 404.
- Réseau/5xx : résultat incertain, aucune relance automatique ; lien de vérification dans un autre onglet et acquittement avant une nouvelle soumission explicite.
- Succès PATCH : détail avec les sept paramètres de retour conservés, un seul toast après navigation réussie et confirmation role=status maintenue pendant la consultation, indépendante du toast. Un paramètre URL updatedEquipmentId ne constitue pas une preuve de succès.
- Navigation false/rejetée après succès : formulaire verrouillé, lien de récupération, aucune nouvelle écriture. Une navigation obsolète ne produit pas de notification sur un autre équipement.
- Styles harmonisés réutilisés ; extension des sélecteurs partagés uniquement pour la nouvelle action equipment-edit.

## Fichiers concernés

11 fichiers modifiés :

- frontend/src/app/app.routes.spec.ts
- frontend/src/app/features/equipments/equipments.routes.ts
- frontend/src/app/features/equipments/components/equipment-form/equipment-form.component.ts
- frontend/src/app/features/equipments/components/equipment-form/equipment-form.component.html
- frontend/src/app/features/equipments/components/equipment-form/equipment-form.component.scss
- frontend/src/app/features/equipments/components/equipment-form/equipment-form.component.spec.ts
- frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts
- frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.html
- frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.scss
- frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.spec.ts
- frontend/src/styles/_buttons.scss

5 fichiers ajoutés :

- frontend/src/app/features/equipments/pages/equipment-edit/equipment-edit.component.ts
- frontend/src/app/features/equipments/pages/equipment-edit/equipment-edit.component.html
- frontend/src/app/features/equipments/pages/equipment-edit/equipment-edit.component.scss
- frontend/src/app/features/equipments/pages/equipment-edit/equipment-edit.component.spec.ts
- docs/ui-5.6-equipment-edit.md

## Validation technique

- Tests ciblés finaux : 288 réussis dans 8 fichiers. GET réels simulés, parents de lecture seule, payloads PATCH exacts et sérialisés, valeurs restaurées, Unicode/espaces, enums, description, doubles soumissions, erreurs, références indisponibles/incohérentes, annulation des lectures, destruction pendant PATCH, navigation tardive, garde et beforeunload, notifications et récupération couverts.
- Une suite Angular complète après stabilisation : 864 réussis dans 49 fichiers, contre 809 dans 48 auparavant, soit +55 tests nets. Non-régressions Equipment Create/List/Detail, Companies, Sites, Dashboard, transport partagé, Shell et 404 réussies.
- Un build production ensuite : réussi. Aucune modification source après cette validation ; relevé SHA-256 dans frontend/tmp/ui-5.6/validated-files.json.
- Ecritures exclusivement avec HttpTestingController et données fictives. Aucun accès réel FastAPI ou PostgreSQL pendant cette étape.
- git diff --check et contrôle des nouveaux fichiers réussis ; index vide. Aucun package, secret, dump ou artefact temporaire ajouté au suivi Git.

Commandes depuis frontend :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-5.6/vitest.config.mjs --include=src/app/features/equipments/**/*.spec.ts --include=src/app/app.routes.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-5.6/vitest.config.mjs
npm.cmd run build -- --configuration production --output-path=tmp/ui-5.6/production
```

Le runner temporaire conserve maxWorkers=2 ; aucun timeout augmenté ni test désactivé.

| Mesure | Avant UI 5.6 | UI 5.6 |
| --- | --- | --- |
| Bundle initial | 604 665 octets | 604 809 octets (+144) |
| Total JS/CSS | 858 562 octets, 36 fichiers | 876 735 octets, 38 fichiers (+18 173 octets) |

Initial affiché : 604,81 ko. Avertissement connu du budget de 500 ko, sous le seuil d'erreur de 1 Mo ; aucun budget modifié. Edition différée : chunk-74HMAJMU.js, 13,48 ko ; formulaire partagé différé : chunk-5X3FG645.js, 14,90 ko ; création : chunk-76MUAM33.js, 17,51 ko ; détail : chunk-ZHZM6MAI.js, 12,94 ko. La réduction du chunk création correspond à l'extraction du formulaire partagé, pas au retrait de fonctionnalités.

## Navigateur, captures et limites

Build production servi localement sur localhost:8098 avec API synthétique GET uniquement, sans proxy ni accès backend. Navigation depuis Modifier avec contexte entreprise/site volontairement différent : parents réels affichés et contexte de retour conservé. Préremplissage, absence de sélecteurs de parents, dates absentes du modèle FormGroup, noms accessibles et aides vérifiés.

| Largeur CSS | Largeur document | Débordement global |
| --- | --- | --- |
| 1440 | 1425 | Aucun |
| 1024 | 1009 | Aucun |
| 1023 | 1008 | Aucun |
| 768 | 753 | Aucun |
| 390 | 375 | Aucun |
| 320 | 305 | Aucun |

Un seul h1 et aucun champ éditable sans libellé aux six largeurs. Les 15 px correspondent à la barre verticale. Enregistrement inchangé : notice accessible, aucun PATCH. Nom blanc : erreur locale aria-invalid et focus sur Nom ; valeur restaurée : retour Annuler au détail avec les sept paramètres, sans dialogue inutile. Focus clavier visible sur Enregistrer, hiérarchie des boutons conservée. Journal navigateur consolidé : 12 GET, aucun POST/PATCH/DELETE ni appel ML. Console sans erreur ou avertissement applicatif observé. Serveur arrêté, viewport restauré et onglets temporaires fermés.

Preuves locales ignorées par Git :

- [Tests ciblés](../frontend/tmp/ui-5.6/targeted-final.log), [suite complète](../frontend/tmp/ui-5.6/full-tests.log), [build](../frontend/tmp/ui-5.6/build.log).
- [Mesures responsive](../frontend/tmp/ui-5.6/responsive.json), [journal HTTP synthétique](../frontend/tmp/ui-5.6/browser-http-audit.json), [tailles des bundles](../frontend/tmp/ui-5.6/bundle-sizes.json).
- [Desktop](../frontend/tmp/ui-5.6/screenshots/equipment-edit-1440.jpg), [actions desktop](../frontend/tmp/ui-5.6/screenshots/equipment-edit-1440-actions.jpg).
- [1024](../frontend/tmp/ui-5.6/screenshots/equipment-edit-1024.jpg), [1023](../frontend/tmp/ui-5.6/screenshots/equipment-edit-1023.jpg), [768](../frontend/tmp/ui-5.6/screenshots/equipment-edit-768.jpg).
- [Mobile 390](../frontend/tmp/ui-5.6/screenshots/equipment-edit-390.jpg), [mobile 320](../frontend/tmp/ui-5.6/screenshots/equipment-edit-320.jpg), [actions mobile](../frontend/tmp/ui-5.6/screenshots/equipment-edit-320-actions.jpg).

Captures de fenêtre : le mécanisme pleine page du navigateur intégré a échoué ; des vues supplémentaires montrent les actions et le suivi. La validation native complète du dialogue d'abandon reste une réserve à vérifier manuellement dans un navigateur utilisateur, comme en UI 5.5. Les refus/acceptations de confirm, la garde Router et beforeunload sont couverts par les tests Angular ; aucune validation native supplémentaire n'est revendiquée.

Aucun PATCH réel ou preuve nouvelle de persistance PostgreSQL. La validation intégrée Equipment reste hors de cette étape. Unicité et concurrence restent contraintes serveur ; aucun verrou optimiste ou contrôle d'autorisation multi-tenant ajouté. Pas d'audit exhaustif de lecteur d'écran ou de zoom 200/400 %.

## UI 5.6.1 - Organisation du formulaire d'édition

20 octobre 2026. Les informations de suivi sont désormais placées après les champs modifiables et avant Enregistrer les modifications / Annuler. Un emplacement de projection equipmentTracking dans EquipmentForm reprend la convention du formulaire Sites. La section est hors du fieldset de saisie, sans contrôle FormGroup ni champ éditable ; les dates et leurs formateurs restent identiques. Le mode création ne projette aucun contenu à cet emplacement.

Cette finition concerne uniquement cinq fichiers du périmètre UI 5.6 : le template EquipmentForm, le template et le SCSS EquipmentEdit, son test et ce rapport. Aucun changement TypeScript, de valeur, de validation, de garde, de notification ou de contrat PATCH.

- Test adapté : ordre DOM fieldset puis suivi puis actions, suivi sans contrôle éditable, dates absentes des contrôles FormGroup.
- Tests ciblés Equipment : 267 réussis dans 7 fichiers, y compris création et édition.
- Une suite complète ensuite : 864 tests réussis dans 49 fichiers.
- Un build production ensuite : réussi ; initial 604,81 ko, avertissement connu de 500 ko inchangé.
- Rendu vérifié à 1440, 390 et 320 px : champs avant suivi, suivi avant boutons, aucun débordement horizontal global, focus clavier visible sur Enregistrer. Trois GET fictifs, aucune écriture navigateur et aucune erreur console. Serveur arrêté, viewport restauré et onglet fermé.
- Journaux : [tests ciblés](../frontend/tmp/ui-5.6.1/targeted.log), [suite complète](../frontend/tmp/ui-5.6.1/full-tests.log), [build](../frontend/tmp/ui-5.6.1/build.log).
- Preuves : [mesures d'ordre et responsive](../frontend/tmp/ui-5.6.1/order-responsive.json), [journal HTTP fictif](../frontend/tmp/ui-5.6.1/browser-http-audit.json).
- Captures du bloc suivi/actions : [desktop](../frontend/tmp/ui-5.6.1/screenshots/edit-order-1440.jpg), [mobile 390](../frontend/tmp/ui-5.6.1/screenshots/edit-order-390.jpg), [mobile 320](../frontend/tmp/ui-5.6.1/screenshots/edit-order-320.jpg). Vues de fenêtre à hauteur 720 px, sans capture pleine page.

Les validations UI 5.6 restent documentées ci-dessus ; les résultats UI 5.6.1 constituent la référence finale après cette finition.

Etat final UI 5.6 et UI 5.6.1 : branche feature/frontend-equipments, HEAD 70d2a0f inchangé, 16 fichiers concernés, modifications non stagées et nouveaux fichiers en attente de validation. Aucun backend, PostgreSQL, Docker, nouveau package, DELETE, transfert, commit, push ou merge. UI 5.7 non commencée.

Attendre validation avant le commit UI 5.6.
