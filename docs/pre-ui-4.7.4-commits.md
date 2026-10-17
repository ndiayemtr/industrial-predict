# Préparation des commits avant UI 4.7.4

Contrôles exécutés le 17 octobre 2026, sur `feature/frontend-sites`, depuis `e8702b0`. Travaux validés enregistrés en quatre commits locaux, sans push, merge ou réécriture de l'historique. UI 4.7.4 n'est pas commencée.

## Audit et conservation

L'état initial comprenait 35 fichiers nouveaux ou modifiés, avec index vide. Les commandes `git status --short`, `git diff --check`, `git diff --stat` et l'inventaire des fichiers non suivis ont été examinés. Les originaux et leurs empreintes ont été conservés hors Git avant préparation.

Les changements partagés sont répartis par staging sélectif, sans retirer de contenu du répertoire de travail :

- SiteEditComponent.spec reçoit les tests fonctionnels UI 4.6 dans le premier commit, puis trois cas UI 4.6.2 dans le second. Le quatrième cas UI 4.6.2 est ajouté au test de création dans le second commit.
- README_AI, project-status et roadmap évoluent à chaque commit pour référencer uniquement les étapes déjà présentes dans cet état de l'historique.
- Le guide DEV est ajouté sans section seed dans le troisième commit ; sa section seed arrive avec les fichiers correspondants dans le quatrième.
- Les rapports historiques conservent leurs résultats datés. Leurs notes de suivi distinguent la validation initiale de cet enregistrement Git.

Chaque commit possède une liste explicite de fichiers. Aucun `git add .` n'est utilisé. Avant chaque commit : examen de `git diff --cached --stat`, `git diff --cached --check`, contrôle des chemins et secrets ajoutés, et vérification des liens internes contre les fichiers présents dans l'index.

## Vérifications réellement relancées

Toutes les commandes ont été exécutées séquentiellement, sans build concurrent avec les tests.

| Contrôle | Résultat |
| --- | --- |
| `ng test --watch=false` | 581 tests réussis, 42 fichiers ; démarrage 15:09:22 UTC, durée Vitest 44,66 s |
| Build production, sortie `frontend/tmp/pre-ui-4.7.4/production` | Réussi ; durée 18,884 s, génération terminée à 15:12:10 UTC |
| Tests du correctif Sass | 5 réussis |
| Compatibilité Nebular/Sass | Dart Sass 1.97.3, quatre expressions, huit breakpoints, media queries et thème unique conformes |
| Tests du simulateur HTTP | 7 réussis, uniquement en mémoire |
| Tests de configuration DEV | 10 réussis |
| Tests du proxy DEV | 10 réussis |
| Tests du seed | 16 réussis, exclusivement sur SQLite en mémoire |
| `npm ls --all` | Code 0, arbre valide |
| `npm audit --json` | Code 0 ; zéro vulnérabilité info/low/moderate/high/critical signalée |
| `git diff --check` et contrôles cached | Conformes |

Total des tests relancés : 629, dont 581 Angular. Les 33 tests métier mentionnés dans le rapport historique UI 4.7.3 ne sont pas revendiqués comme une nouvelle exécution ici. Aucun échec de test, build ou commande npm n'a été observé. L'avertissement budget et la dette de secrets préexistante sont documentés séparément.

## Bundles et avertissements

- Initial : 601 509 octets, soit 601,51 ko, pour un budget warning de 500 ko ; dépassement existant de 101,51 ko.
- Ensemble JS/CSS : 785 921 octets, 31 fichiers ; les 31 empreintes sont identiques aux artefacts UI 4.6.2 conservés.
- Page édition différée : 12 291 octets. Formulaire Sites partagé : 10 457 octets.
- Aucun budget, dépendance ou fichier applicatif n'a été modifié pendant cette préparation.

Le build reste réussi avec l'avertissement existant. Le seuil d'erreur demeure 1 Mo. Les tests SQLite affichent une dépréciation `datetime.utcnow()` provenant des défauts ORM existants ; aucun correctif backend n'est inclus pour la masquer.

## Secrets et artefacts

Les 35 fichiers candidats initiaux ont été comparés aux secrets réels du DEV et de la base historique, sans afficher ces valeurs : aucun match. Les blobs ajoutés ou modifiés sont contrôlés à nouveau avant chaque commit. Aucun fichier `.env` sensible, archive PostgreSQL, sauvegarde, journal local, répertoire de secrets, artefact compilé ou volume Docker n'est ajouté. `backend/.env.example` était déjà suivi et ne correspond pas aux secrets réels contrôlés.

**Limite de sécurité préexistante :** le scan des 436 fichiers déjà suivis a confirmé la présence du mot de passe réel de la base historique dans `backend/alembic.ini` et `docker-compose.yml`. Ces deux fichiers étaient déjà présents dans `e8702b0`, ne sont pas modifiés et ne font pas partie des chemins changés par cette série. Il n'est donc pas exact d'affirmer que tout le dépôt est exempt de secrets : la garantie est qu'aucun nouveau secret n'est ajouté par ces commits.

Le traitement de ces identifiants historiques nécessite un travail distinct : externalisation des valeurs, procédure de lancement explicite et rotation coordonnée des identifiants exposés. Aucune rotation, modification de configuration historique ou réécriture des anciens commits n'est effectuée ici. Les valeurs ne sont ni copiées dans ce rapport ni affichées dans les sorties.

Les noms de rôles et ressources UI47 conservés sont des identités techniques, pas des secrets. La cible permanente reste `industrial_predict_dev` sur 5434, FastAPI 8001 et Angular 4201 ; les diagnostics et le proxy n'ont aucun repli vers 8000. Les anciennes appellations de base dans les rapports UI 4.7.2 sont historiques, pas des cibles de lancement actuelles.

## PostgreSQL

Aucune commande de seed réelle, migration, mutation métier, suppression, arrêt ou recréation de conteneur n'a été exécutée pendant cette préparation. Les tests du seed utilisent SQLite en mémoire ; les tests du simulateur écrivent uniquement dans leurs objets en mémoire.

Une comparaison en lecture seule confirme que les lignes et séquences DEV sont identiques au relevé après UI 4.7.3. Les manifestes complets de `industrial_predict` et `industrial_predict_restore_ui471_20261017t121921z` restent identiques, y compris PETROSEN et le site historique `id=3`.

## Répartition exacte des fichiers

### Commit 1 - UI 4.6

`feat(frontend): implement Sites editing` - 60619a1.

```text
README_AI.md
docs/project-status.md
docs/roadmap.md
docs/ui-4.5-site-create.md
docs/ui-4.6-site-edit.md
frontend/src/app/features/sites/components/site-form/site-form.component.ts
frontend/src/app/features/sites/components/site-form/site-form.component.html
frontend/src/app/features/sites/components/site-form/site-form.component.scss
frontend/src/app/features/sites/pages/site-detail/site-detail.component.ts
frontend/src/app/features/sites/pages/site-detail/site-detail.component.html
frontend/src/app/features/sites/pages/site-detail/site-detail.component.scss
frontend/src/app/features/sites/pages/site-detail/site-detail.component.spec.ts
frontend/src/app/features/sites/sites.routes.ts
frontend/src/app/features/sites/sites.routes.spec.ts
frontend/src/app/features/sites/pages/site-edit/site-edit.component.ts
frontend/src/app/features/sites/pages/site-edit/site-edit.component.html
frontend/src/app/features/sites/pages/site-edit/site-edit.component.scss
frontend/src/app/features/sites/pages/site-edit/site-edit.component.spec.ts
```

### Commit 2 - UI 4.6.2

`test(frontend): secure Sites simulation workflows` - 9833d71.

```text
README_AI.md
docs/project-status.md
docs/roadmap.md
docs/ui-4.6.2-site-code-simulation.md
frontend/src/app/features/sites/pages/site-create/site-create.component.spec.ts
frontend/src/app/features/sites/pages/site-edit/site-edit.component.spec.ts
frontend/scripts/sites-simulation-server.mjs
frontend/scripts/sites-simulation-server.test.mjs
```

### Commit 3 - Environnement DEV permanent

`chore(infra): add isolated development environment` - 39fb7e4.

```text
README_AI.md
docs/project-status.md
docs/roadmap.md
docs/ui-4.7.2-integration-environment.md
docs/ui-4.7.2.1-development-environment-plan.md
docs/ui-4.7.2.1-development-environment.md
infra/development/README.md
infra/development/compose.yaml
infra/development/manage.py
infra/development/test_manage.py
infra/development/angular-proxy.cjs
infra/development/angular-proxy.test.cjs
```

### Commit 4 - UI 4.7.3 et bilan de préparation

`feat(dev): add reproducible industrial seed data` - commit courant, consulter git log.

```text
README_AI.md
docs/project-status.md
docs/roadmap.md
docs/ui-4.7.3-development-data.md
docs/pre-ui-4.7.4-commits.md
infra/development/README.md
infra/development/demo-data.json
infra/development/seed.py
infra/development/test_seed.py
```

## État final attendu et limites

Les quatre commits sont consécutifs à `e8702b0`, sur `feature/frontend-sites`. Le dernier contient ce bilan ; son identifiant est fourni par `git log -6 --oneline` après création. L'index et le répertoire de travail doivent être propres avant remise. Aucun push ni merge.

Les sorties npm complètes, empreintes, originaux et manifestes de staging restent hors Git sous `D:\integration\industrial-predict\development\evidence\pre-ui-4.7.4-commits`. Les artefacts du nouveau build restent dans le répertoire frontend ignoré.

Le dépassement du budget, les identifiants historiques déjà suivis, l'autorisation multi-entreprises non démontrée et les validations d'accessibilité restantes demeurent des limites. La création de données par seed ne valide pas les parcours CRUD réels du navigateur. Attendre validation avant UI 4.7.4.
