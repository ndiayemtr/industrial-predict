# UI 4.7.5 - Bilan de clôture de la validation intégrée Sites

Contrôle du 19 octobre 2026 (UTC), branche `feature/frontend-sites`, HEAD `8554684`. Clôture proposée **avec une réserve navigateur documentée**, soumise à validation. Aucun début d'UI 4.8, commit, push ou merge.

## Périmètre et conservation

L'état initial comporte uniquement `?? docs/ui-4.7.4-real-sites-crud.md`. Ce [rapport UI 4.7.4](ui-4.7.4-real-sites-crud.md) est conservé sans modification, ainsi que ses preuves locales ignorées par Git. Son SHA-256 reste `85239128d974a7f4b86a549e04d2748f4f2f59094d771e15dd387cdc9750fbaa`.

Cette étape relit les traces existantes et effectue un nouvel instantané PostgreSQL en transaction `READ ONLY`. Elle ne rejoue aucun POST/PATCH réel, y compris les refus 409/422. Aucun DELETE, transfert d'entreprise, nettoyage, réapplication du seed, reset, migration ou modification backend. Aucune connexion de cette étape ne vise la base historique, PETROSEN ou la restauration UI 4.7.1. Le site dédié de validation DEV id=4 reste conservé.

Les preuves complémentaires sont dans `D:\projets\industrial-predict\frontend\tmp\ui-4.7.5`, ignoré par Git. Le manifeste `ui474-evidence-sha256.json` conserve les empreintes des fichiers de preuve UI 4.7.4.

## Synthèse du cycle UI 4.7

| Étape | Validation et portée |
| --- | --- |
| UI 4.7.2 / 4.7.2.1 | Environnement permanent DEV : PostgreSQL 5434, API 8001, Angular 4201, identité vérifiée, proxy sans repli vers les services historiques. Voir les [contrôles d'intégration](ui-4.7.2-integration-environment.md) et la [transition DEV](ui-4.7.2.1-development-environment.md). |
| UI 4.7.3 | [Seed fictif](ui-4.7.3-development-data.md) : 36 lignes dans huit tables, intégrité et parcours de lecture contrôlés. |
| UI 4.7.4 | Création, fiche, modification et rechargement réels depuis Angular ; liste, pagination, recherche et contexte ; conflit 409 dans le formulaire ; refus 422 réel via le proxy. |
| UI 4.7.5 | Recoupement indépendant des traces et instantanés, contrôle SQL actuel en lecture seule, couverture frontend 422 et abandon complétée, clôture proposée avec limite navigateur explicite. |

Les validations héritées sont attribuées à leurs rapports ; elles ne sont pas toutes réexécutées ici.

## Preuves HTTP et persistance PostgreSQL

Le script local `audit.py` relit `http.jsonl`, `writes-exact.json`, les quatre instantanés SQL UI 4.7.4 et le nouvel instantané `current.json`. Les assertions réussies sont consignées dans `audit-results.json`.

| Requête existante UI 4.7.4 | Résultat recoupé |
| --- | --- |
| POST `/api/v1/sites` | **201**, site dédié id=4, code `UI474-SITE-20261019-01`, company_id=1 ; tous les champs de réponse correspondent à `created.json`. |
| PATCH `/api/v1/sites/4` | **200** ; corps limité à name/description ; tous les champs de réponse correspondent à `updated.json`. |
| POST doublon | **409**, sans ligne supplémentaire. |
| POST sans name via le proxy | **422**, `loc=["body","name"]`, sans ligne supplémentaire. |

Les quatre événements d'écriture de `http.jsonl` sont identiques à `writes-exact.json`. Aucun autre événement d'écriture dans cette trace. Après PATCH, seules name, description et updated_at diffèrent de l'état créé ; id, code, entreprise et created_at sont conservés. Les dates des réponses sont comparées aux dates SQL après lecture ISO, sans changer leur fuseau ni leur valeur.

L'instantané actuel vérifie la même identité : `industrial_predict_dev`, `ui47_app` non superutilisateur, cluster `industrial-predict-development`, OID 16384, révision `09ac8101e9fe`, même instance que les preuves précédentes. Toutes les lignes actuelles sont identiques à `after.json`, y compris le site dédié modifié.

| Table | Seed initial | État actuel |
| --- | ---: | ---: |
| companies | 2 | 2 |
| sites | 3 | 4 |
| equipments | 4 | 4 |
| sensors | 6 | 6 |
| measurements | 18 | 18 |
| maintenance_records | 3 | 3 |
| prediction_records | 0 | 0 |
| maintenance_recommendations | 0 | 0 |

Comparaison de **toutes les colonnes des 36 lignes seed** par table et id dans created, updated, after et current : aucune différence. Les trois sites seed DEV sont inchangés. Neuf clés étrangères sans orphelin ; aucun code dupliqué dans companies/sites/equipments/sensors. Aucun nouvel appel métier d'écriture n'est nécessaire pour confirmer cette persistance.

Le premier essai de lecture SQL sous restriction Windows a été refusé à l'accès à la configuration privée, avant connexion. Le contrôle effectif a ensuite réussi avec les permissions nécessaires, sans afficher les secrets. Le script d'instantané est une copie locale de celui d'UI 4.7.4, avec sortie dans le nouveau dossier.

## Réserve 1 - Abandon des modifications

**Couverture Angular confirmée et renforcée ; validation complète du dialogue natif navigateur encore réservée.**

Les tests existants utilisent le vrai routeur Angular et `HttpTestingController`, avec `window.confirm` simulé. Ils vérifient refus de navigation, acceptation de l'abandon, conservation du contexte, `beforeunload`, absence de toast et absence d'écriture. L'édition vérifie également le retour aux valeurs d'origine, qui autorise de nouveau la sortie. Les tests d'enregistrement couvrent le blocage de navigation pendant la requête et la sortie après succès.

Complément ciblé dans les deux tests de protection existants : clic sur le véritable bouton DOM Annuler, réponse false à confirm, maintien de l'URL et du nom saisi, aucun appel HTTP. Les branches true et `beforeunload` restent vérifiées. Le test de `beforeunload` vérifie l'événement annulé ; il ne démontre pas l'affichage natif du navigateur.

Essai navigateur isolé sur `127.0.0.1:8098`, avec le simulateur existant et le build production UI 4.7.4. Aucun proxy, client FastAPI ou accès PostgreSQL ; CSP limitée à l'origine locale, données fictives en mémoire. Le journal final `simulation-journal.json` vaut `[]` et `simulation-status.json` confirme `upstream=null`, `persistence=memory-only`.

Le formulaire se charge et accepte le brouillon. Le premier essai Annuler aboutit à la liste sans preuve exploitable de la réponse au dialogue. Une seconde tentative de refus explicite rencontre un délai dépassé du pilotage navigateur ; l'API de dialogue ne fournit aucun dialogue accessible. Le formulaire reste ensuite ouvert avec le brouillon. Cela ne permet pas d'attester le choix utilisateur false/true dans un dialogue natif, ni de conclure à un défaut applicatif. Capture `abandon-form.png` et DOM `abandon-dom.txt` conservés comme **preuves partielles**, pas comme validation complète.

Le nom est ensuite remis à sa valeur vide d'origine et Annuler revient à la liste sans blocage. L'onglet temporaire est fermé et le serveur de simulation arrêté ; les services DEV ne sont pas redémarrés.

Pour lever totalement cette réserve : sur le simulateur isolé, contrôler manuellement en création puis édition le dialogue Annuler (rester avec saisie conservée, puis quitter avec contexte conservé) et le rechargement avec brouillon. Ne pas enregistrer. Cette vérification reste à valider séparément ; la clôture documentaire ne la remplace pas.

## Réserve 2 - Affichage frontend des erreurs 422

**Réserve levée au niveau des tests frontend ; aucun nouveau 422 réel soumis.** Le 422 UI 4.7.4 établit le refus backend via le proxy, sans prouver son affichage dans le navigateur.

Les tests existants confirment : propagation fidèle des erreurs du service sans retry ; alerte et saisies conservées ; aucun toast de succès ; mapping des seuls champs reconnus sous `body`, message local sûr et focus sur le premier champ. En création, les réponses detail textuelles et les messages serveur contenant du balisage étaient déjà couvertes. En édition, code est mappé et company_id ignoré ; aucun POST de recréation.

Deux cas manquants sont ajoutés uniquement au test d'édition :

- Tableau detail contenant name/description, entrée null, champs inconnus, champ query, champ imbriqué et company_id : seuls name/description sont signalés, priorité de focus sur name même si description apparaît d'abord, aucun balisage serveur rendu.
- detail textuel : alerte générique, aucun champ attribué arbitrairement, texte brut serveur non affiché.

Dans les deux cas : saisie conservée, état error, résultat non incertain, aucune notification de succès ni nouvelle requête automatique. Aucun code applicatif n'a nécessité de correction.

## Vérifications techniques

Les tests et le build sont exécutés séquentiellement ; résultats détaillés dans les journaux locaux.

- Première suite Angular : 582 réussis / 583 ; seul échec, timeout de 5 s du test shell responsive à 1440 px (5266 ms), hors fichiers modifiés. Aucun échec d'assertion signalé. Journal `angular-tests.log` conservé.
- Nouvelle suite complète avec configuration temporaire `maxWorkers: 2`, sans changement des délais, assertions ou exclusions : **583 tests réussis, 42 fichiers**, durée 24,92 s ; compilation 16,530 s. Journal `angular-tests-two-workers.log`. La sensibilité à la concurrence du test shell est documentée comme dette de stabilité, sans modification hors périmètre.
- Build production réussi en **17,124 s**. Avertissement existant : 601 509 octets (601,51 ko) pour un budget warning de 500 ko, dépassement 101,51 ko. Aucun budget relevé. Les **31 fichiers JS/CSS** ont les mêmes empreintes que le build UI 4.7.4, pour 785 921 octets au total. Journal `production-build.log` et synthèse `technical-results.json`.

## Limites et dettes conservées

- Dialogue natif d'abandon : réserve navigateur ouverte décrite ci-dessus ; couverture Angular réussie ne vaut pas validation manuelle native.
- Avertissement existant de budget initial Angular : traiter l'optimisation dans une étape dédiée ; aucun budget augmenté ici.
- Test shell responsive sensible au délai sous concurrence ; réduction temporaire des workers pour la vérification, sans changement de configuration suivie.
- Filtrage par entreprise vérifié fonctionnellement ; aucune démonstration d'autorisation SaaS multi-tenant. Authentification, autorisation et secrets historiques de Git restent des sujets distincts.
- Aucun DELETE, transfert, test de charge, panne concurrente, lecteur d'écran réel ou audit exhaustif responsive/zoom revendiqué. Les dates administratives sans fuseau restent affichées selon les composantes serveur.
- Les preuves volumineuses sont locales et ignorées par Git : conserver ces répertoires avec le rapport pour pouvoir reproduire l'audit. Ne pas publier en bloc les configurations privées d'environnement.

## Fichiers et état Git final

Fichiers modifiés par UI 4.7.5 :

- `frontend/src/app/features/sites/pages/site-create/site-create.component.spec.ts` : refus via le bouton Annuler.
- `frontend/src/app/features/sites/pages/site-edit/site-edit.component.spec.ts` : même contrôle et deux cas 422 manquants.
- `docs/ui-4.7.5-sites-closure.md` : présent rapport.

Le rapport UI 4.7.4 préexistant reste non suivi et inchangé. Aucun fichier de production, backend, dépendance, configuration suivie ou budget modifié. Les preuves et la configuration de test à deux workers restent ignorées.

```text
 M frontend/src/app/features/sites/pages/site-create/site-create.component.spec.ts
 M frontend/src/app/features/sites/pages/site-edit/site-edit.component.spec.ts
?? docs/ui-4.7.4-real-sites-crud.md
?? docs/ui-4.7.5-sites-closure.md
```

Branche `feature/frontend-sites`, HEAD `8554684`, index vide. `git diff --check` conforme ; les espaces de fin de ligne et les liens relatifs du nouveau rapport sont également contrôlés séparément, car il n'est pas suivi. Aucun commit, push ou merge. **Validation attendue avant toute suite ; UI 4.8 non commencée.**
