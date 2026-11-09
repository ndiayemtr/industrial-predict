# Infrastructure du runner de qualification P101

## Actualisation REAL-1

[REAL-1](../../tests/p101_postgres_qualification/REAL-1.md) décrit un parcours
préparé, mais FIX1 garde l'exécution réelle fermée faute de collecteur Docker
authentifié distinct de la readiness signée. Le transport RW/TLS sur la même
socket et le profil writer P101 restent préparés. Le nouveau
Dockerfile.real1.in démarre operator en mode describe ; aucune exécution par défaut.
La racine publique de confiance est un fichier root-owned embarqué, séparé des
requêtes. Les configurations/artefacts de campagne résident dans le nouveau volume
de registre, unique mount du runner ; les profils B2B précédents ne sont pas modifiés.

Ce second volume neuf est indispensable au registre anti-rejeu durable avec une
racine RO. P101ResourceCollector consulte les ressources sur l'hôte, sans monter
Docker dans le runner ; son résultat reste `unverified_external` et une readiness
signée ne l'atteste pas. `LiveGuard` refuse donc toute exécution réelle.
Le sous-réseau candidat reste non approuvé. real1-dependencies.json et le modèle
de Dockerfile n'inventent ni base par digest ni wheels/lock manquants : build
désactivé, aucune reproductibilité démontrée. Aucun téléchargement ou provisionnement.

Les listes de sources EXECUTION_SOURCES incluent les modules REAL-1 et le nouveau
manifeste. Le reste de ce document décrit les lots préparatoires précédents.

## État au 9 novembre 2026

EXEC-2 ajoute un backend SQL et un observateur au noyau existant, utilisables
uniquement sur doubles sans réseau. Le nouveau [dossier EXEC-2](../../tests/p101_postgres_qualification/EXEC-2.md)
précise le blocage : psycopg 3.3.4 n'expose pas le certificat serveur sur le même
canal SQL. Le connecteur réel et run_live restent fermés. Le manifeste
exec2-dependencies.json fixe psycopg/psycopg-binary 3.3.4 comme références, sans
wheels Linux ni hashes validés ; aucun build reproductible n'est revendiqué.
Le catalogue SQL inclut les drapeaux et politiques RLS ; toute RLS/politique est
refusée et le rôle de comptage est requalifié sans SUPERUSER/BYPASSRLS sous verrou.
Une baseline indépendante reste nécessaire. Ces contrôles sont testés hors ligne,
pas qualifiés sur PostgreSQL réel. Les sections suivantes rappellent EXEC-1.

RUNNER-1 fournit un modèle `Dockerfile.in` volontairement non constructible et un
dossier de dépendances. EXEC-1 ajoute un compilateur pour les **14 migrations
reconnues**, des intentions Ed25519, un registre anti-rejeu local et un noyau
transactionnel testés hors ligne, uniquement sur backend simulé. Voir le
[dossier EXEC-1](../../tests/p101_postgres_qualification/EXEC-1.md).

**Aucun build, téléchargement ou provisionnement n'est autorisé par ces fichiers.**
`run_live` et les actions du CLI RUNNER-1 restent fermés. Le runner n'est pas
qualifié sur PostgreSQL réel ; le writer métier reste désactivé. Aucun changement
des ressources DEV, P101 historiques ou OIDC, ni des API ou d'Angular.

## Artefacts préparatoires

- `Dockerfile.in` : base à fournir par digest, Python/psql, installation uniquement
  depuis un wheelhouse local avec lock et hashes ; aucun tag de repli.
- `dependencies.json` : références de versions RUNNER-1, sans base ni wheels validés.
- `exec1-dependencies.json` : références supplémentaires du compilateur et de la
  vérification cryptographique ; ce n'est pas un lock transitif complet.
- `exec2-dependencies.json` : références DB-API supplémentaires et blocages ;
  inclus avec sql_backend.py et offline_dbapi.py dans l'empreinte signée du noyau.
- La liste RUNNER-1 des sources est étendue par EXEC-1 aux modules d'exécution et
  helpers B2B effectivement utilisés. Le contexte futur doit être assemblé depuis
  ces listes, sans copie du dépôt complet, secrets, .env, venv, .git ou données DEV.

Le SQL compilé est du SQL natif PostgreSQL (`paramstyle='named'`), lié à son
empreinte dans l'intention. Il ne doit pas subir une interpolation `%` ou une
correction manuelle de l'échappement. Cette représentation ne démontre pas que
PostgreSQL accepte ou applique les DDL.

## Prérequis avant une campagne réelle

1. Base d'image approuvée par digest, artefacts linux/amd64 et lock transitif
   intégral avec hashes ; archive de sources immuable et construction vérifiée.
2. Nouvelle campagne/instance et inventaire réel frais : réseau bridge interne,
   volume neuf, aucun port publié ou lien avec les environnements existants,
   rôles distincts et limites de ressources vérifiées.
3. Profil de livraison indépendant des secrets et certificats. Le profil Docker
   B2B actuel refuse les mounts supplémentaires : aucune exception implicite.
4. Autorité humaine et racines publiques administrées hors du dossier soumis,
   fenêtre d'approbation valide et stockage anti-rejeu local dont ACL, intégrité
   et comportement après interruption sont qualifiés.
5. Backend TLS/SCRAM RW lié à sa socket, collecteurs de base vide et de catalogue/
   privilèges, référence indépendante, sources verrouillées et observateur réel.

L'objectif métier est une prédiction P101 réellement persistée puis consultable
dans Angular DEV. La campagne isolée doit précéder une intégration distinctement
autorisée ; aucune fonctionnalité déployée ou utilisable n'est annoncée ici.
