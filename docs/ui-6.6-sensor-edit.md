# UI 6.6 : modification d’un capteur industriel

Date de validation technique : 20 octobre 2026.
Branche vérifiée : `feature/frontend-sensors`. HEAD initial et final : `012cfd2`.
Dépôt propre au démarrage. Aucun commit, push ou merge à cette étape.

## 1. Résultat et périmètre

La route lazy `/sensors/:sensorId/edit` réutilise SensorForm. L’ordre est liste,
`new`, `:sensorId/edit`, puis `:sensorId`. La garde de sortie appelle canLeave.
Les routes de création et de détail restent distinctes et leurs tests passent.
Le bouton Modifier est affiché après un GET Sensor valide et cohérent avec l’id
courant, y compris si un parent échoue ensuite. Aucun bouton pendant le chargement,
sur un identifiant invalide, un Sensor introuvable ou une réponse d’un autre id.

Les décisions SEN-01 à SEN-10 validées sont conservées. Aucun changement backend,
SQL, migration, Docker, package ou configuration de budgets. Aucune connexion à
PostgreSQL, aucune mesure ou donnée IA ajoutée. UI 6.7 non commencée.

## 2. Fichiers concernés

15 fichiers : 10 fichiers existants modifiés et 5 nouveaux, dont le rapport.

| Fichier | Contenu |
| --- | --- |
| [frontend/src/app/features/sensors/pages/sensor-edit/sensor-edit.component.ts](D:/projets/industrial-predict/frontend/src/app/features/sensors/pages/sensor-edit/sensor-edit.component.ts) | Nouveau : orchestration des lectures, PATCH, gardes, erreurs et récupération de navigation. |
| [frontend/src/app/features/sensors/pages/sensor-edit/sensor-edit.component.html](D:/projets/industrial-predict/frontend/src/app/features/sensors/pages/sensor-edit/sensor-edit.component.html) | Nouveau : états de page, formulaire partagé et suivi administratif avant les actions. |
| [frontend/src/app/features/sensors/pages/sensor-edit/sensor-edit.component.scss](D:/projets/industrial-predict/frontend/src/app/features/sensors/pages/sensor-edit/sensor-edit.component.scss) | Nouveau : styles repris des conventions Equipment Edit. |
| [frontend/src/app/features/sensors/pages/sensor-edit/sensor-edit.component.spec.ts](D:/projets/industrial-predict/frontend/src/app/features/sensors/pages/sensor-edit/sensor-edit.component.spec.ts) | Nouveau : 58 scénarios de non-régression sur HTTP isolé et navigation. |
| [frontend/src/app/features/sensors/components/sensor-form/sensor-form.component.ts](D:/projets/industrial-predict/frontend/src/app/features/sensors/components/sensor-form/sensor-form.component.ts) | Mode édition typé, validation sans trim et calcul explicite des différences. |
| [frontend/src/app/features/sensors/components/sensor-form/sensor-form.component.html](D:/projets/industrial-predict/frontend/src/app/features/sensors/components/sensor-form/sensor-form.component.html) | Rattachement, type et unité rendus comme texte ; projection du suivi avant les actions. |
| [frontend/src/app/features/sensors/components/sensor-form/sensor-form.component.scss](D:/projets/industrial-predict/frontend/src/app/features/sensors/components/sensor-form/sensor-form.component.scss) | Présentation des valeurs en lecture seule. |
| [frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.ts](D:/projets/industrial-predict/frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.ts) | Confirmation liée à une navigation interne vers le bon identifiant. |
| [frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.html](D:/projets/industrial-predict/frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.html) | Action Modifier conditionnée au chargement valide et confirmation de modification. |
| [frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.scss](D:/projets/industrial-predict/frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.scss) | Géométrie de l’action via le mixin partagé navigation-action. |
| [frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.spec.ts](D:/projets/industrial-predict/frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.spec.ts) | Contrôle de visibilité de Modifier et conservation du contexte. |
| [frontend/src/app/features/sensors/sensors.routes.ts](D:/projets/industrial-predict/frontend/src/app/features/sensors/sensors.routes.ts) | Route lazy gardée placée avant le détail. |
| [frontend/src/app/features/sensors/sensors.routes.spec.ts](D:/projets/industrial-predict/frontend/src/app/features/sensors/sensors.routes.spec.ts) | Ordre des routes, titre, Shell et destination active. |
| [frontend/src/styles/_buttons.scss](D:/projets/industrial-predict/frontend/src/styles/_buttons.scss) | Ajout de sensor-edit aux listes d’actions harmonisées, y compris réduction des animations. |
| [docs/ui-6.6-sensor-edit.md](D:/projets/industrial-predict/docs/ui-6.6-sensor-edit.md) | Nouveau : présent rapport. |

Le service SensorsApiService, les DTO et les modèles de UI 6.2 ne sont pas modifiés.
Le calcul des différences reste dans le formulaire et l’éditeur. La whitelist de
transport existante reste une seconde protection indépendante.

## 3. Lectures et rattachement immuable

La page lit successivement `/api/v1/sensors/{id}`, `/equipments/{equipment_id}`,
`/sites/{site_id}` puis `/companies/{company_id}`, sous le même préfixe API.
Chaque identifiant doit être un entier positif sûr ; chaque réponse doit
correspondre à la référence attendue. Les paramètres de retour ne remplacent
jamais ces données réelles. Aucun catalogue de sélection ni choix automatique
en édition, aucun transfert implicite.

Un échec Sensor empêche d’afficher un formulaire vide. Une référence absente,
inaccessible, invalide ou incohérente bloque l’enregistrement, conserve le Sensor
et les saisies et affiche une erreur de référence distincte. Les références
résolues avant l’échec restent identifiées. Une relance manuelle des références
réseau/5xx relit la chaîne sans réinitialiser le formulaire. Pas de relance
proposée pour 404/403 ou incohérence. Les lectures obsolètes sont annulées lors
d’un changement d’id ou de la destruction du composant.

Entreprise, site, équipement, type et unité sont des textes sémantiques dans le
DOM, sans select ou input éditable. Les contrôles correspondants du FormGroup
partagé sont désactivés et exclus du calcul du PATCH. Les dates ne font pas
partie du FormGroup. La section Informations de suivi affiche created_at et
updated_at avec le formateur administratif existant, avant les boutons d’action.

## 4. Contrat du PATCH différentiel

Seuls `name`, `code`, `status` et `description` peuvent être envoyés à
`PATCH /api/v1/sensors/{id}`. La page recalcule elle-même les différences à la
soumission ; elle n’accepte pas de payload arbitraire émis par un appelant.
La whitelist est une comparaison explicite champ par champ avec le Sensor initial.

| Situation | Payload |
| --- | --- |
| Aucun changement effectif | Aucun appel HTTP ; notice accessible |
| Nom seul modifié, code inchangé | `{name: valeur}` uniquement |
| Code différent | `{code: valeur}` uniquement si seul changement |
| Valeur modifiée puis restaurée | Champ omis ; aucun appel si le reste est inchangé |
| Description initiale conservée, y compris null | Description omise |
| Description remplacée par chaîne vide | `description: ""` |
| Retrait explicite d’une description existante | `description: null` |
| Retrait alors que la valeur initiale était null | Aucun changement effectif |

Aucun equipment_id, sensor_type, unit, company_id, site_id, id, created_at ou
updated_at dans le PATCH, même si des contrôles immuables sont altérés par code.
Aucun DELETE ou POST dans le parcours d’édition. Le statut reste active/inactive.
Nom et code modifiés : non blancs, limites respectives de 150 et 100 points de
code Unicode, espaces périphériques inclus. Aucun trim ni changement de casse.
Les textes historiques inchangés restent acceptés sans normalisation implicite.
Description : espaces et sauts de ligne conservés. La création garde ses règles
UI 6.5, notamment le trim des textes obligatoires et la description intacte omise.

## 5. Erreurs, soumissions et sortie

- Double soumission empêchée par l’état saving, indépendamment du bouton désactivé.
  Formulaire bloqué durant l’écriture et sortie Router refusée pendant celle-ci.
- 409 : conflit global, sans déduire de façon fragile sa cause depuis le texte
  serveur. Saisies conservées, code libre modifiable avant soumission manuelle.
- 422 : seules les localisations body/name, code, status et description reconnues
  sont associées au formulaire. Message local sûr, aria-invalid et focus sur le
  premier champ signalé. Les champs immuables et erreurs query restent globaux.
- 404 après PATCH : capteur indisponible, saisies conservées, aucune recréation.
  401/403 et autres refus : message défensif sans exposer de détail serveur.
- Réseau ou 5xx après PATCH : résultat incertain, formulaire et renvoi bloqués,
  lien de vérification de la fiche dans un nouvel onglet. Une confirmation
  explicite de vérification autorise une nouvelle soumission manuelle.
  Aucun retry automatique, aucune promesse d’idempotence.
- Réponse 200 incohérente sur id, équipement, type ou unité : résultat incertain,
  aucune navigation de succès ni notification prématurée.
- Brouillon effectif : confirmation de sortie Router et protection beforeunload.
  Restaurer toutes les valeurs initiales supprime la garde de brouillon.
  Annuler retourne à la fiche réelle après confirmation si nécessaire.

Après 200 cohérent, les nouvelles soumissions sont bloquées ; navigation vers la
fiche réelle avec state updatedSensorId. Un message accessible confirme la
modification ; le toast est émis une seule fois après ouverture réelle de la fiche.
Un faux paramètre de query ne produit pas de confirmation. En cas de navigation
false ou rejetée, résultat confirmé et lien de récupération sont conservés ;
aucun second PATCH. Les résolutions de navigation devenues obsolètes sont ignorées.

Le contexte de liste indépendant conserve company_id, site_id, equipment_id,
search, status, page et page_size sur détail, édition, annulation et succès.
Les valeurs sont bornées et normalisées selon les conventions Sensors existantes ;
aucun returnUrl externe n’est accepté. Company_id et site_id ne partent jamais
vers l’API Sensors. Les champs affichés proviennent toujours de la chaîne réelle.

## 6. Tests exécutés

Résultats finaux sur les sources livrées :

| Validation | Résultat |
| --- | --- |
| Sensors complets et app.routes.spec.ts | 310 tests réussis, 9 fichiers |
| Suite Angular complète | 1 153 tests réussis, 57 fichiers |
| Build production avec statistiques | Réussi |
| git diff --check | Réussi |

Les 58 nouveaux scénarios de Sensor Edit couvrent : champs immuables et dates,
code inchangé, code libre, conflit, PATCH d’un seul champ, restauration de toutes
les valeurs, description vide/null/omise et retrait explicite, texte historique,
Unicode et blancs, absence de PATCH vide, doubles soumissions, garde Router et
beforeunload, erreurs GET/PATCH 0/404/409/422/401/403/5xx, focus 422 sûr,
références absentes/incohérentes/inaccessibles, FK invalides, relance des seules
références, annulation des requêtes obsolètes, navigation false/rejetée/récupérée,
résolution tardive après changement de route ou destruction, contexte URL et
réponse 200 incohérente. Les tests de transport existants vérifient aussi les
whitelists et les enums. Les suites Create, List, Detail et Equipments restent
réussies dans l’exécution complète.

Commandes depuis frontend, sans installation de package :

```powershell
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.6/vitest.config.mjs --include=src/app/features/sensors/**/*.spec.ts --include=src/app/app.routes.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.6/vitest.config.mjs
npm.cmd run build -- --configuration production --stats-json
```

Le runner temporaire limite Vitest à deux workers. Tests HTTP via
HttpTestingController uniquement ; aucun backend démarré. Une première exécution
a détecté le toast supprimé par un contrôle de destruction trop strict ; le
contrôle est corrigé et tous les résultats ci-dessus proviennent des relances finales.

## 7. Responsive et recette navigateur isolée

Build production servi sur 127.0.0.1:8099 par un serveur synthétique sans upstream,
proxy, import backend ou accès base. GET et PATCH en mémoire seulement.
Le serveur et les onglets de recette sont arrêtés à la fin de la vérification.
Les captures et traces restent sous frontend/tmp, ignoré par Git.

| Cible CSS | Largeur observée | Formulaire et détail |
| --- | --- | --- |
| 1440 | 1440 | Contrôlés, navigation desktop |
| 1024 | 1024 | Contrôlés, navigation desktop |
| 1023 | 1023 | Contrôlés, navigation compacte |
| 768 | 768 | Contrôlés, suivi sur deux colonnes |
| 390 | 389 et 391 | Deux rendus voisins contrôlés, réserve d’arrondi |
| 320 | 320 | Contrôlés, actions empilées |

Aucun débordement horizontal global mesuré ; textes et aides repliés, champs
immuables sans contrôle éditable, suivi avant les actions à chaque largeur.
Boutons d’enregistrement et d’annulation de hauteur 44 px ; Modifier de hauteur
44 px, texte blanc, transition 120 ms et focus visible. Le mixin partagé et les
listes globales d’actions couvrent aussi hover, active et prefers-reduced-motion.
Le clavier permet d’atteindre Modifier ; la 422 remet le focus sur le code.
Les dialogues natifs confirm/beforeunload sont couverts par les tests Angular,
sans revendiquer une validation manuelle exhaustive des dialogues du navigateur.

Limite précise : le navigateur utilise un facteur de zoom qui arrondit la largeur
390 à 389 ou 391 lorsqu’on lui fournit une largeur physique entière. Les deux
rendus sont capturés ; une mesure à exactement 390 reste à refaire dans un
navigateur permettant cette largeur CSS exacte.

Recette interactive : aucune différence, conflit 409, rejet 422 avec focus,
code libre puis succès 200, retour fiche, bouton Modifier et annulation propre,
retour à la liste avec tous les filtres, parent équipement absent et saisies
préservées. Trace : trois PATCH strictement `{code: ...}` pour ces trois essais,
aucun PATCH lors de la soumission inchangée, aucun DELETE/POST. Le GET liste
Sensors contient uniquement equipment_id/page/page_size/search/status.

### Captures et preuves locales

| Cible | Formulaire | Détail et action Modifier |
| --- | --- | --- |
| 1440 | [Édition](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/edit-1440.jpg) | [Détail](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/detail-1440.jpg) |
| 1024 | [Édition](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/edit-1024.jpg) | [Détail](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/detail-1024.jpg) |
| 1023 | [Édition](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/edit-1023.jpg) | [Détail](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/detail-1023.jpg) |
| 768 | [Édition](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/edit-768.jpg) | [Détail](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/detail-768.jpg) |
| 390-near-389 | [Édition](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/edit-390-near-389.jpg) | [Détail](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/detail-390-near-389.jpg) |
| 390-near-391 | [Édition](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/edit-390-near-391.jpg) | [Détail](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/detail-390-near-391.jpg) |
| 320 | [Édition](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/edit-320.jpg) | [Détail](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/detail-320.jpg) |

- [Conflit 409 à 320 px](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/error-409-320.jpg)
- [Erreur 422 à 320 px](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/error-422-320.jpg)
- [Succès et focus Modifier à 1440 px](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/detail-success-1440.jpg)
- [Parent absent à 320 px](D:/projets/industrial-predict/frontend/tmp/ui-6.6/screenshots/parent-missing-320.jpg)
- [Trace HTTP synthétique](D:/projets/industrial-predict/frontend/tmp/ui-6.6/http-audit.json)
- [Mesures formulaire](D:/projets/industrial-predict/frontend/tmp/ui-6.6/responsive.json)
- [Mesures détail](D:/projets/industrial-predict/frontend/tmp/ui-6.6/detail-responsive.json)

## 8. Bundle et budgets

Bundle initial : **605 125 octets, soit 605,13 kB**, contre 605 008 octets en
UI 6.5 : **+117 octets**. Estimation de transfert : 153,82 kB.
Avertissement initial existant à 500 kB : dépassement de 105,13 kB.
Seuil d’erreur initial 1 MB et budgets composants 4/8 kB inchangés.

Chunk lazy Sensor Edit : 14 036 octets ; formulaire désormais partagé dans un
chunk de 15 661 octets ; Sensor Create : 20 979 octets ; Sensor Detail : 15 036
octets. Ces chiffres sont les tailles brutes des chunks, pas un coût de page
cumulé. La factorisation déplace une partie de Create dans le chunk partagé.
Ensemble JS/CSS émis : 1 016 510 octets contre 956 205 à l’étape précédente,
soit +60 305 octets. Aucun relèvement artificiel de budget.

## 9. Réserves et limites conservées

- B-SEN-01 reste le correctif déjà livré séparément. Aucun backend modifié ici.
- **B-SEN-02** : divergences des contraintes Pydantic/SQL, blancs/longueurs/null.
  Le frontend applique les décisions validées ; il ne corrige pas le contrat backend.
- **B-SEN-03** : courses d’unicité/FK, IntegrityError non traduites et transactions
  non harmonisées. Un contrôle préalable du code ne garantit pas la concurrence.
- Aucun contrôle optimiste, version ou idempotence backend disponible ; une écriture
  peut rester incertaine après perte réseau. Vérification manuelle nécessaire.
- La chaîne vérifiée côté Angular n’est pas une garantie d’autorisation ou
  d’isolation tenant. Aucun changement de sécurité backend dans cette livraison.
- Pas de recette d’intégration sur une base réelle : tests isolés et données
  synthétiques seulement. B-SEN-02/03 ne sont ni masqués ni déclarés résolus.
- Réserve responsive à exactement 390 px et dialogues natifs décrite ci-dessus.

## 10. État Git et point d’arrêt

15 fichiers uniquement dans le périmètre UI 6.6. Index vide. Pas de capture,
statistique de build, runner ou serveur temporaire dans les fichiers à livrer.
Aucun secret identifié dans les changements. Aucun fichier backend, SQL, Docker,
package ou lockfile modifié. HEAD conservé à 012cfd2, sans commit/push/merge.

Validation utilisateur attendue avant commit. UI 6.7 non commencée.
