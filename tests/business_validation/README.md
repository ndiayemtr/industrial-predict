# 1.4.17.7 — Tests des validations métier

Suite `unittest` cohérente avec les tests existants, sans dépendance supplémentaire.
Les schémas Pydantic réels sont instanciés directement, sans mocks, serveur ni base
de données. Les modèles, services, routes et enums ne sont pas modifiés.

Depuis `backend`, avec Python 3.12 et les dépendances du backend :

```powershell
# Tests ciblés
python -m unittest discover -s ../tests/business_validation -v
# Suite complète, dashboard inclus
python -m unittest discover -s ../tests -v
# Compilation indépendante du résultat des tests
python -m compileall app
```

## Couverture

- Toutes les valeurs des sept enums sont vérifiées sur Create et Update, sous
  forme de chaînes JSON et d'instances Enum ; rejet des valeurs inconnues, vides,
  de casse incorrecte, avec espace initial et numériques. Le vocabulaire attendu
  est explicite pour détecter aussi la disparition accidentelle d'une valeur.
- Valeurs par défaut des Create et absence de champs implicites dans un PATCH vide.
- Unité de capteur obligatoire en création, refus du vide et de null en création,
  refus attendu du vide en Update ; omission autorisée pour un PATCH partiel.
- Timestamp des mesures : objets datetime et chaînes ISO avec fuseau acceptés ;
  objets/chaînes sans fuseau refusés, y compris un tzinfo dont utcoffset vaut None.
- Dates de maintenance : fuseaux, dates facultatives nulles, début antérieur ou
  égal à la fin, rejet de l'ordre inverse et comparaison des instants avec des
  décalages UTC différents.
- Coûts et arrêts : zéro, valeurs positives et valeurs absentes acceptés ; valeurs
  négatives refusées sur Create et Update.

Les validations portant sur un PATCH sont évaluées sur les champs transmis.
La cohérence d'une date modifiée avec une date existante en base relève du service
et n'est pas vérifiable par le seul schéma Update ; aucun comportement de service
supplémentaire n'est supposé ici.

## Résultats du 22 septembre 2026

| Suite | Tests | Réussis | Échecs d'assertion | Erreurs | Ignorés |
| --- | ---: | ---: | ---: | ---: | ---: |
| Validations métier | 33 | 28 | 4 | 1 | 0 |
| Ensemble du projet | 84 | 78 | 4 | 1 | 1 |

Les cas tabulaires utilisent `subTest` : ces nombres désignent les méthodes de
test, pas chaque valeur testée. Les deux commandes de tests retournent un code
non nul. Aucun échec n'est masqué par `expectedFailure` ou par un skip ajouté.
Le test ignoré est le test Dashboard PostgreSQL existant, faute de serveur configuré.
`python -m compileall app` réussit.

Sur cette machine, le Python fourni par Codex a été utilisé avec les paquets de
`backend/.venv/Lib/site-packages`, l'interpréteur Python référencé par le venv
n'étant pas disponible. Aucune modification de l'environnement du projet n'a été
enregistrée pour cette exécution.

## Bugs reproduits, laissés visibles sans correction métier

| Reproduction | Attendu | Constat | Test |
| --- | --- | --- | --- |
| `SensorUpdate(unit="")` | ValidationError, comme en Create | Chaîne vide acceptée : absence de `min_length=1` sur Update | `test_update_rejects_empty_unit` |
| `MaintenanceUpdate(planned_at=datetime(2026, 1, 1))` | Refus sans timezone | Accepté : validateur de fuseau absent sur Update | `test_update_rejects_naive_planned_at` |
| `MaintenanceUpdate(started_at=datetime(2026, 1, 1))` | Refus sans timezone | Accepté pour la même raison | `test_update_rejects_naive_started_at` |
| `MaintenanceUpdate(completed_at=datetime(2026, 1, 1))` | Refus sans timezone | Accepté pour la même raison | `test_update_rejects_naive_completed_at` |
| `MeasurementUpdate(timestamp=None)` | Traitement contrôlé de null : acceptation ou ValidationError selon la convention retenue | AttributeError : le validateur lit `value.tzinfo` sans traiter None | `test_update_null_does_not_raise_unhandled_attribute_error` |

Le dernier cas dépasse le minimum demandé et révèle une exception non contrôlée
sur un champ annoté nullable. Le test ne décide pas à la place du métier si null
doit être autorisé ; il exige que ce cas ne provoque pas d'AttributeError.

Corrections recommandées dans une étape dédiée : appliquer la contrainte d'unité
à Update, partager la validation des fuseaux entre Create et Update de maintenance,
et traiter explicitement null dans le validateur du timestamp de MeasurementUpdate.
Relancer ensuite cette suite sans assouplir les assertions.
