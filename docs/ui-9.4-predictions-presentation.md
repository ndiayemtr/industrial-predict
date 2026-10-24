# UI 9.4 — Présentation métier des prédictions

## Périmètre

Branche `feature/frontend-predictions`, base vérifiée propre à
`3600d8e461f8c38ca00e2277b57e0c49374773b9`. Les décisions PRE-05, PRE-07,
PRE-08, PRE-09, PRE-12 et PRE-16 ont été relues avec les bilans UI 9.2/9.3.
Seule la présentation Predictions évolue. UI 9.5 n'est pas commencée.

Les 14 champs de PredictionRead, le transport GET, la façade, la cascade
Entreprise → Site → Équipement, les filtres appliqués/brouillons, les instants
inclusifs avec égalité, offsets et microsecondes, les états et la pagination
serveur sont conservés. Aucun routage global ou Equipment Detail modifié.

## Fichiers

Quatre fichiers existants modifiés dans
`frontend/src/app/features/predictions/pages/predictions-list/` :

- `predictions-list.component.ts` : état local des panneaux et présentation.
- `predictions-list.component.html` : six colonnes et panneaux dépliables.
- `predictions-list.component.scss` : proportions, valeurs et panneaux.
- `predictions-list.component.spec.ts` : rendu actualisé et tests de dépliage.

Huit nouveaux fichiers dans `frontend/src/app/features/predictions/` :

- `utils/prediction-display.ts` et `utils/prediction-display.spec.ts`.
- `utils/prediction-json-preview.ts` et `utils/prediction-json-preview.spec.ts`.
- `components/prediction-details/prediction-details.component.ts`.
- `components/prediction-details/prediction-details.component.html`.
- `components/prediction-details/prediction-details.component.scss`.
- `components/prediction-details/prediction-details.component.spec.ts`.

Ce rapport est le neuvième nouveau fichier : **13 fichiers au total**.
Les tokens et la mixin d'action partagés sont réutilisés sans modification.

## Règles métier

| Type | Présentation |
| --- | --- |
| anomaly | « Indice d’anomalie », score déclaré conservé ; aucune probabilité ou niveau inféré |
| failure_risk | « Score de risque déclaré », sans `%` ; probabilité distincte seulement si `details.failure_probability` est un nombre fini dans [0,1], affiché sur cette échelle sans arrondi |
| health_score | « Indice de santé » ; `/ 100` réservé au profil déclaré du producteur audité ; aucune échelle déduite de la seule valeur |
| rul | « Durée de vie utile restante », score en heures, zéro conservé ; divergence avec `details.rul_hours` signalée sans correction ; aucune date de panne extrapolée |

La reconnaissance santé est volontairement prudente : type `health_score`,
`model_name === 'health_score'`, version déclarée `null` et quatre composantes
valides correspondant au profil persisté audité en UI 9.1. Nom inconnu, version
non auditée ou composantes absentes/invalides : valeur brute et avertissement
d'échelle non confirmée. Ce rapprochement avec le contrat connu ne constitue
pas une authentification de la provenance. Une valeur hors [0,100] du profil
reconnu est signalée et conservée, sans écrêtage ni ajout de `/ 100`.

Les quatre composantes sont des nombres finis dans [0,100] : `failure_health`,
`anomaly_health`, `data_quality_health`, `maintenance_health`. Elles sont
présentées séparément si toutes sont valides ; l'unité `/ 100` suit la même
reconnaissance du producteur. Les propriétés supplémentaires restent dans le
JSON. Aucune moyenne ou recommandation n'est calculée.

Seuls les niveaux connus du type sont traduits : risque
`low/medium/high/critical`, santé `healthy/good/degraded/poor/critical`, RUL
`critical/warning/watch/healthy`. Aucun dictionnaire de niveaux pour anomalie.
Les autres chaînes restent textuelles, y compris les espaces. `null` et chaîne
vide sont distincts. L'alerte garde « Oui », « Non », « Non renseignée » pour
true, false, null. Aucun seuil ni niveau recalculé ; aucune information portée
uniquement par la couleur.

## Détails et JSON

Chaque bouton natif Détails possède un nom accessible propre à l'identifiant,
`aria-expanded` et, lorsque le panneau existe, `aria-controls`. Le panneau
est une section nommée par ce bouton. Entrée/Espace déclenchent l'action native ;
le focus reste sur le bouton. Plusieurs panneaux peuvent être ouverts ; ils
sont supprimés lorsque les résultats quittent l'état chargé. Aucun GET, URL,
filtre ou numéro de page ne dépend de cette action.

Le panneau présente nom/version du modèle, horizon en heures, `created_at`
séparé de `predicted_at` dans la ligne, puis références capteur/mesure sans
lien. Les chaînes ISO et leurs offsets/fractions sont affichés tels que reçus.
Les métadonnées nulles ou vides sont explicites. Motif texte, probabilité,
composantes et durée RUL sont validés individuellement ; les champs invalides
restent dans le JSON avec une notice, sans coercition.

Le JSON est construit progressivement, puis rendu par interpolation échappée,
sans `innerHTML`, lien, script, explication ou recommandation générée. Objets,
tableaux, null, false et zéro sont conservés. Les valeurs inattendues et cycles
sont traités défensivement. Au plus **10 000 caractères** de texte JSON et
**six niveaux de conteneurs** (racine comprise) : le septième est remplacé par
un marqueur. Une troncature affiche un avertissement ; le texte tronqué n'est
pas nécessairement un document JSON complet. L'objet reçu n'est jamais modifié.
La limite porte uniquement sur cet aperçu frontend, jamais sur le volume HTTP,
la taille autorisée par le backend ou ses risques de stockage/traitement.

## Vérifications

Tests ciblés après stabilisation : **413 réussis sur 10 fichiers**, commande
`ng test --watch=false --include=src/app/features/predictions/**/*.spec.ts --runner-config=tmp/ui-8.8/vitest.config.mjs --progress=false`.
Une première compilation a révélé un typage ambigu dans une fixture vide ;
il a été corrigé avant la passe réussie. Aucun test n'avait alors été exécuté.

Les tests couvrent types, scores limites, profil santé inconnu/incompatible,
niveaux, alertes, probabilités, composantes, RUL contradictoire/nulle, métadonnées,
dates, échappement, JSON vide/profond/volumineux, bornes de rendu, maintien du
focus, absence de HTTP/navigation au dépliage et fermeture lors d'une pagination.
Les tests HTTP et temporels UI 9.2/9.3 restent inclus. Les touches natives sont
vérifiées dans le navigateur, et non simulées par un clic dans le DOM de test.

Une seule suite Angular complète : **2 325 tests réussis sur 82 fichiers**,
`ng test --watch=false --runner-config=tmp/ui-8.8/vitest.config.mjs --progress=false`.
Durée Vitest 59,57 s ; compilation des tests 30,170 s.

Un seul build production : **réussi**, `ng build --configuration production
--progress=false`, durée 24,903 s. Bundle initial : **605 998 octets**
(606,00 kB affichés, transfert estimé 153,92 kB), somme des neuf fichiers
initiaux effectivement émis. Inchangé par rapport à UI 9.3. L'avertissement
préexistant de dépassement du budget initial 500 kB (+106,00 kB) demeure ;
budgets et dépendances inchangés. La route globale restant un placeholder,
ce bundle ne prouve pas l'intégration de Predictions au routage applicatif.
Le composant est compilé et exercé par les tests et la revue isolée.

Exécutions séquentielles : ciblés, revue isolée arrêtée, suite complète,
build production. Aucun changement de source après les validations réussies.
Journaux ignorés : `frontend/tmp/ui-9.4/targeted.log`, `full-tests.log`,
`build.log` ; mesures dans `frontend/tmp/ui-9.4/responsive.json`.

## Revue isolée dans le navigateur

Lanceur temporaire ignoré `frontend/tmp/ui-9.4/preview/`, composant et route
interne réels, six fixtures en mémoire. L'intercepteur répond à chaque GET
autorisé et bloque tout autre appel sans transmettre au réseau métier. Aucun
accès PostgreSQL DEV, backend ou calcul ML. Ces fixtures ne prouvent pas la
présence de prédictions réelles ; recette DEV différée à UI 9.6.

Entrée ouvre, Espace ferme ; focus conservé, contour solid et cible de 44 px
constatés. Probabilité fournie égale à zéro, quatre composantes santé, RUL 0 h
avec détail 2 h, métadonnées et dates distinctes constatées. Le motif contenant
`<img ...>` reste du texte : aucun nœud img/script créé. Les deux troncatures
(longueur et profondeur) affichent leur avertissement, aperçu long de 10 000
caractères mesuré. L'URL est inchangée lors du dépliage.

| Largeur CSS | scrollWidth document, fermé/ouvert | Zone tableau | Débordement global |
| --- | --- | --- | --- |
| 320 | 300 / 300 | 250 | Aucun |
| 390 | 370 / 370 | 320 | Aucun |
| 768 | 748 / 748 | 682 | Aucun |
| 1440 | 1420 / 1420 | 1334 | Aucun |

Le tableau mesure au moins 960 px et défile dans sa région ; les panneaux sont
dans cette région. Les 20 px de différence correspondent au défilement vertical.
Le viewport du navigateur applique un facteur 0,75 : les dimensions physiques
240/576/1080 donnent 320/768/1440 CSS. Le cas 390 CSS exact utilise un iframe
390 px du seul lanceur ignoré, mesuré à l'intérieur du cadre. Les lignes
fermées courantes mesurent environ 61 px ; celles avec avertissement explicite
environ 111 à 132 px. Les trois actions de filtres conservent hauteur minimale
44 px et regroupement à gauche ; le libellé long se replie à 320 px.

Limites de la première passe : les captures pleine page et viewport ont échoué dans
l'outil. Aucune image de cette passe n'est donc présentée comme revue visuelle
achevée. Vérifications fondées sur DOM rendu, mesures CSS et clavier ; validation
visuelle utilisateur encore attendue. Aucune erreur console sur la page directe.
Le cadre 390 a journalisé une erreur MutationObserver (« parameter 1 is not of
type Node »), origine non établie ; aucun MutationObserver dans les nouveaux
composants. Les contrôles du cadre ont néanmoins abouti. Aucune conclusion de
compatibilité lecteur d'écran ou de zoom réel 200/400 % n'est revendiquée.
Dimensions réinitialisées, onglets fermés et serveur de revue 4213 arrêté.

### Complément de revue finale — 24 octobre 2026

Le même dispositif isolé issu de UI 9.3, conservé dans
`frontend/tmp/ui-9.4/preview/`, a été relancé sans modifier ses fixtures ni les
sources de l'application. Branche et HEAD revérifiés conformes. Les empreintes
des fichiers Predictions avant/après revue sont identiques. Aucun test ni build
production relancé ; seule la compilation de développement du lanceur a eu lieu.

Nouvelle preuve obtenue : **deux captures viewport réussies**, après affichage
de la prévisualisation dans le navigateur intégré. La tentative pleine page
effectuée auparavant en arrière-plan a renvoyé uniquement « Unable to capture
screenshot », sans code d'erreur ou cause interne accessible. Le succès après
affichage et changement de mode de capture est constaté ; il ne permet pas
d'attribuer avec certitude l'échec à l'un de ces paramètres.

- `frontend/tmp/ui-9.4/final-table-viewport.png` : six lignes, dont les quatre
  types, et six colonnes visibles ensemble à 1440 × 1000 px CSS.
- `frontend/tmp/ui-9.4/final-details-viewport.png` : panneau anomalie ouvert,
  métadonnées en deux colonnes, motif fourni et aperçu JSON échappé.
- `frontend/tmp/ui-9.4/final-long-json.png` : contrôle complémentaire du panneau
  santé de provenance inconnue, avertissement de troncature et JSON long.

Ces images proviennent exclusivement des fixtures synthétiques : noms
« Entreprise fictive A », « Site fictif de production », équipement de
démonstration ; bandeau « REVUE ISOLÉE - DONNÉES FICTIVES - Aucun accès DEV. »
présent en tête de page, hors viewport des captures centrées sur le tableau.
Elles restent des artefacts locaux ignorés, sans données DEV. Leur netteté
limitée permet la revue de disposition ; les textes exacts sont confirmés par
le DOM et non déduits de pixels peu nets.

Disposition constatée : en-têtes alignés avec les six colonnes, valeurs et
libellés séparés, niveaux/alertes textuels, boutons Détails alignés, panneau
sur toute la largeur du tableau, sans chevauchement visible. Valeurs confirmées
dans le DOM : anomalie 0.85, risque 75 sans `%`, santé 85 / 100 du profil reconnu,
RUL 0 h avec avertissement de divergence ; niveaux « Non renseigné », « Élevé »,
« Sain », « Critique » et alertes non renseignée/non/oui distinctes.

Entrée ouvre le panneau, Espace le ferme : `aria-expanded` true puis false,
panneau retiré et focus conservé sur le bouton avec contour solid. Date
d'enregistrement `2026-10-23T12:00:01.654321Z` conservée, distincte de la date de
prédiction avec offset +05:30. Le motif `<img ...>` reste du texte ; zéro nœud
img/script dans les détails. URL inchangée. Le JSON long de 10 000 caractères
est replié (`pre-wrap`, `overflow-wrap: anywhere`) dans une zone de hauteur
318 px, scrollHeight 1008 px, défilement vertical auto ; largeur 1280 px et
scrollWidth 1280 px. Aucun débordement global : document 1420 px pour viewport
1440 px. La fermeture retire aussi ce panneau. Aucune erreur/warn console
relevée sur cette page directe. Mesures dans `final-long-json.json`, ignoré.

Aucune correction de code requise par ces observations. Serveur isolé arrêté,
onglet fermé et viewport/visibilité du navigateur réinitialisés. Cette passe
complète les preuves de présentation ; validation finale utilisateur attendue.

## Risques B-PRE conservés

| Risque | Situation UI 9.4 |
| --- | --- |
| B-PRE-01 | Authentification, autorisation de ressource et sécurité multi-tenant absentes ; toujours bloquant pour production SaaS, cascade UI insuffisante |
| B-PRE-02 | Scores et niveaux backend génériques inchangés ; présentation prudente sans probabilité ou seuil inventé |
| B-PRE-03 | Dates et période backend non durcies ; validation client inclusive, offsets et précision conservés |
| B-PRE-04 | Intégrité des références capteur/mesure non garantie ; aucun lien automatique |
| B-PRE-05 | JSON backend générique et volumineux possible ; aperçu borné/échappé seulement, aucune limite réseau/backend ajoutée |
| B-PRE-06 | Cascades de suppression backend inchangées ; aucune suppression UI |
| B-PRE-07 | OFFSET/COUNT distincts, concurrence et index inchangés ; pagination serveur conservée |
| B-PRE-08 | Risques des POST RUL et artefacts inchangés ; aucun calcul ou endpoint de mutation appelé |
| B-PRE-09 | Historique non alimenté par l'UI ; aucune génération automatique, vide neutre |
| B-PRE-10 | Données historiques et provenance parfois invalides/incomplètes ; validation HTTP conservée et limites de provenance déclarée explicites |
| B-PRE-11 | Aucun endpoint détail/latest ajouté ; détails issus uniquement du GET de liste |

## État Git

Branche `feature/frontend-predictions` et HEAD
`3600d8e461f8c38ca00e2277b57e0c49374773b9` inchangés. `main` et `origin/main`
locaux restent à `05545a88dcd45940f00c1c029d9e567a9c5a4cee` ; aucun fetch.

État final : quatre fichiers suivis modifiés, neuf nouveaux fichiers non suivis,
index vide. `git diff --check` et contrôle des espaces des nouveaux fichiers
réussis. Relecture du diff et recherche de secrets : aucun secret, fichier
temporaire, fixture persistée ou artefact dans les 13 fichiers proposés.
Preview, données fictives en mémoire, mesures et journaux restent ignorés.

Aucun changement backend, modèle/transport API, façade, route globale,
Equipment Detail, migration, SQL, package ou budget. Aucun accès DEV,
PostgreSQL, Docker ou calcul ML ; aucun POST/PATCH/DELETE. Aucun commit, push,
merge ou rebase effectué. Rapport et implémentation en attente de validation
technique et visuelle ; UI 9.5 non commencée.
