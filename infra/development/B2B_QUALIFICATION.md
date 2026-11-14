# DEV-5B-4H-3A — Contexte isolé, désactivé par défaut

Préparation hors connexion seulement. Aucune ressource, clé ou connexion réelle
n'est créée par ce lot. La qualification réelle et sa configuration de création
exacte nécessitent une autorisation opérateur séparée.

## Frontière avec DEV

Sans `--qualification-campaign auth-b2b-dev-5b-4h-3`, le lanceur garde son parcours
DEV inchangé. Un fichier de qualification n'est pas accepté comme profil DEV.
L'argument de campagne n'est admis que pour les cinq commandes b2b-locks-* et le
relais ; il est refusé pour api, frontend, migration, diagnostic et auth-plan.
Aucun profil candidat ne devient lançable. Aucune substitution de profil,
révision, rôle, CA ou port en cas d'erreur.

L'instance de qualification aura uniquement :

| Élément | Valeur obligatoire |
|---|---|
| Conteneur neuf | industrial-predict-b2b-deploy-qual-4h3-20261114 |
| Volume neuf | industrial-predict-b2b-deploy-qual-4h3-20261114-data |
| Image locale | postgres:17.10 linux/amd64 |
| ID image | sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317 |
| Réseau | none |
| Ports Docker publiés | aucun |
| Écoute PostgreSQL interne | 127.0.0.1:55443 uniquement |
| Base source | b2b_deploy_qual_4h3 |
| Base de restauration vide | b2b_deploy_restore_4h3 |
| cluster_name | industrial-predict-b2b-qual-4h3 |
| Montage unique | volume nommé vers /var/lib/postgresql/data, RW |
| Labels exacts (conteneur et volume) | industrial-predict.qualification = auth-b2b-dev-5b-4h-3 ; industrial-predict.run = UUID de campagne |

Seuls les labels déjà présents dans l'image officielle épinglée sont également
admis sur le conteneur, après comparaison à cette image. Aucun autre label ajouté
ou remplacement des labels de campagne n'est accepté. Le volume porte seulement
les deux labels de campagne.

Interdits : ports 5433/5434, base industrial_predict_dev, identités des clusters
existants, OID DEV 16384, conteneurs/volumes existants, bind mounts, volumes
anonymes/supplémentaires, options de volume local détournant son emplacement,
mode privilégié, PID/IPC host et tmpfs non prévu. La disponibilité de l'image et
l'absence initiale des noms seront contrôlées après autorisation, sans pull.

Les noms des rôles restent ui47_admin, ui47_migrator, ui47_app et
ui47_b2b_lock_owner, car les corps qualifiés imposent ces noms. Ce sont des rôles
neufs dans un cluster neuf, avec leurs propres OID et secrets synthétiques ;
aucun compte, volume, certificat ou profil DEV n'est utilisé. Le bootstrap devra
créer les 15 tables et 11 séquences à partir des sources approuvées, sans modifier
les migrations historiques, puis les données synthétiques et ACL de référence.
Ce bootstrap n'est pas exécuté ni ajouté comme effet des commandes de déploiement.

## Profil privé indépendant

Exemple d'emplacement futur, hors Git et hors répertoire privé DEV :
`D:\qualification\industrial-predict-b2b-deploy-qual-4h3-20261114\qualification.json`.
Le nom du répertoire et du fichier est obligatoire. Le JSON contient exactement
les champs ci-dessous, sans mot de passe. Les valeurs nulles et enabled=false
rendent volontairement ce modèle inutilisable tant que l'inventaire réel n'a
pas été contrôlé et approuvé. Ne pas inventer d'OID, d'ID Docker ou d'empreinte.

```json
{
  "format": "b2b-isolated-qualification-v1",
  "enabled": false,
  "qualification_campaign": "auth-b2b-dev-5b-4h-3",
  "synthetic_only": true,
  "mode": "isolated-qualification",
  "runtime_profile": "b2b-preparation",
  "db_host": "127.0.0.1",
  "db_port": 55443,
  "database": "b2b_deploy_qual_4h3",
  "database_oid": null,
  "restore_database_oid": null,
  "instance_id": null,
  "restore_instance_id": null,
  "cluster_identifier": null,
  "cluster_name": "industrial-predict-b2b-qual-4h3",
  "run_id": null,
  "container": "industrial-predict-b2b-deploy-qual-4h3-20261114",
  "container_id": null,
  "volume": "industrial-predict-b2b-deploy-qual-4h3-20261114-data",
  "volume_created_at": null,
  "image_id": "sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317",
  "ca_sha256": null,
  "server_certificate_sha256": null
}
```

À côté, uniquement pour cette campagne : ca.crt, server.crt (publics),
admin-password.txt, migrator-password.txt, app-password.txt (64 caractères hex
aléatoires chacun) et un sous-répertoire evidence préexistant. Les fichiers liés
symboliquement sont refusés. Le programme n'accepte aucun chemin de secret ou
de CA arbitraire. Restreindre les ACL NTFS et chiffrer le stockage ; ces mesures
et la provenance synthétique doivent être attestées par l'opérateur. Ne jamais
copier de secrets DEV dans ce répertoire. Aucune clé privée n'est lue par le
gestionnaire ou le relais. Le serveur aura sa clé privée temporaire, mode 0600,
propriétaire postgres, exclusivement dans le volume de qualification.

Créer après autorisation une CA temporaire indépendante et un certificat serveur
signé par elle avec SAN IP 127.0.0.1, BasicConstraints CA=false et usage serveur
TLS. Le gestionnaire contrôle les SHA-256 exacts des deux certificats, leur durée
de validité, leur signature directe et le SAN. libpq vérifie réellement la chaîne
et le nom pendant chaque connexion, avec verify-full et gssencmode=disable.
Refuser les variables PG* ambiantes. PostgreSQL doit accepter seulement les
connexions hostssl SCRAM synthétiques attendues et refuser hostnossl ; le socket
Unix peut servir au bootstrap isolé, jamais à la qualification du transport TLS.

## Relais opaque

Windows 127.0.0.1:55443 → pipes binaires docker exec -i par ID vérifié →
bash/cat → PostgreSQL 127.0.0.1:55443 dans le conteneur sans réseau externe.
Aucun port Docker n'est publié. Aucun TTY, mode texte, décodage/réencodage,
PowerShell pipeline ou terminaison TLS. SO_EXCLUSIVEADDRUSE Windows ; aucun
port de remplacement si 55443 est occupé. Les flux sont copiés dans les deux
sens avec gestion des écritures partielles. Limite : 16 connexions simultanées.

Le relais vérifie les ressources au démarrage, avant chaque flux et durant son
fonctionnement. La résolution du nom exact doit donner l'ID approuvé avant son
inspection. Sont vérifiés image/architecture, ID, labels, montage, identité du
volume, état, réseau et absence de publication. L'inspection évite Config.Env
et ne lit aucun secret. Un changement d'identité arrête le relais sans reconnexion.
L'image doit déjà contenir /bin/bash et cat ; leur absence provoquera l'arrêt,
sans installation ou téléchargement. Le relais ne peut pas compenser un moteur
Docker ou un administrateur Windows compromis.

## Commandes futures exactes, non exécutées

Après approbation distincte du provisioning, précontrôle des noms libres, création
des seules ressources prévues et qualification de leur inventaire/certificats :

```powershell
$QualPython = 'D:\projets\industrial-predict\backend\.venv\Scripts\python.exe'
$QualManager = 'D:\projets\industrial-predict\infra\development\manage.py'
$QualProfile = 'D:\qualification\industrial-predict-b2b-deploy-qual-4h3-20261114\qualification.json'
$QualCampaign = 'auth-b2b-dev-5b-4h-3'
$QualEvidence = 'D:\qualification\industrial-predict-b2b-deploy-qual-4h3-20261114\evidence\cycle-01'
```

Premier terminal dédié au relais (confirmation QUALIFICATION-RELAY) :

```powershell
& $QualPython -B $QualManager b2b-locks-relay --config $QualProfile --qualification-campaign $QualCampaign
```

Second terminal, chaque commande séparément avec son approbation interactive :

```powershell
& $QualPython -B $QualManager b2b-locks-backup --config $QualProfile --qualification-campaign $QualCampaign --bundle $QualEvidence
& $QualPython -B $QualManager b2b-locks-rehearse --config $QualProfile --qualification-campaign $QualCampaign --bundle $QualEvidence
& $QualPython -B $QualManager b2b-locks-install --config $QualProfile --qualification-campaign $QualCampaign --bundle $QualEvidence
& $QualPython -B $QualManager b2b-locks-grant --config $QualProfile --qualification-campaign $QualCampaign --bundle $QualEvidence
& $QualPython -B $QualManager b2b-locks-rollback --config $QualProfile --qualification-campaign $QualCampaign --bundle $QualEvidence
```

Les commandes restent les mêmes opérations du gestionnaire. Seuls le transport,
l'inventaire et les préludes de garde SQL changent. Les scripts DEV épinglés sont
capturés et vérifiés avant rendu ; aucune substitution globale de noms dans le
SQL. Les cinq corps, signatures, search_path et assertions ACL restent identiques.
Les gardes de campagne imposent base/OID, cluster/identifiant système, instance,
rôle, port interne, version exacte et TLS. Le plan lie scripts rendus, certificats,
inventaire et sources du contexte/relais par empreintes.

Snapshots, archive complète, destination vide, preuves 24h, confirmations
distinctes A/B/inverse, transactions, timeouts, sept OID, delta de 16 accords,
rollback et traitement des commits incertains restent dans Deployment. Aucun
service Google ou métier n'est démarré. Les clients 17.10 pg_dump/pg_restore
Windows doivent déjà être présents ; argv fixe 127.0.0.1:55443, mot de passe
uniquement dans l'environnement éphémère du fils, diagnostics expurgés.

## Arrêt et nettoyage après autorisation réelle

Après réussite, vérifier les reçus et l'absence de connexion active puis Ctrl+C
dans le terminal du relais. Il ferme son écoute et ses propres sockets/processus
et signale tout arrêt incomplet. Ne pas l'arrêter pendant un commit : sa perte
peut rendre l'acquittement incertain. Aucune relance automatique. Sur échec,
arrêter et conserver l'état pour diagnostic, sans suppression de ressources.

La suppression Docker reste une opération opérateur séparée : comparer de
nouveau ID/nom/image/labels et montage au reçu de création, arrêter puis retirer
uniquement ce conteneur par son ID, vérifier que le volume n'est plus monté,
revérifier son nom/CreatedAt/labels/driver et retirer uniquement ce volume. Jamais
de prune, wildcard, CASCADE ou nettoyage global. Retirer seulement les secrets
temporaires de la campagne après vérification des chemins absolus ; garder les
preuves expurgées. Le relais ne supprime aucun conteneur, volume ou fichier.

## Tests hors connexion

```powershell
Push-Location D:\projets\industrial-predict\infra\development
try {
  & ..\..\backend\.venv\Scripts\python.exe -B -m unittest test_b2b_qualification test_b2b_deployment -q
} finally { Pop-Location }
git diff --check
```

Doubles uniquement pour sockets, processus, Docker et SQL. Certificats et secrets
de tests synthétiques dans des dossiers temporaires. Cette validation ne prouve
pas encore le fonctionnement réel de docker exec, du pont bash/cat, du client
Windows ou de TLS : la campagne réelle devra commencer par ces préconditions,
et s'arrêter au premier échec. Ne pas répéter les 26 scénarios des fonctions.
