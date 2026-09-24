# 2.1.9 — Tests automatisés du Data Pipeline

Depuis `backend`, avec Python 3.12, les dépendances backend et pandas :

```powershell
python -m unittest discover -s ../tests/data_pipeline -t ../tests -v
python -m unittest discover -s ../tests -v
python -m compileall app
```

Le paramètre `-t ../tests` permet de réutiliser `dashboard.support.DatabaseCase`.
La suite suit la structure `unittest` existante, sans ajout de framework.

## Couverture et conventions

- `support.py` : données déterministes et liste explicite des colonnes attendues.
- `test_transforms.py` : dataset vide, UTC, ordre capteur/date/id, qualité,
  valeurs manquantes/non numériques, doublons, timestamps invalides, distribution
  des qualités, intervalles, profils réguliers/irréguliers et fenêtres glissantes.
  Les formules attendues sont calculées explicitement, sans réutiliser le code testé.
- `test_pipeline.py` : filtres transmis exactement à l'extracteur, fenêtre par
  défaut/personnalisée, toutes les transformations réelles, colonnes dérivées,
  rapports et orchestration avec extraction SQL réelle sur base isolée.
- `test_extractor.py` : vraies requêtes SQL, tous les filtres seuls et combinés,
  périmètres incohérents, ancêtres corrects, ordre timestamp puis id croissants,
  bornes inclusives/exclusives et absence de résultats.

L'écart-type attendu est l'écart-type d'échantillon (`ddof=1`) : première valeur
indéfinie. Les premières différences temporelles et numériques sont indéfinies
pour chaque capteur. Les tests utilisent des valeurs très différentes entre
capteurs pour détecter toute contamination. Ils vérifient aussi la non-mutation
des entrées et l'absence de comptage des observations manquantes.

Le dataset construit à partir d'une liste vide est actuellement sans colonnes ;
ce contrat est testé explicitement. Les colonnes dérivées sont exigées sur les
datasets non vides. Aucun nettoyage implicite n'est ajouté aux transformations.

## Base de test et PostgreSQL

La fixture réutilisée crée une base SQLite en mémoire par test par défaut ; elle
remplace la configuration de connexion avant l'import des modèles. Aucun accès à
la base de développement, aucune modification des modèles ou des routes.

Pour PostgreSQL, utiliser la variable du pattern existant :

```powershell
$env:DASHBOARD_TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/industrial_predict_test'
python -m unittest discover -s ../tests/data_pipeline -t ../tests -v
```

La fixture crée un schéma unique avec une transaction annulée après le test. Le
compte doit pouvoir créer des schémas dans cette base dédiée aux tests. Sans
PostgreSQL configuré, le test natif des décalages horaires est ignoré explicitement.
Une connexion PostgreSQL indisponible dans les tests d'extracteur est également
signalée par un skip. La fixture des autres tests conserve son comportement
existant en cas de configuration explicite inaccessible (échec).

SQLite ne restitue pas de datetime avec fuseau. Les tests SQL courants utilisent
des instants UTC, puis le builder les convertit en UTC. Ils ne prouvent pas la
sémantique native timestamptz. Le test PostgreSQL dédié vide l'identity map,
utilise des bornes avec décalage `+05:30` et vérifie les timestamps réhydratés.

## Bugs reproduits — aucun correctif métier appliqué

1. **Fenêtre de taille 1 :** `WindowFeatureBuilder.build(..., window_size=1)`
   échoue sur un dataset non vide avec `min_periods 2 must be <= window 1`.
   La taille est autorisée par le contrôle `window_size >= 1`, mais le rolling
   standard deviation impose `min_periods=2`. Test : `test_window_one`.
   Correction recommandée dans une étape dédiée : permettre une fenêtre de 1
   tout en conservant un écart-type indéfini avec une seule observation.
2. **Fenêtre invalide et dataset vide :** `window_size=0` n'est pas rejeté pour un
   DataFrame vide, car le retour anticipé précède le contrôle. Test :
   `test_invalid_window_size_empty_dataset`. Recommandation : valider la taille
   avant le retour sur dataset vide, conformément à la règle demandée.
3. **Timestamp textuel illisible :** `DataQualityReport.analyze` retourne zéro
   timestamp invalide pour `"not-a-timestamp"`, car il ne compte que `isna()`.
   Test : `test_unparseable_timestamp_is_reported_invalid`. Ce défaut concerne
   l'analyse directe d'un DataFrame brut ; le builder impose déjà la conversion
   des dates en amont. Recommandation : détecter les dates non convertibles dans
   le rapport, ou formaliser explicitement un contrat d'entrée déjà normalisée.

Les trois cas restent visibles comme échecs/erreur, sans `expectedFailure` ni skip
masquant un bug. Aucune correction silencieuse n'a été effectuée.

## Environnement

L'exécution locale utilise pandas 3.0.6, disponible dans l'environnement virtuel.
`backend/requirements.txt` ne déclare actuellement pas pandas, alors que le module
métier l'importe. Une installation vierge à partir de ce fichier seul risque donc
de ne pas pouvoir charger le Data Pipeline. Ce problème de dépendance est signalé,
sans modification du fichier de dépendances dans cette étape consacrée aux tests.

## Résultats du 24 septembre 2026

| Suite | Réussis | Échecs d'assertion | Erreurs | Ignorés | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Data Pipeline | 50 | 2 | 1 | 1 | 54 |
| Toute la suite | 224 | 2 | 1 | 3 | 230 |

Les deux commandes de tests retournent un code non nul à cause des trois défauts
documentés ci-dessus. Les tests ignorés nécessitent PostgreSQL : extraction avec
fuseaux, pagination avec fuseaux et regroupement journalier du dashboard.
`python -m compileall app` réussit. Les avertissements existants de dépréciation
SQLAlchemy/datetime.utcnow et Starlette/httpx restent hors périmètre.

Seuls les six fichiers de `tests/data_pipeline/` sont créés ; aucun code métier,
modèle SQLAlchemy ou route API n'a été modifié. Aucun commit effectué.
