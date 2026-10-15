# Étape 2.9.1 - Predictive Maintenance Recommendations

## Objectif

Transformer les résultats analytiques et ML déjà disponibles dans Industrial Predict AI en une recommandation de maintenance principale, compréhensible et priorisée pour chaque équipement.

Le moteur de recommandations V1 ne constitue pas un nouveau modèle ML.

Il combine les résultats existants :

- Anomaly Detection
- Failure Risk
- Health Score
- Remaining Useful Life (RUL)

pour produire une action opérationnelle.

---

## Principe

Pour un équipement donné :

Anomaly Detection

- Failure Risk
- Health Score
- RUL
  ↓
  Recommendation Engine
  ↓
  Une recommandation principale

La recommandation doit être déterministe, explicable et non contradictoire.

---

## Données d'entrée

Le moteur peut utiliser :

- `anomaly_score`
- `failure_probability`
- `failure_risk_level`
- `health_score`
- `health_level`
- `rul_hours`
- `rul_level`

Toutes les données ne sont pas obligatoirement disponibles.

Le moteur doit pouvoir fonctionner avec des signaux partiellement disponibles.

---

## Priorités

Les niveaux de priorité sont :

1. `critical`
2. `high`
3. `medium`
4. `low`

La priorité la plus sévère déterminée par les signaux disponibles prévaut.

---

## Types de recommandations

### urgent_maintenance

Maintenance urgente requise.

Utilisée lorsqu'un risque important de panne à court terme est identifié.

### inspection

Inspection technique recommandée.

Utilisée lorsqu'un équipement présente des signes de dégradation nécessitant une vérification.

### planned_maintenance

Maintenance à planifier.

Utilisée lorsqu'une intervention est nécessaire prochainement mais qu'une action immédiate n'est pas requise.

### monitoring

Surveillance renforcée.

Utilisée lorsqu'un signal anormal existe sans justifier encore une intervention.

### no_action

Aucune intervention particulière requise.

L'équipement continue à être surveillé normalement.

---

## Règles métier V1

### Priorité critical

Une recommandation `urgent_maintenance` avec priorité `critical` est générée si au moins une des conditions suivantes est satisfaite :

- RUL <= 24 heures
- failure_probability >= 0.75
- Health Score < 30

---

## Priorité high

Si aucune règle `critical` n'est satisfaite :

Une recommandation de priorité `high` est générée dans les cas suivants :

- RUL <= 72 heures
- Health Score entre 30 inclus et 50 exclus
- combinaison d'une anomalie forte et d'un risque de panne élevé

Actions possibles :

- `planned_maintenance`
- `inspection`

---

## Priorité medium

Si aucune règle `critical` ou `high` n'est satisfaite :

Une recommandation de priorité `medium` est générée dans les cas suivants :

- RUL <= 168 heures
- anomalie modérée
- dégradation nécessitant une surveillance renforcée

Actions possibles :

- `planned_maintenance`
- `monitoring`

---

## Priorité low

Si aucun signal significatif de risque ou de dégradation n'est détecté :

- priorité : `low`
- recommandation : `no_action`

---

## Gestion des conflits

Le moteur produit une seule recommandation principale.

Ordre de priorité :

critical > high > medium > low

Lorsqu'une condition plus sévère est satisfaite, les règles de niveau inférieur ne remplacent pas cette recommandation.

Exemple :

- RUL = 18 heures
- failure_probability = 0.82
- Health Score = 42
- anomaly_score = 0.76

Résultat :

- priority = critical
- recommendation_type = urgent_maintenance

Même si plusieurs signaux justifient différentes actions, une seule recommandation principale est produite.

---

## Explicabilité

Chaque recommandation doit contenir au minimum :

- priorité
- type de recommandation
- titre
- raison
- action recommandée

Les signaux ayant déclenché la recommandation doivent pouvoir être expliqués.

Exemple :

"Maintenance urgente recommandée car le RUL est inférieur à 24 heures et le risque de panne est supérieur à 75 %."

---

## Données manquantes

Une donnée ML absente ne doit pas provoquer automatiquement une erreur.

Le moteur prend sa décision uniquement à partir des signaux disponibles.

Si aucun signal exploitable n'est disponible, aucune recommandation fiable ne peut être produite.

Ce cas devra être explicitement signalé.

---

## Responsabilité opérationnelle

Industrial Predict AI fournit une aide à la décision.

Une recommandation ne crée pas automatiquement un ordre de maintenance et ne provoque pas automatiquement l'arrêt d'un équipement.

La décision opérationnelle finale appartient au responsable de maintenance ou à l'opérateur autorisé.

---

## Hors périmètre V1

Ne sont pas inclus dans cette première version :

- génération automatique de Work Orders
- planification automatique des techniciens
- optimisation des pièces de rechange
- génération des coûts prévisionnels
- recommandations générées par LLM
- apprentissage automatique du moteur de décision
- arrêt automatique d'un équipement
