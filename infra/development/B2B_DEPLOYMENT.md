# DEV-5B-4H-2 — Déploiement fermé

Procédure préparée, **non exécutée**. Seule entrée opérateur : `manage.py`.
Le contrat historique `b2b-backup/rehearse/migrate` reste inchangé ; ne pas
l'utiliser pour cette installation à `b2b_0002_analyze`.

## Prérequis à approuver avant toute connexion

- Livraison et empreinte du plan revues humainement. Cinq sources approuvées
  (spécifications et scripts de revue) épinglées ; SHA-256 des deux exécutants
  liés au plan. Tout changement impose un nouveau dossier de preuves.
- Profil officiel exclusivement `D:\integration\industrial-predict\development\config.json`.
  Instance, OID, cluster, PostgreSQL 17.10, révision exacts ; port 5434 ; transport
  officiel verify-full et CA approuvée. Aucun accès à 5433, Docker ou Google.
- Clients pg_dump/pg_restore 17.10 déjà installés. Aucun téléchargement.
- Sauvegarde/restauration et étape B : `ui47_migrator`, propriétaire de public,
  des 15 tables et 11 séquences, sans héritage/superutilisateur. Étape A et retrait
  des objets : `ui47_admin` superutilisateur, nécessaire à la gestion du rôle
  technique. L'opération impose le rôle ; aucun choix implicite de compte SQL.
- Geler les écritures et fermer manuellement tous les clients pendant toute la
  fenêtre sauvegarde/restauration/A/B (API, pools, outils SQL). L'exécutant refuse
  tout autre client connecté avant écriture. Empêcher aussi les nouvelles
  connexions : le verrou advisory ne contraint pas les autres logiciels. Aucun
  arrêt de client ni changement de rôle automatique.
- Répertoire privé `...\development\evidence` préexistant, ACL NTFS restreintes
  à l'opérateur et aux administrateurs autorisés, stockage chiffré, espace pour
  archive complète + lecture SQL de contrôle + restauration. L'archive et
  `archive-readback.sql` contiennent des données sensibles : ne jamais les
  afficher, versionner ou transmettre. Les reçus contiennent empreintes de lignes
  et métadonnées de rôles, aucun mot de passe. L'ACL NTFS et le chiffrement sont
  des préconditions opérateur ; les tests Python ne les certifient pas.

## Destination de répétition distincte

Préparation DBA distincte à approuver : base vide
`industrial_predict_b2b_locks_restore` sur le même cluster approuvé, avec OID et
marqueur d'instance distincts. public appartient au migrateur. Propriétaire de
base, ACL de base, locale, extensions et rôles doivent reproduire la source,
sans export de mots de passe. Aucun objet résiduel dans public (tables,
séquences, vues, fonctions, types), ni autre schéma utilisateur. Aucune commande
ci-dessous ne crée cette destination ou ne restaure sur la base active.

Fichier privé dédié `...\development\b2b-locks-restore.json`, exactement quatre
champs. Ce modèle volontairement invalide doit être rempli après qualification :

```json
{
  "database": "industrial_predict_b2b_locks_restore",
  "database_oid": 0,
  "instance_id": "REMPLACER_PAR_UUID_DISTINCT_VERIFIE",
  "cluster_identifier": "REMPLACER_PAR_CLUSTER_APPROUVE"
}
```

Ne pas réutiliser `b2b-restore.json` historique. Une cible non vide est refusée ;
jamais de --clean, --create ou effacement automatique. La destination doit rester
disponible et inchangée pour les vérifications précédant A/B/inverse.

## Commandes futures — approbations séparées

Depuis `D:\projets\industrial-predict`, uniquement après autorisation de
l'opération concernée. Ne pas exécuter les étapes en bloc.

```powershell
$DevPython = 'D:\projets\industrial-predict\backend\.venv\Scripts\python.exe'
$DevManager = 'D:\projets\industrial-predict\infra\development\manage.py'
$DevProfile = 'D:\integration\industrial-predict\development\config.json'
$DevEvidence = 'D:\integration\industrial-predict\development\evidence\b2b-locks-4h2-APPROUVE'
```

1. Sauvegarde actualisée dans un dossier neuf, confirmation BACKUP-B2B-LOCKS :

```powershell
& $DevPython -B $DevManager b2b-locks-backup --config $DevProfile --bundle $DevEvidence
```

Export MVCC en lecture seule, pg_dump custom de toute la base avec snapshot
exporté, sans filtre. Contrôle TOC et lecture intégrale de l'archive. Couverture :
8 tables industrielles, 6 B2B, alembic_version ; 11 séquences (catalogue, ACL,
valeurs) ; colonnes/contraintes/index/triggers ; rôles/héritages, ACL/default ACL,
propriétés de base et extensions. Empreintes de toutes les colonnes de lignes
dans un ordre déterministe. Les séquences ne sont pas MVCC : gel externe requis.

2. Répétition, confirmation RESTORE-ISOLATED-B2B-LOCKS liée à l'inventaire cible :

```powershell
& $DevPython -B $DevManager b2b-locks-rehearse --config $DevProfile --bundle $DevEvidence
```

pg_restore --single-transaction --exit-on-error sur cette seule cible vide,
comparaison intégrale des empreintes et ACL, SHA-256 de l'archive revérifié.
Marqueur d'intention interdisant toute relance automatique après tentative.

3. Étape A, confirmation INSTALL-B2B-LOCKS-A :

```powershell
& $DevPython -B $DevManager b2b-locks-install --config $DevProfile --bundle $DevEvidence
```

Sept objets : rôle ui47_b2b_lock_owner NOLOGIN/NOINHERIT sans pouvoirs
administratifs, schéma b2b_lock détenu par migrateur, cinq fonctions détenues par
le rôle technique. Signatures exactes dans b2b_lock :

| Fonction | Paramètres SQL |
|---|---|
| lock_user_v1 | integer |
| lock_external_identity_v1 | integer,integer,text,text |
| lock_memberships_v1 | integer |
| lock_membership_permissions_v1 | integer,integer |
| lock_oidc_transaction_v1 | text,text,text,text,timestamp with time zone |

Résultats, prédicats et corps inchangés dans b2b_locks.FUNCTIONS. Droits
techniques : USAGE public/b2b_lock, SELECT des colonnes OWNER_RIGHTS et UPDATE
des cinq clés de verrouillage, EXECUTE délégable au migrateur. Aucun EXECUTE
PUBLIC ni droit applicatif ajouté. Le mode préparation reste fermé.

4. Étape B, nouvelle approbation GRANT-B2B-LOCKS-B liée au reçu de A :

```powershell
& $DevPython -B $DevManager b2b-locks-grant --config $DevProfile --bundle $DevEvidence
```

16 accords : SELECT de colonnes sur 6 tables ; INSERT de colonnes sur sessions
et OIDC ; UPDATE de last_activity_at/revoked_at/replaced_by sur sessions ; DELETE
OIDC ; USAGE b2b_lock ; EXECUTE des 5 signatures. Aucun UPDATE des cinq clés
sensibles ni droit de séquence B2B à ui47_app.

**B n'active aucun runtime.** Le candidat reste non lançable. La préparation
refusera ces droits applicatifs au prochain lancement ; garder l'API arrêtée.
Toute activation future exige un autre lot approuvé.

Chaque confirmation exige un terminal et la saisie exacte du jeton, de
l'empreinte du plan lié à l'opération et de l'archive affichés. Aucun --yes ni
approbation persistante partagée entre A et B.

## Contrôles et échecs

Reçus scellés SHA-256 valides 24 h, liés à l'archive, au plan, à la restauration
et aux étapes précédentes. Relecture réelle de la destination restaurée et
comparaison actualisée de la source au baseline avant chaque opération. Toute
dérive bloque. Les reçus prouvent l'intégrité locale, pas l'authenticité face à
un administrateur malveillant du disque. Ne jamais les éditer pour débloquer.

Pré-commit : identité/révision/TLS, absence d'autre client, advisory transactionnel
(474702,2), SHARE sur les 15 tables, snapshot inchangé, delta ACL exact et contrôle
des fonctions (SHA-256, paramètres/résultats, propriétaire, SECURITY DEFINER,
VOLATILE/PARALLEL UNSAFE, search_path, PUBLIC). lock_timeout 5s, statement_timeout
15s. Une transaction explicite par étape. Scripts de revue inchangés, ROLLBACK
final conservé dans leurs fichiers ; l'exécutant capture les octets approuvés et
retire uniquement l'enveloppe de revue.

Post-commit acquitté : nouvelle connexion de vérification, puis connexion
indépendante ui47_app (identité, séquences, ACL). Reçu de réussite seulement
après tous les contrôles. Aucune modification de données ni montage de routes.

Échec pré-commit : rollback. Acquittement perdu : code 3, aucune relance ou
restauration automatique. Échec après commit acquitté : code 4, garder fermé.
Marqueurs d'intention non réutilisables ; diagnostic et validation humaine
obligatoires. Une preuve expirée ou un contrôle dépassant 15s impose l'arrêt,
pas une réduction de couverture ni une prolongation automatique des délais.

## Inverse limité au delta prouvé

Nouvelle autorisation ROLLBACK-B2B-LOCKS, preuves toujours valides/cohérentes :

```powershell
& $DevPython -B $DevManager b2b-locks-rollback --config $DevProfile --bundle $DevEvidence
```

Si B est prouvée : retrait exact des 16 accords sous migrateur, commit et
contrôles. Puis sous admin : révocation des EXECUTE délégables, DROP des cinq
fonctions par signature avec RESTRICT, retrait des droits techniques, DROP
SCHEMA RESTRICT et DROP ROLE. Dépendances étrangères des fonctions/du rôle,
notamment dans d'autres bases, bloquantes ; RESTRICT reste l'autorité finale.
Comparaison finale au baseline : tables, données, séquences, rôles préexistants,
ACL industrielles préservés. ACL NULL/explicites comparées sémantiquement sur
les objets concernés. Aucun CASCADE, DROP OWNED, nettoyage global ou restauration
active. Deux identités peuvent nécessiter deux commits : l'échec intermédiaire
laisse un état fermé partiel documenté, sans prétendre à l'atomicité globale.
Preuves expirées, activité après B ou commit incertain : récupération distincte
à approuver, aucun inverse aveugle.

Le reçu de A enregistre les sept OID effectivement créés. B et l'inverse les
revérifient avant écriture et refusent un objet remplacé, même de même nom/code.

## Tests hors connexion

```powershell
Push-Location D:\projets\industrial-predict\infra\development
try {
  & ..\..\backend\.venv\Scripts\python.exe -B -m unittest test_b2b_deployment -v
} finally { Pop-Location }
git diff --check
```

Tests avec doubles, moteurs réels, accès secrets/réseau/processus interdits.
La qualification réelle de ce nouvel exécutant et de la destination reste à
approuver ; la qualification isolée antérieure des fonctions ne la remplace pas.
