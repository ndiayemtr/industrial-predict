# AUTH-B2B-ACT-1 — chemin critique vers une première connexion réelle

Audit ciblé au HEAD `7a7282b`, branche `feature/auth-b2b-identity-access`.
Aucun PostgreSQL, Docker, Google, secret privé ou déploiement HTTPS consulté.
Les états réels SQL/provisioning/configuration ne sont donc pas réattestés ici.
Les résultats des campagnes isolées ne prouvent pas une installation DEV.

| Élément | Classement / état dans le code | Minimum restant |
|---|---|---|
| Mode de lancement | **Bloquant**. `manage.prepare_runtime_app`, `activation.require_preparation` et le CLI n'autorisent que `b2b-preparation`. Le candidat ACL est expressément non activable. | Petit raccordement explicite du lanceur vers l'assemblage auth-only, avec garde réel et configuration privée validée ; pas de drapeau pour convertir le candidat en activation. Ce lot ne modifie pas le lanceur. |
| Garde du profil navigateur | **Bloquant**. `BrowserAuthProfile.check` exige un garde serveur réel ; `install_google_b2b(..., browser_profile=...)` le rejoue avant montage et les routes à chaque appel. | Raccorder les contrôles approuvés d'identité/cluster/instance/base/ui47_app, TLS/CA, révision et schéma/ACL/fonctions sur le même moteur officiel. Aucun `lambda: None` en environnement réel. |
| Fonctions et droits SQL | **Bloquant**, déploiement DEV non confirmé ; aucun repli des stores sur les anciens verrous. | Qualifier l'état réel en lecture seule, puis seulement si nécessaire autoriser séparément le delta existant A/B, sauvegarde/restauration et inverse déjà préparés. Pas de nouvelle migration ni refonte. |
| Preuve avant connexion | **Résolu dans le code**, non activé. `/api/v1/auth/readiness` rejoue le garde et contrôle le chargeur secret ; le vérificateur Angular exige le DTO et les en-têtes exacts. | Configurer l'origine Angular approuvée après activation serveur ; vérifier 200 en HTTPS réel. Toute erreur garde le bouton fermé. |
| HTTPS navigateur | **Bloquant**, distinct du TLS PostgreSQL déjà qualifié. | Une origine commune proposée `https://localhost:4443` (à approuver, port non vérifié ici), certificat navigateur approuvé pour localhost ; `/connexion` vers Angular et seuls les cinq chemins auth vers FastAPI. Backend loopback non exposé, proxy de confiance explicite ; préserver scheme/host, interdire l'usurpation des forwarded headers. |
| Google | **Bloquant**, aucune valeur privée ni console examinée. | Client Web, client_id/secret serveur, issuer Google et RS256, callback exact `https://localhost:4443/auth/oidc/google/callback`, scopes existants `openid email`, politiques Workspace/consentement autorisant le compte pilote. Pas de SDK Google ou de flux OIDC supplémentaire. |
| Identité / entreprise | **Bloquant**, non vérifié ici. `admit_caller`, `store.create(require_company_access=True)` et `browser_profile` imposent l'identité et une entreprise explicitement autorisée. | Provisioning administratif revu : utilisateur actif, lien exact issuer/subject issu d'une preuve vérifiée indépendante, entreprise réelle autorisée, appartenance active/role cohérent et au moins un grant explicite accepté (ex. reader + predictions:read). Pas de droit par domaine, pas de création au callback. |
| Parcours de session | Déjà codé : PKCE/state/nonce, popup contrôlée, bearer mémoire, `/me`, `/logout`. | Essai navigateur réel après les préconditions : le 200 readiness ne vaut pas authentification ou garantie que Google acceptera le secret. |
| Ouverture métier | **Nécessaire avant ouverture métier**, hors première connexion. | Gardes des routes métier, qualification des périmètres et politique de rôles SQL métier ; conserver les anciennes API fermées et les guards Angular. La provenance P101 reste indépendante. |
| Extensions | **Reportable**. | Noms d'affichage (null permis), sélection d'entreprise, enrichissements UX, renouvellement persistant, harmonisation UI. Aucun n'est nécessaire au premier login/profile/logout. |

## Droits requis : conserver la matrice qualifiée

Source unique : `infra/development/b2b_activation.py::matrix(CANDIDATE)` et
`b2b_locks.FUNCTIONS`. Ne pas créer un second jeu de GRANT pour cet essai.

- SELECT par colonne sur les six tables, exactement les colonnes de `COLUMNS` :
  `local_users(id,state)`, `external_identities(id,user_id,issuer,subject)`,
  `company_memberships(id,user_id,company_id,state,role)`,
  `membership_permissions(membership_id,permission,role)` et toutes les colonnes
  de session/transaction listées dans `SESSION_COLUMNS`/`OIDC_COLUMNS`.
- INSERT par colonne sur `application_sessions` et `oidc_transactions` seulement.
- UPDATE sur `application_sessions(last_activity_at,revoked_at,replaced_by)`
  seulement, pour les opérations existantes et le verrou de session ; DELETE sur
  `oidc_transactions` pour la consommation unique sous verrou.
- USAGE sur `b2b_lock`, EXECUTE sur les cinq signatures exactes :
  `lock_user_v1(integer)`, `lock_external_identity_v1(integer,integer,text,text)`,
  `lock_memberships_v1(integer)`, `lock_membership_permissions_v1(integer,integer)`,
  `lock_oidc_transaction_v1(text,text,text,text,timestamp with time zone)`.
- Total inchangé : **16 accords**. Aucun UPDATE direct des cinq clés sensibles,
  aucun INSERT de compte/appartenance/grant, aucun accès aux séquences B2B requis.
  Droits PUBLIC, héritages, grant option et privilèges excessifs restent refusés.
- Rôle de connexion ui47_app, CONNECT/USAGE public et lectures de qualification
  existantes (notamment Alembic, catalogue, `pg_control_system()` et identité)
  à conserver/qualifier via le mécanisme officiel. Aucun droit industriel ajouté
  pour authentifier quelqu'un. Le rôle technique NOLOGIN, propriétaires,
  search_path et empreintes des fonctions demeurent ceux déjà qualifiés.

Le garde futur doit combiner `manage.inspect_runtime_connection` et
`manage.inspect_runtime_schema(..., profile=activation.CANDIDATE)` sur le
SqlRuntime officiel ; le second inclut les ACL et les cinq fonctions. La création
du moteur doit conserver `runtime_connect_args` (destination privée approuvée,
verify-full/CA SHA-256, pas d'environnement libpq ambiant). Ne pas utiliser les
attentes ACL de préparation après attribution des droits ; elles les refusent
volontairement. Le raccordement du lanceur reste une adaptation logicielle
obligatoire avant d'exécuter ce plan, pas une simple modification de config.

## Conditions d'environnement et ordre le plus court

1. Revoir le contrat applicatif livré et le petit raccordement du lanceur encore
   nécessaire ; conserver le mode préparation par défaut. Ne pas utiliser
   `app.main` : son assemblage contient les CRUD historiques et sera refusé.
   Réutiliser `install_google_b2b` avec BrowserAuthProfile, même SqlRuntime et
   garde réel ; aucune nouvelle implémentation OIDC ni connexion SQL parallèle.
2. Avec autorisation **lecture seule PostgreSQL** distincte, confirmer l'état
   réel. Seulement si un delta manque, approuver ses opérations A/B et les preuves
   prévues dans `infra/development/B2B_DEPLOYMENT.md`. La qualification DevOps en
   pause n'est ni relancée ni déclarée réussie ici.
3. Faire approuver l'origine et le port HTTPS, le routage fermé, le certificat et
   la confiance navigateur, les journaux expurgés, et le client Google/Workspace.
   Enregistrer le callback exact (schéma/hôte/port/chemin). Le flux est serveur :
   pas de secret client dans Angular ni de GIS/One Tap requis. Vérifier les règles
   officielles Google ci-dessous avant configuration effective.
4. Obtenir puis provisionner sous autorisation un `(issuer, subject)` du compte
   pilote à partir d'une preuve vérifiée, sans le déduire d'un email ni admettre
   provisoirement un compte inconnu. Approuver appartenance et grant minimal dans
   une entreprise précise. Si cette preuve manque, c'est un préalable administratif
   réel ; ne pas lancer un callback en espérant un auto-provisioning.
5. Autoriser explicitement le lancement auth-only et le routage HTTPS. Vérifier
   readiness 200, `/me` sans bearer 401, toutes anciennes API 404, absence d'API
   métier et de traces de secrets. Configurer alors seulement
   `PROFESSIONAL_AUTH_CONFIGURATION` avec l'origine canonique et le protocole
   `industrial-predict:b2b-session:v1`. Le vérificateur réel est déjà fourni par
   appConfig, mais un statut ready ne connecte personne et n'ouvre aucune route.
6. Sous autorisation **connexion Google réelle**, clic utilisateur → popup →
   callback → `/me` 200 et seule entreprise provisionnée → logout 204 → ancien
   bearer refusé 401. Tester refus identité inconnue/appartenance inactive,
   origine incorrecte et indisponibilité sans ouvrir de CRUD. Ne pas copier un
   bearer dans la console ou dans un rapport. Vérifier les effets COOP sur opener.

Le TLS PostgreSQL verify-full n'est jamais remplacé par HTTPS navigateur ni
inversement. Les logs proxy/serveur doivent exclure query du callback, cookies,
Authorization et corps ; access logs désactivés. Ne pas remplacer HTTPS par
HTTP loopback malgré les exceptions Google. Les cookies de binding __Host-
Secure/HttpOnly/SameSite=Lax restent inchangés, les API utilisent le bearer mémoire.

Arrêt : tout échec d'identité/TLS/ACL/readiness, callback ou commit incertain
garde le parcours fermé, sans retry automatique. Retirer la configuration Angular
et arrêter l'assemblage auth-only/routage pour refermer l'accès. Un retour au
lanceur préparation avec les ACL B2B encore installées sera refusé : soit garder
le service arrêté, soit faire approuver l'inverse existant séparément. Ne pas
révoquer des droits, restaurer la base ou annuler le provisioning automatiquement.

Sources Google officielles :
[flux serveur et correspondance exacte du redirect_uri](https://developers.google.com/identity/protocols/oauth2/web-server),
[validation des clients, origines et redirect URIs](https://support.google.com/cloud/answer/15549257).

## Validation du lot (hors connexion)

Les tests ajoutés utilisent seulement ASGI, le garde/chargeur synthétiques et
HttpTestingController. Ils vérifient notamment garde échoué, profil fermé,
identité runtime incohérente, secrets indisponibles, refus d'origine/query/bearer,
contrat exact/no-store, absence d'admission et fermeture métier. Ils ne prouvent
pas qu'un vrai SQL/Google/proxy a réussi. Aucun test global n'est requis.

Résultats du lot : **40 tests backend réussis** (28 nouveaux cas readiness et
12 cas existants directement concernés : profil/logout/401 avant garde/origines/
assemblage fermé/lifespan), **18 tests Angular réussis** (vérificateur réel sur
HTTP synthétique et configuration applicative fermée). Pas de suite globale ni
de build supplémentaire. `git diff --check` valide les changements.

Le sandbox Windows bloquait la paire interne de sockets d'asyncio avant les
fixtures. Après diagnostic, la seule exécution backend hors sandbox a réussi ;
les interdictions SQL/réseau/process des fixtures sont restées appliquées aux
tests. Aucun accès aux ports PostgreSQL ou à Google n'a été nécessaire.
