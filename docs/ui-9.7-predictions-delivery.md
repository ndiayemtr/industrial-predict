# UI 9.7 - Livraison documentaire du MVP Prédictions

Date : 25 octobre 2026. **Documentation préparée, validation utilisateur attendue.**
Branche `feature/frontend-predictions` ; HEAD inchangé
`edb7b6c5e1bc1e8f17ba6f5ed4668c0fe2a6e3f2`.
Aucun commit, push, merge ou rebase effectué pour UI 9.7.

## 1. Objectif et périmètre

Préparer la livraison Git du MVP de consultation des prédictions déjà persistées.
Mission exclusivement documentaire : six documents de suivi synchronisés et ce
rapport créé. Aucun code exécutable, contrat API, migration, package ou budget
modifié. Aucun test Angular, build, accès HTTP/PostgreSQL, Docker, seed ou calcul
ML exécuté ; les résultats ci-dessous sont historiques, réutilisés sans relance.

Les six rapports historiques sont conservés intégralement, sans réécriture de
leurs statuts datés ni de leurs validations :

- [UI 9.1 - Conception](etape-ui-9.1-predictions.md), PRE-01 à PRE-16 acceptées.
- [UI 9.2 - Modèles et GET](ui-9.2-predictions-data-access.md).
- [UI 9.3 - Liste et filtres](ui-9.3-predictions-list.md).
- [UI 9.4 - Présentation](ui-9.4-predictions-presentation.md).
- [UI 9.5 - Navigation](ui-9.5-predictions-navigation.md).
- [UI 9.6 - Recette DEV partielle](ui-9.6-predictions-integration.md).

La mention historique de 15 champs dans UI 9.1 est une erreur de comptage
documentée dès UI 9.2 : PredictionRead contient exactement **14 champs réels**.
UI 9.1 est déjà intégré et publié selon la référence de livraison fournie ;
Git confirme sa présence dans main et origin/main locaux à `05545a8`.
Aucun fetch : l'état actuel du serveur distant n'est pas vérifié en direct.

## 2. Architecture réellement implémentée

Sidebar -> `/predictions`, lazy loadChildren PREDICTION_ROUTES puis loadComponent
PredictionsListComponent standalone OnPush. Une seule route interne, full-match ;
aucune page détail autonome ni route new/edit. Le Shell et ses titres/focus restent
partagés. La [description frontend](frontend-architecture.md) est synchronisée.

PredictionsListFacade locale utilise signals/switchMap et le cycle DestroyRef.
ReferenceDataApiService fournit les catalogues paginés et les parents réels ;
la chaîne Equipment -> Site -> Company est vérifiée avant GET historique.
Aucun choix automatique, cache global multi-équipements ou chargement exhaustif.
Les lectures obsolètes sont annulées ; aucun appel supplémentaire par ligne.

PredictionsApiService expose uniquement
`GET /api/v1/equipments/{equipment_id}/predictions`, avec Page partagé.
Whitelist : page, page_size, prediction_type, level, is_alert, start_time, end_time.
Ni company_id ni site_id vers cet endpoint. IDs et pagination validés, page >=1,
taille 1..100, niveau de filtre libre de 1 à 50 caractères ; false explicite.
Validation défensive unknown -> DTO/page, sans coercition ni valeur inventée :
14 champs, huit nullables, enum exact, nombres finis, dates avec offset,
JSON récursif typé sans any et appartenance de chaque ligne à l'équipement demandé.

La comparaison temporelle réutilise le helper précis de Measurements, avec une
validation dédiée inclusive autorisant l'égalité. La convention exclusive des
autres modules n'est pas transposée. Détails locaux via PredictionDetailsComponent,
utils de présentation/JSON et contexte de navigation typé whitelisté.

## 3. Fonctionnalités livrées

- Route lazy /predictions depuis la Sidebar ; sélection explicite Entreprise ->
  Site -> Équipement, rattachements réels et contextes contradictoires contrôlés.
- Historique GET paginé, taille initiale 20, choix 20/50/100 et tailles URL valides
  1..100 conservées. États attente/chargement/historique vide/aucun résultat filtré/
  hors plage/erreur distincts ; récupération et retry manuels.
- Filtres type, niveau, alerte et période ; URL comme état appliqué et brouillons
  séparés. Changement de filtre/taille remet la page à 1.
- Période `predicted_at [début, fin]`, bornes inclusives et égalité autorisée,
  y compris mêmes instants à offsets différents. Chaînes ISO, offsets et précision
  jusqu'à six décimales conservés, aucune normalisation silencieuse.
- anomaly : indice déclaré ; failure_risk : score déclaré sans pourcentage
  inféré, probabilité séparée seulement si valide ; health_score : échelle /100
  réservée au profil producteur audité reconnu ; rul : durée en heures sans
  extrapolation de date de panne. Aucune échelle déduite de la seule valeur.
  Reconnaître un profil ne constitue pas une authentification de sa provenance.
- Niveaux déclarés et inconnus conservés, alertes Oui/Non/Non renseignée, sans
  recalcul de seuil. predicted_at et created_at présentés séparément.
- Détails dépliables, métadonnées et JSON échappé, textes longs et null explicites,
  sans innerHTML ni liens descendants à partir de sensor_id/measurement_id.
  Aperçu limité à 10 000 caractères et six niveaux uniquement côté présentation :
  ni le volume réseau ni la taille autorisée par le backend ne sont bornés ainsi.
- Equipment <-> Predictions : retour contextuel `pre_` avec filtres appliqués,
  false, période et pagination préservés. Voir les prédictions / Retour aux
  prédictions exclusifs ; retour liste, capteurs, interventions et Modifier
  préservés. Repli de Modifier sur deuxième ligne approuvé.
- Aucun POST, PATCH, DELETE, polling ou calcul ML dans le module ; aucune
  génération automatique de prédictions ni modèle de remplacement.

### Rapprochement des décisions PRE avec les preuves

| Décision | Réalisation / preuve historique et limite |
| --- | --- |
| PRE-01 | GET seul UI 9.2 à UI 9.6 ; aucun calcul ou écriture métier |
| PRE-02 | Sélections explicites, catalogues et blocage UI 9.3 ; parcours Angular UI 9.6 |
| PRE-03 | IDs/FK et équipement des lignes validés en tests isolés ; chaîne réelle SQL/Angular UI 9.6, aucune ligne Predictions réelle |
| PRE-04 | URL appliquée/brouillons/false/page en UI 9.3/9.5 ; restauration observée UI 9.6 |
| PRE-05 | DTO 14 champs et validation défensive UI 9.2 ; schéma SQL confirmé UI 9.6, aucune instance réelle |
| PRE-06 | Période inclusive/égalité/offsets/microsecondes testés ; acceptation HTTP UI 9.6, pas de ligne réelle sur une borne |
| PRE-07 | Dates distinctes et ISO sources en UI 9.4 ; filtres restaurés UI 9.6, dates de lignes seulement en fixtures |
| PRE-08 | Présentation selon type/provenance UI 9.4 et revue isolée ; aucun score réel DEV |
| PRE-09 | Panneaux et JSON échappé/borné UI 9.4, captures isolées ; aucun JSON réel DEV |
| PRE-10 | États et retry testés UI 9.3 ; états vides réellement observés UI 9.6, pas d'inférence de modèle absent |
| PRE-11 | Navigation typée bidirectionnelle et exclusivité UI 9.5 ; contexte pre_ réel UI 9.6 |
| PRE-12 | Labels/tableau/focus/clavier/responsive UI 9.3 à UI 9.5 ; limites d'accessibilité ci-dessous |
| PRE-13 | Pagination serveur/catalogues bornés en tests ; métadonnées vides réelles UI 9.6, multiligne non démontré |
| PRE-14 | Façade locale/annulation/destruction testées UI 9.3 ; pas de cache global |
| PRE-15 | Sécurité multi-tenant absente ; contrôles UI/DEV insuffisants, B-PRE-01 ouvert |
| PRE-16 | Provenance et données incomplètes signalées ; fixtures distinguées des observations DEV UI 9.6 |

## 4. Résultats et nature des preuves

| Catégorie | Résultat de référence conservé |
| --- | --- |
| Tests isolés UI 9.5 | **642 tests ciblés réussis**, **2 376 tests Angular réussis dans 84 fichiers** |
| Finition contextuelle UI 9.5 | **163 tests ciblés réussis**, confirmés par le journal existant ; suite complète non relancée ensuite |
| Build UI 9.5 | Production réussi ; bundle initial **606 501 octets**, avant finition contextuelle ; aucune nouvelle mesure UI 9.6/9.7 |
| Visuel utilisateur UI 9.5 | **8/8**, puis finition contextuelle et capture utilisateur approuvées |
| HTTP indépendants UI 9.6 | **33 contrôles conformes** : 26 réponses HTTP 200 comparées au SQL et 7 réponses 422 attendues ; pas du trafic Angular capturé |
| PostgreSQL UI 9.6 | DEV permanent Angular 4201/API 8001/PostgreSQL 5434 ; base industrial_predict_dev, rôle ui47_app ; **8 tables et 40 lignes métier conservées**, empreintes globales et par ligne identiques, **zéro PredictionRecord**, aucune écriture métier |
| Observations Angular UI 9.6 | Sélections, contexte pre_, filtres, retour/rechargement, exclusivité, navigation et état vide réels ; capture d'état vide locale ignorée |
| Capture XHR brute | Absente : outil sans journal réseau/XHR ; les GET indépendants ne certifient pas le trafic du navigateur |

Les quatre types, scores, niveaux, JSON, filtres sélectifs et pages non vides sont
couverts par tests et fixtures isolées des étapes UI 9.2 à UI 9.5. Ils ne constituent
pas des prédictions persistées ou une validation sur des lignes PostgreSQL DEV.
L'inclusion d'une ligne réelle aux bornes, le tri multiligne et la cohérence de
toutes les valeurs DTO avec SQL ne sont pas démontrés sur cette table vide.

## 5. Limites et dettes techniques

Les onze risques ne sont pas corrigés par cette livraison :

| Réserve | Situation conservée depuis UI 9.6 |
| --- | --- |
| B-PRE-01 | Authentification, autorisation de ressource et isolation multi-tenant absentes ; bloque la production SaaS. Identité DEV et cascade UI ne constituent pas une sécurité multi-tenant |
| B-PRE-02 | Scores et niveaux backend génériques inchangés ; aucune interprétation d'une valeur réelle possible ici, règles prudentes UI 9.4 conservées |
| B-PRE-03 | Validation temporelle backend non durcie ; égalité/offsets acceptés, mais inclusion de lignes aux bornes non prouvée sur table vide |
| B-PRE-04 | Intégrité Equipment/Sensor/Measurement backend partielle ; références réelles Equipment/Site/Company vérifiées, aucun lien descendant ajouté |
| B-PRE-05 | JSON backend générique sans limite de taille ; limites UI 10 000 caractères/six niveaux uniquement visuelles, aucun JSON réel à auditer ici |
| B-PRE-06 | Cascades de suppression backend inchangées ; aucun DELETE ni test destructif |
| B-PRE-07 | OFFSET/COUNT distincts, concurrence et index inchangés ; pas de mesure de volume ni garantie de snapshot API, comparaisons SQL isolées seulement |
| B-PRE-08 | Risques des POST RUL et artefacts inchangés ; aucun calcul, POST ou chargement ML déclenché |
| B-PRE-09 | Historique réellement vide constaté ; aucune génération automatique ou déduction de modèle absent, mécanisme d'alimentation non testé |
| B-PRE-10 | Données/provenance historiques potentiellement invalides ou incomplètes ; 14 colonnes constatées, aucune ligne pour auditer les valeurs |
| B-PRE-11 | Aucun GET détail/latest ou écran détail autonome ajouté ; détails locaux de liste non exercés sur données DEV |

Le seed strict Sensor ID 1 reste historiquement non conforme : description
`Capteur fictif` au lieu de `Capteur fictif.` et updated_at
`2026-10-20T22:11:55.315993` au lieu de `2026-10-16T12:00:00`.
Écart préservé, aucune correction, seed ou nouvelle vérification PostgreSQL UI 9.7.

Budget initial Angular d'avertissement **500 kB**, bundle historique
**606 501 octets**, dépassement **106 501 octets** (106,50 kB affichés), budget
inchangé. La réussite du build ne supprime pas cet avertissement.

Responsive et clavier contrôlés historiquement, notamment 320/390/768/1440 CSS
en UI 9.4 et parcours Shell UI 9.5 ; dimensions exactes et cadrages selon leurs
rapports, certains contrôles 390 dans un iframe isolé ou encadrés 389/391.
Ces contrôles ne valent pas audit exhaustif WCAG. Lecteur d'écran réel et zoom
réel 200/400 % Predictions non certifiés, calendriers natifs non exhaustifs,
pas de certification de compatibilité multi-navigateurs. Les validations réelles
du zoom Dashboard ne sont pas transférées à Predictions.

**Authentification, autorisation de ressource et isolation multi-tenant absentes.**
La livraison du MVP de consultation ne constitue pas une validation pour la
production SaaS. La [proposition ML](roadmap.md) est distincte, non commencée et
sans date ; sa recette isolée et toute écriture exigent une autorisation dédiée.

## 6. Inventaire exact des commits

Diff `main..HEAD` et `origin/main..HEAD` : **5 commits**, déterminés depuis Git.
UI 9.1 (`05545a8`) est dans la base et exclu de ce compte.
UI 9.7 n'est pas commitée et ne reçoit aucun SHA anticipé.

| SHA | Message |
| --- | --- |
| `f956c90f4ad187dc897132e48f36d53fac1e99b6` | feat(frontend): add Predictions data models and API integration |
| `3600d8e461f8c38ca00e2277b57e0c49374773b9` | feat(frontend): implement Predictions list and filters |
| `da9f0e07ad33b4f3ea65b13f59ce2e72743596e3` | feat(frontend): present Predictions scores and details |
| `b92ab9e406d037dc8505b0e90dd2c0eb52d9cc6b` | feat(frontend): integrate Predictions routing and Equipment navigation |
| `edb7b6c5e1bc1e8f17ba6f5ed4668c0fe2a6e3f2` | docs(frontend): validate Predictions DEV integration |

## 7. Inventaire exact des fichiers

### Diff commité par rapport à main et origin/main

**47 fichiers distincts**, 36 nouveaux (A), 11 modifiés (M).
Déterminés par `git diff --name-status main...HEAD`, identiques pour origin/main.

| Statut | Chemin |
| --- | --- |
| A | `docs/ui-9.2-predictions-data-access.md` |
| A | `docs/ui-9.3-predictions-list.md` |
| A | `docs/ui-9.4-predictions-presentation.md` |
| A | `docs/ui-9.5-predictions-navigation.md` |
| A | `docs/ui-9.6-predictions-integration.md` |
| M | `frontend/src/app/app.routes.spec.ts` |
| M | `frontend/src/app/app.routes.ts` |
| M | `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.html` |
| M | `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.scss` |
| M | `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.spec.ts` |
| M | `frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts` |
| M | `frontend/src/app/features/equipments/pages/equipment-detail/equipment-maintenance-navigation.spec.ts` |
| A | `frontend/src/app/features/equipments/pages/equipment-detail/equipment-predictions-navigation.spec.ts` |
| A | `frontend/src/app/features/predictions/components/prediction-details/prediction-details.component.html` |
| A | `frontend/src/app/features/predictions/components/prediction-details/prediction-details.component.scss` |
| A | `frontend/src/app/features/predictions/components/prediction-details/prediction-details.component.spec.ts` |
| A | `frontend/src/app/features/predictions/components/prediction-details/prediction-details.component.ts` |
| A | `frontend/src/app/features/predictions/data-access/predictions-api.service.spec.ts` |
| A | `frontend/src/app/features/predictions/data-access/predictions-api.service.ts` |
| A | `frontend/src/app/features/predictions/models/prediction-page-query.model.ts` |
| A | `frontend/src/app/features/predictions/models/prediction.model.ts` |
| A | `frontend/src/app/features/predictions/models/predictions-state.model.ts` |
| A | `frontend/src/app/features/predictions/pages/predictions-list/predictions-list.component.html` |
| A | `frontend/src/app/features/predictions/pages/predictions-list/predictions-list.component.scss` |
| A | `frontend/src/app/features/predictions/pages/predictions-list/predictions-list.component.spec.ts` |
| A | `frontend/src/app/features/predictions/pages/predictions-list/predictions-list.component.ts` |
| A | `frontend/src/app/features/predictions/predictions-list.facade.spec.ts` |
| A | `frontend/src/app/features/predictions/predictions-list.facade.ts` |
| A | `frontend/src/app/features/predictions/predictions.routes.spec.ts` |
| A | `frontend/src/app/features/predictions/predictions.routes.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-display.spec.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-display.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-json-preview.spec.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-json-preview.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-navigation.spec.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-navigation.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-period-draft.spec.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-period-draft.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-query.spec.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-query.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-reference-catalog.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-time.spec.ts` |
| A | `frontend/src/app/features/predictions/utils/prediction-time.ts` |
| M | `frontend/src/app/layout/shell/shell-focus.spec.ts` |
| M | `frontend/src/app/layout/shell/shell-responsive.spec.ts` |
| M | `frontend/src/app/layout/sidebar/sidebar.component.spec.ts` |
| M | `frontend/src/styles/_buttons.scss` |

### Préparation documentaire UI 9.7 non commitée

**7 documents**, six existants modifiés (M) et un nouveau (A) :

| Statut | Chemin |
| --- | --- |
| M | `README_AI.md` |
| M | `frontend/README.md` |
| M | `docs/project-status.md` |
| M | `docs/roadmap.md` |
| M | `docs/architecture.md` |
| M | `docs/frontend-architecture.md` |
| A | `docs/ui-9.7-predictions-delivery.md` |

L'union des 47 fichiers commités et de ces sept documents forme **54 fichiers
distincts** pour la livraison préparée, sans supposer qu'un commit documentaire
existe déjà. Aucun des six rapports UI 9.1 à UI 9.6 n'est modifié par UI 9.7.
Les preuves locales frontend/tmp sont ignorées, hors index et hors livraison.

## 8. Comparaison avec main et origin/main

Contrôle local du 25 octobre 2026, sans fetch :

| Référence | SHA | Retard / avance de la feature |
| --- | --- | --- |
| main | `05545a88dcd45940f00c1c029d9e567a9c5a4cee` | 0 / 5 |
| origin/main (référence locale) | `05545a88dcd45940f00c1c029d9e567a9c5a4cee` | 0 / 5 |
| HEAD feature | `edb7b6c5e1bc1e8f17ba6f5ed4668c0fe2a6e3f2` | 5 commits après la base commune |

Git confirme main et origin/main ancêtres de HEAD ; fusion fast-forward possible
dans cet état local **après** validation et commit documentaire autorisés.
Diff commité : **47 fichiers, 3 740 insertions et 11 suppressions**. Les sept
documents UI 9.7 restent hors de ce diff commité ; la cible n'est pas déjà fusionnée.
La concordance des références locales ne prouve pas l'état distant en direct.

## 9. Checklist de fusion fast-forward

Préparation seulement ; aucune des opérations de livraison ci-dessous exécutée :

- [ ] Validation utilisateur du présent dossier et des sept documents.
- [ ] Autorisation explicite du commit documentaire ; vérifier branche/HEAD,
  index et périmètre exact, ajouter seulement les sept chemins ci-dessus,
  examiner diff indexé/stat/--check, puis créer le commit autorisé.
- [ ] Relever le SHA obtenu et les comptes effectifs dans le bilan Git final,
  sans réécrire les rapports historiques ni inventer un futur SHA.
- [ ] Autorisation distincte de fusion ; vérifier arbre/index propres et
  référence main cible. Recontrôler `git merge-base --is-ancestor main feature/frontend-predictions`.
- [ ] Si la cible a avancé ou divergé, suspendre la fusion et réévaluer son
  périmètre ; aucun merge classique ou rebase implicite.
- [ ] Après autorisation seulement : `git switch main` puis
  `git merge --ff-only feature/frontend-predictions` ; vérifier HEAD, statut et log.
- [ ] Vérifier la référence distante selon le cadre autorisé avant publication ;
  push uniquement sur autorisation distincte. Aucun déploiement SaaS déduit.

Aucune validation applicative relancée pour la documentation. Un éventuel
changement exécutable ultérieur doit être évalué séparément.

## 10. Contrôles documentaires et état Git final

Relecture des contrats, statuts et versions à partir des six rapports validés ;
aucune nouvelle version de stack ni résultat applicatif annoncé.
Liens Markdown internes des documents modifiés contrôlés, ainsi que les ancres.
Contrôle des espaces du nouveau rapport et `git diff --check` conformes.
Contrôle du périmètre : uniquement les sept documents autorisés, six rapports
historiques identiques à HEAD ; aucun secret, DSN privé, dump, capture ou artefact
ajouté à la livraison.

Branche `feature/frontend-predictions`, HEAD `edb7b6c` inchangé ;
index vide, **6 documents modifiés et 1 nouveau non suivi**. Les preuves locales
ignorées de recette restent hors livraison. Aucun commit/push/merge/rebase,
aucun accès DEV, test, build ou calcul ML effectué pour UI 9.7.
Validation attendue avant le commit final.
