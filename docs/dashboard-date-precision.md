# Dashboard - Précision des filtres temporels

Livré et publié dans `main` via `2c49c4f` : code `9c183e0`, documentation
`3e83b0b`. Validation finale : 386 tests Angular réussis, build production réussi
et `npm audit` sans vulnérabilité signalée. Aucune relance lors de la présente
synchronisation documentaire. Les vérifications locales détaillées ci-dessous
ont été réalisées le 16 octobre 2026 sur `fix/frontend-datetime-display`,
base `537822c`, avant commit et fusion.

## Correction appliquée

- Le mode simple initialise des valeurs `YYYY-MM-DDTHH:mm`, avec `step="60"`.
  La fin est la minute UTC entière atteinte, sans secondes ni millisecondes ;
  le début est exactement 168 heures auparavant.
- Le préréglage initial non modifié est recalé à l'application. En mode simple,
  la fin est de nouveau ramenée à la minute UTC inférieure. En mode avancé,
  le comportement précis existant est conservé, avec l'instant courant exact.
  Dans les deux cas, l'intervalle est exactement de 168 heures.
- L'option native « Précision avancée » active `step="0.001"`. Toute valeur
  chargée dans les contrôles avec secondes ou millisecondes non nulles active
  automatiquement cette option, sans réécriture de la date.
- Revenir au mode simple avec une précision non nulle ouvre une confirmation.
  Les dates restent intactes et l'application est bloquée pendant ce choix.
  « Conserver la précision avancée » annule la conversion. Seul le bouton
  « Supprimer les secondes et millisecondes » ramène explicitement les deux
  bornes à la minute inférieure, avec annonce du résultat. Les contrôles sont
  alors marqués modifiés pour empêcher le recalage du préréglage initial.
- Si cette conversion produit deux bornes égales, le validateur bloque la
  soumission. La fin exclusive n'est jamais élargie automatiquement.
- Les représentations complètes répétées sous les champs sont supprimées.
  Les aides courtes « Début inclus » et « Fin exclue » restent présentes, avec
  UTC visible dans les libellés et l'aide de période.

Exemple simple : `2026-10-16T12:34`, affiché par le navigateur français comme
`16/10/2026 12:34`. Exemple avancé : `2026-10-16T12:34:56.789`, affiché comme
`16/10/2026 12:34:56,789`. La présentation native dépend du navigateur et de sa
langue ; aucune dépendance ou imitation du sélecteur natif n'est ajoutée.

## Contrats temporels préservés

Le parseur ajoute explicitement `Z` aux composantes du contrôle, puis vérifie
leur aller-retour ISO et leur validité calendaire. Aucun parsing en fuseau local
du navigateur. Le début reste inclus, la fin exclusive et non future ; le début
doit précéder strictement la fin. Les filtres sont émis uniquement à la
soumission valide. Le modèle, le service HTTP, le snapshot appliqué et
l'actualisation du Dashboard ne sont pas modifiés.

Requêtes observées sur le serveur local simulé en lecture seule :

```text
start_time=2026-10-09T12:34:56.123Z&end_time=2026-10-16T12:34:56.789Z
```

L'actualisation réutilise ces mêmes bornes précises. Après conversion confirmée
et nouvelle application :

```text
start_time=2026-10-09T12:34:00.000Z&end_time=2026-10-16T12:34:00.000Z
```

## Fichiers de cette correction

- `frontend/src/app/features/dashboard/components/dashboard-filters/dashboard-filters.component.ts`
- `frontend/src/app/features/dashboard/components/dashboard-filters/dashboard-filters.component.html`
- `frontend/src/app/features/dashboard/components/dashboard-filters/dashboard-filters.component.scss`
- `frontend/src/app/features/dashboard/components/dashboard-filters/dashboard-filters.component.spec.ts`
- Ce rapport et une note de remplacement dans [le rapport précédent](frontend-datetime-display.md).

Les autres modifications déjà présentes dans le répertoire de travail concernent
la finition précédente des dates. Aucun fichier Companies n'a été modifié par
cette correction des filtres. Aucun changement backend, PostgreSQL, dépendance
ou budget Angular.

## Vérifications exécutées

Les commandes applicatives ont été exécutées successivement depuis `frontend`,
sans build concurrent aux tests :

1. `node node_modules/@angular/cli/bin/ng.js test --watch=false` :
   **386 tests réussis, 32 fichiers**, le 16 octobre 2026 à 12:59:42 UTC.
   Ces résultats incluent les suites Dashboard et Companies.
2. `node node_modules/@angular/cli/bin/ng.js build --configuration=production --output-path=tmp/datetime/production` :
   **réussi**, terminé à 13:02:16 UTC.
3. `git diff --check` : réussi, sans erreur.

Les tests couvrent notamment les minutes initiales, les deux recalages de
168 heures, l'activation automatique de la précision, les millisecondes UTC,
les transitions sans perte, la confirmation et son annulation, l'intervalle
effondré après conversion, les dates impossibles ou absentes, la fin future et
les bornes égales ou inversées. Les contrôles existants de snapshot,
d'actualisation et de paramètres HTTP restent dans la suite complète.

Le build de production a été servi sur `127.0.0.1:8099`, avec fixtures HTTP et
rejet de toute écriture. Contrôle visuel à 1440 px et 320 px, sans débordement
horizontal constaté dans les filtres. Cases et boutons actionnés au clavier
(Espace et Entrée), valeurs et requêtes vérifiées après application,
actualisation et conversion. Les messages de conversion exposent `role="status"` ;
les erreurs conservent leur annonce `aria-live` et les champs leurs aides et
états d'invalidité. Aucun lecteur d'écran réel ni appareil mobile physique
testé. Aucune nouvelle validation contre FastAPI réel revendiquée.

Captures livrées pour les modes simple et avancé à 1440 px et 320 px, ainsi que
pour la confirmation à 320 px (`dashboard-precision-*.png`).

## Poids du build

- Bundle initial : **600,89 ko**, inchangé par rapport au build de la finition
  précédente. Avertissement existant : dépassement de 100,89 ko du budget de
  500 ko. Aucun relèvement du budget.
- Chunk différé Dashboard : **49,39 ko**, contre 45,81 ko auparavant.
- Ensemble JavaScript et CSS : **717 583 octets**, contre 714 010 octets au
  build précédent, soit **+3 573 octets** pour cette correction.

Les journaux de cette exécution sont dans `frontend/tmp/datetime/` :
`tests-precision.log`, `build-precision.log` et `preview-requests.log`.
Ce répertoire de validation est ignoré par Git. La correction est désormais
fusionnée et publiée ; cela ne constitue pas un déploiement de production.
