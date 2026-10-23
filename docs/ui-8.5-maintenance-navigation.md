# UI 8.5 - Navigation Equipment vers Maintenance

Date : 23 octobre 2026. Branche : `feature/frontend-maintenance`. HEAD de départ : `c66e7f3`, inchangé. Dépôt propre au démarrage.

## Navigation livrée

Conformément à [MAIN-04, MAIN-11, MAIN-12 et MAIN-13](etape-ui-8.1-maintenance.md), Equipment Detail propose l’action secondaire « Voir les interventions » uniquement après résolution cohérente Equipment -> Site -> Company.

Le contrôle existant est partagé dans un computed privé `industrialQuery`, exposé sans changement de comportement à `sensorsQuery`, puis à `maintenanceQuery`. Aucun nouvel appel API n’est ajouté sur Equipment Detail. Les identifiants doivent être des entiers positifs sûrs, Equipment.site_id doit correspondre au site reçu et Site.company_id à l’entreprise reçue. Le bouton est absent pendant le chargement, sur erreur parent, clé étrangère invalide ou identité incohérente. Les données Equipment restent affichées selon le comportement existant.

Destination exacte après résolution :

```text
/maintenance?company_id=<Company.id>&site_id=<Site.id>&equipment_id=<Equipment.id>&page=1&page_size=20
```

Aucun statut, criticité, recherche, filtre de date, type, priorité ou `returnUrl` Equipment n’est transmis. Le contexte de retour Equipment reste indépendant : s’il est contradictoire avec la chaîne réelle, l’URL n’est pas remplacée et l’information de contexte existante reste affichée. Le bouton utilise les références réellement vérifiées, jamais les paramètres de retour. Une contradiction entre les références elles-mêmes empêche le lien.

La liste Maintenance revérifie la chaîne reçue avant son GET paginé. Si un parent change entre le clic et cette vérification, elle bloque la lecture sans remplacer les identifiants de l’URL ni tenter un périmètre plus large. La réponse doit contenir exclusivement les interventions de l’équipement sélectionné.

## Navigation inverse et UX préservées

Maintenance Detail -> Equipment Detail conserve le contrat UI 8.4, sans modification de ses sources : Equipment est lu depuis `Maintenance.equipment_id` et son identité vérifiée. Le lien peut exister avec un contexte partiel après résolution de l’équipement ; seuls les identifiants parents connus des références réelles complètent ce contexte. Les libellés de la chaîne complète restent soumis aux GET Site et Company, avec erreurs distinctes. Aucune identité n’est reconstruite depuis les filtres de retour. L’arrivée sur Equipment revérifie elle-même les parents avant d’afficher les deux actions vers Sensors et Maintenance.

Le lien inverse ne transmet ni statut/type Maintenance ni recherche/période. Le bouton Retour propre à Maintenance conserve les paramètres autorisés, pagination, fractions, offsets, paramètres répétés et fragment selon UI 8.4. L’accès direct conserve une destination locale explicite, sans dépendance à `history.back()`.

Ordre des actions Equipment : Retour à la liste, Voir les capteurs, Voir les interventions, Modifier. L’ordre relatif et les destinations des actions existantes sont préservés. `navigation-action` est réutilisé dans le même sélecteur que Voir les capteurs. `_buttons.scss` inclut la nouvelle classe pour les transitions, hover/active, focus et mouvement réduit. Le nouveau bouton mesure 44 px de hauteur ; il reste secondaire. Le Modifier existant concerne Equipment, pas Maintenance.

Titres cliquables, six colonnes sans ID, badges statut/priorité, dates ISO et 18 champs Maintenance sont inchangés. Aucun formulaire, POST, PATCH, DELETE ou transition Maintenance n’est ajouté. Aucun écran Sensors ou Measurements n’est modifié.

## Fichiers concernés : 6

| Fichier | Changement |
| --- | --- |
| [equipment-detail.component.ts](../frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.ts) | Mutualisation du contexte industriel vérifié, alias Maintenance |
| [equipment-detail.component.html](../frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.html) | Action conditionnelle vers Maintenance |
| [equipment-detail.component.scss](../frontend/src/app/features/equipments/pages/equipment-detail/equipment-detail.component.scss) | Réutilisation du mixin partagé dans le sélecteur existant |
| [equipment-maintenance-navigation.spec.ts](../frontend/src/app/features/equipments/pages/equipment-detail/equipment-maintenance-navigation.spec.ts) | Nouveau fichier, 29 scénarios de navigation et non-régression |
| [_buttons.scss](../frontend/src/styles/_buttons.scss) | Classe `.equipment-maintenance` ajoutée aux actions et au mouvement réduit |
| [ui-8.5-maintenance-navigation.md](ui-8.5-maintenance-navigation.md) | Présent rapport |

## Tests et build réellement exécutés

Après stabilisation, une exécution par commande :

| Contrôle | Résultat |
| --- | --- |
| Tests ciblés Equipment, Maintenance, routes application et sidebar | **741 réussis, 16 fichiers** |
| Suite Angular complète | **1 899 réussis, 72 fichiers** |
| Build production | **Réussi** |
| `git diff --check` et vérification des nouveaux fichiers/liens | **Réussis** |

```text
npx ng test --watch=false --include='src/app/features/maintenance/**/*.spec.ts' --include='src/app/features/equipments/**/*.spec.ts' --include='src/app/app.routes.spec.ts' --include='src/app/layout/sidebar/sidebar.component.spec.ts' --runner-config=tmp/ui-8.5/vitest.config.mjs
npx ng test --watch=false --runner-config=tmp/ui-8.5/vitest.config.mjs
npx ng build --configuration production
```

Le fichier Vitest temporaire limite les workers à deux, sans package ou configuration suivie supplémentaire. Journaux locaux ignorés : [ciblés](../frontend/tmp/ui-8.5/targeted-tests.log), [suite complète](../frontend/tmp/ui-8.5/full-tests.log), [build](../frontend/tmp/ui-8.5/build.log).

Les nouveaux tests couvrent : disponibilité après chaque résolution ; ids réels et URL exacte ; aucun filtre Equipment recyclé ; contexte de retour contradictoire laissé intact ; focus du lien ; ordre/destinations des anciennes actions ; changement de paramètres sans nouvelles lectures ; parents incohérents, absents ou inaccessibles, retries manuels ; clés étrangères invalides ; ID Equipment invalide ou absent ; annulation sur changement rapide d’équipement ; restauration Maintenance avec catalogue et GET bloqué jusqu’au dernier parent ; changement de rattachement avant GET liste ; rejet d’une réponse hors équipement ; lien inverse et retour Maintenance complet, incluant offset/microsecondes et fragment. Tous les échanges HTTP des scénarios sont vérifiés comme GET. Les tests UI 8.4 de détail, dates, retour direct et erreurs sont également réexécutés dans la suite ciblée.

### Bundles et budgets

| Mesure brute | Avant UI 8.5 | Après UI 8.5 |
| --- | ---: | ---: |
| Bundle initial | 605 860 octets (605,86 kB) | **605 998 octets (606,00 kB)** |
| Ensemble JS/CSS produit | 1 103 219 octets | **1 103 944 octets** |
| CSS Equipment Detail local compilé/minifié, saut de ligne inclus | 2 427 octets | **2 571 octets** |

Initial : **+138 octets**. Total JS/CSS : **+725 octets**. Chunk Equipment Detail : **14 795 octets**, affiché 14,79 kB par Angular. Chunks Maintenance List **43 974 octets (43,97 kB)** et Maintenance Detail **16 404 octets (16,40 kB)** inchangés, noms de fichiers identiques à la validation précédente.

Budgets inchangés : initial avertissement 500 kB/erreur 1 MB ; composant avertissement 4 kB/erreur 8 kB. Seul l’avertissement initial existant demeure, avec dépassement de 106,00 kB. Aucun nouvel avertissement SCSS. La mesure CSS locale Sass/esbuild est distincte du style encapsulé embarqué dans le chunk ; aucune règle n’est déplacée globalement pour contourner le seuil.

## Responsive, focus et captures

Le build production est servi sur `127.0.0.1:8098` par un serveur synthétique GET uniquement, sans proxy ni base. Les mesures DOM contrôlent le document, les conteneurs Shell et les limites des quatre actions, sur une fiche fictive dont le contexte URL est volontairement différent de la chaîne réelle.

| Cible CSS | Largeur obtenue | Document utile / scrollWidth | Nouveau bouton |
| --- | ---: | ---: | --- |
| 1440 | 1440 | 1440 / 1440 | 44 px, contenu dans l’en-tête |
| 1024 | 1024 | 1024 / 1024 | 44 px, repli des actions sans débordement |
| 1023 | 1023 | 1023 / 1023 | 44 px, navigation repliée |
| 768 | 768 | 768 / 768 | 44 px, actions contenues |
| 390 | 389 et 391 | 369 / 369 et 371 / 371 | 44 px ; réserve sur la cible exacte |
| 320 | 320 | 300 / 300 | 44 px, actions contenues |

Les quatre actions mesurent 44 px à ces largeurs et gardent leur ordre. Aucun lien ne dépasse les limites du document, aucun débordement global relevé. Tab depuis Voir les capteurs atteint Voir les interventions avec focus bleu visible et transitions partagées. Mesures détaillées : [responsive.json](../frontend/tmp/ui-8.5/responsive.json).

Réserve : l’outil de capture échoue sur le serveur de fixtures, y compris avec une fenêtre moins haute et une autre API de capture. Les contrôles responsive ci-dessus sont donc des preuves DOM, pas une revue visuelle de sept captures. La cible exacte 390 est couverte à 389/391 px à cause de l’arrondi du navigateur. Un [contrôle DOM DEV distinct](../frontend/tmp/ui-8.5/dev-responsive-320.json) confirme aussi 320 px, document 300/300, bouton de 44 px.

Captures DEV desktop réellement obtenues et examinées : [Equipment et focus du bouton](../frontend/tmp/ui-8.5/screenshots/dev-equipment-maintenance.png), [contexte Maintenance sélectionné](../frontend/tmp/ui-8.5/screenshots/dev-maintenance-list.png). Ces vues ne sont pas présentées comme des captures aux six largeurs demandées. La capture mobile DEV a également échoué. Cette limite de capture de l’agent est conservée ; la recette visuelle a ensuite été validée par l’utilisateur, comme consigné ci-dessous.

## Validation visuelle utilisateur

L’utilisateur a confirmé dans cet échange : **recette visuelle manuelle UI 8.5 validée, 9 contrôles sur 9 réussis**. Cette validation clôture l’attente de recette visuelle signalée dans le bilan précédent.

Cette preuve est une validation manuelle déclarée par l’utilisateur, distincte des **741 tests ciblés**, des **1 899 tests Angular** et du build déjà exécutés par l’agent. Aucun test ni build n’est relancé pour cet ajout documentaire, les sources exécutables étant inchangées.

La liste détaillée des neuf contrôles et les largeurs de la recette manuelle ne sont pas précisées dans le message de validation. Les mesures DOM et les captures de l’agent conservent donc leur périmètre propre : cible exacte 390 non obtenue par l’outil, captures mobile/tablette indisponibles. La validation utilisateur ne constitue pas une nouvelle capture ni une nouvelle trace XHR de l’agent.

La recette SQL et le contrôle global d’intégrité de UI 8.6 restent séparés et **non commencés**. Aucun compteur, empreinte des huit tables, résultat SQL ou conformité du seed n’est déduit des 9 contrôles visuels. Aucune écriture PostgreSQL ou modification métier n’est effectuée pour cette mise à jour.

## Vérification DEV réelle, en lecture seule

Les listeners 4201 et 8001 étaient déjà actifs. Aucun serveur DEV, Docker ou PostgreSQL n’a été démarré, arrêté ou redémarré. Les deux `/__dev/identity` ont été comparés aux seuls champs attendus de la configuration privée, sans afficher de secret :

- Mode `local-development`, base `industrial_predict_dev`, rôle `ui47_app`, non superutilisateur.
- Instance identique et conforme à la configuration : `fb3284bd-fb7b-4c22-b620-96a1564b1d0c`.
- Révision `09ac8101e9fe`, hôte configuré `127.0.0.1`, PostgreSQL `5434`, API `8001`, Angular `4201`.
- Le guide [infra/development/README.md](../infra/development/README.md) et le contrôle de cible du lanceur ont été consultés, sans exécuter de commande SQL, seed, migration ou reset. Le proxy et l’API contrôlent leur cible avant les requêtes, sans fallback historique.

Parcours navigateur effectué depuis Angular 4201 :

1. Sélection explicite INDUSTRIE DEMO A (id 1), puis Site de production (id 1), dans la liste Equipment.
2. Ouverture de Pompe de circulation P101 (id 1). Après résolution des parents : Retour, Voir les capteurs, Voir les interventions, Modifier ; quatre actions de 44 px. Focus au clavier et activation de Voir les interventions avec Entrée.
3. Arrivée exacte sur `/maintenance?company_id=1&site_id=1&equipment_id=1&page=1&page_size=20`, sans filtre Equipment. Les trois sélections sont restaurées ; une intervention réelle, id 1, titre `UI47-MAINT-PUMP-01 - Contrôle préventif`, type préventif, statut terminé, priorité moyenne.
4. Filtre Maintenance réel `status=completed`, taille choisie 50. Ouverture du détail id 1 et de ses 18 champs, puis retour liste avec statut/taille conservés.
5. Nouvelle ouverture du détail puis lien Equipment réel `/equipments/1?site_id=1&company_id=1&page=1&page_size=20`. Aucun statut/type Maintenance transmis. Le nouveau bouton est de nouveau disponible après vérification des parents et réinitialise uniquement la navigation d’entrée Maintenance à page 1/taille 20.

Preuves locales ignorées : [identité](../frontend/tmp/ui-8.5/dev-identity.json), [navigation](../frontend/tmp/ui-8.5/dev-navigation.json), [inverse et retour](../frontend/tmp/ui-8.5/dev-inverse.json).

Cinq GET de contrôle distincts ont ensuite été exécutés via le proxy Angular 4201, avec réponse **200** et en-tête `X-Industrial-Predict-Environment: local-development` :

```text
/api/v1/equipments/1
/api/v1/sites/1
/api/v1/companies/1
/api/v1/maintenance?equipment_id=1&page=1&page_size=20
/api/v1/maintenance/1
```

Les réponses confirment Equipment 1 -> Site 1 -> Company 1, Maintenance 1 -> Equipment 1 et un total de 1 intervention pour cet équipement. Elles concordent avec l’affichage navigateur. Voir [GET réels de contrôle](../frontend/tmp/ui-8.5/dev-http-control.json).

Distinction de preuve : ces cinq statuts proviennent de GET HTTP explicites de contrôle, pas d’une capture des réponses XHR du navigateur. La navigation visuelle est réelle, mais sa trace réseau XHR brute n’est pas disponible avec les outils utilisés. Les scénarios d’erreurs, changements de parents et annulation restent des tests Angular simulés ; ils ne sont pas provoqués sur les données DEV. Les dates du dossier DEV consulté sont à la seconde avec Z ; la précision microseconde et les offsets non nuls sont couverts par les tests simulés, sans prétendre que ce dossier réel les démontre.

Aucune action d’écriture, aucun POST/PATCH/DELETE Maintenance ou Equipment, aucune opération SQL directe, aucun accès historique. Aucun compteur ou empreinte des huit tables n’a été relevé : leur intégrité globale n’est pas revendiquée comme nouvellement contrôlée. Il ne s’agit pas de la recette complète UI 8.6.

## Réserves et état Git

B-MAIN-01 à B-MAIN-09 restent ouverts : validation/chronologie Pydantic et SQL, valeurs numériques et précision, workflow, intégrité/concurrence, dates administratives, authentification/isolation tenant, volumes et politique de coût/audit. Les filtres et références frontend ne sont pas une autorisation multi-tenant. Les dates administratives naïves restent sans hypothèse UTC ; aucune devise n’est ajoutée. Le seed strict et le capteur ID 1 ne sont ni modifiés ni requalifiés comme conformes.

La recette visuelle utilisateur est validée à 9/9 ; elle ne reste plus en attente. Limites de preuve de l’agent conservées : cible exacte 390 non obtenue, captures mobile/tablette indisponibles et trace XHR brute DEV absente. Le contrôle SQL global d’intégrité relève de UI 8.6, non commencée. Le dialogue natif d’abandon historique n’est pas revalidé. Le dépassement du budget initial et les réserves backend restent ouverts.

Seuls les six fichiers listés sont concernés. Aucun changement backend, SQL, Docker, package, contrat GET ou module Sensors/Measurements. Aucun formulaire Maintenance. Rapports historiques préservés. Index vide, HEAD `c66e7f3` inchangé ; aucun commit, push, merge ou rebase. UI 8.6 non commencée. En attente de validation avant commit.
