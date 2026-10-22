# UI 7.3 - Liste et historique Measurements

22 octobre 2026. Branche feature/frontend-measurements, HEAD de départ 4b34f67,
dépôt propre avant intervention. Implémentation selon
[UI 7.1 et MES-01 à MES-12 validées](etape-ui-7.1-measurements.md) et
[le contrat UI 7.2](ui-7.2-measurements-data-access.md).
Aucun backend, SQL, migration, Docker, package, budget ou donnée PostgreSQL modifié.
Aucun commit, push ou merge ; UI 7.4 non commencée.

## 1. Périmètre et fichiers

18 fichiers concernés après UI 7.3.1, dont quatre fichiers existants modifiés et quatorze nouveaux :

- [app.routes.ts](../frontend/src/app/app.routes.ts) et
  [son test](../frontend/src/app/app.routes.spec.ts) : Measurements passe au
  chargement lazy par MEASUREMENT_ROUTES, autres destinations inchangées.
- [Test Sidebar](../frontend/src/app/layout/sidebar/sidebar.component.spec.ts) :
  ancienne attente de placeholder Measurements retirée ; sélection active vérifiée
  dans le nouveau test de routage avec le Shell réel.
- [MeasurementsApiService](../frontend/src/app/features/measurements/data-access/measurements-api.service.ts) :
  extraction de la validation temporelle existante vers l'utilitaire de feature,
  sans changement des deux GET ou des paramètres envoyés.
- [measurements-state.model.ts](../frontend/src/app/features/measurements/models/measurements-state.model.ts) :
  contexte industriel UI distinct des filtres API, états discriminés.
- [Façade](../frontend/src/app/features/measurements/measurements-list.facade.ts) et
  [ses tests](../frontend/src/app/features/measurements/measurements-list.facade.spec.ts) :
  résolution des quatre références, annulation, lectures paginées et erreurs.
- Les quatre fichiers [TypeScript](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.ts),
  [template](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.html),
  [SCSS](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.scss) et
  [tests](../frontend/src/app/features/measurements/pages/measurements-list/measurements-list.component.spec.ts)
  de MeasurementsListComponent : catalogues, formulaire de période, URL et tableau.
- [Routes](../frontend/src/app/features/measurements/measurements.routes.ts) et
  [tests de routage](../frontend/src/app/features/measurements/measurements.routes.spec.ts).
- [Utilitaire temporel](../frontend/src/app/features/measurements/utils/measurement-time.ts) et
  [tests de précision](../frontend/src/app/features/measurements/utils/measurement-time.spec.ts).
- [Brouillon temporel typé](../frontend/src/app/features/measurements/utils/measurement-period-draft.ts) et
  [ses tests](../frontend/src/app/features/measurements/utils/measurement-period-draft.spec.ts), ajoutés en UI 7.3.1.
- Le présent rapport, actualisé pour UI 7.3.1.

Les modèles Read/query de UI 7.2 et ses 126 tests restent inchangés. Aucun
composant shared, transport de références, formulaire Sensors ou stylesheet global
modifié. Aucun nouveau composant transversal ou package.

## 2. Sélection et vérification du périmètre

Entreprise -> Site -> Équipement -> Capteur, sans choix automatique du premier
élément, même avec une seule option. Au départ seul le catalogue Companies est
chargé. Chaque descendant reste indisponible tant que son parent n'est pas vérifié.
Le changement d'un parent retire descendants/résultats et période, conserve
qualité/taille valides et revient à la page 1.

Catalogues de 50 éléments via ReferenceDataApiService et SensorsApiService,
chargement supplémentaire explicite, options dédupliquées par id. Une page suivante
échouée conserve les options déjà chargées et se relance manuellement pour
réseau/5xx. Une référence sélectionnée hors première page est ajoutée après GET
ciblé ; l'absence du catalogue courant ne signifie pas inexistence.
Les catalogues Sites/Equipments/Sensors sont vérifiés contre leur parent attendu.
Aucun filtre active imposé au catalogue Sensor : les inactifs restent consultables.

Une sélection Sensor déclenche Sensor -> Equipment -> Site -> Company réels.
Chaque id et FK est vérifié, indépendamment des paramètres d'URL déclarés.
Une contradiction bloque, sans remplacement silencieux ni élargissement global.
Le GET Measurements ne part qu'après succès de toute la chaîne.

Une URL sensor_id seul est une sélection explicite ; les trois parents sont
résolus puis ajoutés à l'URL. Equipment seul attend Sensor, Site seul attend
Equipment/Sensor, Company seule attend les descendants. Aucun descendant déduit
du premier résultat. Un ancien capteur est retiré immédiatement lorsqu'un nouveau
périmètre doit être validé ; les réponses obsolètes sont annulées par switchMap.

Une fois la chaîne résolue, les changements de qualité/période/page/taille
réutilisent ces références et ne relisent que Measurements. Ce contexte est local
à la page, pas un cache global ou une preuve d'autorisation tenant.

## 3. Filtres, URL et temps précis

Snapshot appliqué dans l'URL : company_id, site_id, equipment_id, sensor_id,
quality, start_time, end_time, page, page_size. Paramètres inconnus et fragment
conservés, sans fuite vers l'API. Les return_sensor_* restent des données de retour
indépendantes ; aucun returnUrl arbitraire n'est suivi par cette page.

- Query Measurements limitée à sensor_id, quality, start_time, end_time, page,
  page_size. Aucun company_id/site_id/equipment_id/unité/search/tri transmis.
- Cinq qualités exactes good/suspect/bad/missing/estimated, affichées Bonne,
  Suspecte, Mauvaise, Manquante, Estimée ; Toutes omet le filtre.
- Pagination serveur, défaut 20 et choix 20/50/100. Une taille d'URL valide 1..100
  reste disponible. Page/taille invalides normalisées avant lecture avec notice ;
  qualité ou périmètre invalides bloquent, sans supprimer discrètement le filtre.
- Deux bornes facultatives composées chacune de date calendaire, heure UTC avec
  secondes et fraction facultative de 0 à 6 chiffres. Application par Entrée ou
  bouton, pas à chaque frappe. Modifier qualité/taille ne réutilise pas le brouillon
  temporel non appliqué. Les filtres appliqués ramènent à la page 1.
- Période d'URL invalide : erreur et aucun GET de référence industrielle ou de
  Measurements ; seul le catalogue initial Companies peut être chargé.
  Période de formulaire invalide : message accessible, URL/résultats appliqués
  conservés, aucune requête. Pas de suppression des bornes pour une lecture élargie.

L'utilitaire partagé à la feature conserve la validation UI 7.2 : calendrier,
offsets explicites, 1..6 décimales, comparaison entière BigInt à la microseconde.
Les chaînes restaurées de query sont transmises sans trim, conversion ou troncature.
Seule une borne explicitement modifiée est reconstruite en UTC avec suffixe Z.
Le formateur UTC convertit seulement les composantes calendaires de l'offset et
conserve les chiffres fractionnaires ; aucun Date/toISOString pour les mesures.
Les attributs time.datetime/title gardent l'ISO original. Pas de fuseau inventé,
fin de journée artificielle ou règle de fin future copiée du Dashboard.

## 4. Affichage, navigation préparée et états

Colonnes : Horodatage UTC, Valeur, Unité actuelle, Qualité, Référence. Valeur reçue
conservée sans arrondi métier, virgule d'affichage française et notation scientifique
si nécessaire. Zéro reste zéro, négatifs restent négatifs ; missing ne remplace
pas la valeur. Les guards du service refusent null/booléen/non-fini, mauvais id,
timestamp ou qualité et les éléments d'un autre sensor_id.

Unité lue sur le Sensor réel, explicitement actuelle, sans conversion ou snapshot
historique promis. Pas de graphique, agrégat, compteur de série calculé, anomalie,
prédiction ou temps réel. Le total affiché provient exclusivement de la page serveur.

La future destination /measurements/{id} est préparée dans data-detail-url avec
le snapshot courant. La référence est un texte ordinaire, sans href, rôle link,
tab stop ou présentation de lien désactivé. Une notice annonce la fiche ultérieure.
Seule la liste est routée ; détail/new/edit vont encore à la 404 globale.
La fiche et le lien Sensor -> Measurements ne sont pas implémentés dans UI 7.3.

Sélection attendue, chargement des catalogues/mesures, aucun descendant, historique
vide, résultat filtré vide, page hors plage et erreur sont distingués. Aucun faux
zéro avant succès. Total=0 : pas de pagination. Items vide avec total positif :
retour manuel à une page disponible, aucune boucle de correction automatique.
Les pages peuvent se déplacer avec les écritures concurrentes ; notice dédiée,
aucun chargement intégral, tri local ou déduplication des relevés par timestamp.

400/422 : période/filtres à vérifier ; 404 : référence ou ressource indisponible ;
401/403 traité défensivement. Réseau/5xx : relance manuelle, aucune boucle ou faux
résultat de secours. Erreur de référence distincte d'une réponse de mesure invalide.
Façade locale, nettoyage takeUntilDestroyed et annulation des anciennes lectures.

PageHeader, LoadingState, EmptyState, ErrorState et styles d'actions existants
réutilisés. Boutons de 44 px, qualité non exprimée par couleur seule, labels et
aides liées, alertes, focus visible et région de tableau focusable/défilable.
L'aide au défilement est masquée lorsque la largeur disponible suffit.

## 5. Tests Angular et build, état final UI 7.3.1

Commandes depuis frontend, runner temporaire à deux workers ignoré, sans timeout
augmenté ni exclusion :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-7.3.1/vitest.config.mjs --include=src/app/features/measurements/**/*.spec.ts --include=src/app/app.routes.spec.ts --include=src/app/layout/sidebar/sidebar.component.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-7.3.1/vitest.config.mjs
npm.cmd run build -- --configuration production --stats-json
```

Les résultats UI 7.3 précédents étaient 221 tests ciblés et 1 367 tests complets.
Après corrections UX UI 7.3.1, tous les contrôles ci-dessous ont été relancés sur
les sources finales, y compris après la correction de cascade CSS tablette.

| Validation finale UI 7.3.1 | Résultat |
| --- | --- |
| Ciblage Measurements/routage/Sidebar | **252 tests réussis, 8 fichiers**, Vitest 10,72 s, compilation 13,976 s |
| Suite Angular complète | **1 398 tests réussis, 64 fichiers**, Vitest 26,75 s, compilation 13,047 s |
| Build production | **Réussi**, 11,611 s |
| git diff --check et contrôles de contenu | Réussis |

Bundle initial : **605 340 octets, soit 605,34 kB**, inchangé depuis UI 7.3 et
+101 octets par rapport aux 605 239 octets de UI 7.2. Chunk lazy de liste :
**43 791 octets**, contre 38 732 en UI 7.3, soit **+5 059 octets**. Ensemble JS/CSS
émis : 1 020 764 octets. Avertissement initial existant : seuil de 500 kB dépassé
de 105,34 kB. Seuil d'erreur 1 MB et budgets styles composants 4/8 kB inchangés.
Un dépassement SCSS intermédiaire a été supprimé en retirant les règles inutiles ;
aucun avertissement de style sur le build final. La liste reste lazy.

31 tests supplémentaires depuis UI 7.3, dont 22 cas du brouillon temporel et neuf
cas de page. Les tests de parcours existants ont aussi été renforcés pour les aides.
Les 126 tests du contrat API UI 7.2 restent inclus et leur source est inchangée.
HTTP intégralement simulé, sans FastAPI, accès PostgreSQL ou fixture SQL.
Aucun test backend relancé.

## 6. Recette navigateur et captures

Build production servi sur 127.0.0.1:8099 avec fixtures synthétiques locales,
GET uniquement, sans proxy/upstream, configuration DEV, moteur SQL ou connexion
à la base. Ces données sont des fixtures de recette, pas une preuve de données
industrielles ou une intégration PostgreSQL. Le serveur refuse toute écriture.

Recette initiale UI 7.3, avant correction UX : rattachement 7/9/12/17, capteur inactif consultable, cinq qualités,
valeurs négatives et non nulles pour missing, pagination Suivant/Précédent, période
d'une microseconde, offset +05:30 et URL encodée sans perte. Deux bornes égales
affichent une erreur en conservant l'URL appliquée : les traces avant/après sont
identiques (20 GET chacune), aucune nouvelle requête.

Captures historiques UI 7.3 avec qualité missing et page_size=1, taille d'URL valide
déjà permise, pour montrer contexte, critères et historique sur une même image.
Les captures sont réelles, non recomposées ; l'image mobile masque normalement
les colonnes à droite du tableau jusqu'au défilement horizontal.

| Cible CSS | Mesurée | Largeur tableau disponible / défilable | Aide |
| --- | ---: | --- | --- |
| 1440 | 1440 | 1086 / 1086 px | Masquée |
| 1024 | 1024 | 670 / 670 px | Masquée |
| 1023 | 1023 | 925 / 925 px | Masquée |
| 768 | 768 | 686 / 686 px | Masquée |
| 390 | 389 et 391 | 340 / 608 puis 341 / 608 px | Visible |
| 320 | 320 | 270 / 608 px | Visible |

Aucun débordement global sur les sept mesures finales. Tous les boutons mesurés
font 44 px de haut ; quatre colonnes de sélection à 1440, deux à 1024/1023/768,
une sur les petits écrans. Focus clavier visible et déplacement horizontal par
flèche sur la région du tableau vérifiés à 320 px. Aucun warning/erreur console
relevé sur la page finale. Les pseudo-états appui maintenu et mouvement réduit
ne sont pas émulés ; les styles communs existants restent inchangés.

Pièces locales ignorées par Git :

- [Capture 1440](../frontend/tmp/ui-7.3/screenshots/measurements-list-1440.png),
  [1024](../frontend/tmp/ui-7.3/screenshots/measurements-list-1024.png),
  [1023](../frontend/tmp/ui-7.3/screenshots/measurements-list-1023.png),
  [768](../frontend/tmp/ui-7.3/screenshots/measurements-list-768.png),
  [389](../frontend/tmp/ui-7.3/screenshots/measurements-list-390-near-389.png),
  [391](../frontend/tmp/ui-7.3/screenshots/measurements-list-390-near-391.png),
  [320](../frontend/tmp/ui-7.3/screenshots/measurements-list-320.png).
- [Focus clavier mobile](../frontend/tmp/ui-7.3/screenshots/measurements-table-keyboard-320.png).
- [Mesures responsive](../frontend/tmp/ui-7.3/responsive.json),
  [synthèse DOM](../frontend/tmp/ui-7.3/browser-summary.json),
  [trace HTTP synthétique](../frontend/tmp/ui-7.3/http-audit.json).
- [Avant période invalide](../frontend/tmp/ui-7.3/audit-before-invalid.json) et
  [après](../frontend/tmp/ui-7.3/audit-after-invalid.json),
  [bundle avant](../frontend/tmp/ui-7.3/bundle-before.json) et
  [après](../frontend/tmp/ui-7.3/bundle-after.json).

Trace historique UI 7.3 : 33 GET, dont neuf lectures Measurements toutes limitées au capteur
et aux seuls paramètres autorisés. La liste n'a fait aucun appel à un endpoint
spécialisé non paginé. Serveur synthétique arrêté et override de viewport retiré
après la recette ; aucun service DEV ou configuration modifié.

L'outil applique un zoom 0,75 et exige des dimensions entières. La cible CSS 390
exigerait une largeur physique 292,5, refusée par l'API : contrôle à 389 et 391 px,
sans revendiquer 390 exact. Les autres cinq largeurs sont mesurées exactement.
Une première navigation a échoué car le serveur isolé n'était pas accessible au
navigateur ; redémarrage du seul serveur synthétique hors bac à sable, puis recette
réussie. Aucun service DEV, réglage de sécurité ou backend modifié.

## 7. Réserves et état Git

B-MES-01 à B-MES-07 et B-SEN-02/03 restent ouverts. L'unité actuelle n'est pas une
garantie historique ; aucune authentification, autorisation de ressource ou
isolation tenant ajoutée. Pagination offset/COUNT et cohérence concurrente restent
des limites backend. Pas de recette FastAPI/PostgreSQL, de charge réelle ou d'audit
lecteur d'écran complet. F-MES-01 est traité pour le transport et l'affichage de
cette liste ; les autres écrans et le détail restent hors périmètre.

HEAD 4b34f67 inchangé. Index vide, uniquement les 18 fichiers listés, aucun backend,
SQL, migration, Docker, dépendance, budget ou rapport historique modifié. Runners,
serveur synthétique, captures et traces restent dans frontend/tmp/ui-7.3 et
frontend/tmp/ui-7.3.1, ignorés.
Contrôles finaux git diff --check, espaces finaux, contenu et liens réussis.
Aucun nouveau secret détecté par les motifs ciblés et la revue du périmètre.
Aucun commit/push/merge. Validation attendue avant commit ; UI 7.4 non commencée.

## 8. Corrections UX UI 7.3.1

### Contrôles utilisés et conservation des timestamps

Angular Reactive Forms typé, sans nouveau package : deux FormGroup de trois
FormControl non nullables, reliés à input type=date (calendrier natif), input
type=time step=1 (heures, minutes, secondes) et un champ texte inputmode=numeric
pour la fraction. Les composants date/heure Nebular ne sont pas intégrés : le
NbNativeDateService installé est typé NbDateService<Date>, sans contrat assurant
le transport des microsecondes. Les contrôles HTML déjà compatibles avec Angular
conservent ici des chaînes, sans adapter Date ni configuration globale.

Aucune date, heure ou fraction par défaut. Une borne entièrement vide est omise ;
une borne partielle est refusée. Une heure native HH:mm représente HH:mm:00,
conformément à la valeur du contrôle, sans ajouter une heure absente. La fraction
reste une chaîne, sans padding automatique, trim, arrondi ou maxlength susceptible
de tronquer un septième chiffre. Les fractions invalides sont refusées.

measurementUtcParts calcule les composantes UTC manuellement, avec reports de
jour/mois/année et copie exacte des chiffres fractionnaires. Le brouillon garde
séparément les composantes affichées et le timestamp URL original. S'il n'y a pas
de modification effective, ou si les composantes initiales sont restaurées, la
chaîne originale est réutilisée, offset et précision compris. Exemple vérifié :
2026-10-22T17:30:00.123456+05:30 est affiché 22/10/2026, 12:00:00 et 123456,
puis envoyé et conservé dans l'URL exactement comme à l'origine après Appliquer
sans édition. Une nouvelle valeur devient YYYY-MM-DDTHH:mm:ss[.fraction]Z.
La modification d'une borne ne normalise pas l'autre.

Une URL temporelle invalide reste bloquante, même si ses composantes ne peuvent
pas être affichées par le calendrier. Elle n'est pas transformée silencieusement
en borne absente. Réparation explicite ou Effacer requis. Le formulaire novalidate
utilise l'erreur applicative accessible : validation du calendrier, heure,
fraction, intervalle strict et validity du contrôle natif avant navigation/HTTP.
Cela couvre notamment une date partiellement tapée, exposée vide par le navigateur
avec badInput=true. Aucun GET Measurements pour une période refusée.
L'ancien snapshot URL et les résultats sont conservés après refus. Les brouillons
ne sont utilisés ni par qualité/taille, ni par pagination avant Appliquer.

### Aides et accessibilité

Les aides sont liées par aria-describedby uniquement lorsqu'elles existent.
Chaque aide disparaît après résolution de la référence et vérification de son
identifiant et de ses parents réels. Les identifiants d'URL seuls ne suffisent pas.
Lors d'une restauration complète, elles restent affichées pendant la vérification.
Les ancêtres déjà vérifiés et inchangés restent valides pendant le choix d'un
descendant. Le changement d'un parent réinitialise les descendants concernés.
Erreurs de référence, catalogue, réseau et avertissements restent indépendants
de cette visibilité. Le navigateur confirme 4 -> 3 -> 2 -> 1 -> 0 aides, puis quatre
après retrait de l'entreprise ; les tests couvrent aussi chargement et erreurs.

Fieldset/legend regroupent les bornes, labels distincts et aide compacte demandée :
« Début inclus, fin exclue. Heures en UTC, précision possible jusqu'à 6 décimales. »
Tab depuis Fraction de début place le focus sur Date de fin, avec contour visible.
Une période refusée replace le focus sur Date de début. La région du tableau reste
focusable ; défilement au clavier confirmé (scrollLeft 53,33 px à 320 px).
Les boutons et les six contrôles mesurés ont une hauteur de 44 px.

### Recette complémentaire et captures finales

Build final, même serveur synthétique GET uniquement, sans backend ou base.
Ouverture réelle du calendrier natif, sélection du 21 octobre via son calendrier
au clavier puis confirmation : date 2026-10-21, heure 12:00:00 et fraction 123456
conservées. Appliquer produit 2026-10-21T12:00:00.123456Z.
Période inversée d'une microseconde : erreur, focus et brouillons conservés,
URL inchangée. Les traces avant/après comportent exactement les mêmes dix GET.
Appliquer une nouvelle borne puis Effacer est aussi vérifié sur le build final :
les six contrôles redeviennent vides, le contexte 7/9/12/17 reste dans l'URL.
Restauration avec offset sans édition confirmée sur le build final.
Trace de toute la recette UI 7.3.1 : 63 GET, aucun appel d'écriture.
Aucun warning ou erreur console relevé en fin de recette.

| Cible CSS | Mesurée | Disposition période | Tableau disponible / défilable |
| --- | ---: | --- | --- |
| 1440 | 1440 | Deux bornes et deux boutons sur une ligne, bas alignés | 1066 / 1066 px |
| 1024 | 1024 | Deux bornes côte à côte, actions en dessous | 650 / 650 px |
| 1023 | 1023 | Deux bornes côte à côte, actions en dessous | 905 / 905 px |
| 768 | 768 | Deux bornes compactes, actions en dessous | 666 / 666 px |
| 390 | 389 et 391 | Contrôles et boutons empilés | 319 / 608 puis 321 / 608 px |
| 320 | 320 | Contrôles et boutons empilés | 250 / 608 px |

Aucun scroll horizontal global : scrollWidth égale clientWidth aux sept mesures.
Seul le tableau défile sur mobile. Une cascade SCSS qui annulait les deux colonnes
sur tablette a été corrigée avant ces captures et la validation finale.
La cible 390 exacte reste réservée pour la raison de zoom documentée en section 6.
La capture à hauteur physique 850 échouait par intermittence ; hauteur réduite à
600 puis captures de page entière réussies. Les PNG bruts peuvent inclure une zone
vide du canevas du navigateur. Aucune recomposition ou retouche des images.
Le popup natif séparé est confirmé via l'arbre accessible et son interaction ;
il n'apparaît pas dans la capture de la page. La portabilité de son aspect sur tous
les navigateurs et appareils n'est pas certifiée, ni l'audit lecteur d'écran complet.

Pièces locales ignorées par Git, nouvelles captures UI 7.3.1 :

- [Desktop 1440](../frontend/tmp/ui-7.3.1/screenshots/measurements-list-1440.png),
  [1024](../frontend/tmp/ui-7.3.1/screenshots/measurements-list-1024.png),
  [1023](../frontend/tmp/ui-7.3.1/screenshots/measurements-list-1023.png).
- [Tablette 768](../frontend/tmp/ui-7.3.1/screenshots/measurements-list-768.png),
  [mobile 389](../frontend/tmp/ui-7.3.1/screenshots/measurements-list-390-near-389.png),
  [mobile 391](../frontend/tmp/ui-7.3.1/screenshots/measurements-list-390-near-391.png),
  [mobile 320](../frontend/tmp/ui-7.3.1/screenshots/measurements-list-320.png).
- [Focus de période mobile](../frontend/tmp/ui-7.3.1/screenshots/period-keyboard-320.png),
  [aides initiales](../frontend/tmp/ui-7.3.1/screenshots/hints-initial-320.png).
- [Mesures responsive](../frontend/tmp/ui-7.3.1/responsive.json),
  [synthèse navigateur](../frontend/tmp/ui-7.3.1/browser-summary.json),
  [trace HTTP synthétique](../frontend/tmp/ui-7.3.1/http-audit.json),
  [avant période invalide](../frontend/tmp/ui-7.3.1/audit-before-invalid.json),
  [après période invalide](../frontend/tmp/ui-7.3.1/audit-after-invalid.json),
  [bundle final](../frontend/tmp/ui-7.3.1/bundle-after.json).

UI 7.3.1 concerne huit fichiers du périmètre cumulé : les quatre fichiers de page,
measurement-time.ts, measurement-period-draft.ts et son test, et le présent rapport.
Les autres travaux UI 7.3 restent préservés. Les réserves backend de la section 7
restent ouvertes. Serveur de recette arrêté, override de viewport retiré et onglets
de recette fermés. Aucun accès PostgreSQL, changement backend ou package,
écriture métier, commit, push, rebase ou merge ; UI 7.4 non commencée.
