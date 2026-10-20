# UI 6.2 - Modèles et accès API Sensors

20 octobre 2026. Branche `feature/frontend-sensors`, HEAD de départ
`4defbe9412db6fcd2c69e613d73581c2c196ef97`, dépôt propre avant intervention.
Implémentation de la couche de données autorisée par l’utilisateur après validation
de UI 6.1 et de B-SEN-01. Aucun commit, push ou merge dans cette étape.

## Périmètre réalisé

La [conception UI 6.1](etape-ui-6.1-sensors.md), décisions SEN-01 à SEN-10,
reste la référence métier. Son diagnostic de méthode manquante décrit l’état
antérieur au correctif B-SEN-01, intégré dans `4defbe9`.

Fichiers ajoutés sous `frontend/src/app/features/sensors/` :

- [sensor.model.ts](../frontend/src/app/features/sensors/models/sensor.model.ts) :
  SensorStatus, SensorRead et SensorPage.
- [sensor-write.model.ts](../frontend/src/app/features/sensors/models/sensor-write.model.ts) :
  DTO SensorCreate et SensorPatch distincts.
- [sensor-page-query.model.ts](../frontend/src/app/features/sensors/models/sensor-page-query.model.ts) :
  requête paginée avec équipement obligatoire.
- [sensors-api.service.ts](../frontend/src/app/features/sensors/data-access/sensors-api.service.ts) :
  service injectable root, quatre opérations froides via HttpClient.
- [sensors-api.service.spec.ts](../frontend/src/app/features/sensors/data-access/sensors-api.service.spec.ts) :
  tests de contrat, transport, frontières d’écriture et propagation des erreurs.

Aucun écran, route, formulaire, façade de sélection, lien contextuel ou changement
de navigation. Le placeholder Capteurs reste en place. Aucun changement de
ReferenceDataApiService, Companies, Sites, Equipments ou Dashboard nécessaire.
Aucun package, backend, SQL, migration, Docker ou budget Angular modifié.
UI 6.3 n’est pas commencée.

## Contrats relus et modèles

Sources relues : [schémas Sensor](../backend/app/schemas/sensor.py),
[routes Sensor](../backend/app/api/routes/sensors.py),
[service Sensor](../backend/app/services/sensor_service.py),
[convention EquipmentsApiService](../frontend/src/app/features/equipments/data-access/equipments-api.service.ts)
et ses tests. Préfixe relatif réutilisé : `/api/v1`, sans URL serveur codée en dur.

SensorRead contient exactement les dix champs réels : id, name, code, sensor_type,
unit, description, status, equipment_id, created_at, updated_at. Id et equipment_id
sont des nombres, description une chaîne ou null, status l’union stricte
`active | inactive`, les autres champs des chaînes. Les dates restent les chaînes
du serveur, sans parsing ni fuseau ajouté. Aucun objet parent, mesure ou champ IA.

SensorPage réutilise `Page<SensorRead>` : items, total, page, page_size, pages.
SensorPageQuery étend ReferencePageQuery avec equipment_id obligatoire et status
facultatif. Aucun company_id, site_id, tri, filtre type/unité ou paramètre inconnu
dans ce contrat.

SensorCreate exige equipment_id, name, code, sensor_type et unit. Description et
status sont facultatifs ; l’omission de status laisse le défaut backend active
s’appliquer. Le service n’injecte aucun défaut. SensorPatch autorise uniquement
name, code, status et description facultatifs. Les trois premiers ne sont pas
nullables ; description peut être omise, vide ou null. Parent, type, unité et
métadonnées sont exclus du DTO PATCH, malgré le contrat backend plus permissif.

## Service et frontières de transport

| Méthode Angular | Requête | Comportement |
| --- | --- | --- |
| list(query) | GET `/api/v1/sensors` | Paramètres explicitement limités à equipment_id, status, search, page, page_size ; SensorPage en réponse |
| getById(id) | GET `/api/v1/sensors/{id}` | SensorRead, aucun paramètre de contexte |
| create(body) | POST `/api/v1/sensors` | Payload reconstruit avec la whitelist création ; SensorRead, succès 201 simulé dans les tests |
| patch(id, body) | PATCH `/api/v1/sensors/{id}` | Whitelist name/code/status/description ; SensorRead, succès 200 simulé |

La liste globale backend existe mais aucun contrat de service frontend existant
ne l’exige. Elle n’est donc pas exposée. List et create vérifient localement que
equipment_id est un entier positif sûr. GetById et patch contrôlent leur id de la
même manière. Aucune lecture sans équipement valide, aucun endpoint non paginé
`/sensors/equipment/{id}`, DELETE, transfert ou méthode getAll.

Les requêtes et validations sont différées à la souscription avec defer. Une
référence invalide ou un statut fourni hors active/inactive produit un TypeError
dans l’Observable, sans HTTP. Les champs obligatoires de création doivent être
des propriétés propres présentes et non nulles ; undefined est aussi refusé.
Les null sur les champs PATCH obligatoires SQL sont refusés localement.

Les whitelists reconstruisent le payload ; elles ne s’appuient pas uniquement sur
le typage structurel TypeScript. Passer un SensorRead ou un objet enrichi ne peut
donc envoyer ni company_id/site_id, ni id/dates/mesures. En PATCH, equipment_id,
sensor_type et unit sont ignorés même si fournis par un objet forcé ou null.
Les propriétés héritées ne sont pas copiées. L’objet reçu n’est pas modifié.

Le calcul du différentiel relève du futur éditeur, comme dans EquipmentsApiService.
Le service reçoit des différences déjà préparées et filtre leurs propriétés.
Sans valeur de référence, il ne peut déterminer si un code est inchangé. Un PATCH
vide explicitement demandé est transmis comme `{}` ; le futur écran devra éviter
cet appel et omettre les valeurs restaurées ou inchangées. Aucune logique d’écran
n’est anticipée dans UI 6.2.

Une propriété absente ou undefined est omise du payload ; description `""` reste
vide, description null reste null. Aucun trim, changement de casse, normalisation
Unicode, conversion d’unité ou nettoyage de description n’est effectué. Les
chaînes de recherche non vides, espaces et jokers inclus, sont transmises telles
quelles ; search vide est omise, selon la convention du transport existant.
Les paramètres de pagination absents restent absents : défauts serveur 1/20.

Le service ne recale ni les pages ni les tailles, et ne modifie pas un résultat
vide avec total positif. Les contrôles de pagination/recherche backend restent
applicables ; les validations et libellés des futurs écrans sont hors étape.
Les erreurs HTTP et réseau sont propagées sans interprétation du detail,
conversion de 409 en « code dupliqué », notification, résultat de secours ou retry.

## Validation

Tous les HTTP sont interceptés par HttpTestingController. Aucun appel API réel,
accès PostgreSQL, moteur SQL, seed ou écriture métier dans cette étape.

La suite vérifie : champs et unions strictes ; quatre opérations froides ; chemins
et méthodes ; paramètres combinés et encodage de recherche ; omission des filtres ;
tailles 1/100 et recherche de 100 caractères ; réponse paginée vide hors plage ;
statuts active/inactive ; réponse détail et dates intactes ; payloads POST/PATCH,
description absente/vide/null ; whitelists même avec objet complet ou propriétés
héritées ; absence de DELETE/transfert ; rejet des références, null et enums
invalides ; HTTP 401/403/404/409/422/500 et réseau sans retry.

Commandes de validation, depuis frontend :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.2/vitest.config.mjs --include=src/app/features/sensors/data-access/sensors-api.service.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.2/vitest.config.mjs
npm.cmd run build -- --configuration production
```

Le runner temporaire est ignoré par Git. Les essais à deux workers reprennent la
convention Equipments ; une relance à un worker réduit la charge sans changer
les délais, assertions ou exclusions. Tests et build sont lancés séquentiellement.

- Premier essai : refus de compilation TypeScript dans deux tests combinant
  Observable de page et Observable de détail. Typage des appels corrigé en
  Observable<unknown>, sans changement de contrat applicatif.
- Essai sans limite de workers : échec de démarrage du processus Vitest, aucun
  test exécuté. Reprise avec le runner temporaire à deux workers.
- Suite ciblée Sensors : **65 tests réussis dans un fichier**, durée Vitest
  18,44 s. Tous les scénarios passent avec HttpTestingController.
- Première suite complète à deux workers : **927 réussis, deux échecs sur 929**,
  dans 50 fichiers, durée 147,03 s. Échecs par timeout de 5 000 ms dans un test
  Companies list et un test Shell existants ; aucun échec Sensors. Une relance
  complète à un worker est effectuée sans modification des sources ou des délais.
- Relance à un worker : **901 réussis, 28 échecs sur 929**, dans 50 fichiers,
  durée 35,10 s. Les échecs concernent des assertions de navigation/Sidebar dans
  six fichiers existants, sans timeout et sans échec Sensors. Le runner Angular
  configure isolate=false ; une sensibilité à l’ordre de partage des modules est
  une hypothèse, pas un défaut attribué au nouveau service. Retour à la
  configuration habituelle à deux workers pour la vérification finale.

- Vérification finale à deux workers : **929 tests réussis dans 50 fichiers**,
  durée Vitest 30,84 s, compilation 19,817 s. Aucune source ni assertion modifiée
  entre les trois suites complètes. Les incidents précédents sont conservés ici
  comme limite de stabilité du runner, malgré ce résultat final entièrement vert.
  La référence UI 5.8 était de 864 tests dans 49 fichiers : ajout de 65 tests et
  d’un fichier, sans exclusion.

- Build production réussi, compilation 57,744 s. Bundle initial **604 809 octets**,
  identique à la référence UI 5.8 / UI 5.6.1, soit **0 octet d’augmentation**.
  Les références initiales sont relevées dans index.html (scripts, styles et
  modulepreload). L’avertissement existant de dépassement du budget initial
  500 ko reste de 104,81 ko ; seuil d’erreur 1 Mo inchangé. Aucun avertissement
  supplémentaire relevé dans cette exécution.
- Comparaison des artefacts JS/CSS avec les fichiers conservés dans
  `frontend/tmp/ui-5.6.1/production/browser` : **38 fichiers, 876 814 octets**, noms,
  tailles et empreintes SHA-256 tous identiques. Le service n’est encore référencé
  par aucun écran et n’ajoute donc pas de code au bundle livré à cette étape.
- `git diff --check` réussi. Aucun fichier existant suivi modifié ; seuls les
  cinq fichiers Sensors et ce rapport sont ajoutés, sans staging ni commit.

## Limites conservées

- Les DTO sont stricts mais HttpClient ne valide pas les réponses à l’exécution.
  Les futurs écrans devront vérifier la cohérence des références et de la chaîne
  entreprise -> site -> équipement. Le service ne charge pas les parents.
- L’unicité globale du code relève du backend. Aucun contrôle par chargement de
  tous les capteurs, aucune normalisation de casse ajoutée.
- Les longueurs SQL 150/100/100/30 et le refus des blancs devront être appliqués
  dans les futurs formulaires selon SEN-09. Le transport ne remplace pas ces
  formulaires et ne corrige pas B-SEN-02 côté backend.
- B-SEN-03 reste ouvert : gestion d’IntegrityError, concurrence et transactions
  serveur inchangées. Une écriture réseau/5xx incertaine n’est jamais réessayée
  automatiquement par ce service.
- Sélection obligatoire et whitelists frontend ne constituent pas une protection
  multi-tenant des endpoints. Authentification et autorisation backend inchangées.
- Aucun composant n’injecte encore SensorsApiService : l’intégration aux écrans,
  les retours contextuels et Measurements restent hors UI 6.2.

Validation utilisateur attendue avant commit ; aucun démarrage UI 6.3.
