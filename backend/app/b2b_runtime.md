# AUTH-B2B-RUNTIME-1

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
