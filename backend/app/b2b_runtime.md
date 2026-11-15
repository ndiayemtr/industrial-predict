# AUTH-B2B-RUNTIME-1

## AUTH-B2B-ACT-1 — disponibilité locale, activation toujours fermée

Le contrat `GET /api/v1/auth/readiness` est désormais monté uniquement par
l'assemblage navigateur explicite. Sans bearer, il vérifie l'origine HTTPS,
le contexte same-origin, la liaison au même SqlRuntime et l'absence de runtime
métier, puis rejoue `BrowserAuthProfile.check`. Il contrôle la disponibilité
locale du secret par le chargeur approuvé, sans le divulguer, sans requête Google,
sans transaction OIDC et sans émission de session. Succès no-store :
`{status: "ready", profile: "auth-only", bridgeVersion: "industrial-predict:b2b-session:v1"}`.
Échec de qualification/chargeur : 503 générique ; origine appelante étrangère,
sélecteurs query ou Authorization : 403. Une application non montée reste en 404.
Ce contrat ne certifie ni l'acceptation distante du secret ni le provisioning.

Angular UI-2 possède les adaptateurs profil/logout ; ACT-1 ajoute leur vérificateur
HTTP de disponibilité, sans configuration active. Le lanceur DEV reste strictement
préparatoire et le candidat ACL ne constitue pas un profil activable. Le
[plan ACT-1](../../docs/auth-b2b-act-1.md) est l'état courant du chemin critique ;
les sections suivantes conservent l'historique des livraisons, sans prouver un
déploiement actuel, ni autoriser l'exemple historique d'assemblage métier.

## AUTH-B2B-API-1 — contrats navigateur optionnels, aucune activation DEV

Le paramètre `browser_profile` de `install_google_b2b` reste `None` par défaut.
Sans ce profil explicite, les deux nouvelles routes auth ne sont pas montées et
le callback existant conserve sa remise JSON historique. Aucun lanceur, profil
privé, proxy ou garde DevOps n'est modifié par ce lot. Angular n'est pas modifié :
son provider d'adaptateur reste null et son bouton demeure désactivé.

Le profil `BrowserAuthProfile` exige une origine HTTPS canonique et un
`qualification_guard(sql)` serveur. Ce garde doit réutiliser la qualification
réelle approuvée : instance/cluster/base, rôle ui47_app, TLS verify-full et CA,
révision b2b_0002_analyze, cinq fonctions et ACL exactes. Il est exécuté avant
montage puis sur chaque requête auth. Il doit lever une erreur si une condition
échoue et ne rien retourner en cas de réussite ; un booléen n'est pas une preuve.
Un objet typé ou une fonction vide n'atteste aucune qualification. Les gardes
vides utilisés dans les tests sont exclusivement des doubles.

L'assemblage navigateur exige une application limitée aux diagnostics ; il
refuse une application qui monte déjà les CRUD historiques. Il renseigne
`app.state.b2b_auth_runtime`, jamais `b2b_runtime`, et ferme aussi les chemins
métier ajoutés ultérieurement. Le moteur SQL et les stores existants sont
réutilisés ; aucun moteur, compte, grant ou migration n'est créé.

| Route | Contrat du profil navigateur |
|---|---|
| GET /auth/oidc/google/start | Route existante inchangée : 302 vers Google et cookie de binding __Host-, Secure, HttpOnly, SameSite=Lax |
| GET /auth/oidc/google/callback | Même vérification OIDC existante ; retour HTML nonce-CSP avec postMessage sur l'origine exacte de la popup Angular |
| GET /api/v1/auth/me | Bearer canonique obligatoire ; profil frais via les lectures verrouillées existantes |
| POST /api/v1/auth/logout | Bearer courant et Origin exacte obligatoires ; 204 seulement après commit confirmé de revoked_at |

La réponse `/me` correspond exactement à la projection Angular UI-1 :

```json
{
  "userId": 17,
  "displayName": null,
  "companies": [
    { "companyId": 101, "displayName": null, "permissions": ["predictions:read"] }
  ]
}
```

Les noms sont null : le schéma local ne fournit pas de nom utilisateur et aucun
accès industriel supplémentaire n'est nécessaire. Aucun email, issuer, subject,
digest ou secret de session ne figure dans ce DTO. Les entreprises sont limitées
aux appartenances actives disposant d'au moins un grant explicite accepté par
`decide_authorization`. Un rôle seul, un domaine Google ou une appartenance
inactive ne fournit aucun droit. Si aucune entreprise ne satisfait ce contrat,
la réponse est 403. Les données incohérentes ou une autorité indisponible donnent
503 ; les sessions absentes/invalides/expirées/révoquées donnent 401. Un compte
suspendu donne 403. Les lectures ne prolongent pas l'activité de la session.

Dans ce profil, la création de session réutilise `store.create` avec
`require_company_access=True` fixé côté serveur. Les appartenances/grants sont
relus dans la même transaction, avant commit et livraison du secret. Un refus
annule l'INSERT ; aucun compte ou membership n'est provisionné. Le comportement
historique de `create()` sans cette option est conservé.

Le message popup succès est celui préparé par Angular :

```text
{kind: "industrial-predict:b2b-session:v1", token_type: "Bearer",
 session_token: <secret opaque>, absolute_expires_at: <date ISO UTC>}
```

Un échec donne seulement `{kind: "industrial-predict:b2b-session:v1",
error: "denied"}` pour 401/403, ou error="unavailable" pour 503. Les erreurs
Google, notamment access_denied, restent des callbacks refusés ; le flux existant
de consommation/corrélation n'est pas remplacé. L'annulation par fermeture de
popup reste gérée par Angular.

Le script vérifie l'origine de sa propre fenêtre ET celle de `window.opener`,
poste seulement à cette origine exacte, puis ferme la popup. Angular vérifie
de son côté origine ET fenêtre émettrice avant de charger `/me`. Aucun profil
dans le message et aucune authentification dérivée du seul message. Une CSP
nonce par réponse autorise uniquement ce script, sans unsafe-inline ni ressource
externe. Cache-Control no-store, Pragma no-cache, Referrer-Policy no-referrer,
nosniff et frame-ancestors none sont conservés. Les paramètres Google sont retirés
de l'adresse de la popup par replaceState ; aucun bearer ou identifiant de
session n'est placé dans une URL, un Location ou un cookie de session API.

Les API auth refusent les query params, les Authorization/Origin ambigus et les
origines/fetch-sites étrangers. `/me` admet l'absence d'Origin pour un GET HTTPS
same-origin ; `/logout` exige Origin exacte. Aucun CORS permissif n'est ajouté.
Le cookie de binding n'authentifie pas les API ; seul le bearer en mémoire le fait.
Le corps du logout ne sélectionne aucun utilisateur ni autre session : seul le
bearer présenté est révoqué. La perte des droits entreprise n'empêche pas ce
logout ; une session déjà invalide donne 401. Aucun 204 sur commit incertain.

Une livraison perdue après commit peut laisser une session non remise jusqu'à
son expiration ; aucun retry automatique n'est effectué. Une erreur de logout
peut laisser sa révocation incertaine et donne 503. Ces cas ne doivent pas être
interprétés comme un succès par le client. Un opener absent/étranger ne reçoit
aucun message ; les politiques COOP réelles et le comportement Google doivent
encore être validés dans le navigateur avant activation.

Restent nécessaires : qualification réelle du rôle/TLS/ACL et des fonctions,
garde approuvé raccordé au lanceur, assemblage auth-only explicitement autorisé,
origine HTTPS commune avec routage du callback vers FastAPI, configuration
Google/Workspace et provisioning explicite des liens issuer/subject et grants.
Il faut également un futur lot Angular branchant son adaptateur sur ces routes,
sans persistance du bearer. Les logs serveur/proxy ne doivent capturer ni query
du callback, ni corps de réponse, ni Authorization. Aucun de ces changements
d'environnement ou frontend n'est effectué ici ; DevOps demeure en pause.

Les tests utilisent ASGI, les doubles OIDC et le store transactionnel simulé
existant. Ils ne constituent pas une connexion Google réelle ni une qualification
PostgreSQL. Le script popup est aussi exécuté dans un VM Node isolé pour vérifier
son refus d'opener absent/étranger, sans navigateur ni réseau.

## Implémenté, sans activation DEV

La chaîne réutilise GoogleOidcClient (code, PKCE, state consommé durablement,
binding navigateur, nonce, RS256/JWKS, issuer/audience/dates), admit_caller,
resolve_local_identity, PostgresApplicationSessionStore et decide_authorization.
GoogleSessionLogin relie le résultat professionnel vérifié à une identité locale
exacte issuer/subject, puis à une session dont le secret n'est livré qu'après commit
confirmé. Une adresse ou un domaine ne crée ni compte ni appartenance ni permission.
Une identité nécessitant une vérification professionnelle indépendante reste refusée.

Le fournisseur CurrentCaller concret recharge session, utilisateur, lien externe,
appartenances et permissions dans la transaction. Il réutilise les contrôles et
verrous du store. Les memberships et grants sont relus FOR SHARE : leurs modifications
doivent prendre les verrous PostgreSQL ordinaires et attendre la fin de transaction.
Une appartenance inactive ne donne aucun droit, même si ses lignes de grants subsistent.
Les procédures administratives de réaffectation d'identité doivent révoquer les
sessions sous le même verrou utilisateur, conformément au contrat existant du store.

Les API acceptent uniquement `Authorization: Bearer <secret de session opaque>`.
Un ID token Google/JWT n'est pas une session API. Aucun cookie de session API n'est
accepté, aucune identité n'est prise dans le corps ou un domaine email. Il n'y a
donc pas de transmission automatique de justificatif aux POST via un cookie.

## Routes existantes

| Route | Contrôle | État sans assemblage |
|---|---|---|
| GET /api/v1/equipments/{id}/predictions | predictions:read | 401 sans secret valide; 503 si runtime absent |
| GET /api/v1/equipments/{id}/recommendations | predictions:read | même comportement |
| POST /api/v1/equipments/{id}/recommendations | predictions:read ET maintenance:write, même entreprise | même comportement |
| POST /api/v1/equipments/{id}/p101-analysis | predictions:analyze + chaîne entreprise/site/équipement/capteur | provenance manquante : 503 après autorisation |
| POST health-score / rul | barrière historique conservée | 503 |

Avec runtime installé, une session absente, invalide, révoquée ou expirée donne
401; une identité authentifiée sans permission/périmètre donne 403; une autorité
SQL indisponible ou incohérente donne 503. Les erreurs SQL n'exposent pas les paramètres.
Les autres routes historiques ne sont pas sécurisées par ce lot.

Les permissions sont évaluées avant toute lecture métier. Le premier accès au
périmètre équipement est lui-même limité aux entreprises déjà autorisées, puis
la chaîne est verrouillée. Le POST recommandations conserve ces verrous jusqu'au
commit de son repository et revalide session/identité/permissions dans before_commit.
Les algorithmes et réponses métier antérieurs ne sont pas modifiés. L'authentification
ne qualifie pas les anciens résultats utilisés par le moteur de recommandations.

Les GET n'écrivent pas de données ni d'activité de session. La durée d'inactivité
continue donc d'expirer suivant le contrat existant. Aucun privilège implicite DEV.

## Assemblage exact, avant démarrage du serveur

1. Faire approuver séparément la destination, le rôle SQL et l'installation des
   révisions déjà publiées. Les tables local_users, external_identities,
   company_memberships, membership_permissions, application_sessions et
   oidc_transactions doivent être réellement installées et qualifiées dans la
   même destination approuvée que les tables industrielles. Aucun garde Alembic
   n'est contourné. L'état documentaire DEV à 09ac8101e9fe ne prouve pas cette installation.
2. Faire provisionner explicitement le lien issuer/subject, l'utilisateur actif,
   l'appartenance entreprise et chaque grant autorisé. La permission analyse nécessite
   également le CHECK b2b_0002_analyze qualifié. Aucun INSERT de ces éléments n'est
   proposé ni exécuté par l'assemblage. Le rôle SQL existant doit être qualifié pour
   lectures/verrous d'identité, stockage OIDC/sessions et opérations métier autorisées;
   le fait que ui47_app dispose du CRUD industriel ne démontre pas ces droits B2B.
   Les verrous de ligne peuvent exiger des droits UPDATE de colonne dédiés : le
   profil existant ne prouve pas ceux des nouveaux verrous memberships/grants.
   Les qualifier explicitement sans accorder UPDATE global ni capacité de gestion
   d'appartenances au runtime; en l'absence de profil acceptable, garder fermé.
3. Enregistrer un client Google avec le callback exact
   `https://<hôte approuvé>/auth/oidc/google/callback`, config OidcConfig validée
   (issuer https://accounts.google.com, RS256), domaines professionnels approuvés
   et secret client lu par un chargeur privé serveur. Ce routeur de remise de secret
   exige HTTPS, même si la fondation OidcConfig admet un callback loopback HTTP opt-in.
   Aucun secret/profil OIDC activé n'est fourni par ce lot.
4. Dans l'assemblage serveur existant, après contrôle indépendant de destination
   et avant uvicorn.run, envelopper le moteur et la fabrique existants sans en créer
   d'autres, puis installer les composants :

```python
from app.main import app
from app.core.database import engine, SessionLocal
from app.core.database_runtime import SqlRuntime
from app.b2b_runtime import install_google_b2b

# config et read_client_secret proviennent du profil privé approuvé, jamais du navigateur.
# config est une OidcConfig validée, avec les paramètres temporels explicitement approuvés.
sql = SqlRuntime(engine, SessionLocal)
app.state.sql_runtime = sql
auth = install_google_b2b(
    app, sql=sql, config=config, approved_domains=approved_domains,
    client_secret_loader=read_client_secret,
)
```

Ce bloc ne fait aucune connexion à sa construction. Il réutilise le moteur déjà
créé par le lanceur, avec echo=False/hide_parameters=True. Le transport Google
concret impose TLS vérifié, trust_env=False et retries=0; il est fermé à l'arrêt.
Il n'y a aucune configuration automatique par DATABASE_URL ou identité de test.
Ne pas exécuter ce bloc tant que les étapes 1–3 ne sont pas qualifiées/autorisées.

## Validation réelle ultérieure, distinctement autorisée

Ouvrir GET /auth/oidc/google/start sur l'origine HTTPS enregistrée. Le backend
pose seulement le cookie de binding __Host-, Secure, HttpOnly, SameSite=Lax et
redirige vers Google. Le callback consomme state/binding une fois via le store
existant. Les paramètres state/code ambigus sont refusés; aucune tentative automatique
n'est faite après erreur ou incertitude. L'origine reçue doit correspondre au
callback enregistré; un éventuel proxy doit être explicitement approuvé/configuré.

Après admission locale et commit confirmé, le callback remet une fois le secret
opaque dans une réponse JSON no-store/no-cache, sans cookie de session API. Le
client doit ensuite le conserver transitoirement en mémoire et l'envoyer dans
Authorization. Aucun branchement Angular n'est livré. Ne pas journaliser le corps
de callback, les headers Authorization, le code, state, le binding ou le secret
client; désactiver les access logs et la capture de corps au serveur/proxy avant
activation. Ne pas copier ces réponses dans un rapport. Aucun token Google n'est livré.

Vérifier ensuite les GET, les refus 401/403 et la révocation avec des comptes et
entreprises explicitement autorisés. Le POST recommandations écrit réellement :
sa validation réelle nécessite une autorisation d'écriture distincte et ne doit
pas être lancée pour simplement vérifier une session. Les verrous et contrôles
avant commit sont codés/testés sur doubles, pas qualifiés sur PostgreSQL réel.

## Provenance et état réel

install_google_b2b n'installe aucun vérificateur de provenance. Même avec une
session valide, P101 reste fermé au calcul. Le raccordement minimal futur est le
provenance_verifier serveur déjà prévu dans P101AnalysisService : il doit vérifier
des preuves exactes couvrant les lignes originales dans l'instantané. Un manifeste
déclaratif ou une signature d'opérateur seule ne prouve pas une acquisition physique.
Les fixtures UI47 demeurent synthétiques et insuffisantes. Aucun synthetic=False
n'est déduit des nombres. Aucun nouveau chantier d'ingestion n'est entrepris.

L'authentification est implémentée et raccordable, mais aucune connexion réelle
Google ni session réelle n'a été validée pendant ce lot. Aucune installation du
schéma, aucun grant et aucun fournisseur DEV ne sont activés automatiquement.
Les tests isolés valident les refus, le mapping HTTP, la chaîne d'admission, les
rechargements de droits et les contrôles avant commit; ils ne constituent pas une
preuve de fournisseur OIDC ni de stockage PostgreSQL réel.

## Validation effectuée dans ce lot

248 tests ciblés validés, plus 167 sous-cas des contrats existants. La première
exécution a validé 196 tests et ignoré 11 cas RSA; 41 cas runtime ont nécessité
une correction de fixture (configuration historique remplacée par un double),
puis une correction de l'assemblage lifespan pour la version FastAPI installée.
Seuls les cas concernés ont été repris, sans relancer les suites générales.

Les 11 cas RSA initialement ignorés ont ensuite tous réussi dans l'environnement
existant D:\projets\industrial-predict-oidc-m1b-venv, avec PyJWT 2.15.1 et
cryptography 50.0.2. Ils vérifient de vraies signatures locales et refus, avec un
transport fournisseur simulé; aucune authentification Google réelle n'en découle.
Le test correctif du lifespan vérifie aussi la fermeture du transport après le
cycle de vie existant. Aucune requête SQL ou Google réelle n'a été exécutée.

État local vérifié lors de GIT-CONSOLIDATION-1 : `backend/.venv` contient désormais
PyJWT 2.15.1 (`jwt`) et cryptography 50.0.2. La dépendance
`PyJWT[crypto]==2.15.1` est déjà déclarée dans `backend/requirements.txt`.
L'absence de ces modules décrivait l'environnement de l'exécution initiale,
pas son état actuel. Aucun package n'a été installé ou téléchargé pendant les
missions de consolidation Git.

Ces dépendances installées ne constituent ni une activation du runtime B2B,
ni une authentification Google réelle validée. Sans assemblage : les routes
protégées refusent une session absente/invalide avec 401 et un justificatif opaque
syntaxiquement valide avec 503 lorsque le runtime manque. Avec runtime : une
session authentifiée sans permission ou hors entreprise donne 403 ; une autorité
indisponible donne 503. Le POST recommandations exige `predictions:read` ET
`maintenance:write` dans la même entreprise. Même avec ces contrôles installés,
l'analyse P101 réelle reste bloquée sans vérificateur de provenance qualifié.

GIT-CONSOLIDATION-2 : 64 tests HTTP de recommandations et 63 tests ciblés
B2B/P101 ont réussi dans `backend/.venv`, sans accès PostgreSQL ou Google.
Les tests HTTP conservent les dépendances B2B, la politique d'autorisation et
le contrôle de périmètre de production ; la vérification de session et la
configuration PostgreSQL sont simulées, les données métier sont en SQLite mémoire.
Les résultats ne qualifient ni les verrous PostgreSQL ni un runtime DEV activé.
