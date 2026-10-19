# UI 4.8 - Documentation et préparation de livraison Sites

19 octobre 2026. Branche `feature/frontend-sites`, HEAD `b3d0352`, dépôt propre
au départ. Intervention strictement documentaire, sans commit, push, merge,
opération PostgreSQL, nouveau package ou début du module suivant.

## Documents mis à jour

- [project-status.md](project-status.md) : bilan courant Sites, preuves et dettes.
- [roadmap.md](roadmap.md) : UI 4.7.4/4.7.5 enregistrées ; UI 4.8 et fusion en attente.
- [README_AI.md](../README_AI.md) : contexte courant et renvoi vers le bilan unique.
- [frontend-architecture.md](frontend-architecture.md) : routes et structure Sites,
  protections et différences avec la conception, fin du statut placeholder.
- [architecture.md](architecture.md) : présence de Sites et parcours DEV permanent.
- [README frontend](../frontend/README.md) : lancement DEV 4201, proxy historique
  distingué et absence de cible e2e configurée.
- Le présent rapport de livraison et sa checklist.

Audit de la conception UI 4.1, des rapports UI 4.2 à UI 4.7.5, du suivi et des
architectures. Les rapports historiques, les décisions D001 à D014 et les choix
métier sont conservés sans réécriture de leurs résultats. Les sections UI 2/UI 3
restent datées ; leurs preuves ne sont pas attribuées à Sites.

## Fonctionnalités et validation de référence

Sites MVP comprend liste, recherche serveur nom/code, pagination, filtre par
entreprise explicite, détail, création et édition. PATCH différentiel limité aux
champs modifiés ; entreprise non transférable et aucun DELETE frontend.
Navigation avec contexte, notifications après succès, conservation de saisie
après erreur et protections des formulaires sont implémentées.

Le [bilan courant](project-status.md#sites-mvp---livraison-préparée-ui-48) centralise
le périmètre exact. Les preuves [UI 4.7.4](ui-4.7.4-real-sites-crud.md) et
[UI 4.7.5](ui-4.7.5-sites-closure.md) restent la référence : **583 tests Angular**
réussis avec deux workers, build production réussi, **POST 201/PATCH 200** réels
et persistance SQL confirmée. Deux entreprises et quatre sites vérifiés dans
Angular ; 36 lignes seed inchangées. **409 réel dans le formulaire** ; **422 réel
par appel contrôlé via le proxy**, traitement frontend confirmé par tests.
Parcours réel : Angular **4201 -> FastAPI 8001 -> PostgreSQL industrial_predict_dev**
sur 5434, sans repli sur les services historiques.

Aucun fichier exécutable modifié : les 583 tests, le build, Sass et npm audit
ne sont pas relancés en UI 4.8. Aucun appel API ni contrôle SQL effectué.

## Limites à accepter ou traiter séparément

- Réserve ouverte sur le dialogue natif d'abandon : tests Angular réussis,
  validation navigateur complète encore manquante.
- Bundle initial **601,51 ko / budget 500 ko** ; seuil inchangé. Timeout initial
  du test shell sous concurrence, suite complète finale réussie avec deux workers.
- Secrets historiques suivis dans `backend/alembic.ini` et `docker-compose.yml` :
  externalisation et rotation nécessaires. Ces fichiers restent identiques à
  `main` ; le contrôle d'absence de nouveaux secrets ne signifie pas dépôt exempt
  de secrets historiques. Aucune valeur reproduite ici.
- Absence d'authentification et d'autorisation multi-tenant : filtrage et
  protections frontend ne sécurisent pas les endpoints backend. Aucune livraison
  de production SaaS multi-tenant revendiquée.
- Liens croisés Companies/Sites prévus en UI 4.1 absents des templates actuels :
  écart explicité pour arbitrage, sans décision de suppression ni implémentation ici.
  Limites d'accessibilité, charge et concurrence détaillées dans le bilan courant.

## Préparation Git par rapport à main

Référence **locale** `main=54dd128`, ancêtre de HEAD : **0 commit de retard,
10 commits d'avance**. Aucun fetch effectué ; l'état distant devra être revérifié
avant fusion. Liste des commits existants, du plus ancien au plus récent :

| Commit | Contenu |
| --- | --- |
| `1630ebc` | Conception Sites MVP |
| `cd2389d` | Modèles et intégration API Sites |
| `43f72f8` | Liste, recherche et finitions UX |
| `491cb24` | Détail et harmonisation des libellés métier |
| `e8702b0` | Création et finitions UX |
| `60619a1` | Édition Sites |
| `9833d71` | Simulations isolées et tests de code métier |
| `39fb7e4` | Environnement permanent DEV isolé |
| `8554684` | Seed industriel reproductible |
| `b3d0352` | Tests finaux et rapports UI 4.7.4/4.7.5 |

L'écart commité `main...HEAD` comprend **77 fichiers (59 ajoutés, 18 modifiés)**,
couvrant documentation,
feature Sites, routing/références partagés, libellés Dashboard/Companies et outillage
de simulation/DEV. Ces adaptations transversales appartiennent aux commits validés
et restent dans le périmètre de revue ; elles ne sont pas de nouvelles modifications
UI 4.8. Aucun changement backend applicatif ni migration dans cette série.
Inventaire exact : `git diff --name-status main...HEAD` ; détails par commit :
`git log --oneline main..HEAD` et `git show --stat <commit>`.

Contrôles de livraison : **183 liens locaux dont 15 ancres dans 23 documents**,
tirets ASCII simples, espaces et `git diff --check` conformes. Périmètre uniquement
documentaire ; **15 rapports/conception historiques conservés sans modification**.
Les nouveaux chemins de la branche ne comprennent ni dump PostgreSQL, capture,
trace HTTP brute, artefact compilé, sauvegarde ou configuration privée. Les secrets
historiques connus sont recherchés en mémoire dans **135 blobs modifiés des dix
commits** et dans la documentation courante : aucune occurrence, sans afficher les valeurs.
Les signatures de secrets sont également contrôlées dans les ajouts courants ;
ces contrôles ciblés ne constituent pas un audit de sécurité exhaustif.
Preuves techniques locales ignorées : `frontend/tmp/ui-4.8/`.

## Checklist de fusion vers main

- [x] Branche/HEAD attendus, historique et inventaire local examinés.
- [x] Documentation cohérente, résultats de référence et limites conservés.
- [x] Aucun changement exécutable UI 4.8 ; rapports de validation préservés.
- [x] Liens, tirets ASCII, diff et absence de nouveaux artefacts/secrets contrôlés.
- [ ] Validation utilisateur du bilan UI 4.8, des réserves et de l'écart de navigation.
- [ ] Autorisation puis commit documentaire avec staging explicite, après
  `git diff --cached --check` et revue de `git diff --cached --stat`.
- [ ] Avant fusion autorisée, actualiser les références distantes, contrôler à
  nouveau l'écart avec main, l'absence de conflit et le périmètre complet.
- [ ] Si la base ou du code exécutable change, réévaluer les validations nécessaires ;
  ne pas attribuer les anciens résultats au nouvel état sans vérification adaptée.
- [ ] Autorisation distincte de fusion ; push uniquement sur demande explicite.

## État Git final UI 4.8

HEAD inchangé `b3d0352`, branche `feature/frontend-sites`, index vide.
Six documents modifiés et un nouveau rapport non suivi :

```text
 M README_AI.md
 M docs/architecture.md
 M docs/frontend-architecture.md
 M docs/project-status.md
 M docs/roadmap.md
 M frontend/README.md
?? docs/ui-4.8-sites-delivery.md
```

`git diff --check` conforme ; nouveau rapport contrôlé séparément car non suivi.
**Validation attendue avant commit documentaire et toute fusion.** Aucun module suivant commencé.
