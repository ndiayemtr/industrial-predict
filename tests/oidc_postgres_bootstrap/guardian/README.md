# Gardien PID 1 inerte — ML 6.2B-2D-3D-2B-2B-3F

Fondation hors ligne uniquement. Aucun gardien, shell, conteneur ou build n'a été
démarré par ce lot. Aucun exécuteur Docker n'est livré. Le bootstrap existant,
ses phases A–G et son refus initial exit 78 restent inchangés et ne sont pas
copiés dans la future image. Le gardien ne sait pas déclencher ces phases.

## Architecture minimale et signaux

`guardian.sh` est un script POSIX destiné au futur PID 1. Il refuse tout argument
avec un message constant et le code 78, avant de créer son unique enfant.
Sans argument, il lance seulement `/usr/bin/sleep infinity` et attend cet enfant.
Il n'interprète ni stdin, ni texte de mission, ni variable d'activation. Il ne lit
pas de secret, n'ouvre pas de socket et ne lance aucun outil PostgreSQL ou SQL.

- TERM et INT : le gestionnaire ignore les nouvelles occurrences de ces deux
  signaux, tente de terminer l'enfant connu, l'attend puis sort avec le code 0.
  Cet arrêt explicite n'est pas une autorisation opérationnelle ou de nettoyage.
- HUP, QUIT, USR1 et USR2 : ignorés, sans changement de comportement.
- Fin spontanée de l'enfant : message constant et sortie 70, sans relance.
- KILL, crash, OOM, arrêt du moteur ou de la VM : non maîtrisables par le script.
  Un arrêt du conteneur fait perdre le tmpfs et invalide la campagne.

Le gardien attend son enfant connu ; ce n'est pas un superviseur générique de
postmaster ni un reaper complet d'enfants adoptés. Il ne promet pas la conservation
du tmpfs après une panne de l'enfant d'attente. Les courses de signaux, le vrai
comportement PID 1 et le délai d'arrêt restent à qualifier sur Linux dans une
mission autorisée. Il n'existe aucune transition A–G, aucun serveur de commande,
aucun dispatcher, aucun chargement dynamique ou fallback vers l'entrypoint image.

## Recette non exécutée et identité de l'image

`Dockerfile.in` fixe la base :

`docker.io/library/postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317`

Plateforme linux/amd64. La recette ne contient ni RUN, ni ADD, ni ARG, ni ENV,
ni installation. Elle copie uniquement guardian.sh vers
`/usr/local/libexec/oidc-test-guardian`, propriétaire numérique 0:0, mode 0555.
L'ENTRYPOINT JSON vise directement ce fichier, CMD est explicitement vide,
STOPSIGNAL vaut SIGTERM et HEALTHCHECK NONE supprime une éventuelle sonde héritée.
Le USER initial est explicitement 0:0. Aucun nouveau montage ou port n'est ajouté
par la recette. Ces directives sont des intentions à vérifier après un build,
pas une preuve d'existence du fichier dans une image actuellement construite.

Référence : [Dockerfile, COPY et configuration de démarrage](https://docs.docker.com/reference/dockerfile/).
Le frontend BuildKit intégré sera à qualifier ; aucun frontend externe flottant
n'est référencé par une directive syntax. Le binaire `/bin/sh`, la présence de
`/usr/bin/sleep` et sa prise en charge de infinity restent à vérifier dans la base.

La future image dérivée aura une identité distincte. Aucun digest de résultat
n'est inventé : artifact_manifest.json indique explicitement son indisponibilité
avant construction autorisée. Son nom dédié, son ID local, sa plateforme, ses
digests et son lien avec la base devront être enregistrés séparément. Ne jamais
présenter l'image dérivée comme l'image officielle PostgreSQL au digest de base.
Le tag local postgres:17 observé précédemment ne prouve pas PostgreSQL 17.10.

La recette hérite encore des métadonnées de base non remplacées : environnement,
VOLUME, WORKDIR et éventuels ONBUILD. Leur inventaire assaini est une précondition
de build ; ONBUILD doit être vide. Un Dockerfile sans RUN ne neutralise pas une
instruction ONBUILD héritée. Les variables de chargeur/interpréteur et options
runtime devront être explicitement contrôlées. Un administrateur pouvant remplacer
l'entrypoint, l'image ou injecter du code n'est pas contenu par ce script.

## Empreintes et validation des octets

| Artefact | SHA-256 |
|---|---|
| guardian.sh | bbca41577ef41c12d6cb3f31615c2c0c4a18fda028c7d5c0c7d44d05fbc992c2 |
| Dockerfile.in | aae8dad868a68f48085a1c6a59abf26a66ad41eb0643f0f18c0013c0033b6e95 |
| .dockerignore | 181be2c9e6db070e048be5103914e0953e35f6042111f7b34b81549223dfe1b8 |
| Bootstrap existant, référence seulement | d319573e82d26516aca327a1294dd44d6abad2e5883995a1b557969a9aa24665 |

`validation.validate_preparation(...)` reçoit cinq paramètres bytes obligatoires :
guardian_bytes, recipe_bytes, ignore_bytes, manifest_bytes et bootstrap_bytes.
Il n'ouvre aucun fichier, ne consulte aucune horloge ou variable d'environnement,
ne traite aucun signal et n'exécute aucun processus. Octets ASCII imprimables et
LF uniquement, taille bornée ; CR, NUL, séparateurs Unicode et conversions
implicites sont refusés. Toujours fournir les octets originaux sans normalisation.

Le manifeste JSON a des champs fermés, des types exacts et refuse les doublons.
Il doit correspondre au contrat fixe du validateur, dont les trois empreintes
ancrées sont indépendantes du manifeste fourni. Recalculer une empreinte dans ce
dernier ne peut donc pas approuver un script modifié. Une évolution légitime exige
une nouvelle revue du code, des pins et des tests. Ce mécanisme n'est ni une
signature, ni une authentification de l'éditeur, ni une analyse générale du shell.

Le résultat est immuable, opaque et refuse bool(). authenticated,
build_authorized et execution_authorized restent faux. Les erreurs sont constantes,
avec contexte/cause détachés, sans journalisation. Cela n'efface pas les données
détenues indépendamment par l'appelant ou accessibles dans ses frames.

`.dockerignore` exclut tout sauf guardian.sh et les deux fichiers de recette.
Le futur contexte de construction devra être un instantané minimal de ces trois
fichiers vérifiés, sans autre fichier, symlink ou ignore spécifique à Dockerfile.in
susceptible de changer ces règles. Le validateur d'octets ne prouve pas que le
contexte réellement envoyé au builder correspond à cet instantané.
Ne jamais utiliser le dépôt entier comme contexte implicite. Aucun secret,
certificat, fichier .env, test, bootstrap ou manifeste n'est copié par la recette.
La provenance de la base ne se réduit pas à l'égalité d'un digest déclaré.

## Racine en lecture seule et chemins futurs

Le gardien seul ne requiert aucun répertoire utilisateur inscriptible. Il lit son
script et les bibliothèques de la base, utilise les processus et /dev/null fournis
par l'environnement, et ne produit que deux diagnostics fixes en cas de refus ou
de panne. La compatibilité réelle avec read-only-rootfs reste non testée.

Pour les futures phases, proposer un seul montage utilisateur tmpfs de 256 Mio
sur `/var/lib/postgresql/data`, mode initial 0700, options nodev/noexec/nosuid :

| Besoin futur | Chemin dans ce tmpfs | Propriétaire/mode cible |
|---|---|---|
| PGDATA et WAL internes | pgdata/ | postgres:postgres, 0700 |
| Socket Unix et fichiers associés | run/ | postgres:postgres, 0700 |
| HOME, TMPDIR, configurations rendues, CSR | work/ | postgres:postgres, 0700 |
| Journaux PostgreSQL bornés | log/ | postgres:postgres, 0700 |
| Mots de passe, pgpass et clé CA éphémères | secrets/ | répertoire 0700, fichiers secrets 0600 |
| Certificats et clé serveur | tls/ | répertoire 0700, clé privée 0600 |

Ce tableau ne crée rien. Aucun secret n'est fourni par le présent lot.
Les écritures temporaires SQL doivent rester dans PGDATA. Aucun WAL, tablespace
ou lien vers l'extérieur. Le besoin éventuel de /tmp, /run ou /var/run ailleurs
doit être mesuré, puis résolu explicitement : ne pas ajouter de montage permissif
ou désactiver read-only automatiquement. HOME/TMPDIR et les chemins explicites
devront être fournis par le futur exécuteur dans un environnement assaini.

Le VOLUME hérité de PostgreSQL ne doit pas entraîner de volume anonyme : le futur
manifeste devra couvrir la cible exacte avec le tmpfs et attester l'absence de
montages supplémentaires. Les montages internes Docker sont à inventorier à part.
Mode et options déclarés ne prouvent pas leurs valeurs effectives après montage.
Taille disponible pour initdb/WAL/TLS, swap de la VM, propriétaire, UID/GID et
options réelles restent des points de qualification. Aucun de ces contrôles n'est
remplacé par une validation statique ou par l'exécution préalable de chmod/chown.

## Privilèges et séparation du postmaster

Le profil déclaré du gardien seul est UID/GID 0:0, privileged faux, cap-drop ALL,
aucune capacité ajoutée et racine en lecture seule. Son enfant d'attente utilise
le même UID ; aucune capacité KILL supplémentaire n'est proposée pour ce profil.
Une exécution entièrement non-root pourra être étudiée séparément ; elle ne doit
pas être présentée comme déjà testée. Le gardien n'utilise pas gosu.

Les futures phases privilégiées, non implémentées ici, pourront nécessiter le jeu
candidat CHOWN, FOWNER, DAC_OVERRIDE, SETUID, SETGID et, suivant le superviseur,
KILL. Ce n'est pas une preuve de minimum. Leur attribution exigerait un autre
profil explicitement revu, jamais une augmentation des privilèges de ce lot.
gosu devra être vérifié pour lancer initdb/postmaster sous postgres et constater
la réduction effective des capacités. Aucun postmaster n'est enfant de ce gardien.
Ce script ne peut pas être transformé en superviseur PostgreSQL par une option.

## Avant toute construction ou utilisation réelle

Exiger une autorisation de construction limitée, une revue des sources/pins,
du contexte, de la base et du builder. Une construction ne vaut ni publication,
ni recréation, ni démarrage. Vérifier ensuite digest dérivé, propriétaire, mode,
entrypoint, CMD, absence de secrets et métadonnées héritées. Un essai PID 1 réel
nécessite une autre autorisation et un environnement isolé explicitement désigné.

Le contrôleur existant reste unique et hors ligne : il ne représente pas encore
le démarrage isolé du gardien. Les contrats de destination/bootstrap/attestation
épinglent encore l'image officielle et ne peuvent pas approuver silencieusement
l'image dérivée. Leurs extensions, le collecteur réel, l'autorité authentifiée,
le registre durable et les nouvelles preuves devront être revus séparément.
bootstrap.sh conserve exit 78 ; aucune extraction, import ou contournement de ses
fonctions n'est permis. L'activation A–G reste un chantier distinct, non livré.

Les tests de ce dossier sont uniquement statiques et utilisent des doubles.
Ils n'exécutent ni le gardien ni un shell, ne construisent pas d'image et ne
prouvent pas le comportement des signaux sur Linux réel. Aucune ancienne suite
n'est requise puisque tous les composants existants restent inchangés.
