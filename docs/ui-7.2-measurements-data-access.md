# UI 7.2 - Modèles et accès API Measurements

21 octobre 2026. Branche feature/frontend-measurements, HEAD de départ 19b64e2,
dépôt propre avant intervention. Implémentation selon
[UI 7.1 et MES-01 à MES-12 validées](etape-ui-7.1-measurements.md).
Couche de données strictement en lecture seule ; aucun écran, composant ou route
Measurements, aucun début UI 7.3, aucun commit/push/merge.

## Fichiers et contrats

Cinq fichiers nouveaux, aucun fichier existant modifié :

- [measurement.model.ts](../frontend/src/app/features/measurements/models/measurement.model.ts) :
  MeasurementRead, MeasurementQuality et MeasurementPage.
- [measurement-page-query.model.ts](../frontend/src/app/features/measurements/models/measurement-page-query.model.ts) :
  requête paginée propre à Measurements, sans héritage de search.
- [measurements-api.service.ts](../frontend/src/app/features/measurements/data-access/measurements-api.service.ts) :
  deux opérations GET froides, validation des entrées et réponses.
- [measurements-api.service.spec.ts](../frontend/src/app/features/measurements/data-access/measurements-api.service.spec.ts) :
  contrats typés, HttpTestingController, temps précis et erreurs.
- Le présent rapport.

Sources relues : [schémas](../backend/app/schemas/measurement.py),
[routes](../backend/app/api/routes/measurements.py),
[service backend](../backend/app/services/measurement_service.py),
[repository](../backend/app/repositories/measurement_repository.py) et
[convention SensorsApiService](../frontend/src/app/features/sensors/data-access/sensors-api.service.ts).

MeasurementRead possède exactement cinq propriétés : id et sensor_id numériques,
timestamp chaîne, value nombre et quality union stricte
good/suspect/bad/missing/estimated. Aucun champ unité, parent industriel,
created_at/updated_at ou prédiction inventé. MeasurementPage réutilise
Page<MeasurementRead> : items, total, page, page_size, pages.

MeasurementPageQuery exige sensor_id et autorise seulement page, page_size,
quality, start_time et end_time facultatifs. Aucun DTO d'écriture.

| Méthode Angular | Endpoint et comportement |
| --- | --- |
| list(query) | GET /api/v1/measurements ; sensor_id obligatoire côté Angular, query whitelist explicite, réponse paginée |
| getById(id) | GET /api/v1/measurements/{id} ; aucun paramètre de contexte ou filtre |

Base relative /api/v1 et HttpClient existants. Aucun appel aux deux lectures
spécialisées non paginées /sensor/{id} ou /sensor/{id}/period : elles ne sont pas
interchangeables avec le paginé retenu. Aucune méthode create/update/patch/delete,
transfert ou liste globale. Aucun POST, PATCH ou DELETE.
Company_id/site_id/equipment_id/unit/search/status/sort et tout champ inconnu
d'un objet enrichi sont exclus des paramètres HTTP. La requête reçue n'est pas
mutée ; le sensor_id d'une souscription est conservé même si l'appelant modifie
ensuite son objet. Aucun défaut de page ou de filtre n'est injecté : les omissions
laissent les défauts backend page=1/page_size=20 s'appliquer.

## Dates et validation avant HTTP

Identifiants : nombres entiers positifs sûrs, sans coercition depuis une chaîne,
booléen ou null. Pagination explicite : page entier positif sûr, page_size 1..100.
Qualité fournie : une des cinq valeurs exactes, sans trim ni changement de casse.
Une propriété optionnelle undefined est omise ; null explicite est refusé.
Les erreurs locales sont des TypeError dans l'Observable à la souscription,
sans requête réseau ni exception synchrone à l'appel de la méthode.

Timestamp API conservé comme chaîne ISO, **aucun objet Date créé par le service**.
Validation calendaire des années 0001..9999, mois/jours réels et bissextiles,
heures/minutes/secondes et offsets. Format supporté : date ISO, T, heure:minute,
secondes facultatives, fraction de 1..6 chiffres avec secondes, puis Z ou offset
explicite ±HH:MM. Espaces, timezone manquante, format invalide et plus de six
décimales sont refusés au lieu d'être corrigés/tronqués. Ce sous-ensemble ISO
frontend préserve le contrat microseconde validé ; le parseur backend accepte
également d'autres représentations/coercitions non exposées ici.

Bornes start_time et end_time facultatives séparément. Si toutes deux sont
fournies, début strictement antérieur à fin après prise en compte des offsets,
avec une comparaison entière BigInt à la microseconde. Le calendrier grégorien
est calculé sans Date ni arrondi milliseconde ; ce calcul sert seulement à
valider l'ordre, jamais à réécrire le transport. Une différence d'une microseconde
est conservée, y compris entre deux représentations d'offset différentes.

Les chaînes et leurs fractions/offsets sont envoyées **exactement à l'identique**.
Les instants sont comparés sur une référence UTC ; les bornes conservent le sens
backend **[début, fin)**, sans ajout de milliseconde ou fin de journée. Le + des
offsets est encodé par HttpParams. Aucun filtre futur interdit ou maximum de
période inventé depuis Dashboard. Une date future valide est acceptée.

## Réponses et limites de responsabilité

Les valeurs et timestamps valides reçus sont retournés sans normalisation,
arrondi, conversion d'unité, tri, déduplication ou substitution. Les cinq qualités
restent distinctes ; missing/suspect/bad ne transforment jamais value en zéro.
Zéro, négatifs et nombres très grands/petits sont permis.
La précision lexicale déjà perdue par JSON/float n'est pas reconstruite.

Validation défensive des cinq champs : ids sûrs, timestamp ISO avec offset,
qualité exacte et value réellement de type number avec Number.isFinite.
Null, booléen, chaîne numérique, NaN et infinis sont rejetés, sans coercition.
Une réponse invalide produit un TypeError distinct d'une erreur HTTP.
La page exige items sous forme de tableau et métadonnées entières sûres,
total/pages >=0 et page/page_size >=1. Un élément d'un autre sensor_id est refusé ;
un détail d'un autre id est refusé. Aucun élargissement du périmètre ni fallback.

La page hors plage reste une réponse vide avec total/pages conservés. Le service
ne recalcule pas ces métadonnées et n'envoie aucune requête de rattrapage.
Il ne résout pas Sensor -> Equipment -> Site -> Company : cette validation UX
appartiendra aux futures pages/façades. Un sensor_id syntaxiquement valide ne
prouve ni existence du capteur ni autorisation d'accès.

Erreurs HttpErrorResponse/réseau propagées avec statut et corps inchangés,
sans retry automatique, toast, cache ou résultat synthétique. Une désinscription
annule la lecture via HttpClient. Aucun accès API réel ou PostgreSQL dans les tests.

## Validation

Les tests utilisent uniquement HttpTestingController, sans appel API réel,
connexion SQL, seed ou écriture métier. Le premier lancement a échoué à la
compilation d'un test combinant deux types d'Observable ; une variable
Observable<unknown> résout ce typage, sans modification du contrat applicatif.
Le ciblage suivant passe à 125 tests. La revue ajoute ensuite le refus explicite
d'un saut de ligne final dans une date et son test ; les validations finales
ci-dessous portent sur ces sources définitives.

| Vérification | Résultat final |
| --- | --- |
| Tests ciblés Measurements | **126 réussis, un fichier** ; compilation 12,265 s, Vitest 1,91 s |
| Suite Angular complète | **1 305 réussis, 59 fichiers** ; compilation 12,323 s, Vitest 29,75 s |
| Build production | **Réussi**, 13,318 s |
| Contrôles du périmètre et git diff --check | Réussis, index vide |

La référence Sensors était 1 179 tests dans 58 fichiers : ajout de 126 tests et
d'un fichier, sans exclusion ou augmentation de timeout. Couverture : contrats
TypeScript exacts, deux méthodes publiques GET, requêtes froides et annulables,
whitelist et encodage, pagination omise/bornes/hors plage, cinq qualités, valeurs
finies intactes, ids/filtres invalides, dates naïves et calendaires invalides,
offsets équivalents, passage de jour/année, bissextiles, six décimales et écart
d'une microseconde, borne isolée/future, réponses invalides et périmètres étrangers.
HTTP 400/401/403/404/409/422/500/503 et réseau sont propagés sans retry. Le test
409 vérifie la propagation défensive, pas un nouveau statut promis par le GET.

Commandes depuis frontend, runner temporaire ignoré avec deux workers comme les
validations Sensors, sans changement de timeout ni exclusion de tests :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-7.2/vitest.config.mjs --include=src/app/features/measurements/data-access/measurements-api.service.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-7.2/vitest.config.mjs
npm.cmd run build -- --configuration production
```

## Bundle et budgets

Bundle initial : **605 239 octets, soit 605,24 kB**, contre exactement 605 239
avant l'étape : **0 octet d'augmentation**. Les neuf références initiales
JS/CSS et leurs empreintes SHA-256 sont identiques avant/après. Le nouveau
service n'est encore référencé par aucun écran ou route, donc absent du graphe
production. Il sera intégré uniquement lors des étapes ultérieures autorisées.

Les 45 fichiers JS/CSS du build local comparé totalisent 976 624 octets et sont
tous identiques par nom/taille/empreinte. Ce relevé local avant/après est distinct
du total d'artefacts rapporté historiquement en UI 6.7 ; aucune évolution n'en
est déduite. La référence initiale Sensors 605,24 kB reste bien concordante.
Les empreintes des quatre sources TypeScript finales sont inchangées entre la
validation complète et le contrôle suivant le build.

Seul avertissement : budget initial de 500 kB dépassé de **105,24 kB**.
Seuil d'erreur initial 1 MB et budgets styles composants 4/8 kB inchangés.
Aucun relèvement de seuil ni nouvelle dépendance. Runner et mesures avant/après
sont dans frontend/tmp/ui-7.2, ignoré par Git ; aucun artefact de build livré.

## Réserves et point d'arrêt

B-MES-01 à B-MES-07 restent documentées en UI 7.1, sans correction backend.
Les refus locaux ne corrigent ni les non-finis/coercitions Pydantic, ni le PATCH
nullable, les conflits d'intégrité, la concurrence, l'absence de snapshot d'unité
ou la sécurité multi-tenant. Les dates précises du transport ne livrent pas encore
l'affichage F-MES-01. Aucun écran ou filtre utilisateur créé à cette étape.
B-SEN-02/03 restent inchangés. Aucune authentification ou isolation tenant ajoutée.

Aucun backend, SQL, migration, Docker, package, lockfile, budget ou rapport UI 7.1
modifié. Aucun accès PostgreSQL. Seuls les cinq fichiers ci-dessus sont à livrer,
scripts/runners/mesures/builds locaux ignorés. Validation attendue avant commit ;
UI 7.3 non commencée.

HEAD final **19b64e2** inchangé sur feature/frontend-measurements ; uniquement
les cinq fichiers listés non suivis. Aucun fichier déjà versionné modifié,
aucune écriture dans l'index. Les liens locaux et espaces finaux des nouveaux
fichiers sont contrôlés, aucun tiret cadratin dans ce rapport.
