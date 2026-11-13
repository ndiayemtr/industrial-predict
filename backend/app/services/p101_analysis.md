# P101-INTEGRATION-1 — analyse applicative sans persistance

Actualisation AUTH-B2B-RUNTIME-1 : le point d'entrée par défaut utilise désormais
la session opaque et le runtime B2B concret. Sans session il renvoie 401; sans
assemblage qualifié ou sans vérificateur de provenance il reste fermé avec 503.
Les GET prédictions/recommandations et POST recommandations disposent de dépendances
d'autorisation dédiées, sans activation DEV automatique. Les états historiques
ci-dessous décrivent le lot INTEGRATION-1; voir [état courant](../b2b_runtime.md).

`P101AnalysisService.analyze` réutilise `P101DevOrchestrator.analyze`, le loader
PostgreSQL existant et `evaluate_snapshot`. Le diagnostic opérateur privé n'est
pas exposé par HTTP; seules ses fonctions de contrôle de connexion native et ses
limites SQL sont réutilisées. Le mode analyse de l'orchestrateur ne conserve aucun
plan de persistance. Aucun writer ni moteur SQL n'est construit par cet adaptateur.

## État d'activation

L'application historique monte `POST /api/v1/equipments/{id}/p101-analysis` sans
fournisseur : réponse 503 `B2B_INTEGRATION_REQUIRED`. Aucun accès SQL n'est effectué.
Le routeur optionnel peut être construit avec un service et un résolveur de session
serveur, mais aucun assemblage de confiance n'est installé dans le dépôt.

Les routes historiques GET predictions, GET/POST recommendations et POST
health-score/rul sont également fermées avec 503, avant acquisition SQL. Elles
ne doivent pas être rouvertes par un simple indicateur ou une dérogation de
dépendance en application. Leur futur remplacement doit contrôler l'appelant et
le périmètre réel. L'historique Prédictions Angular affichera donc une erreur de
chargement; la simulation locale reste indépendante et l'action réelle désactivée.
Les autres routes historiques ne sont pas sécurisées par cette livraison.

## Dépendances de confiance requises

- Résolveur HTTP : vérifier le justificatif de session et retourner seulement une
  `SessionReference` interne. Aucun identifiant de corps, email ou domaine ne suffit.
- `CurrentCallerProvider` : vérifier session stockée, expiration/révocation,
  identité liée, compte et appartenances fraîches. Le type `CurrentCaller` ne prouve
  pas cette vérification. La permission explicite `predictions:analyze` est ensuite
  contrôlée par `decide_authorization`, avant acquisition et dans l'instantané.
- Contexte de connexion du runtime déjà installé : destination vérifiée, connexion
  synchrone psycopg inactive, sans autocommit ni transaction préexistante. Aucun DSN
  ou canal PostgreSQL supplémentaire n'est fourni par le service.
- Vérificateur de provenance serveur : vérifier une preuve couvrant exactement
  l'équipement, le capteur, la cible et les références originales dans l'instantané.
  Retourner `DeclaredProvenance` seulement après vérification effective, jamais
  depuis une déclaration du navigateur. Une référence de manifeste ou sa seule
  empreinte ne prouvent pas une acquisition physique. Ce fournisseur manque encore;
  aucun adaptateur acceptant simplement une déclaration n'est installé.

Ces dépendances sont des frontières de confiance explicites, pas des preuves
créées par les dataclasses. Les doubles des tests ne peuvent pas les qualifier.
La permission SQL `predictions:analyze` reste à installer/qualifier séparément;
aucune migration ni aucun droit runtime n'est modifié ici.

## Lecture et résultats

Le service impose REPEATABLE READ READ ONLY, statement_timeout=15s et
lock_timeout=5s transactionnels, vérifiés côté serveur avant lecture métier.
Les limites sont par instruction/attente de verrou, sans garantie de durée totale.
La connexion native doit rester identique. La transaction créée est terminée par
rollback, y compris après erreur. Une transaction préexistante est refusée sans
rollback. Le contexte propriétaire conserve la responsabilité de la connexion.

La chaîne entreprise/site/équipement/capteur est comparée avant lecture des mesures.
Le loader vérifie ensuite cible, références et contrat transactionnel; le moteur
conserve intégralement ses règles v1. Une provenance absente, synthétique ou sans
preuve référencée ferme le parcours avant le calcul. UI47 reste un jeu de
démonstration; il ne peut pas être déclaré physique pour rendre le calcul possible.

Entrée JSON : company_id, site_id, sensor_id, target_measurement_id et cutoff_utc.
L'équipement est dans le chemin. Aucun champ d'identité ou de provenance client.
Réponse discriminée HTTP 200 : COMPUTED (score binaire, is_alert, statistiques,
références), ABSTAINED (motif et nombre de références), REJECTED (motif et champ).
Chaque réponse conserve équipement, cible, version, source et `persisted=false`.
401/403 restent des refus d'identité/autorisation; 503 signale une dépendance ou
précondition indisponible, sans diagnostic interne. Les entrées HTTP invalides
restent 422. Ce contrat n'est pas `PredictionRead` et ne crée aucun historique ni
recommandation. Le score n'est pas une probabilité de panne.

## Validation hors ligne

Tests ciblés sous `tests/p101_integration`, complétés par les régressions loader,
orchestrateur et diagnostic dont les contrôles natifs sont réutilisés. Doubles
uniquement : aucun test ne constitue une qualification PostgreSQL ou B2B réelle.
Résultat : 186 cas ciblés validés (167 lors de l'exécution initiale, puis 19 tests
HTTP après correction du harnais et reprise hors sandbox). Sous Windows, la
création de la paire de sockets interne à la boucle asyncio était bloquée dans
le sandbox; les requêtes HTTP sont ASGI en processus et les connexions SQL restent
interdites pendant les tests. Aucune suite générale n'a été relancée.
Les anciennes vérifications HTTP supposant un accès anonyme 200/201 doivent
désormais distinguer tests métier isolés et fermeture de l'assemblage réel.

Prochaine activation : installer et qualifier les fournisseurs de session et de
provenance dans l'assemblage serveur, puis tester le périmètre avec le runtime
déjà vérifié. En leur absence, conserver les réponses 503 et Angular désactivé.
