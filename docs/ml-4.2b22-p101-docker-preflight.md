# ML 4.2B-2.2 / P1 — Inventaire Docker avant provisionnement P101

Date : 25 octobre 2026. Statut : inventaire local en lecture seule, soumis à validation.

## 1. Résultat et périmètre

**Le moteur Docker Desktop/Linux est opérationnel.** Une image locale déclare
PostgreSQL 17.10 et possède un digest précis. Aucun nom de ressource P101 proposé
n'entre en collision avec l'inventaire observé. Le port TCP hôte 55432 paraît
disponible à cet instant, sans réservation ni preuve qu'un futur bind réussira.

Dépôt `D:/projets/industrial-predict`, branche
`feature/ml-4-p101-persistence`, HEAD attendu et observé
`bcdeb5c469453a234f0c3a2dc39d210b15e29db8`. Arbre propre et index vide au départ.
Seul ce rapport est créé ; aucun code, Compose ou autre configuration modifié.

Commandes utilisées : lectures Git, Docker version/info, image ls/inspect,
container ls, volume ls, network ls/inspect et system df ; inventaires Windows
Get-NetTCPConnection, netstat, plages TCP exclues et espace des lecteurs.
Les requêtes Docker sont passées par le canal local nommé du moteur. L'accès
sandbox initial était refusé ; une lecture avec les permissions adaptées a réussi,
sans démarrage ni réparation du service.

Aucun run, compose up, pull, build, start, stop, rm, prune, téléchargement ou
création/modification de ressource. Aucune connexion PostgreSQL ou HTTP externe,
aucun exec/attach/log de conteneur, lecture de données DEV, migration, DML, test ML,
certificat ou secret créé. Aucun commit/push/merge/rebase. Les informations des
conteneurs existants se limitent aux métadonnées d'inventaire du moteur ; leurs
environnements, comptes, secrets et contenus de volumes n'ont pas été inspectés.

Références : [audit local](ml-4.2b2-p101-sandbox-readiness.md),
[durcissement](ml-4.2b21-p101-sandbox-hardening.md).

## 2. Moteur et capacités observées

| Élément | Observation |
| --- | --- |
| Client / serveur Docker | 29.6.1 / 29.6.1 |
| Contexte | desktop-linux |
| Serveur | linux, amd64 ; docker info précise x86_64 |
| Stockage moteur | overlayfs, racine Linux `/var/lib/docker` |
| Ressources annoncées au moteur | 8 CPU ; 8 228 892 672 octets de mémoire totale |
| Images | 1, active ; 645,2 MB selon system df |
| Conteneurs | 2, tous deux actifs ; couches inscriptibles totalisant 73,73 kB |
| Volumes locaux | 2, tous deux actifs ; 123,6 MB au total |
| Cache de build | 0 |

Ces totaux ne représentent ni la mémoire libre ni une réservation pour P101.
Les lecteurs Windows annonçaient environ 80,0 GB libres sur C et 174,8 GB sur D
(unités décimales). La localisation physique et l'espace libre du disque virtuel
Docker Desktop n'ont pas été vérifiés ; l'espace hôte ne prouve pas la capacité
disponible dans le stockage Linux. Aucun fichier de configuration Docker Desktop
ou disque virtuel n'a été ouvert.

## 3. Inventaire existant et collisions

### Image et conteneurs

Une seule image locale est listée sous le tag mutable `postgres:17` :

```text
postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317
```

Les seules métadonnées d'image retenues sont le digest, la plateforme et les
paramètres publics PG_MAJOR/PG_VERSION/PGDATA/volume déclaré, détaillés en section 5.

| Conteneur existant | Référence d'image affichée | État Docker | Ports publiés |
| --- | --- | --- | --- |
| industrial-predict-postgres | postgres:17 | Actif, healthy | 5433 vers 5432, interfaces IPv4/IPv6 globales |
| industrial-predict-postgres-ui47 | postgres au digest ci-dessus | Actif, healthy | 127.0.0.1:5434 vers 5432 |

Les états healthy sont des métadonnées déjà disponibles dans Docker. Aucun contrôle
de santé SQL ni accès aux bases n'a été lancé par cet audit. Ces deux conteneurs
doivent rester intacts ; aucun redémarrage ou changement de publication n'est proposé.

### Volumes et réseaux

| Type | Nom observé | Driver / portée |
| --- | --- | --- |
| Volume | industrial-predict_postgres_data | local / local |
| Volume | industrial-predict-postgres-ui47-data | local / local |
| Réseau | bridge | bridge / local ; subnet 172.17.0.0/16 |
| Réseau | industrial-predict_default | bridge / local ; subnet 172.18.0.0/16 |
| Réseau | industrial-predict-ui47_default | bridge / local ; subnet 172.19.0.0/16 |
| Réseau | host | host / local |
| Réseau | none | null / local |

La lecture réseau a été limitée aux noms/drivers/portées et aux subnets des trois
bridges. Aucun endpoint de conteneur, label privé ou option sensible n'est copié.
Les montages réels des conteneurs DEV et le contenu des volumes restent hors audit.

### Noms proposés, non réservés

| Ressource future | Nom proposé | Résultat de comparaison |
| --- | --- | --- |
| Projet Compose | industrial-predict-p101-sandbox | Aucun préfixe de ressource correspondant observé |
| Conteneur | industrial-predict-p101-sandbox-postgres | Absent des conteneurs, y compris arrêtés |
| Volume | industrial-predict-p101-sandbox-data | Absent des volumes |
| Réseau | industrial-predict-p101-sandbox-net | Absent des réseaux |

Les quatre noms ont aussi été comparés aux trois listes de ressources : aucune
collision exacte. Un nom de projet Compose n'est pas un objet autonome réservé
par Docker ; les noms générés, labels et projets devront être revérifiés lors de
la préparation du futur Compose. Aucun projet existant n'est adopté.

## 4. Port hôte proposé 55432

Après adaptation des permissions de lecture Windows :

- Get-NetTCPConnection ne montre aucun écouteur TCP sur 55432.
- netstat ne montre aucun endpoint TCP local sur 55432.
- Les plages TCP exclues Windows, IPv4 et IPv6, ne contiennent pas 55432.
- Aucune publication Docker inventoriée n'utilise 55432 ; les publications
  PostgreSQL existantes concernent 5433 et 5434.

**Disponibilité apparente seulement** : aucun socket ouvert, bind testé, port
réservé ou règle de pare-feu modifiée. Une course avec un autre processus, une
évolution des exclusions Hyper-V/Windows ou une contrainte de publication Docker
reste possible. Refaire ces lectures immédiatement avant une création autorisée ;
si le port est occupé/exclu, arrêter et faire approuver une nouvelle destination.

Publication future proposée : `127.0.0.1:55432:5432`, jamais toutes les interfaces.
Le port client 55432 sera distinct du port serveur 5432 attendu dans le conteneur.
L'adresse serveur interne attendue reste à définir ; aucune IP/subnet P101 n'est
allouée ou approuvée par ce rapport.

## 5. Image précise proposée et vérification future du digest

L'inspection locale de `postgres:17` donne :

| Champ | Valeur déclarée |
| --- | --- |
| OS / architecture | linux / amd64 |
| PG_MAJOR | 17 |
| PG_VERSION | 17.10-1.pgdg13+1 |
| PGDATA | /var/lib/postgresql/data |
| Volume déclaré par l'image | /var/lib/postgresql/data |
| RepoDigest | postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317 |

Référence candidate immuable à approuver pour le futur sandbox :

```text
docker.io/library/postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317
```

Elle correspond au digest déjà déclaré localement par le dépôt `postgres`, avec
une plateforme linux/amd64 et un paquet PostgreSQL 17.10 déclaré. Aucun processus
postgres de cette image n'a été lancé par cet audit pour vérifier la version du
binaire. Le tag
`postgres:17.10` serait un libellé humain possible, mais son existence et sa
résolution dans un registre n'ont pas été vérifiées. Le tag local `postgres:17`
seul est insuffisant pour épingler la future création.

Vérification future, avant utilisation :

1. Approuver le dépôt complet, le digest attendu, la plateforme et la version
   déclarée ; conserver cette preuve sans secrets.
2. Interroger localement `docker image inspect` sur la référence par digest et
   comparer RepoDigests, OS/architecture, PG_VERSION et PGDATA à cette décision.
   Ne pas confondre un tag mutable ou un identifiant court avec un digest de dépôt.
3. Si une attestation de provenance distante est requise, obtenir une autorisation
   distincte pour consulter le registre et vérifier le manifeste/digest et la
   plateforme. Le digest local est un constat, pas une attestation indépendante
   de provenance ou une signature éditeur. Aucun accès registre n'a eu lieu ici.
4. En cas d'image absente, digest différent ou plateforme/version inattendue,
   arrêter. Aucun pull automatique ou repli sur un autre tag. Tout téléchargement
   éventuel nécessitera une nouvelle autorisation.

Une image immuable peut fournir les binaires d'un nouveau cluster vide. Aucun
conteneur, volume, réseau, données ou compte DEV ne sera réutilisé pour ce cluster.
Le futur lancement devra empêcher un téléchargement implicite si seule l'image
locale approuvée est autorisée (politique équivalente à pull never).

## 6. Contraintes de stockage, montages et isolation PostgreSQL 17

Pour cette image 17 observée, prévoir un nouveau volume nommé exclusivement P101,
monté explicitement à `/var/lib/postgresql/data`, cohérent avec PGDATA. Ne pas
monter seulement un autre niveau parent et laisser Docker créer un volume anonyme
au chemin déclaré par l'image. Aucun volume externe existant, copie de PGDATA,
dump, restauration DEV ou répertoire de données Windows partagé avec DEV.

Conserver ce choix majeur 17 et la version/digest approuvés : le PostgreSQL natif
18 installé sur l'hôte ne doit pas intervenir dans le stockage de ce cluster.
Une évolution de version majeure ou de disposition PGDATA exigera un plan distinct.
L'initialisation doit trouver un volume neuf vide et des permissions compatibles
avec l'utilisateur de l'image ; l'UID/GID effectif et les droits du futur volume
ne sont pas validés par cet inventaire.

La fixture comporte peu de lignes, mais un cluster comporte aussi catalogues,
WAL, fichiers temporaires et journaux. Prévoir une marge explicite de stockage
et des limites mémoire/CPU adaptées avant création ; les tailles observées des
volumes existants ne constituent pas une estimation suffisante ni une garantie
de capacité P101. Vérifier la capacité du disque virtuel Docker au provisionnement,
sans prune ni nettoyage d'une autre ressource pour obtenir de l'espace.

Créer ultérieurement un réseau bridge dédié, sans connexion aux réseaux existants,
avec subnet non chevauchant les bridges observés et les routes Windows/VPN encore
à examiner. Le fonctionnement d'un réseau internal avec publication loopback
Docker Desktop reste à valider ; aucun subnet n'est choisi automatiquement.
Ne pas employer host network, le bridge par défaut ou le socket Docker en montage.

Certificat serveur et clé future : montages privés en lecture seule, hors volume
de données partagé et hors Git ; CA privée non montée dans le serveur. Chemin et
empreinte de CA client devront correspondre à SandboxConfig. Aucun certificat,
fichier Compose, secret, UUID réel ou configuration privée n'est créé ici.

## 7. Inconnues et conditions d'arrêt avant création

| Sujet | État / condition d'arrêt |
| --- | --- |
| Moteur | Accessible et Linux aujourd'hui ; arrêter s'il devient inaccessible ou change de contexte, sans démarrage/réparation automatique |
| Ressources | Aucun nom P101 observé ; arrêter sur toute collision ou ressource préexistante non explicitement autorisée, sans adoption ni suppression |
| Port | 55432 apparemment disponible ; arrêter sur écouteur, exclusion ou publication conflictuelle |
| Image | Digest local précis proposé ; arrêter sur absence, divergence, version/plateforme différente ; aucun téléchargement implicite |
| Stockage | Espace du disque virtuel, limites et permissions à vérifier ; aucune réutilisation ou suppression de volume DEV |
| Réseau | Nouveau subnet/IP, routes/VPN et règles de publication/pare-feu non validés ; aucune connexion à un réseau DEV |
| PKI / secrets | Outil PKI, CA/SAN/validité/ACL et secrets indépendants restent à préparer dans une étape autorisée |
| Autorisations | Contrats admin/métier préparés, émetteurs/clefs réels non provisionnés ; aucune permission déduite de ce rapport |
| Schéma / bootstrap | Aucun schéma créé ou migré ; lanceurs, contraintes et bootstrap restent à valider sur une infrastructure explicitement autorisée |

R04 est donc partiellement renseigné (moteur, inventaire, image locale et port),
pas clos : capacité, topologie, certificats et création restent à approuver.
R05, R08 et R09 restent des prérequis/validations ultérieurs. Les réserves
B-PRE-01 à B-PRE-11 demeurent ouvertes ; aucun résultat PostgreSQL I01–I12 n'est
produit par cet inventaire.

Avant toute création future, faire valider les noms exacts, image/digest/plateforme,
volume/PGDATA, subnet/IP, port, ressources, TLS, comptes nouveaux et périmètre de
l'autorisation. **Aucun volume, réseau, conteneur, identifiant ou secret DEV ne
devra être réutilisé.** Aucune connexion de test à DEV n'est nécessaire.

## 8. État Git et livraison

Branche et HEAD conservés ; index vide, aucun fichier suivi modifié. Seul ajout :
`docs/ml-4.2b22-p101-docker-preflight.md`. Contrôles finaux conformes : périmètre
limité au rapport, `git diff --check` et contrôle `git diff --no-index --check`
du nouveau fichier sans erreur d'espacement. Recherche de motifs de secrets/DSN
sans résultat. Aucune indexation ni aucun commit.

**Rapport soumis à validation. Aucune création ou connexion PostgreSQL n'est
autorisée implicitement par ces constats.**
