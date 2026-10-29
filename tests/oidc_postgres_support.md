# Contrats PostgreSQL OIDC — ML 6.2B-2D-3D-2A

`oidc_postgres_support.py` reste exclusivement dans les tests et ne dépend que
de la bibliothèque standard. Aucun collecteur, moteur, client Docker, lanceur,
requête ou nettoyage n'est implémenté. Les fabriques ne consultent ni fichiers,
ni variables d'environnement, ni settings applicatifs. DEV/P101 restent interdits.

## Trois étapes distinctes

- `campaign_contract(**champs)` et `validate_contract()` contrôlent la syntaxe et
  la cohérence d'une déclaration explicite. Tous les champs sont obligatoires.
- `docker_inventory(**champs)`, `sql_observation(**champs)` et
  `compare_evidence(contrat, inventaire, observations)` comparent les données
  injectées. Le résultat `EvidenceConcordance` signifie uniquement concordance
  de ces données. Il n'authentifie aucune source.
- L'autorité opérationnelle indépendante reste à concevoir. Aucun résultat ne
  porte de capacité d'exécution ; `execution_authorized` reste faux, la conversion
  booléenne et `require_operational_authority()` refusent toujours l'autorisation.

Les dataclasses sont immuables, avec représentation opaque. Les fabriques sont
les points d'entrée validants ; un constructeur dataclass brut n'est pas une
validation. Les opérations de comparaison et de registre revalident leurs
arguments. Les refus publics des fabriques, validations, comparaisons et opérations
de support, ainsi que les refus booléens et d'autorité, gardent leurs types et
messages constants. Leur émission efface `__context__` et `__cause__`, et fixe
`__suppress_context__` à vrai, y compris dans un gestionnaire d'exception actif
chez l'appelant. Une relance nue préserve cet assainissement sous Python 3.12.
Le traceback formaté standard de l'erreur publique ne contient donc pas la chaîne
d'exceptions sensibles détachée. Aucune journalisation.

Cette protection n'efface pas l'exception originale détenue indépendamment par
l'appelant. Elle ne nettoie ni les variables locales des frames, ni leur code
source, ni les chemins de pile ; un outil capturant les variables locales ou
un appelant réattachant ensuite une exception reste hors de cette garantie.
Les constructeurs dataclass bruts ne deviennent pas des points de validation.

## Déclarations et observations

`CampaignContract` explicite UUID, identifiants complets du conteneur/réseau,
noms liés à la campagne, image par empreinte et image ID Docker, plateforme Linux,
réseau RFC1918, adresse serveur, stockage tmpfs borné, endpoint loopback, base,
trois rôles distincts, version PostgreSQL 17 exacte, marqueur cluster,
transport `verify-full` et empreinte CA, périmètre `public.oidc_transactions`.
Les ports exposés 5433, 5434 et 55432 observés dans DEV/P101 sont refusés.
Le port serveur interne explicite reste 5432. Ni URL, ni résolution DNS, ni
conversion implicite, ni valeur par défaut de destination ne sont admises.

`DockerInventory` fournit des faits indépendants : identité, image, plateforme,
réseau interne et ses membres exhaustifs, réseaux du conteneur exhaustifs,
montages et publications exhaustifs, état, redémarrage et privilèges. Le seul
montage accepté est un tmpfs de données ; son identité est le couple conteneur
et cible, car un tmpfs n'a pas d'identifiant de volume Docker. Les binds,
volumes persistants, réseaux/membres supplémentaires et publications inattendues
échouent. Les tuples imbriqués conservent l'immuabilité des observations.

Trois `SqlObservation` sont obligatoires, une par rôle, avec PID distincts,
identité de campagne, base, session_user/current_user, adresse/port/version,
cluster, TLS, attributs de rôle et périmètre. `client_verification`,
`client_ca_sha256` et `client_verified_host` sont des faits du client à collecter
indépendamment ; ils ne sont pas déductibles de SQL seul. Les tests construisent
les observations séparément du contrat et exercent les divergences.

## Préparation des fixtures

`synthetic_oidc_ids()` produit des empreintes synthétiques déterministes par
campagne/cas ; elles ne remplacent pas le générateur sécurisé OIDC de production.
`campaign_resources()` décrit l'inventaire attendu ; `created_registry()`
enregistre des déclarations explicites de création, sans attester leur réalité.
Cet inventaire contient le conteneur, le réseau, le tmpfs et la table OIDC exacte.
`describe_cleanup()` accepte uniquement un sous-ensemble des ressources et lignes
enregistrées, identifiées exactement, dans le même périmètre et la même campagne.
Le registre et la description portent une `DestinationIdentity` immuable composée
des valeurs existantes du contrat : identifiant exact du conteneur, nom exact de
la base et périmètre. Sa présence, ses types et son égalité exacte avec le contrat
sont vérifiés avant toute description, même si le registre ne contient que la
table ou des lignes. Réutiliser l'UUID avec un autre conteneur ne permet pas de
réutiliser le registre. Les contraintes initiales de nom de base lié à l'UUID et
de périmètre unique restent inchangées ; aucune autre base ou table n'est admise.
Cette liaison est une comparaison de données, sans autorité opérationnelle.
Il ne produit ni commande ni SQL, et ne nettoie rien.

`describe_actors()` exige des identités de connexion distinctes ;
`concurrency_event()` et `lock_wait_condition()` décrivent des événements et une
attente de verrou observés. Aucun thread, processus, temporisation ou horloge
n'est démarré. Les futurs tests de consommation devront conserver les commits
indépendants de l'adaptateur, sans transaction englobante ni savepoint d'isolation.

## Limites avant activation

Les données injectées peuvent être fausses, périmées ou falsifiées. Les noms,
préfixes, labels, empreintes fournies et résultats de comparaison ne prouvent ni
propriété, ni isolation réelle, ni authenticité. Aucun privilège SQL effectif,
comportement de verrouillage, commit, confidentialité TLS ou absence de course
entre observation et utilisation n'est vérifié sur un serveur dans ce lot.

Une future activation doit faire valider une autorité indépendante, un collecteur
Docker/SQL/client fiable, la fraîcheur et la liaison des preuves aux connexions,
un conteneur et réseau réellement neufs, la propriété et l'exhaustivité des
ressources, les privilèges minimaux et le nettoyage borné après commits réels.
Il faudra fixer une image réelle vérifiée et un certificat valide pour l'endpoint
loopback. La remise de ce certificat devra respecter la politique sans bind/volume
supplémentaire, ou faire l'objet d'une extension expressément revue. Les valeurs
des tests sont fictives ; aucun provisionnement n'est autorisé par ce document.
