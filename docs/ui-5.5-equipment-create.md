# UI 5.5 - Création d'un équipement industriel

## Livraison et périmètre

19 octobre 2026. Branche `feature/frontend-equipments`, HEAD initial et final
`37992ffe3ecc55ae9e43579b8ce823bfe25f324a`. Dépôt propre avant intervention.
Référence : [UI 5.1, décisions EQ-01 à EQ-07](etape-ui-5.1-equipments.md).

- Route lazy-loaded `/equipments/new` avant `:equipmentId`, avec canDeactivate.
  Lien Angular « Nouvel équipement » depuis la liste, portant ses sept paramètres
  appliqués : company_id, site_id, search, status, criticality, page, page_size.
- EquipmentForm propre à la feature, avec contrôles, erreurs, focus et événements
  réutilisables en UI 5.6. Aucun écran, PATCH ou calcul différentiel d'édition ajouté.
- Entreprise et site sélectionnés explicitement ; aucun choix du premier élément
  d'un catalogue. Préremplissage seulement après vérification du contexte URL et
  de la relation. Un site seul dans l'URL résout son entreprise réelle ; une paire
  incohérente ne préremplit pas les contrôles. Entreprise seule : aucun site choisi.
- Catalogues serveur de 50 références par page, chargement supplémentaire,
  déduplication, conservation des pages après erreur et relance GET manuelle.
  Références hors première page résolues directement. Lectures obsolètes annulées.
- Changer d'entreprise invalide le site ; changer de site exige sa vérification.
  Les champs métier restent intacts pendant ces lectures. Un préremplissage
  vérifié n'est pas considéré comme une modification non enregistrée.
- Nom/code/type non blancs, limites 150/100/100 en points de code Unicode après
  trim de création ; casse conservée, sans restriction ASCII ni catalogue de types.
  Code globalement unique annoncé, sans fausse prévalidation d'unicité.
- Défauts visibles operational/medium, indépendants des filtres de la liste.
  Description intacte omise, effacée manuellement transmise vide, retirée par
  action explicite transmise null ; espaces et sauts de ligne conservés.
- POST limité aux champs EquipmentCreate autorisés, avec site vérifié de
  l'entreprise choisie. Aucun company_id, id, date, filtre ou descendant envoyé.
  EquipmentsApiService et contrats core existants inchangés.
- POST réussi : navigation vers l'id retourné, toast Nebular unique seulement
  après navigation réussie et confirmation accessible sur le détail. Une URL
  comportant createdEquipmentId ne constitue pas une preuve de création.
- Navigation refusée ou rejetée après POST réussi : formulaire verrouillé,
  lien de récupération, aucune nouvelle écriture ; récupération via Router,
  confirmation du détail et notification unique après navigation réussie.
- Retour à la liste conservant le contexte initial validé, même si les parents
  de création ont été changés. Le détail affiche alors le rattachement réel et
  la notice de divergence déjà validée en UI 5.4.
- Erreur 409 générique (site ou code), 422 limité aux champs body connus avec
  messages locaux sûrs et focus, 404 imposant une nouvelle vérification du
  rattachement. Réseau/5xx : résultat incertain, aucune relance POST automatique,
  vérification de la liste et acquittement avant une nouvelle soumission explicite.
- Verrou de double soumission et de navigation pendant saving, fieldset désactivé,
  protection des changements réels avec confirm et beforeunload. Annuler conserve
  les saisies si la sortie est refusée ; valeurs restaurées autorisent la sortie.
- Sans site disponible, lien vers la création Site existante dans un nouvel
  onglet, sans création imbriquée ni perte du brouillon Equipment.

## Fichiers concernés

Ajoutés :

- `frontend/src/app/features/equipments/components/equipment-form/equipment-form.component.ts`
- `frontend/src/app/features/equipments/components/equipment-form/equipment-form.component.html`
- `frontend/src/app/features/equipments/components/equipment-form/equipment-form.component.scss`
- `frontend/src/app/features/equipments/components/equipment-form/equipment-form.component.spec.ts`
- `frontend/src/app/features/equipments/pages/equipment-create/equipment-create-references.facade.ts`
- `frontend/src/app/features/equipments/pages/equipment-create/equipment-create.component.ts`
- `frontend/src/app/features/equipments/pages/equipment-create/equipment-create.component.html`
- `frontend/src/app/features/equipments/pages/equipment-create/equipment-create.component.scss`
- `frontend/src/app/features/equipments/pages/equipment-create/equipment-create.component.spec.ts`
- Ce rapport.

Modifiés :

- `frontend/src/app/app.routes.spec.ts`
- `frontend/src/app/features/equipments/equipments.routes.ts`
- `frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.html`
- `frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.scss`
- `frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.spec.ts`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.html`
- `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.spec.ts`

## Tests, non-régressions et bundles

- Tests ciblés finaux : **269 réussis / 9 fichiers**. Écritures exclusivement
  HttpTestingController avec données fictives. Payloads exacts, Unicode aux limites
  et hors limites, defaults/enums, description omise/vide/null, préremplissage
  vérifié, références paginées/indisponibles/incohérentes, annulations, changement
  de site, validation et focus, erreurs, abandon, verrou saving, notifications et
  récupération après navigation false/rejetée couverts.
- Une suite Angular complète finale : **809 réussis / 48 fichiers**, contre
  746 / 46 en UI 5.4.1, soit 63 tests supplémentaires nets. Companies, Sites,
  Equipment List/Detail, Dashboard, transport, Shell, Header, Sidebar et 404 verts.
- Un build production final après cette suite : **réussi**. Aucun fichier
  exécutable modifié après ces validations, empreintes SHA-256 contrôlées.
- Runner temporaire maxWorkers=2, aucun timeout augmenté ni test désactivé.

Commandes finales depuis `frontend` :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-5.5/vitest.config.mjs --include=src/app/features/equipments/**/*.spec.ts --include=src/app/features/sites/pages/site-detail/site-detail.component.spec.ts --include=src/app/app.routes.spec.ts --include=src/app/layout/sidebar/sidebar.component.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-5.5/vitest.config.mjs
npm.cmd run build -- --configuration production --output-path=tmp/ui-5.5/production
```

| Mesure | UI 5.4.1 | UI 5.5 |
| --- | --- | --- |
| Initial | 601 859 octets | 601 859 octets, inchangé |
| Création différée, formulaire et références inclus | Absente | 29 727 octets |
| Détail différé | 10 918 octets | 11 342 octets |
| Liste différée | 24 057 octets | 24 485 octets |
| Routes Equipment différées | 517 octets | 741 octets |
| Total JS/CSS émis | 823 474 octets / 35 fichiers | 854 277 octets / 36 fichiers |

Initial affiché **601,86 ko** : avertissement connu du budget initial de 500 ko
(+101,86 ko), sous le budget d'erreur de 1 Mo. Aucun budget ou package modifié.
Création : `chunk-F3H647HC.js` ; détail : `chunk-I7ESLRDT.js` ; liste :
`chunk-HE7HLKU3.js` ; routes : `chunk-NLYFNIBI.js`. Total émis : +30 803 octets.

## Navigateur et captures

Nouveau build servi sur localhost:8098 avec une API synthétique GET uniquement,
sans upstream FastAPI/PostgreSQL. Saisie fictive sans soumission valide. Le seul
clic Créer a été effectué avec champs métier vides : validation locale et focus
sur Nom vérifiés, aucun POST envoyé. L'entreprise/site du contexte sont vérifiés
et préremplis ; Opérationnel/Moyenne restent les défauts malgré les filtres de
liste différents. Textes Unicode, description multiligne et focus visible testés.

| Viewport CSS | Largeur document | Largeur formulaire / contenu |
| --- | --- | --- |
| 1440 x 1000 | 1425 | 1103 / 1103 |
| 1024 x 900 | 1009 | 687 / 687 |
| 1023 x 900 | 1008 | 943 / 943 |
| 768 x 1024 | 753 | 703 / 703 |
| 390 x 844 | 375 | 341 / 341 |
| 320 x 720 | 305 | 271 / 271 |

Un seul h1, aucun contrôle sans label, aucun débordement horizontal global.
Les 15 px correspondent à la barre verticale. Actions repliées sur mobile et
dimensions des champs adaptées à la largeur disponible.

**Réserve native d'abandon :** les refus/acceptations confirm, la garde Router et
beforeunload sont vérifiés par tests Angular. La tentative de contrôle du dialogue
natif dans le navigateur intégré a expiré ; son interface JavaScript n'a pas
permis d'observer de façon fiable le refus ou l'acceptation. La navigation a
ensuite rejoint la liste avec son contexte conservé. Aucune validation native
complète n'est revendiquée ; un essai manuel dans un navigateur utilisateur reste
nécessaire. Aucun remplacement du dialogue existant ou contournement de garde.

Journal navigateur : **9 GET, 0 POST/PATCH/DELETE, 0 appel ML/descendant**.
Console sans erreur ni alerte applicative observée. Serveur arrêté, viewport
restauré et onglet temporaire fermé après vérification.

Preuves locales ignorées par Git, sans données réelles :

- [Tests ciblés](../frontend/tmp/ui-5.5/targeted.log), [suite complète](../frontend/tmp/ui-5.5/full-tests.log), [build](../frontend/tmp/ui-5.5/build.log)
- [Mesures responsive](../frontend/tmp/ui-5.5/responsive.json), [journal HTTP synthétique](../frontend/tmp/ui-5.5/browser-http-audit.json)
- [Desktop 1440](../frontend/tmp/ui-5.5/screenshots/equipment-create-1440.jpg)
- [1024](../frontend/tmp/ui-5.5/screenshots/equipment-create-1024.jpg), [1023](../frontend/tmp/ui-5.5/screenshots/equipment-create-1023.jpg), [768](../frontend/tmp/ui-5.5/screenshots/equipment-create-768.jpg)
- [Mobile 390](../frontend/tmp/ui-5.5/screenshots/equipment-create-390.jpg), [mobile 320](../frontend/tmp/ui-5.5/screenshots/equipment-create-320.jpg)

## Limites et état Git

Aucune création réelle, validation SQL ou nouvelle preuve de persistance
PostgreSQL : l'intégration réelle Equipment reste prévue en UI 5.7. L'unicité
globale est garantie par le backend, pas par le formulaire ; un résultat incertain
nécessite toujours une vérification utilisateur. Confirmation accessible et
appel unique du service toast testés sur HTTP simulé, sans démonstration POST
navigateur. Pas d'audit exhaustif de lecteur d'écran ou de zoom 200/400 %.
Les références UI ne constituent pas une autorisation multi-tenant.

18 fichiers concernés : 8 modifiés et 10 nouveaux, rapport inclus. Branche et
HEAD inchangés, index vide. `git diff --check`, contrôle des nouveaux fichiers,
liens documentaires et empreintes finales réussis. Aucun secret, dump, package
ou artefact temporaire dans ce périmètre. Aucun backend, PostgreSQL, Docker,
DELETE, transfert, commit, push ou merge. UI 5.6 non commencée.

**Attendre validation avant le commit UI 5.5 et avant UI 5.6.**
