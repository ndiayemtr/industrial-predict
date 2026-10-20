# UI 5.7 - Validation intégrée Équipements

20 octobre 2026. Branche feature/frontend-equipments, HEAD b4ffa06. Dépôt propre au départ. Aucun code applicatif, backend, Docker ou package modifié. Aucun commit, push ou merge. UI 5.8 non commencée.

## Environnement réel vérifié

- Angular 127.0.0.1:4201 -> FastAPI 127.0.0.1:8001 -> PostgreSQL 127.0.0.1:5434 / industrial_predict_dev.
- PostgreSQL 17.10, cluster industrial-predict-development, OID 16384. Marqueur d'instance identique dans la configuration privée, SQL, /__dev/identity direct et via Angular. Aucun secret de connexion affiché ou ajouté au dépôt.
- Alembic en base et tête des sources : 09ac8101e9fe. Aucune migration exécutée.
- Compte effectif ui47_app non superutilisateur, sans CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS, DDL ni modification d'Alembic. Identité administrateur dédiée utilisée uniquement pour la lecture de l'identifiant du cluster par le contrôle existant.
- Lanceurs DEV et proxy actifs confirmés. Cible fixe 8001, contrôle d'identité avant transfert et absence de repli vers 8000 vérifiés dans le proxy existant. Aucun appel aux bases ou services historiques.
- Identité revérifiée avant les écritures et après restauration du lanceur API normal. Les trois ports finaux restent liés à 127.0.0.1.

## Réutilisation de l'équipement existant

L'équipement UI5-EQ-TEST-001 existait avant cette intervention :

| Champ | Valeur constatée |
| --- | --- |
| Identifiant de preuve | 5 |
| Nom | Pompe hydraulique de test - Modifiée |
| Type | hydraulic_pump |
| Statut / criticité | maintenance / high |
| Description | Équipement modifié pour valider le PATCH différentiel. |
| Site | Site de production - UI47-SITE-A-PROD, entreprise UI47-COMP-A |
| Création | 2026-10-20T06:48:29.059069 |
| Dernière modification | 2026-10-20T06:50:03.556981 |

Sa fiche a été vérifiée par GET direct FastAPI, GET via Angular, affichage Angular et actualisation complète. Toutes les valeurs HTTP correspondent à PostgreSQL. Ses valeurs et ses horodatages sont restés strictement identiques à la fin.

Aucune recréation ni modification de cette ligne. Les recherches dans les preuves locales de travail et les dossiers d'intégration n'ont retrouvé aucune trace POST/PATCH initiale portant ce code. Les captures initiales de ce parcours n'étaient pas disponibles dans ces preuves. Ses payloads initiaux et ses statuts HTTP d'écriture ne sont donc pas reconstitués ni déduits de ses dates.

## Essai complémentaire autorisé et borné

L'utilisateur a explicitement choisi le scénario complémentaire proposé : un nouvel équipement fictif dédié, un POST puis un PATCH limité à sa description. Code retenu : UI57-EQ-20261020-01, absent avant création ; site de production de l'entreprise A vérifié en base et dans Angular.

Les deux actions ont été effectuées dans les formulaires Angular réels, avec FastAPI et PostgreSQL réels, sans réponse simulée. Un observateur ASGI temporaire externe au code backend a enregistré les méthodes, chemins, query strings et corps exacts, sans en-têtes d'authentification. Le lanceur DEV et son contrôle SQL d'identité sont conservés dans ce processus.

Le garde-fou n'autorisait qu'une tentative POST avec les sept valeurs exactes prévues, puis une tentative PATCH de l'identifiant réellement créé avec la seule description exacte prévue. Toutes les autres écritures, dont DELETE, étaient bloquées. Aucun blocage de ce garde-fou n'a été rencontré. Journal observateur : 29 GET, 1 POST, 1 PATCH, 0 DELETE. Les diagnostics d'identité et les GET effectués hors de cette fenêtre sont conservés séparément.

Pendant le démarrage de l'observateur, deux diagnostics d'identité ont échoué avant disponibilité ; un second lancement a ensuite été refusé par le contrôle de port occupé. Aucun POST n'a précédé la réussite des contrôles direct et via Angular. Un chargement initial des catalogues est resté indisponible après ce redémarrage ; les relances GET manuelles ont récupéré les références avant la saisie. Aucun statut précis de ces requêtes initiales non capturées n'est revendiqué.

L'observateur a été arrêté après les deux écritures. Le lanceur FastAPI DEV normal est rétabli et son identité, ses compteurs et ses réponses ont été vérifiés de nouveau. Aucun fichier backend ou de configuration suivi n'a changé.

### POST réel depuis Angular

POST /api/v1/equipments, corps exact observé :

```json
{"name":"Pompe de validation intégrée UI 5.7","code":"UI57-EQ-20261020-01","equipment_type":"hydraulic_pump","description":"Équipement fictif dédié à la validation intégrée UI 5.7.","status":"operational","criticality":"medium","site_id":1}
```

Réponse réelle 201, corps exact :

```json
{"name":"Pompe de validation intégrée UI 5.7","code":"UI57-EQ-20261020-01","equipment_type":"hydraulic_pump","description":"Équipement fictif dédié à la validation intégrée UI 5.7.","status":"operational","criticality":"medium","id":6,"site_id":1,"created_at":"2026-10-20T07:24:12.186073","updated_at":"2026-10-20T07:24:12.186073"}
```

Aucun company_id, id, horodatage ou descendant dans le POST. Les défauts operational/medium sont conservés malgré le contexte de retour maintenance/high. Navigation vers la fiche, un toast et une confirmation accessible « Équipement créé avec succès. ». Actualisation et SELECT PostgreSQL conformes à la réponse 201 avant toute modification.

### PATCH différentiel réel depuis Angular

Le formulaire préremplit les valeurs réelles ; site et entreprise sont des textes de lecture seule, sans sélecteur. Un premier clic Enregistrer sans changement a affiché « Aucune modification à enregistrer. » ; le journal contenait alors un seul POST et aucun PATCH.

Seule la description a ensuite été saisie à nouveau. PATCH /api/v1/equipments/6, corps exact :

```json
{"description":"Description modifiée depuis Angular pour valider le PATCH différentiel UI 5.7."}
```

Réponse réelle 200, corps exact :

```json
{"name":"Pompe de validation intégrée UI 5.7","code":"UI57-EQ-20261020-01","equipment_type":"hydraulic_pump","description":"Description modifiée depuis Angular pour valider le PATCH différentiel UI 5.7.","status":"operational","criticality":"medium","id":6,"site_id":1,"created_at":"2026-10-20T07:24:12.186073","updated_at":"2026-10-20T07:25:19.617479"}
```

Le PATCH ne contient ni site_id, company_id, nom, code, type, enums inchangés, id ou dates. La comparaison des deux lectures SQL montre exactement description et updated_at modifiés. Tous les autres champs sont identiques.

Navigation vers le détail avec les sept paramètres de retour conservés : company_id=1, site_id=1, page=1, page_size=1, search=UI5-EQ-TEST-001, status=maintenance, criticality=high. Un toast unique et la confirmation accessible « Équipement modifié avec succès. » ont été observés. L'actualisation complète, les GET directs et via Angular et la lecture SQL confirment la description persistée.

## Parcours et non-régressions réels

- Liste sans contexte : aucune entreprise ni aucun site présélectionné, état Sélection attendue. Sélection explicite entreprise A puis site de production : trois équipements avant l'essai complémentaire.
- Pagination serveur page_size=1 : pages 1, 2 et 3 avec identifiants 1, 2 et 5 ; Suivant désactivé à la dernière page. Recherche du code existant depuis la page 3 : retour page 1 et un résultat. Taille, filtres et contexte conservés dans les liens de détail et de création.
- GET réels indépendants statut maintenance et criticité high : deux résultats chacun avant création dédiée ; combinaison : l'équipement existant seul. Recherche dans le site de B : zéro résultat.
- Contexte entreprise 2 / site 1 : message d'appartenance incohérente, recherche désactivée, aucun tableau et aucun GET Equipment liste dans le journal de cette fenêtre.
- Parents réels et valeurs de détail indépendants des filtres de retour ; aucun transfert proposé en édition. Index PostgreSQL unique global ix_equipments_code confirmé, sans colonne site_id dans la clé et sans doublon.
- Companies : deux entreprises affichées et GET 200. Sites : trois sites pour A, un pour B, dont l'essai UI 4.7.4 conservé avec ses valeurs exactes.
- Dashboard réel pour A, période UTC [2026-10-12, 2026-10-17[ : réponse 200 et affichage cohérent avec 3 sites, 5 équipements et 4 capteurs, dont 3 actifs, 12 mesures sur la période. Aucun endpoint de calcul ML appelé.
- GET équipement absent : 404 réel et état Angular « Équipement introuvable (404) ». GET liste avec statut invalide : 422 réel via Angular.

## Ce qui reste validé par HTTP simulé

Les résultats UI 5.6.1 de référence couvrent notamment : erreurs POST/PATCH 409 et 422, mapping des seuls champs body autorisés, erreurs réseau/5xx, acquittement d'un résultat incertain, double soumission, réponses obsolètes, navigation refusée et récupération, description omise/vide/null, enums, Unicode et valeurs restaurées.

Ces essais d'erreur d'écriture n'ont pas été rejoués sur FastAPI pendant UI 5.7 afin de limiter les écritures aux deux actions autorisées. Le 422 réel de cette étape est un refus de filtre GET, pas une preuve de gestion réelle d'un 422 POST/PATCH. Le 409 Equipment reste couvert par les tests simulés et la contrainte d'unicité SQL ; aucun nouveau POST de doublon n'a été effectué. Une requête unique observée par action ne remplace pas le test simulé de double clic concurrent.

Réserve d'abandon maintenue : refus/acceptation confirm, garde Router et beforeunload sont couverts par les tests Angular existants. Aucune vérification native supplémentaire fiable du dialogue n'a été réalisée dans cette étape.

## Données conservées et intégrité

| Table | Avant | Après |
| --- | --- | --- |
| companies | 2 | 2 |
| sites | 4 | 4 |
| equipments | 5 | 6 |
| sensors | 6 | 6 |
| measurements | 18 | 18 |
| maintenance_records | 3 | 3 |
| prediction_records | 0 | 0 |
| maintenance_recommendations | 0 | 0 |

- Les 36 lignes du seed correspondent toujours exactement à la fixture, valeurs et parents compris. Le contrôle utilisé est en lecture seule, write=False ; aucune réapplication du seed.
- Les empreintes des 38 lignes préexistantes sont identiques avant/après, dont UI5-EQ-TEST-001 et le site UI474-SITE-20261019-01. Les sept tables autres que equipments ont aussi des empreintes globales identiques.
- Seule une ligne Equipment a été ajoutée ; la modification suivante est limitée à sa description et à l'horodatage serveur. Cet équipement fictif est conservé, sans nettoyage.
- Neuf clés étrangères contrôlées avant/après : zéro orphelin. Zéro code dupliqué dans Companies, Sites, Equipments et Sensors.
- Aucun DELETE, transfert, reset, sauvegarde PostgreSQL ou modification de données historiques. Les preuves SQL locales contiennent des empreintes et les seules lignes utiles à la comparaison, pas un dump de base.

## Références techniques et preuves locales

Les 864 tests Angular réussis dans 49 fichiers et le build réussi de UI 5.6.1 restent les références ; ils n'ont pas été relancés. Les empreintes des sources Angular sont identiques. Bundle initial de référence : 604,81 ko, avertissement existant du budget de 500 ko. Aucun budget changé.

Contrôles exécutés ici : identités et permissions DEV, validation readonly du seed, comparaison SQL par empreintes, contrôles FK/unicité/Alembic, GET réels et navigateur, comparaison des traces POST/PATCH à PostgreSQL et git diff --check.

Preuves de travail ignorées par Git, sans en-tête secret ni fichier de mot de passe :

- [Résumé des comparaisons](../frontend/tmp/ui-5.7/verification-summary.json), [identité finale](../frontend/tmp/ui-5.7/environment-final.json).
- [SQL avant](../frontend/tmp/ui-5.7/sql-before.json), [après création](../frontend/tmp/ui-5.7/sql-created.json), [après PATCH](../frontend/tmp/ui-5.7/sql-after.json).
- [Requêtes et réponses exactes des deux écritures](../frontend/tmp/ui-5.7/writes-exact.json), [journal observateur](../frontend/tmp/ui-5.7/observed-http.jsonl).
- [GET initiaux](../frontend/tmp/ui-5.7/http-get-traces.json), [GET après restauration API](../frontend/tmp/ui-5.7/http-final-get-traces.json), [contexte incohérent](../frontend/tmp/ui-5.7/wrong-context-http.json).
- [Équipement existant actualisé](../frontend/tmp/ui-5.7/screenshots/existing-persisted.jpg), [création confirmée](../frontend/tmp/ui-5.7/screenshots/dedicated-created.jpg), [modification confirmée](../frontend/tmp/ui-5.7/screenshots/dedicated-updated-confirmation.jpg).
- [Persistance finale desktop](../frontend/tmp/ui-5.7/screenshots/final-dedicated-desktop.jpg), [mobile](../frontend/tmp/ui-5.7/screenshots/final-dedicated-mobile.jpg).

## État Git et réserves de clôture

Un seul fichier ajouté : docs/ui-5.7-equipments-integration.md. Index vide, HEAD b4ffa06 inchangé sur feature/frontend-equipments. Aucun secret, dump, trace temporaire ou capture ajouté au suivi Git. Aucun code modifié, aucun commit, push ou merge.

Limites : payloads initiaux de UI5-EQ-TEST-001 indisponibles ; erreurs d'écriture 409/422 et protections de concurrence/abandon couvertes par les tests de référence sans nouvel essai réel destructif ou redondant ; dialogue natif à vérifier manuellement. L'absence actuelle d'autorisation multi-tenant et le budget du bundle restent des dettes connues, non corrigées dans cette validation.

Attendre validation avant clôture UI 5.7. Ne pas commencer UI 5.8.
