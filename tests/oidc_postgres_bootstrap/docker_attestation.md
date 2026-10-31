# Observations Docker injectées — ML 6.2B-2D-3D-2B-2B-3C

Ce module prépare une collecte future. Il ne contient aucun transport Docker,
client HTTP, processus, accès aux settings, lecture de variables d'environnement,
lecture de fichier, horloge réelle ou accès PostgreSQL. Il n'existe aucune option
d'activation. Aucun composant existant ou garde du bootstrap n'est modifié.

## API et contrats

Les contrats sont des dataclasses gelées avec slots, collections en tuples,
types exacts et représentation opaque. La conversion booléenne est refusée.
Les constructeurs bruts décrivent des données ; ils ne valident pas leur contenu.
Les fabriques publiques et les opérations de comparaison revalident les entrées :

- `docker_snapshot(**champs)` valide une configuration déclarée complète.
- `docker_expectation(binding=..., snapshot=...)` lie les attentes au
  ControllerContract et à son CampaignContract existants.
- `docker_observation(**champs)` valide une observation déclarative horodatée.
- `build_attestation(attentes, observation, maintenant)` compare sans callback.
- `collect_attestation(attentes, source, horloge)` encadre le double de collecte
  avec l'interface Clock existante, puis compare. Aucun Clock réel n'est fourni.
- `ObservationSource.collect()` est abstraite : seules des implémentations de
  test sont livrées, dans le fichier de tests.

Pour `Mount.options`, le conteneur doit être exactement un tuple et chaque élément
exactement une chaîne native (`type(option) is str`). Les sous-classes de chaînes,
objets personnalisés et sous-classes de tuple sont refusés avant toute comparaison
des options, sans invoquer leur méthode `__eq__`. L'égalité stricte avec
`("nodev", "noexec", "nosuid")` est ensuite conservée. Cette revalidation s'applique
aussi aux objets bruts transmis à `build_attestation` et `collect_attestation` :
un constructeur gelé ne remplace pas la validation des éléments imbriqués.

| Contrat | Champs collectés ou attendus |
|---|---|
| EngineIdentity | UUID du moteur, version déclarée, OS et architecture |
| DockerContext | Nom exact du contexte, empreinte SHA-256 de l'endpoint attendu |
| ContainerIdentity | ID Docker complet et nom exact |
| NetworkIdentity | ID complet, nom, driver, internal, sous-réseau, passerelle, membres |
| ImageIdentity | ID local sha256, référence PostgreSQL épinglée par digest, plateforme |
| Mount | Type, source, cible, taille, lecture seule, options |
| PortBinding | Adresse hôte, port publié, port conteneur, protocole |
| ResourceLimits | Mémoire en octets et CPU en NanoCPUs |
| RestartPolicy | Politique et nombre maximal de tentatives |
| ContainerState | Statut, running/paused/restarting/dead, démarrage antérieur, code de sortie, compteur de redémarrage |
| DockerSnapshot | Campagne, identités, entrypoint/commande, inventaires complets des montages, volumes, réseaux et publications, limites, état, privileged |
| CollectionInterval | Début/fin UTC et début/fin monotones en nanosecondes |
| DockerObservation | Snapshot, provenance déclarée, sessions de contrôle/collecte, révision Git, empreintes, intervalle |

Les URLs d'endpoint, certificats, mots de passe, tokens, variables d'environnement
du conteneur et sorties Docker brutes ne sont pas des champs du contrat. Le futur
collecteur devra définir comment obtenir et normaliser l'identité d'endpoint avant
son empreinte ; cette empreinte injectée n'authentifie pas une connexion réelle.
Les valeurs d'entrypoint/commande restent des tuples de tokens ASCII bornés, jamais
des instructions exécutées. Ne pas y placer de secrets.

## Politique de comparaison

Cette première politique vise exclusivement un conteneur de préparation **created,
jamais démarré**. Elle ne valide pas les phases bootstrap, TLS ou running : ces
profils demanderont une revue explicite. Aucune observation effective du conteneur
réel n'a été effectuée dans cette mission.

Les identités moteur/conteneur/réseau/image, campagne, plateforme, stockage et
publication sont liées exactement au contrat existant. Contexte, version moteur,
entrypoint et commande sont des attentes administratives explicites, sans défaut
hérité du contexte Docker actif. Deux snapshots validés doivent être intégralement
égaux, y compris leurs listes ; aucun champ déclaré n'est ignoré.

Profil fermé : bridge interne, aucun membre réseau déclaré avant démarrage, un
seul réseau conteneur, un seul tmpfs à la cible PGDATA du contrat, aucun volume ni
bind, options nodev/noexec/nosuid, une publication TCP loopback vers 5432 conforme
au contrat, mémoire 768 MiB, CPU 1, politique de redémarrage no avec zéro tentative,
aucun démarrage antérieur ou redémarrage et privileged faux. Toute liste en plus,
valeur divergente, type incorrect, champ obligatoire absent ou champ inconnu dans
une fabrique est refusé. Ces restrictions décrivent le profil accepté ; elles ne
constituent pas une affirmation sur la configuration actuellement déployée.

Les sessions, révision et empreintes sont comparées au ControllerContract. Le jeu
d'artefacts existant est réutilisé sans modification. Il n'inclut pas encore le
nouveau module : son épinglage et toute évolution du manifeste devront faire
l'objet d'une mission d'intégration distincte. Aucun EvidenceEnvelope de succès,
verdict d'autorité, droit d'exécution ou changement de phase n'est produit.

## Temps et confidentialité

UTC natif en timezone.utc, compteurs monotones entiers non négatifs dans un même
domaine d'horloge. Durée de collecte et âge depuis la fin sont chacun limités à
cinq secondes incluses, avec tolérance de cohérence UTC/monotone de 1 ms incluse,
reprise de la politique existante. Cette tolérance ne prolonge aucune borne et
n'autorise aucun intervalle négatif ou futur. Le début d'une collecte peut donc
précéder maintenant de la somme des deux bornes : la fraîcheur est mesurée depuis
sa fin, séparément de sa durée.

La variante avec source relit l'horloge après son retour : le total de cet appel
doit aussi rester dans les cinq secondes et l'intervalle déclaré doit être inclus
entre les deux échantillons. Les paires d'horloge doivent être acquises avec une
précision/dérive compatible avec 1 ms ; un ajustement système plus important est
refusé prudemment. Aucune horloge globale ni mécanisme de retry n'est utilisé.

AttestationRejected porte un message constant ; les causes et contextes sensibles
sont détachés, même depuis un gestionnaire d'exception actif chez l'appelant.
Aucune journalisation. Cela n'efface ni les données conservées indépendamment
par l'appelant, ni les variables locales et sources accessibles via les frames.

## Frontière de confiance et suites nécessaires

`authenticated` et `execution_authorized` valent toujours faux, même après une
comparaison nominale. La classification est injected_docker_concordance_only.
SIMULATED et UNVERIFIED_DECLARATION sont les seules provenances admises : leur
concordance ne les rend jamais authentifiées. Une provenance absente ou un libellé
prétendant être authentifié est refusé. Les fixtures observées sont définies
indépendamment des attentes, sans recopier un contrat attendu.

Un double peut inventer tous les faits, omettre une vraie ressource ou mentir sur
le contexte et l'horloge. Les interfaces Python ne sont pas un sandbox : un code
injecté arbitraire pourrait effectuer des effets de bord. Ce lot ne fournit et
n'exécute qu'une simulation ; il ne démontre aucune propriété du moteur réel.

Avant toute collecte réelle : autorisation humaine explicite limitée au moteur,
aux IDs et aux seules lectures approuvées ; collecteur indépendant revu ; acquisition
complète et normalisation des réponses Docker ; contrôle du contexte et de la
connexion effectifs ; protection des accès aux credentials ; horloges et provenance
authentifiables ; vérification TOCTOU et non-interférence DEV/P101. Les clés de
sécurité Docker non modélisées ici, la mémoire swap, les autres réglages CPU,
devices, capabilities et namespaces restent à examiner. L'inventaire fourni ne
prouve pas que des champs omis du modèle sont sûrs.

La liaison à une approbation, l'anti-rejeu durable, les nouvelles générations de
conteneur et l'intégration au contrôleur restent séparés. Une attestation injectée
ne doit jamais servir de justification pour démarrer, recréer ou nettoyer.

## Tests ciblés

Uniquement `tests/oidc_postgres_bootstrap/test_docker_attestation.py` : données
synthétiques, doubles de source/horloge, refus de processus/connexions pendant les
tests, contrôle statique des imports et import à dépendances déjà chargées sans IO.
Ces gardes complètent la lecture du code ; ils ne prétendent pas intercepter
toutes les capacités d'un programme Python arbitraire. Aucune ancienne suite n'est
nécessaire tant que les composants existants restent inchangés.
