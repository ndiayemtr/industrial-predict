# Préparation hors ligne — ML 6.2B-2D-3D-2B-2B-2

Ces artefacts ne sont ni déployés ni validés sur PostgreSQL réel. Aucun certificat
ou secret opérationnel n'est fourni. Les modèles `.in` ne sont pas des fichiers
prêts à déployer. Ils ne déclenchent aucune commande à leur lecture.

`bootstrap.sh` commence par un refus inconditionnel (code 78). Les ébauches de
phases placées après ce refus ne sont jamais appelées. Chaque phase conserve
également une garde fermée et un point d'attestation non implémenté. Aucun
argument, fichier de configuration ou drapeau d'environnement n'autorise leur
exécution. Il n'existe ni dispatcher, ni déploiement automatique, ni nettoyage.
La levée de ces gardes nécessiterait un nouveau lot expressément revu et autorisé.

## Artefacts et validation

`validation.py` n'importe que la bibliothèque standard et le support pur 3D-2A.
Les contrats existants restent inchangés. Ses API sont `bootstrap_plan()`,
`validate_templates()`, `validate_entrypoint()` et `validate_phases()` : elles
consomment des données/textes fournis, sans lire de fichiers ni lancer de processus.
Les plans, chemins, rôles, preuves et résultats sont des dataclasses gelées avec
représentation opaque. Tous les résultats restent sans autorité d'exécution.

Le validateur fixe les identités de campagne, moteur, réseau, image et version
approuvées. L'ancien ID du conteneur arrêté est refusé pour le futur bootstrap :
un nouveau conteneur devra recevoir un nouvel ID vérifié. Les tests utilisent
un ID fictif et une empreinte CA synthétique, jamais des observations réelles.
Les modèles sont contrôlés par listes fermées de paramètres et lignes, avec
refus des ajouts, doublons, substitutions inconnues et configurations partielles.
Le contrôle de l'entrypoint vérifie sa garde et ses marqueurs de phases ; il
n'est pas un analyseur complet du langage shell ni une preuve d'exécution sûre.

Les formats sont traités explicitement : les configurations PostgreSQL, HBA et
OpenSSL admettent des commentaires de ligne `#`, le modèle SQL n'en admet aucun.
Le SQL est une liste fermée de lignes physiques exactes : aucune ligne `#`,
aucune ligne vide interne ou ajout, et une seule métacommande `\connect`, sous
sa forme exacte à sa position prévue. Tout autre backslash/métacommande, même
après une instruction SQL, est refusé. Ce contrôle structurel n'est pas un parseur
SQL complet. Les modèles utilisent le jeu ASCII imprimable et LF ; les autres
caractères de contrôle et séparateurs Unicode sont refusés sans normalisation.

`validate_entrypoint()` exige les octets originaux immuables (`bytes`). Il décode
strictement UTF-8, impose le jeu ASCII de cet artefact, LF uniquement, le shebang
attendu et le préfixe de refus sur les lignes physiques séparées par LF. CR,
CRLF, NUL, séparateurs ambigus, BOM et octets non UTF-8 sont refusés. Les lecteurs
futurs doivent utiliser `read_bytes()` ; ils ne doivent ni passer par la conversion
universelle des fins de ligne, ni réencoder un texte déjà normalisé. Une conversion
faite en amont ne peut pas être décelée par le validateur après coup. Les modèles
textuels doivent également être décodés sans conversion des séparateurs.

## Phases et points d'arrêt

| Phase | Préconditions | Postconditions distinctes exigées |
|---|---|---|
| A — environnement | Identités explicites, autorité future indépendante, environnement propre | Secrets de campagne privés et non vides ; aucune autorité fournie par ce lot |
| B — ressources | Première génération, montage réel identifié et sans ressource partagée | tmpfs 256 Mio, racine et sous-répertoires traversables par postgres, modes 0700 |
| C — initdb | PostgreSQL 17.10, utilisateur postgres, PGDATA vide, fichier de mot de passe 0600 | Cluster initialisé, SCRAM local/hôte, aucune écoute TCP |
| D — administration | Socket Unix privé authentifié, configurations locales vérifiées | Base dédiée et trois rôles restreints NOLOGIN ; aucune table OIDC |
| E — TLS/HBA | CA propre à la campagne, fichiers dans le tmpfs | Signature, dates, correspondance clé/certificat, SAN IP, empreinte CA, permissions et HBA vérifiés réellement |
| F — activation | Mots de passe installés par un canal revu avant LOGIN ; bootstrap NOLOGIN | Postmaster local arrêté, même conteneur actif, TLS/HBA validés avant lancement réseau |
| G — attestation | Connexions réelles retenues, preuves fraîches indépendantes | Trois identités/PID, verify-full, source effectivement observée ; aucun DDL automatique |

Les preuves injectées sont comparées à des observations requises pour CHAQUE
phase ; un code de sortie zéro ou la réussite de la phase précédente ne suffit
pas. Le validateur recontrôle l'historique fourni et refuse ordre incohérent,
identités divergentes, génération autre que 1 ou campagne invalidée. Il ne peut
pas empêcher un appelant de fabriquer des observations ni prouver qu'une campagne
a réellement redémarré : provenance, fraîcheur et registre d'invalidation fiable
relèvent du futur contrôleur. L'étape A « authority unavailable » n'est qu'un
constat statique, jamais une autorisation opérationnelle.

L'invalidation déclarée et une génération divergente sont refusées sur les
données fournies. L'expiration temporelle réelle n'est pas implémentée :
`PhaseEvidence` ne porte aucune échéance et ce lot n'ajoute ni horloge ni autorité.
Une campagne périmée ne peut donc pas être identifiée par ces contrôles seuls.

## Secrets, stockage et transition

Un futur broker devra transmettre les secrets par un canal privé, jamais par
arguments, labels, variables Docker persistantes ou fichiers du dépôt. `initdb`
ne reçoit que le chemin du fichier de mot de passe. `psql` utilisera un fichier
de mots de passe local protégé et un environnement explicitement nettoyé.
L'installation sécurisée des mots de passe et l'activation LOGIN ne sont pas
implémentées : c'est un point d'arrêt volontaire avant F, non une invitation à
ajouter des secrets aux modèles. Les quatre secrets synthétiques des tests sont
distincts ; la validation impose au moins 32 octets et refuse NUL/CR/LF.

La racine `/var/lib/postgresql/data` doit devenir propriété de postgres, mode
0700, avant toute descente vers `pgdata`. `run`, `secrets`, `tls`, `log`, `work`
restent sous le même tmpfs. Avant usage, un contrôleur devra vérifier mountinfo,
taille, propriétaires, chemins canoniques et absence de symlinks, tablespaces,
WAL externe ou montages inattendus. Rien de cela n'est attesté sur le montage
actuel, puisque le conteneur reste arrêté. Un chmod/chown ne remplace pas ces
preuves. Les limites à conserver : 768 Mio mémoire et mémoire+swap, 1 CPU, restart=no.

Le futur PID 1 restera vivant pendant l'arrêt du seul postmaster local puis
son remplacement par PostgreSQL TLS. Un arrêt/redémarrage du conteneur perd le
tmpfs et invalide la campagne. Aucune reprise, réinitialisation ou suppression
automatique n'est prévue. Les écritures, journaux et variables de travail devront
rester bornés au tmpfs ; les garanties sur le swap de la VM restent à établir.
`fsync`, `synchronous_commit` et `full_page_writes` restent activés ; le tmpfs ne
constitue pas une preuve de durabilité après perte du conteneur.

## TLS, rôles et limites

OpenSSL est prévu dans l'image figée ; CA d'un jour et clé serveur restent dans
le tmpfs, clé serveur postgres:postgres en 0600. La CA publique seule sera remise
au client, avec empreinte épinglée. Le SAN est IP:127.0.0.1 et le client doit
imposer verify-full, paramètres explicites et absence de fallback libpq.
Les assertions statiques du modèle ne prouvent aucune validité cryptographique.

Le CIDR source doit être un /32 explicitement approuvé. Une valeur candidate
n'atteste pas l'adresse NAT réellement vue sous Docker Desktop. La règle HBA
reste étroite ; un échec de connexion ne permet pas de l'élargir. G doit recueillir
et vérifier la source réelle. Les connexions non TLS et toutes les autres
combinaisons base/rôle/source sont refusées. Le socket local sera fermé aux
connexions dans la configuration finale.

Le rôle technique est créé par initdb, distinct des trois rôles de campagne.
La base lui appartient ; PUBLIC perd ses droits sur cette base et le schéma
public. Owner seul reçoit CREATE sur le schéma ; App/Observer ont CONNECT et
USAGE, sans TEMPORARY, DDL ni privilège sur une table inexistante. Les rôles
restent NOLOGIN tant que le broker n'a pas installé leurs mots de passe ;
la désactivation du login technique et la fermeture de ses sessions sont exigées
avant F. Aucun pg_read_all_stats n'est accordé. Les privilèges sur la table OIDC
et sa création relèvent d'un lot distinct.

Les erreurs publiques du validateur sont constantes, contexte/cause détachés,
y compris depuis un gestionnaire actif. L'exception indépendante de l'appelant,
ses variables locales et les sources de pile ne sont pas effacées. Le refus
actuel du shell est constant ; la collecte et l'assainissement des erreurs des
futures commandes opérationnelles devront encore être implémentés et revus.

La future recréation, l'installation du script, son activation contrôlée,
initdb, les clés/certificats, l'administration SQL et l'ouverture TLS nécessitent
des autorisations explicites. Aucun modèle ni résultat statique ne les accorde.
