# ML 5.3B — Vérification Docker avant création P101

## 1. Conclusion et périmètre

Audit du 26 octobre 2026, exclusivement en lecture seule, sauf création du présent
rapport. Références : ML 5.1, ML 5.2 et ML 5.3A.

**NO-GO immédiat pour la création : marge mémoire Windows trop faible pour
conclure sereinement à l'absence d'impact sur les instances existantes.** Le moteur,
l'image épinglée, les noms, le port et le sous-réseau proposé sont compatibles
avec le plan. La mémoire disponible dans Linux ne constitue pas une réserve
physique indépendante de l'hôte Windows. Recontrôler cette marge avant toute
autorisation de création ; aucun service n'a été arrêté ou reconfiguré ici.

Cette décision est une précaution d'exploitation sur un hôte partagé, pas une
preuve que PostgreSQL ne pourrait pas démarrer ni un minimum officiel PostgreSQL.
Les montages privés et leur fonctionnement effectif restent également à préparer
et à vérifier après autorisation. Le présent rapport n'autorise aucun démarrage.

Git au départ : branche `feature/ml-4-p101-persistence`, HEAD attendu et observé
`51d765a1f0c19010cad14c0432fb2e741d37bbe9`, arbre propre et index vide.
Aucun changement applicatif, configuration DEV ou composant ML 4.

## 2. Résultat des dix vérifications

| Contrôle | Résultat observé | État |
| --- | --- | --- |
| Branche, HEAD, état Git | Référence conforme ; aucun changement initial | Conforme |
| Moteur et contexte | desktop-linux, pipe local Docker Desktop, serveur Linux amd64 29.6.1 | Conforme |
| Inventaire | Deux conteneurs actifs, deux volumes locaux, cinq réseaux ; détails ci-dessous | Réalisé sans mutation |
| Noms P101 | Aucun conteneur, réseau ou volume portant les noms proposés | Aucune collision observée |
| Image exacte | RepoDigest épinglé présent localement ; PostgreSQL 17.10, linux/amd64 | Conforme, aucun pull |
| Port 127.0.0.1:55432 | Aucun listener TCP sur 55432, toutes adresses ; aucune exclusion TCP Windows couvrant ce port | Apparemment disponible, non réservé |
| Réseaux/routes | Trois réseaux Docker et routes Windows examinés ; 172.30.101.0/28 sans recouvrement spécifique observé | Proposition compatible à cet instant |
| Ressources/montages | Disque et capacités Docker cohérents ; faible mémoire libre Windows ; montages privés futurs non testés | Réserve bloquante mémoire et validations restantes |
| Compose statique | config --no-interpolate --quiet réussit, sans fichier .env DEV | Structure valide, configuration privée non interpolée |
| Blocages avant création | Revalider mémoire ; préparer fichiers privés/ACL ; recontrôler contexte, noms, routes, port, digest | Création non commencée |

Les contrôles sont des instantanés ; ils ne réservent aucune ressource et ne
garantissent pas leur disponibilité lors d'une étape ultérieure.

## 3. Moteur Docker et accès local

- Contexte actif : `desktop-linux`.
- Endpoint : `npipe:////./pipe/dockerDesktopLinuxEngine` ; aucun endpoint TCP distant.
- Autre contexte recensé : `default`, pipe local docker_engine, inactif.
- Client et serveur : Docker 29.6.1 ; serveur linux/amd64, nom docker-desktop.
- Docker Compose : v5.3.0.
- Stockage déclaré : overlayfs, DockerRootDir `/var/lib/docker`.
- Capacités déclarées : 8 CPU, 8 228 892 672 octets de RAM, soit environ 7,66 Gio.
- Aucune surcharge héritée DOCKER_HOST/DOCKER_CONTEXT, aucune variable
  P101_LOCAL_* ni sélection COMPOSE_ENV_FILES observée.

L'accès au pipe Docker était refusé dans le bac à sable initial. Les mêmes
lectures ont réussi avec l'autorisation d'accès local étendu ; le moteur n'a été
ni démarré, ni réparé, ni modifié. Les lectures CIM Windows ont nécessité le même
type d'accès. Ce n'était pas une panne du moteur.

## 4. Ressources existantes à préserver

### Conteneurs

| Nom | Image affichée | État | Publication |
| --- | --- | --- | --- |
| industrial-predict-postgres | postgres:17 | Actif depuis 11 jours, healthy | 0.0.0.0:5433 et IPv6 :5433 vers 5432 |
| industrial-predict-postgres-ui47 | 7958605b474b | Actif depuis 8 jours, healthy | 127.0.0.1:5434 vers 5432 |

Aucun autre conteneur, y compris arrêté, dans docker ps -a. Les états healthy
sont ceux fournis par Docker ; aucun healthcheck ni requête PostgreSQL n'a été
déclenché par cette mission. Les processus et healthchecks déjà actifs continuent
indépendamment de l'audit.

### Volumes et montages existants

| Volume | Driver / portée | Utilisation observée |
| --- | --- | --- |
| industrial-predict_postgres_data | local / local | Données du conteneur industrial-predict-postgres, /var/lib/postgresql/data en écriture |
| industrial-predict-postgres-ui47-data | local / local | Données du conteneur ui47, /var/lib/postgresql/data en écriture |

Ui47 possède également un bind mount de secret en lecture seule. Seuls le type,
la destination et le mode du montage ont été lus ; ni le chemin source privé,
ni le contenu du secret n'ont été extraits. Aucun inventaire complet des variables
d'environnement des conteneurs. Aucune inspection de fichiers de données.

La base industrial_predict_dev n'a pas été contactée. L'audit Docker ne prouve
pas l'identité des bases hébergées ; les deux conteneurs et leurs ressources sont
traités comme existants à protéger, sans aucune réutilisation pour P101.

### Réseaux

| Nom | Driver / portée | Sous-réseau | Passerelle |
| --- | --- | --- | --- |
| bridge | bridge / local | 172.17.0.0/16 | 172.17.0.1 |
| industrial-predict_default | bridge / local | 172.18.0.0/16 | 172.18.0.1 |
| industrial-predict-ui47_default | bridge / local | 172.19.0.0/16 | 172.19.0.1 |
| host | host / local | Sans IPAM bridge | Sans objet |
| none | null / local | Sans IPAM bridge | Sans objet |

Les trois bridges sont non internes. Les conteneurs existants utilisent leurs
réseaux de projet respectifs. Aucun réseau P101 local déjà présent.

## 5. Image PostgreSQL épinglée

Référence du Compose, retrouvée exactement dans les RepoDigests locaux :

`docker.io/library/postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317`

L'inspection par cette référence a réussi, sans registre ni téléchargement :

- RepoDigest déclaré : `postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317` ;
- ID observé : `sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317` ;
- OS/architecture : linux/amd64, conforme au platform du Compose ;
- seules variables d'image retenues : PG_MAJOR=17, PG_VERSION=17.10-1.pgdg13+1 ;
- volume déclaré par l'image : `/var/lib/postgresql/data` ;
- champ Size de l'inspection : 161 234 895 octets ; docker system df comptabilise
  l'unique image à 645,2 MB. Ces métriques Docker ont des présentations différentes
  et ne constituent pas une mesure de capacité libre.

L'image est déjà utilisée par ui47. La réutilisation de cette image standard
immuable est conforme ; aucun conteneur, volume ou secret existant ne doit être
réutilisé. Aucun binaire postgres n'a été exécuté pour vérifier sa version :
l'identification repose sur le digest et les métadonnées locales.

## 6. Port et proposition réseau

Get-NetTCPConnection, état Listen, n'a trouvé aucun listener sur 55432, y compris
0.0.0.0 ou ::. Les exclusions TCP IPv4 et IPv6 affichées par netsh ne couvrent
pas 55432. Aucun bind, réservation de socket ou test de connexion n'a été fait.
Ce port ne recouvre pas les publications existantes 5433 et 5434.

Les routes IPv4 actives Windows comprennent un LAN en 10.x/24, loopback,
172.17.112.0/20 et 172.25.192.0/20, ainsi que les routes par défaut,
multicast/broadcast et routes hôte associées. La route par défaut n'est pas une
collision de sous-réseau. Aucune route spécifique ne recouvre la proposition
172.30.101.0/28 ; aucun recouvrement avec les trois IPAM Docker observés.

Paramètres proposés, sans création ni affectation :

| Paramètre | Proposition |
| --- | --- |
| Sous-réseau | 172.30.101.0/28 |
| Passerelle | 172.30.101.1 |
| IP conteneur | 172.30.101.2 |
| Endpoint hôte | 127.0.0.1:55432 |
| Port PostgreSQL interne | 5432 |
| Réseau | industrial-predict-p101-local-demo-net, bridge internal:true, indépendant |

La proposition respecte les bornes IPv4 et exclusions de SetupSettings. Elle
reste à approuver explicitement. Une nouvelle connexion VPN, des routes ajoutées
ou un autre projet Docker peuvent invalider cet instantané. Aucun inventaire
exhaustif du routage interne de tous les composants Desktop/VPN n'est revendiqué.

## 7. Ressources et compatibilité des montages

Docker stats --no-stream a observé environ 37,99 Mio pour ui47 et 77,85 Mio pour
industrial-predict-postgres, CPU 0,00 % pour chacun au moment du relevé. Le total
des volumes est 123,6 MB, deux volumes actifs ; deux conteneurs et aucun build
cache recensé par docker system df. Ces valeurs ne justifient aucune suppression.

Windows : environ 15,82 Gio de RAM visible, seulement 570 888 puis 649 732 Kio
libres, soit **0,54 à 0,62 Gio**. Le Compose proposé autorise 512 Mio au nouveau
conteneur, plus la charge non couverte par cette limite côté moteur/hôte. Une
limite est un plafond, pas une réservation ni une estimation de consommation.
Le manque de marge hôte est retenu comme condition d'arrêt prudentielle.

La distribution WSL docker-desktop a d'abord été vérifiée déjà démarrée ; seules
des lectures de /proc/meminfo et df ont ensuite été lancées, sans démarrer de
distribution. Linux rapporte 8 036 028 Kio totaux et 7 087 000 Kio MemAvailable,
soit environ 6,76 Gio disponibles. **Ces chiffres Linux et Windows ne s'additionnent
pas** : ils relèvent du même hôte avec gestion mémoire WSL/Desktop. Il faut
réconcilier cette marge avec la pression Windows avant création, sans arrêter DEV.

Disques hôte observés : environ 71,48 Gio libres sur C: et 162,82 Gio sur D:.
Le système de fichiers du disque Docker monté dans WSL rapporte 999 799 136 Kio
disponibles, environ 953,48 Gio logiques. Cette capacité de disque virtuel ne
garantit pas autant d'espace physique sur le disque Windows qui le porte. Le
chemin Windows du VHDX et son expansion maximale n'ont pas été inspectés.

Compatibilité préparée :

- volume Docker neuf vers /var/lib/postgresql/data, conforme à l'image PG17 ;
- fichier suivi postgresql.conf présent et lisible, montage /etc/postgresql/p101.conf
  en lecture seule ; écoute 0.0.0.0 interne au conteneur, publication hôte loopback ;
- futur fichier HBA privé vers /etc/postgresql/pg_hba.conf en lecture seule ;
- futur fichier admin privé par secret Compose vers /run/secrets/admin_password ;
- aucune clé/certificat : profil local SCRAM avec ssl=off explicite, ML 4 intact ;
- 1 CPU, mem_limit 512m, shared_buffers 64MB, shm_size 128m, max_connections 20.

Les fichiers privés n'existent pas dans cette livraison et n'ont pas été créés
ou cherchés dans un répertoire privé de l'utilisateur. ACL Windows, partage de
chemins Desktop, lecture du secret/HBA côté Linux et comportement de l'entrypoint
officiel ne sont pas vérifiés par un montage réel. Avant création, exiger des
fichiers physiques valides : un bind court sur un chemin inexistant ne doit pas
entraîner la création involontaire d'un répertoire à la place du fichier attendu.

## 8. Validation Compose effectuée

Commande réellement exécutée, retour 0, sans accès à PostgreSQL :

```powershell
docker compose --env-file NUL -f infra/p101-local/compose.yaml config --no-interpolate --quiet
```

Le fichier .env implicite est écarté par --env-file NUL. L'absence d'interpolation
évite de fabriquer une configuration privée ou de fournir un secret fictif.
Ce contrôle confirme la structure Compose, pas la résolution des variables
obligatoires ni la disponibilité des chemins privés futurs. Aucun up, create,
pull, build, start, stop, rm, prune ou compose down exécuté.

La revue du fichier confirme noms dédiés, aucun external, aucun env_file DEV,
aucun montage de seed ou données DEV, pull_policy:never, publication exclusivement
127.0.0.1, restart:no et healthcheck désactivé. La validation interpolée complète
restera obligatoire avec le futur compose.vars approuvé, hors Git, avant création.
Le réseau internal et les publications Desktop devront ensuite être contrôlés
réellement ; la lecture statique ne prouve ni leur accessibilité ni leur isolation.

## 9. Conditions avant réexamen du GO

1. Réévaluer une marge mémoire Windows stable et suffisante pour le plafond de
   512 Mio et la charge additionnelle du moteur/hôte, avec les deux instances
   existantes maintenues. Aucun arrêt, réparation ou changement de limite automatique.
2. Confirmer à nouveau le contexte local Linux, l'image exacte présente, les noms
   absents, les IPAM/routes sans collision et 55432 libre et non exclu.
3. Faire approuver sous-réseau/IP, UUID neuf et configuration privée ; créer les
   secrets distincts seulement après autorisation, sans identifiant DEV.
4. Vérifier chemins réels, fichiers de montage et ACL, puis Compose interpolé sans
   .env DEV ni surcharge héritée. Aucun recours à un volume/réseau préexistant.
5. Obtenir une autorisation distincte couvrant la création Docker **et** l'initialisation
   implicite du cluster, de la base et du rôle admin par l'image officielle.
6. Après création seulement, dans un périmètre autorisé ultérieur, contrôler les
   ports, le réseau, l'identité réelle, SCRAM, privilèges et montages avant migrations
   ou bootstrap. Ne jamais élargir le HBA en trust pour contourner un problème.

Arrêt obligatoire si collision de nom, volume non neuf, digest absent/différent,
contexte distant, port indisponible, route contradictoire, mémoire trop tendue,
chemin privé ambigu, secret réutilisé, ACL non maîtrisée ou identité SQL inconnue.
L'audit ne clôt aucune réserve B-PRE-01 à B-PRE-11 ni TLS-01 ; les validations
PostgreSQL, transactionnelles, concurrentes et API restent ouvertes.

## 10. Intégrité et état final

Seul fichier créé : `docs/ml-5.3b-p101-docker-readiness.md`. Aucun fichier existant
modifié, index vide et HEAD conservé. Contrôles Git d'espacement du suivi et du
nouveau rapport effectués sans indexation. Aucun secret, DSN privé ou contenu
de fichier de connexion copié dans le rapport.

Aucune création/suppression de ressource Docker ; aucun pull, PostgreSQL/HTTP,
migration, bootstrap, calcul ML, test/build ou modification DEV. Aucun commit,
push, merge ou rebase. **Provisionnement non commencé ; attente de validation.**
