# UI 5.8 - Livraison du module Équipements industriels

20 octobre 2026. Branche feature/frontend-equipments, HEAD de référence
39e2f0dca6ef81c0d084d440b0060e13ea628bf0. Dépôt propre avant intervention.
Étape strictement documentaire : aucun changement applicatif, backend, package,
Docker ou PostgreSQL ; aucun test/build relancé, commit, push ou merge.

## Périmètre livré

Les décisions EQ-01 à EQ-07 de la [conception UI 5.1](etape-ui-5.1-equipments.md)
sont approuvées et implémentées :

- Liste paginée côté serveur, recherche explicite nom/code/type, filtres statut
  et criticité en français ; sélection entreprise puis site sans choix arbitraire.
  Références multipages, appartenance vérifiée, aucun GET liste sans site valide.
- Détail en lecture seule des données Equipment, dates et rattachement réel
  Equipment -> Site -> Company, indépendant du contexte URL. Libellés définitifs
  Site industriel et Entreprise de rattachement. Erreurs parent distinctes.
- Navigation Site vers Équipements et lien de retour vers le site réel ; contexte
  de liste company_id/site_id/search/status/criticality/page/page_size conservé.
- Création via EquipmentForm partagé, type libre, limites Unicode 150/100/100
  pour nom/code/type, code unique globalement ; défauts operational/medium.
  Entreprise/site préremplis seulement après validation du contexte.
- Modification des six champs éditables avec PATCH différentiel ; aucune requête
  sans différence ou après restauration des valeurs. Casse, espaces et Unicode
  non modifiés préservés ; description omise, vide et null distinctes.
  Rattachement et dates en lecture seule, suivi avant boutons d'action.
- Aucun company_id dans les écritures Equipment, aucun site_id ou métadonnée en
  PATCH, aucun transfert d'équipement ni DELETE frontend.
- Protection des brouillons, double soumission bloquée, saisies conservées après
  erreur, aucun retry automatique d'écriture incertaine. Toast unique après
  navigation réussie, confirmation accessible persistante et lien de récupération.
- Boutons harmonisés sur Nouvelle entreprise : variantes primaire/secondaire,
  hover/focus/active/disabled/loading et transitions partagés ; aides et noms
  accessibles préservés, aucun tooltip redondant ajouté.

Routes lazy : /equipments, /equipments/new, /equipments/:equipmentId/edit puis
/equipments/:equipmentId. Shell, Sidebar et 404 conservés. Les écrans de gestion
Capteurs, Mesures, Maintenance, Prédictions et Recommandations restent futurs.
Health Score, Failure Risk et RUL ne sont pas affichés dans cette fiche ; aucune
donnée prédictive inventée ni calcul ML lancé. Les agrégats Dashboard et les
fonctions ML backend existants ne constituent pas ces futurs écrans.

Architecture détaillée et contrats dans l'[architecture frontend](frontend-architecture.md#équipements-mvp---architecture-implémentée-ui-5).

## Résultats de validation conservés

| Preuve | Résultat et portée |
| --- | --- |
| UI 5.6.1, tests Angular | 864 réussis dans 49 fichiers ; non-régressions Create/List/Detail/Edit, Companies, Sites, Dashboard, transport, Shell et 404 |
| UI 5.6.1, build production | Réussi ; initial 604,81 ko (604 809 octets), budget warning 500 ko inchangé |
| UI 5.7, chaîne réelle | Angular 4201 -> FastAPI 8001 -> PostgreSQL 5434 / industrial_predict_dev ; identité, Alembic et compte applicatif non superutilisateur vérifiés |
| UI 5.7, écritures réelles | Un POST 201 puis un PATCH 200 limité à la description de UI57-EQ-20261020-01 ; corps exacts dans le rapport historique |
| UI 5.7, persistance | GET, actualisation Angular et lectures SQL concordants ; seules description et updated_at modifiées par le PATCH |
| UI 5.7, conservation | 36 lignes seed et 38 lignes préexistantes inchangées ; UI5-EQ-TEST-001 et essais Sites préservés ; un équipement fictif ajouté, conservé ; zéro orphelin sur neuf FK |
| UI 5.7, lectures réelles | Sélection, recherche, filtres, pagination, incohérence parent bloquée, Companies/Sites/Dashboard ; GET 404 et GET 422 réels |
| HTTP simulé | Erreurs POST/PATCH 409/422, double soumission, courses, navigation échouée, descriptions et protections de formulaire |

Les résultats viennent des rapports [UI 5.2](ui-5.2-equipments-data-access.md),
[UI 5.3](ui-5.3-equipments-list.md), [UI 5.4](ui-5.4-equipment-detail.md),
[UI 5.5](ui-5.5-equipment-create.md), [boutons](ui-buttons-harmonization.md),
[UI 5.6 et UI 5.6.1](ui-5.6-equipment-edit.md) et
[UI 5.7](ui-5.7-equipments-integration.md), conservés sans modification.
Les observations responsive couvrent 1440/1024/1023/768/390/320 px ; UI 5.6.1
documente le contrôle final de l'ordre à 1440/390/320 px. Les captures et traces
locales citées dans ces rapports sont ignorées par Git et ne font pas partie
de la livraison versionnée ; leurs liens dépendent du poste de validation.

Les journaux UI 5.6.1 conservés confirment 864/864 tests et le build de référence ;
les empreintes SHA-256 des 192 sources Angular correspondent au relevé validé.

Aucune nouvelle exécution Angular, build, requête HTTP ou opération PostgreSQL
dans UI 5.8. Les deux écritures appartiennent exclusivement à UI 5.7 ; les traces
initiales de UI5-EQ-TEST-001 restent indisponibles, sans payload reconstitué.

## Limites et dettes techniques

- Dialogue natif d'abandon non validé complètement dans un navigateur utilisateur.
  Confirm, garde Router et beforeunload couverts par les tests Angular.
- Erreurs d'écriture 409/422 et double clic concurrent vérifiés par simulation
  HTTP ; le 422 réel concerne un filtre GET. L'unicité SQL constatée ne remplace
  pas un nouvel essai réel de conflit. Aucune écriture supplémentaire nécessaire ici.
- Budget initial dépassé de 104,81 ko ; seuil d'erreur 1 Mo et budgets inchangés.
- Secrets historiques suivis dans backend/alembic.ini et docker-compose.yml :
  externalisation et renouvellement coordonnés nécessaires. Valeurs non affichées,
  non recopiées et fichiers inchangés dans cette branche.
- Authentification et autorisation multi-tenant absentes ; filtres et restrictions
  frontend ne constituent pas une protection des endpoints backend. Aucune
  déclaration de préparation à une production SaaS multi-tenant.
- Pas de suppression/transfert frontend, de verrou optimiste ou d'idempotence
  serveur promis ; résultat incertain à vérifier avant nouvelle tentative manuelle.
- Lecteur d'écran réel, zoom exhaustif 200/400 %, charge et concurrence serveur
  non validés. Appui maintenu et préférence de mouvement réduit définis en SCSS,
  sans émulation navigateur dans l'audit boutons.

## Audit Git et documents actualisés

- Branche et HEAD attendus confirmés. main et la référence locale origin/main :
  667fe5b978aeda5cebf2d7cabf62497c987e8da4. Aucun fetch dans cette étape ; ce
  constat ne garantit pas l'état distant au moment d'une future fusion.
- Comparaison main...HEAD : zéro commit de retard, huit à intégrer ; main est
  ancêtre de HEAD. Fusion fast-forward possible dans cet état local, sans conflit
  de fusion à résoudre. La présente documentation n'est pas encore commitée.
- Huit commits : f797c54 conception, ff3fed3 transport, c8af423 liste,
  37992ff détail, a874b4e création, 70d2a0f boutons, b4ffa06 édition,
  39e2f0d intégration. Périmètre commité : 52 fichiers, tous sous docs/ ou
  frontend/src/. Aucun backend, Docker, script DEV, migration ou dépendance modifié.
- Aucun nouveau secret, dump PostgreSQL, capture ou fichier temporaire dans les
  chemins et ajouts examinés. Les secrets historiques restent une dette ouverte.
- Six documents actualisés : docs/project-status.md, docs/roadmap.md,
  docs/frontend-architecture.md, docs/architecture.md, README_AI.md,
  frontend/README.md. Le présent rapport est le seul nouveau fichier.
- 100 liens documentaires locaux contrôlés sans erreur, git diff --check réussi ; index vide.
  État attendu en fin d'étape : ces sept documents seuls en attente de validation,
  HEAD inchangé et aucun fichier exécutable modifié.

## Checklist avant fusion

- [x] Relire UI 5.1 à UI 5.7 et les rapports de finitions ; conserver l'historique.
- [x] Distinguer implémentation, preuves réelles, HTTP simulé et limites natives.
- [x] Comparer commits et chemins à main ; contrôler secrets, artefacts et liens.
- [x] Contrôler git diff --check ; conserver les références tests/build sans relance.
- [ ] Obtenir validation de ce bilan et du diff documentaire.
- [ ] Sur autorisation distincte, indexer explicitement les sept documents,
  examiner diff indexé/check/stat et créer le commit documentaire final.
- [ ] Avant fusion autorisée, dépôt propre, fetch origin, revérifier HEAD source,
  main/origin/main, ascendance et éventuels nouveaux commits ; arrêter si divergence.
- [ ] Obtenir autorisation explicite de fusion ; privilégier ff-only si toujours possible.
- [ ] Vérifier ensuite HEAD des branches et dépôt propre ; publication distante
  uniquement sur autorisation séparée. Préserver la branche source.

Attendre validation avant le commit documentaire final et toute fusion.
Aucun module suivant commencé.
