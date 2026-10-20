# UI 6.4 - Fiche détail Capteur

20 octobre 2026. Branche `feature/frontend-sensors`, HEAD initial `b5d74e5`.
Branche, HEAD et dépôt propre vérifiés avant intervention.

## Périmètre et fichiers

La fiche est strictement en lecture seule. Aucun bouton Modifier, formulaire,
DELETE, transfert, mesure, compteur, graphique, prédiction ou appel de calcul.
UI 6.5 n'est pas commencée.

- `frontend/src/app/features/sensors/pages/sensor-detail/sensor-detail.component.ts` :
  état de lecture, résolution séquentielle et reprises indépendantes.
- Les fichiers `.html`, `.scss` et `.spec.ts` associés : présentation accessible,
  responsive et tests HttpTestingController.
- `frontend/src/app/features/sensors/sensors.routes.ts` et son test : route lazy détail.
- Les quatre fichiers `sensors-list.component.*` : activation du lien, focus visible
  et test de navigation depuis une page filtrée.
- Le présent rapport.

Les modèles et services UI 6.2, la façade et les filtres UI 6.3 restent inchangés.
Aucun changement backend, SQL, migration, Docker, package ou budget Angular.
Aucun accès ni écriture PostgreSQL. Aucun commit pendant l’implémentation initiale.
Le commit local est autorisé par la validation finale décrite ci-dessous ; aucun push ou merge.

## Contrat de lecture et routes

La route lazy `/sensors/:sensorId` complète `/sensors`, qui conserve son full-match.
Titre de page et Shell : « Détail capteur ». Les futures routes `new` et
`:sensorId/edit` devront précéder le détail. Elles ne sont pas implémentées :
`pathMatch: full` évite de capturer `/:sensorId/edit` ; `canMatch` réserve `new`
à la future création. Ces deux chemins aboutissent actuellement à la 404 globale,
sans GET Sensor. Un autre identifiant invalide ouvre une erreur locale.

Seuls les entiers décimaux positifs sûrs sont acceptés pour sensorId. Zéro,
négatifs, décimaux, notation exponentielle, texte et dépassement de précision
n'entraînent aucun appel HTTP.

Lectures unitaires, sans paramètres de liste :

1. GET `/api/v1/sensors/{sensorId}` avec SensorsApiService existant.
2. GET `/api/v1/equipments/{sensor.equipment_id}`.
3. GET `/api/v1/sites/{equipment.site_id}`.
4. GET `/api/v1/companies/{site.company_id}`.

Les trois lectures parentes utilisent ReferenceDataApiService existant. Chaque
clé étrangère est contrôlée avant requête et chaque `id` reçu doit correspondre
à la clé demandée. Aucun catalogue ni mesure n'est chargé pour cette fiche.
Les paramètres company_id/site_id/equipment_id de retour ne déterminent jamais
les parents affichés.

La fiche affiche nom, code métier, type libre, unité libre, statut Actif/Inactif,
description, équipement, site, entreprise et dates de création/modification.
Pas d'ID technique affiché comme libellé métier. businessReferenceLabel combine
nom/code sans doublon. Les interpolations Angular échappent le texte métier.
Description absente, vide ou blanche : « Non renseignée », sans mutation du DTO.
Les sauts de ligne sont conservés. Un statut inconnu affiche « Non disponible ».

Les dates réutilisent formatAdministrativeDateTime : pas de fuseau inventé pour
une date naïve ; un offset explicite est affiché en UTC ; date invalide ou absente :
« Non disponible ». La note horaire reprend la convention Equipment Detail.

## États, références et réponses tardives

Chargement Sensor : indicateur partagé et aria-busy. Échec Sensor : pas de fiche
vide, 404 dédiée « Capteur introuvable (404) », retour à la liste disponible.
401/403 : accès refusé ; 400/422 : référence refusée ; réseau/5xx : erreur et
reprise manuelle. Pas de reprise automatique.

Dès que le Sensor est reçu et son identité vérifiée, ses champs restent visibles
pendant les lectures parentes. Une référence indisponible ou incohérente produit
une erreur distincte dans sa section ; les descendants attendent, les données déjà
résolues sont conservées. Aucun remplacement par des parents de l'URL.

Chaque niveau possède une reprise indépendante, disponible seulement pour réseau
ou 5xx. Elle recharge ce parent puis ses descendants, sans recharger Sensor ni
ses ancêtres. Une incohérence d'identité ou de clé est non réessayable.

switchMap annule toute la chaîne précédente quand sensorId change. toSignal
libère les souscriptions à la destruction. Un changement des seuls paramètres de
retour ne déclenche aucune relecture. Les tests vérifient l'annulation à chacun
des quatre stades ainsi que la navigation vers un ID invalide et la destruction.

## Navigation contextuelle

Le nom dans la liste est un vrai RouterLink clavier vers le détail, avec le
snapshot appliqué : company_id, site_id, equipment_id, page, page_size, search,
status. Aucun changement des filtres, du brouillon ou de la page de la liste.

« Retour à la liste des capteurs » conserve ces sept paramètres validés selon les
bornes UI 6.3 : IDs positifs sûrs, statut exact, recherche trimée de 1 à 100,
page positive, taille de 1 à 100. Défauts page 1/taille 20. Les paramètres inconnus,
fragments et returnUrl libres ne sont pas propagés. Aucun parent réel n'est injecté
comme choix par défaut. Un accès direct sans contexte retourne donc à une liste
qui attend une sélection explicite, sans GET Sensors global.

Une notice explique une différence connue entre contexte et chaîne réelle, en
conservant le retour d'origine. La validation des parents du contexte reste
assurée par la liste lors du retour.

Le lien équipement s'active dès que son identité réelle est résolue. Sa destination
est `/equipments/{id}`, avec site_id réel s'il est valide et company_id issu du
site réel lorsqu'il est résolu. Une panne du site ou de l'entreprise ne retire
pas un équipement déjà vérifié. Aucun search/status/page Sensors n'est réutilisé
comme filtre Equipment. Le détail Equipment conserve son comportement existant ;
un retour réciproque Equipment -> fiche Sensor n'est pas ajouté ici.

## Validation

Commandes depuis frontend, sans package ajouté :

```text
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.4/vitest.config.mjs --include=src/app/features/sensors/**/*.spec.ts --include=src/app/app.routes.spec.ts
npm.cmd test -- --watch=false --runner-config=tmp/ui-6.4/vitest.config.mjs
npm.cmd run build -- --configuration production
```

Le runner temporaire ignoré par Git limite Vitest à deux workers. Aucun test
exclu, aucun timeout augmenté. Les tentatives dans le bac à sable Windows ont
échoué avant exécution sur des accès temporaires/realpath EPERM. Les tests ont
ensuite tourné avec autorisation hors bac à sable, sans accès backend.

Premier ciblage effectif : 187 réussis, un échec dans le matcher du test de retour
à la liste, qui attendait une URL sans paramètres. Matcher corrigé ; ajout d'un
scénario de clic liste -> détail. Ciblage final : **189 tests réussis dans six
fichiers**, compilation 17,278 s et Vitest 17,24 s.

Suite complète : **1 032 tests réussis dans 54 fichiers**, compilation 20,602 s et
Vitest 40,03 s. Référence UI 6.3 : 977 tests dans 53 fichiers, soit 55 scénarios
supplémentaires : 52 pour la nouvelle fiche, deux pour le routage et un pour le
clic depuis la liste.

Couverture : les onze libellés métier, séquence des quatre GET, chargements
intermédiaires, IDs invalides, 404/réseau/400/401/403/422/500 Sensor, erreurs
réseau/401/403/404/422/500 des trois références, reprise locale, identités
incohérentes, clés étrangères invalides, réponses obsolètes, destruction,
contexte contradictoire, query seule, retour liste et absence de fuite des
filtres Sensors vers Equipment, texte échappé, description et dates absentes,
statut inconnu, lien focusable et absence d'action d'écriture.

Build production **réussi**, 23,429 s. Bundle initial : **604 900 octets
(604,90 kB)**, identique à UI 6.3, transfert estimé 153,82 kB. Chunk lazy détail :
13 126 octets ; liste : 28 459 octets. Ensemble JS/CSS : 42 fichiers,
920 739 octets, contre 40 fichiers et 907 241 octets en UI 6.3, soit +13 498 octets.
L'extraction de dépendances communes explique la réduction du chunk liste par
rapport aux 30 096 octets antérieurs ; le détail n'est pas chargé dans l'initial.

L'avertissement initial existant reste présent : budget warning 500 kB dépassé
de 104,90 kB. Budget error 1 MB et budgets de styles 4/8 kB inchangés. Aucun
budget augmenté.

## Recette visuelle et captures

Build production servi exclusivement sur 127.0.0.1:8099 par un serveur temporaire
GET-only à réponses synthétiques. Aucun proxy ni upstream, aucun appel au backend
applicatif. Serveur arrêté et viewport réinitialisé après recette. Le navigateur
n'a signalé aucune erreur ou warning console lors du contrôle final.

L'audit local recense 30 GET API synthétiques : quatre lectures Sensor unitaires
sans query, deux listes Sensors avec equipment_id/statut/page/taille uniquement,
et les références parentes/catalogues nécessaires. Aucune écriture, aucun
company_id/site_id dans les requêtes Sensors, aucune mesure ou prédiction.

| Largeur cible CSS | innerWidth mesuré | Colonnes fiche | Résultat |
| --- | --- | --- | --- |
| 1440 | 1440 | 2 | Lisible, navigation latérale visible |
| 1024 | 1024 | 2 | Lisible, navigation latérale visible |
| 1023 | 1023 | 2 | Navigation repliée, pas de débordement |
| 768 | 768 | 2 | Lisible, lien retour sur la ligne du titre |
| 390 | 389 et 391 | 1 | Lisible aux deux arrondis, réserve de mesure exacte |
| 320 | 320 | 1 | Bouton retour, références et dates lisibles |

Réserve explicite : le navigateur intégré applique un zoom de 0,75 et n'accepte
que des dimensions entières de viewport. La largeur 390 CSS exacte demanderait
292,5, refusée par l'API. Les réglages entiers adjacents donnent innerWidth 389
et 391. Les deux ont été contrôlés et capturés, sans prétendre à une preuve
exacte à 390. Les autres largeurs mesurées correspondent aux cibles.

Aucun débordement horizontal du document dans les sept mesures ; le mobile
utilise un défilement vertical normal. Vérification visuelle des descriptions,
libellés, dates et liens à chaque largeur. Les captures JPEG complètes peuvent
avoir une résolution en pixels image différente des dimensions CSS mesurées.

Scénarios navigateur : lien équipement ouvre sa fiche réelle avec site/entreprise
sans filtres Sensors ; retour navigateur vers Sensor ; Tab depuis le retour liste
place le focus sur l'équipement avec contour visible ; retour liste conserve le
statut inactive et page 2, affichant la page hors plage attendue avec 11 résultats ;
reprise manuelle page 1 puis clic sur le nom ouvre le détail avec le même statut
et la page 1. Un capteur synthétique dont l'équipement est absent garde tous ses
champs, affiche une erreur de référence et la notice de contexte différent.

Captures locales, ignorées par Git :

- [1440](../frontend/tmp/ui-6.4/screenshots/sensor-detail-1440.jpg),
  [1024](../frontend/tmp/ui-6.4/screenshots/sensor-detail-1024.jpg),
  [1023](../frontend/tmp/ui-6.4/screenshots/sensor-detail-1023.jpg),
  [768](../frontend/tmp/ui-6.4/screenshots/sensor-detail-768.jpg).
- Cible 390 : [389 mesurés](../frontend/tmp/ui-6.4/screenshots/sensor-detail-390-cible-389-mesures.jpg),
  [391 mesurés](../frontend/tmp/ui-6.4/screenshots/sensor-detail-390-cible-391-mesures.jpg).
- [320](../frontend/tmp/ui-6.4/screenshots/sensor-detail-320.jpg),
  [focus clavier 320](../frontend/tmp/ui-6.4/screenshots/sensor-detail-320-focus.jpg),
  [équipement absent](../frontend/tmp/ui-6.4/screenshots/sensor-detail-reference-404.jpg).

Les scripts de recette, runner, audit HTTP, mesures responsive et captures sont
placés dans frontend/tmp/ui-6.4, entièrement ignoré par Git. Ils ne font pas
partie des onze fichiers livrés.

git diff --check réussi sur les sources finales ; contrôle de contenu également
appliqué aux nouveaux fichiers. Index vide, HEAD inchangé : b5d74e5.

## Réserves

La recette isolée et les tests HTTP simulés ne constituent pas une recette
PostgreSQL ni une preuve de sécurité tenant. Les réserves B-SEN-02/03 et
l'absence d'authentification/isolation métier backend restent inchangées.
B-SEN-01 a été livré auparavant ; cette étape n'utilise aucune écriture Sensor.
Les incohérences sont détectées entre réponses successives, sans garantie
d'instantané transactionnel ou de version fournie par l'API.

## Validation finale avant commit

UI 6.4 est techniquement approuvée par l’utilisateur. Le commit local est autorisé
après vérification du message de défilement, du périmètre et des contrôles finaux.

Le message « Sur petit écran, faites défiler le tableau horizontalement. » était
encore affiché sur desktop. Correction limitée au SCSS de la liste : la zone de
résultats devient un conteneur nommé sensor-results ; l’aide est masquée par défaut
et affichée uniquement si sa largeur de contenu est inférieure aux 38 rem minimum
du tableau. Aucune logique TypeScript, aucun filtre, aucune pagination modifiés.
Cette condition évite aussi une aide inutile sur un petit écran où le tableau tient.

Les assertions du test de liste vérifient le texte unique dans les résultats,
l’absence d’aide sur une liste vide et sur une page hors plage. JSDOM n’effectue
pas la mise en page des container queries : visibilité et débordement sont donc
contrôlés dans le navigateur sur le build production.

Ciblage après correction : 189 tests réussis dans six fichiers, compilation
16,222 s et Vitest 13,15 s. Suite complète après correction : **1 032 tests réussis dans 54 fichiers**,
compilation 15,477 s et Vitest 31,21 s. Build production à nouveau réussi en
22,049 s, sans changement de budget. Bundle initial : 604 900 octets, transfert
estimé 153,81 kB ; warning 500 kB inchangé. Le chunk liste et le total JS/CSS
ci-dessus décrivent le build initial UI 6.4 ; les tailles après correction sont
consignées ci-dessous : chunk liste 28 658 octets ; total JS/CSS 920 938 octets
pour 42 fichiers, soit +199 octets par rapport au build UI 6.4 initial.

Le contrôle navigateur sur données GET synthétiques compare la visibilité de
l’aide au débordement réel (scrollWidth > clientWidth) :

| Largeur CSS mesurée | Largeur disponible du tableau | Largeur défilable | Aide |
| --- | --- | --- | --- |
| 1440 | 1066 | 1066 | Masquée |
| 1024 | 650 | 650 | Masquée |
| 1023 | 905 | 905 | Masquée |
| 768 | 666 | 666 | Masquée |
| 700 | 614 | 614 | Masquée |
| 640 | 554 | 608 | Visible |
| 391 (cible 390) | 321 | 608 | Visible |
| 320 | 250 | 608 | Visible |

Les huit assertions de cohérence passent. La réserve d’arrondi de la cible 390
reste celle documentée plus haut. La recette complète les tests JSDOM ; aucun
fichier de test exécutable, script ou package supplémentaire n’est ajouté au commit.

Captures après correction : [desktop](../frontend/tmp/ui-6.4/screenshots/sensors-list-scroll-help-desktop.jpg)
et [mobile](../frontend/tmp/ui-6.4/screenshots/sensors-list-scroll-help-mobile.jpg).
Les versions complètes à 1440 et 320 ainsi que scroll-help-responsive.json sont
aussi disponibles dans frontend/tmp/ui-6.4, ignoré par Git. Serveur arrêté et
viewport réinitialisé après le contrôle.

Point d’arrêt : UI 6.5 non commencée. Aucun push ni merge autorisé.
