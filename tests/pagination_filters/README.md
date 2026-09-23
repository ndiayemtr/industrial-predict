# 1.4.18.8 — Tests pagination et filtres

Depuis `backend`, avec Python 3.12 et les dépendances du backend :

```powershell
# Suite ciblée (le répertoire parent permet de réutiliser dashboard.support)
python -m unittest discover -s ../tests -p test_routes.py -v
# Toute la suite
python -m unittest discover -s ../tests -v
python -m compileall app
```

La suite utilise `unittest`, comme les tests existants, et réutilise leur fixture
`dashboard.support.DatabaseCase`. Aucune dépendance supplémentaire.

## Périmètre et données

Les six routes principales sont appelées via TestClient sur l'application réelle.
La seule substitution est la dépendance `get_db` vers une session isolée. Les
services, repositories, filtres SQL et schémas de réponse ne sont pas simulés.
Les dépendances FastAPI sont restaurées à la fin de chaque test.

Chaque test reçoit quatre lignes de chaque entité, des liens parents distincts,
des catégories métier valides, des recherches discriminantes et des dates fixes.
Les résultats attendus sont explicites, indépendants des requêtes de production.
Les méthodes de test sont générées depuis des tables de cas pour donner un résultat
distinct par route/filtre sans recopier les mêmes assertions.

Couverture :

- Valeurs par défaut, paramètres page/page_size, bornes et HTTP 422.
- Structure exacte items/total/page/page_size/pages, dernière page partielle,
  dépassement de dernière page, aucun résultat filtré et base entièrement vide.
- Tous les filtres demandés, seuls et combinés ; total filtré cohérent sur les
  pages suivantes ; intersection des filtres contradictoires.
- Recherche insensible à la casse, suppression des espaces aux extrémités,
  recherche uniquement composée d'espaces équivalente à l'absence de filtre.
- Recherche sur nom/code et champs supplémentaires existants (type d'équipement,
  type/unité de capteur, champs textuels de maintenance).
- Enums invalides : HTTP 422 et localisation du paramètre fautif.
- Périodes égales/inversées : HTTP 400 ; dates sans fuseau : HTTP 400.
- Bornes temporelles `[start_time, end_time)` et bornes fournies individuellement.
  Les mesures utilisent timestamp ; les maintenances utilisent created_at. Les
  dates planned_at/completed_at des fixtures diffèrent pour détecter une confusion.
- Ordre stable à travers plusieurs pages et lectures répétées ; timestamp puis id
  décroissants pour mesures/maintenances, y compris un ancien relevé d'id supérieur.

Les routes spécialisées et les méthodes get_all ne sont pas modifiées.

## SQLite et PostgreSQL

Par défaut les tests utilisent SQLite en mémoire, avec clés étrangères activées.
La fixture existante remplace DATABASE_URL avant l'import applicatif et ne touche
pas à la base de développement configurée dans `.env`.

SQLite ne conserve pas les fuseaux des datetime SQLAlchemy. Les objets des fixtures
restent référencés dans la session pour conserver leurs dates UTC lors de la
sérialisation des réponses. Les SELECT, COUNT, filtres, tris et limites sont bien
exécutés en SQL, mais ce mode ne valide pas la réhydratation native timestamptz.
Les tests temporels SQLite utilisent des bornes UTC.

Pour vérifier les dates et décalages UTC sur PostgreSQL :

```powershell
$env:DASHBOARD_TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@localhost:5432/industrial_predict_test'
python -m unittest discover -s ../tests -p test_routes.py -v
```

Ce nom de variable est conservé pour réutiliser la fixture du dashboard : chaque
test crée un schéma unique et annule sa transaction à la fin. Utiliser une base
dédiée aux tests avec droit de création de schéma. Une URL configurée mais
inaccessible provoque un échec, sans repli silencieux sur SQLite.

Le test PostgreSQL supplémentaire vide l'identity map avant la requête HTTP et
utilise des bornes `+05:30` équivalentes aux bornes UTC. Il est explicitement ignoré
sans PostgreSQL. Aucun adaptateur de dates ni modification des modèles métier
n'est introduit pour rendre SQLite artificiellement conforme à PostgreSQL.

## Résultats du 23 septembre 2026

| Suite | Réussis | Échoués / erreurs | Ignorés | Total |
| --- | ---: | ---: | ---: | ---: |
| Pagination et filtres | 91 | 0 | 1 | 92 |
| Suite complète | 174 | 0 | 2 | 176 |

Les deux tests ignorés nécessitent PostgreSQL : celui de cette suite et le test
de regroupement journalier UTC du dashboard. Compilation `python -m compileall app`
réussie. Aucun bug fonctionnel détecté par les tests exécutés ; la validation
PostgreSQL native reste à exécuter sur une base configurée.

Les avertissements existants de dépréciation `datetime.utcnow()` et du TestClient
Starlette/httpx restent hors périmètre. Aucun fichier métier n'a été modifié.
