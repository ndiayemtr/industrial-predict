# Étape 1.4.16.1 — Analyse et définition des KPI du dashboard

## Périmètre

Livrable de conception uniquement, fondé sur le code du dépôt au 21 septembre 2026.
Aucune spécification numérotée 1.4.16.1 n'a été trouvée dans le dépôt : le périmètre
retenu est celui de la demande, soit l'analyse de l'architecture et la proposition
des KPI, des sources et des règles de calcul. Les règles ci-dessous sont des
propositions métier, pas des comportements déjà implémentés.

Aucune route, aucun service, repository, schéma exécutable, modèle, migration ou
composant frontend n'est ajouté ou modifié dans cette étape. Aucune donnée de la
base n'a été consultée : la faisabilité est évaluée à partir du schéma et du code.

## Architecture constatée

```text
Company (companies)
  └─ 0..N Site (sites.company_id, obligatoire)
       └─ 0..N Equipment (equipments.site_id, obligatoire)
            ├─ 0..N Sensor (sensors.equipment_id, obligatoire)
            │    └─ 0..N Measurement (measurements.sensor_id, obligatoire)
            └─ 0..N MaintenanceRecord (maintenance_records.equipment_id, obligatoire)
```

Chaque enfant possède exactement un parent. Une intervention appartient directement
à un équipement, sans lien direct avec un capteur ou une mesure. Les relations ORM
utilisent `all, delete-orphan` et les clés étrangères `ON DELETE CASCADE` : les
indicateurs ne peuvent porter que sur les données conservées. Les rattachements
sont modifiables et non historisés ; les événements passés sont donc attribués au
site et à l'entreprise actuels de l'équipement.

Le backend suit le chemin `routes FastAPI → services → repositories SQLAlchemy →
PostgreSQL`, avec des schémas Pydantic d'entrée/sortie. Les routes sont enregistrées
dans `backend/app/main.py` sous `/api/v1`. Les repositories proposent des lectures
CRUD et des listes par parent ; les services portent les validations et les commits.
Il n'existe pas de couche d'agrégation dashboard. Les méthodes `get_all()` chargent
des listes complètes et ne constituent pas une bonne base pour agréger les mesures.

| Entité | Données exploitables | Limites constatées |
| --- | --- | --- |
| Company / Site | Identifiants, noms, codes, lien entreprise–site | Pas de calendrier d'exploitation ni de fuseau métier |
| Equipment | `site_id`, `equipment_type`, `status`, `criticality` | État courant seulement ; valeurs libres, défauts `operational` et `medium` |
| Sensor | `equipment_id`, `sensor_type`, `unit`, `status` | Défaut `active` ; aucune fréquence attendue ni seuil d'alerte |
| Measurement | `sensor_id`, `timestamp`, `value`, `quality` | Défaut `good` ; pas d'unicité sur `(sensor_id, timestamp)` ni date d'ingestion |
| MaintenanceRecord | Type, statut, priorité, dates, arrêt, coût, code panne | Défauts `planned` et `medium` ; dates, coût et arrêt facultatifs ; aucune devise |

Les schémas et services n'imposent pas de vocabulaire fermé pour les statuts,
types, criticités ou qualités, ni de validation métier des montants négatifs ou
de la chronologie des interventions. `Sensor.unit` est facultatif dans le schéma
Pydantic mais obligatoire en base. Ces constats sont documentés sans correction.
Les dates des mesures et interventions sont déclarées avec fuseau en base ; les
dates techniques de Company, Site, Equipment et Sensor sont sans fuseau.

## Conventions proposées

1. **Périmètre :** entreprise sélectionnée, puis filtres optionnels site et
   équipement. Vérifier leur appartenance ; une combinaison incohérente doit être
   rejetée, et non élargie silencieusement. Filtrer les mesures par
   `Measurement → Sensor → Equipment → Site → Company`, et les interventions par
   `MaintenanceRecord → Equipment → Site → Company`. Ce filtrage ne remplace pas
   une future autorisation d'accès.
2. **Temps :** fixer une seule date de calcul `T` en UTC. Les KPI de flux utilisent
   une période explicite `P = [début, fin)`, avec `début < fin <= T`. Les KPI de stock
   décrivent l'état courant à la lecture, indépendamment de P. Ne pas présenter un
   statut actuel comme un statut historique. Les dates d'entrée doivent préciser
   leur fuseau ; aucune interprétation silencieuse d'une date naïve.
3. **Valeurs proposées :** équipements `operational`, `maintenance`, `out_of_service` ;
   criticité `low`, `medium`, `high`, `critical` ; capteurs `active`, `inactive` ;
   interventions `planned`, `in_progress`, `completed`, `cancelled`, de type
   `preventive`, `corrective`, `predictive`. Hormis les valeurs par défaut constatées,
   ce vocabulaire reste à valider avant implémentation. Les valeurs non reconnues
   restent dans les totaux et dans une catégorie « autres / non reconnus », sans
   être assimilées à une panne ou à un état normal.
4. **Résultats vides :** un comptage vaut 0 ; un ratio à dénominateur nul, une
   moyenne sans observation ou une dernière mesure absente vaut `null` (« non
   disponible »). Arrondir les pourcentages à deux décimales à la restitution,
   après calcul sur les effectifs bruts.
5. **Granularité :** compter chaque identifiant une fois dans son entité. Agréger
   séparément mesures et interventions avant rapprochement ; une jointure des
   deux branches multiplierait artificiellement les comptes et sommes. Conserver
   les équipements sans capteur et les capteurs sans mesure dans les dénominateurs
   concernés. Ne jamais moyenner des pourcentages de sites pour obtenir celui de
   l'entreprise : recalculer depuis les numérateurs et dénominateurs.
6. **Qualité :** rendre visibles les effectifs manquants, invalides et non reconnus.
   Une valeur absente n'est pas zéro. Les sommes de coûts/arrêts portent sur les
   valeurs renseignées, finies et non négatives, accompagnées de leur couverture
   `nombre de valeurs valides / nombre d'interventions éligibles`.

La borne haute exclusive est une convention du futur dashboard. Le repository
actuel des mesures utilise `timestamp <= end_time` : son comportement reste intact.

## KPI prioritaires

Dans ce tableau, E désigne les équipements du périmètre, S leurs capteurs, M les
mesures de ces capteurs dans P, et R les interventions de ces équipements.

| KPI et utilité | Sources | Règle proposée |
| --- | --- | --- |
| Parc suivi | `sites.id`, `equipments.id`, `sensors.id` et clés parentes | Compter distinctement les sites, équipements et capteurs du périmètre courant, y compris les parents sans enfant |
| Répartition des équipements par état | `Equipment.status` | Compter E par statut ; afficher les valeurs non reconnues séparément |
| Part du parc opérationnel | `Equipment.status` | `100 × nombre(status = operational) / nombre(E)` ; indicateur instantané, pas une disponibilité sur P |
| Équipements prioritaires | `Equipment.criticality`, `status` | Compter les criticités `high` ou `critical` ; afficher séparément ceux en `maintenance` ou `out_of_service`. Un statut inconnu reste indéterminé |
| Couverture en capteurs actifs | `Equipment.id`, `Sensor.equipment_id`, `status` | `100 × nombre d'équipements ayant au moins un capteur active / nombre(E)` ; chaque équipement compte une fois |
| Capteurs actifs | `Sensor.status` | Nombre de capteurs `active`, et `100 × ce nombre / nombre(S)` ; état déclaré, pas preuve de communication |
| Volume de mesures | `Measurement.id`, `timestamp` | `nombre(M)` ; séries quotidiennes selon les jours UTC, avec 0 pour les jours sans mesure ; les doublons stockés sont comptés comme des lignes distinctes |
| Qualité déclarée des mesures | `Measurement.quality` | `100 × nombre(M avec quality = good) / nombre(M)` ; toute autre qualité reste au dénominateur, avec répartition des libellés. Ce taux ne prouve pas la validité physique des valeurs |
| Capteurs actifs ayant émis sur P | `Sensor.status`, `Measurement.sensor_id`, `timestamp` | `100 × nombre de capteurs actuellement active avec au moins une mesure dans P / nombre de capteurs actuellement active` ; qualité quelconque, aucune fréquence attendue présumée |
| Dernière mesure par capteur | `Measurement.timestamp`, `id`, `value`, `quality`, `Sensor.unit` | Sélectionner la ligne de timestamp maximal `<= T`, départagée par l'id décroissant ; âge = `T - timestamp`. Sans ligne : « jamais observé ». Afficher valeur, unité et qualité ensemble |
| Charge de maintenance ouverte | `MaintenanceRecord.status`, `priority` | Compter R dont statut dans `{planned, in_progress}`, avec ventilation par priorité ; aucun filtre sur P pour ce stock courant |
| Interventions en retard de démarrage | `status`, `planned_at`, `started_at` | Compter R avec `status = planned`, `planned_at < T` et `started_at IS NULL`. Une date prévue absente est indéterminée ; une intervention en cours n'est pas déclarée en retard de fin faute d'échéance de fin |
| Interventions terminées sur P | `status`, `completed_at`, `maintenance_type` | Compter R avec `status = completed` et `completed_at ∈ P`, ventilé par type ; signaler séparément les completed sans date de fin |
| Part de maintenance corrective | `maintenance_type`, `status`, `completed_at` | `100 × interventions corrective terminées sur P / toutes les interventions terminées sur P` ; les types inconnus restent au dénominateur et sont signalés |
| Arrêt déclaré pour les interventions terminées | `downtime_minutes`, `status`, `completed_at` | Somme des minutes valides sur les interventions terminées sur P ; afficher aussi les heures (`minutes / 60`) et la couverture de saisie |
| Coût déclaré des interventions terminées | `cost`, `status`, `completed_at` | Somme des coûts valides des interventions terminées sur P, avec couverture ; affichage monétaire conditionné à la confirmation d'une devise commune, absente du modèle |

Les mesures futures sont exclues du dernier relevé et des flux achevés, et signalées
comme incohérentes. Les statistiques éventuelles de valeur (min/max/moyenne) doivent
rester par capteur et porter sur les valeurs finies de qualité `good` dans P ; aucune
moyenne globale entre températures, vibrations ou unités différentes. La moyenne
arithmétique des relevés n'est pas une moyenne pondérée par le temps.

Pour les coûts et arrêts, zéro intervention éligible donne une somme de 0 ; des
interventions présentes mais aucune valeur valide donnent `null`. Une couverture
partielle produit une somme explicitement partielle. Des arrêts se chevauchant
peuvent être comptés plusieurs fois : cette somme décrit les déclarations, pas la
durée d'indisponibilité réelle. Toute la déclaration est affectée à la période de
fin d'intervention ; elle n'est pas répartie sur les jours traversés. Aucun symbole
de devise ne doit être inventé ; sans convention de devise commune, différer le
KPI monétaire. Le stockage actuel en Float ne garantit pas une exactitude comptable.

## KPI à différer

| KPI envisagé | Données ou décisions manquantes |
| --- | --- |
| Capteurs silencieux au-delà d'un délai | Fréquence d'acquisition et tolérance par capteur/type ; l'âge de la dernière mesure est affichable sans inventer un seuil |
| Disponibilité réelle, MTBF, MTTR | Historique des états, périodes d'exploitation, événements de panne et bornes de réparation fiables ; `completed_at - started_at` est une durée d'intervention, pas nécessairement de réparation |
| Taux de maintenance réalisée à temps | Échéance de fin et historique des changements de planning/statut |
| Alertes, anomalies, score de santé, risque de panne, durée de vie restante | Seuils métier, entités d'alerte/prédiction, modèle ML validé et sorties horodatées ; la criticité n'est pas une probabilité de panne |
| Complétude réelle de télémétrie | Nombre de mesures attendues, calendrier et règle de déduplication ; le volume reçu seul ne suffit pas |
| Économies et retour sur investissement | Référence de comparaison, coût d'arrêt et devise |

## Exemples de vérification pour une future implémentation

- Deux équipements, dont un avec trois capteurs actifs : couverture = 50 %, pas
  150 %. Deux interventions sur cet équipement restent deux, quel que soit le
  nombre de mesures jointes.
- Quatre mesures sur P, dont trois `good` : qualité déclarée = 75 %. Une mesure à
  `début` est incluse ; une mesure à `fin` appartient à la période suivante.
- Aucun équipement : comptes à 0 et taux opérationnel/couverture à `null`.
  Un équipement sans capteur reste dans le total du parc.
- Trois interventions terminées sur P, arrêts 30, 0 et null : total déclaré 30 min,
  couverture 2/3. Si tous les arrêts sont absents : total `null`.
- Une intervention planned sans `planned_at` reste ouverte mais son retard est
  indéterminé. Une planned à `planned_at = T` n'est pas encore en retard.
- Un capteur avec deux relevés au même instant retient l'id le plus élevé pour le
  dernier relevé ; les deux restent inclus dans le volume. Un relevé futur ne
  remplace pas la dernière mesure passée.
- Une entreprise A ne reçoit aucune mesure/intervention de B. Un site vide de A
  apparaît dans le compte des sites ; un site de B sélectionné avec A est rejeté.
- Un statut inconnu contribue au total et à la catégorie non reconnue, jamais au
  numérateur « operational » ou « completed » par déduction.

## Fichiers consultés

Les chemins ci-dessous sont relatifs à la racine du dépôt.

- `README.md`, `backend/requirements.txt` : objectif et pile technique déclarée.
- `backend/app/main.py`, `backend/app/core/database.py` : assemblage de l'API et
  sessions SQLAlchemy.
- `backend/app/models/` : `company.py`, `site.py`, `equipment.py`, `sensor.py`,
  `measurement.py`, `maintenance_record.py`, `__init__.py` : relations, colonnes,
  types, défauts et cascades.
- `backend/app/schemas/` : `company.py`, `site.py`, `equipment.py`, `sensor.py`,
  `measurement.py`, `maintenance.py`, `__init__.py` : contrats et validations.
- `backend/app/repositories/` : `company_repository.py`, `site_repository.py`,
  `equipment_repository.py`, `sensor_repository.py`, `measurement_repository.py`,
  `maintenance_repository.py` : accès existants et bornes temporelles.
- `backend/app/services/` : `company_service.py`, `site_service.py`,
  `equipment_service.py`, `sensor_service.py`, `measurement_service.py`,
  `maintenance_service.py` : contrôles métier et transactions.
- `backend/app/api/routes/` : `companies.py`, `sites.py`, `equipment.py`,
  `sensors.py`, `measurements.py`, `maintenance.py` : exposition CRUD existante.
- `backend/migrations/versions/` : les six migrations de création des tables et
  `675ebfea0bb5_add_equipment_criticality.py` : vérification des clés, index et
  contraintes déclarés. Leur application sur une base réelle n'a pas été vérifiée.

## Prochaines modifications recommandées — hors de cette étape

1. Fixer le vocabulaire métier, la convention de devise et le contrat de période ;
   vérifier les valeurs réellement présentes avant de figer les catégories.
2. Définir un futur `backend/app/schemas/dashboard.py` avec périmètre, période,
   date de calcul, valeurs nullables, numérateurs/dénominateurs et indicateurs de
   couverture de saisie.
3. Prévoir un `backend/app/repositories/dashboard_repository.py` pour des agrégats
   SQL séparés par branche et filtrés dès la requête, sans charger toutes les
   mesures. Évaluer un index composé `(sensor_id, timestamp)` et les index de
   maintenance à partir des requêtes et de leurs plans avant toute migration.
4. Dans une étape ultérieure seulement, créer le service dashboard pour les
   contrôles de périmètre et les règles ci-dessus, puis les routes et leur
   enregistrement dans `main.py`. Prévoir une lecture cohérente des agrégats.
5. Ajouter alors les tests des cas précédents, notamment l'isolation des
   entreprises, les bornes temporelles, les valeurs absentes et la multiplication
   des lignes par jointure. Traiter les éventuelles corrections des CRUD et les
   KPI prédictifs dans des travaux séparés.

Validation de cette étape : revue de cohérence de la note avec les modèles,
schémas, accès aux données et migrations ; contrôle du diff pour garantir que seul
ce document est ajouté. Aucun test applicatif requis pour cette modification
documentaire et aucun test d'exécution du futur dashboard réalisé.
