# Google OIDC B2B — Mission 1

Client backend synchrone sans route, session, utilisateur, SQL ou permission.
Les composants existants oidc_config, oidc_transactions et identity sont réutilisés
sans modification. Aucun bootstrap, environnement DEV ou P101 n'est raccordé.

## API et frontière de confiance

`GoogleOidcClient(config=..., approved_domains=(...), transport=..., clock=...,
store=..., allowed_return_targets=(...))`
exige des dépendances serveur explicites. Les domaines sont une liste fermée
d'éligibilité définie par l'administrateur, jamais une liste obtenue du navigateur.
Le profil Google impose issuer HTTPS canonique et RS256 seulement. L'extension à
un autre fournisseur utilisera les contrats génériques existants ; aucune URL
de fournisseur n'est acceptée depuis une requête utilisateur.

- `authorization_url(start)` accepte un TransactionStart du manager existant :
  code flow, scopes openid/email, state, nonce et PKCE S256. Aucun hd n'est émis.
  Cette URL contient du matériel de corrélation : ne pas la journaliser.
- `complete_callback(state=..., browser_binding=..., code=..., client_secret=...)`
  est le seul point d'entrée public produisant une identité. Il valide state et
  liaison navigateur, vérifie la disponibilité JOSE puis appelle consume() du
  OidcTransactionManager existant, construit avec la même configuration, le store
  serveur explicite, l'horloge et les cibles de retour autorisées.
  L'échange de code n'est effectué qu'après le retour confirmé de ce manager.
  Transaction absente, expirée, rejouée, liaison divergente, reçu malformé ou
  résultat incertain interdisent tout appel réseau et toute identité retournée.
- Les anciennes méthodes publiques exchange()/verify_id_token() sont retirées.
  `_exchange()` et `_verify_id_token()` sont des détails privés, réservés au
  client et aux tests unitaires. Les futurs callbacks doivent utiliser uniquement
  complete_callback(), jamais ces helpers ni un OidcTransaction fourni librement.
  La visibilité privée Python n'est pas une isolation contre du code serveur
  malveillant ; un développeur capable de modifier/appeler les internes reste
  dans la frontière de confiance. Aucun nouveau reçu déclaratif n'est introduit.

La consommation durable réutilise exactement TransactionStore : CONFIRMED
signifie que l'adaptateur promet un commit terminé, après correspondance de toutes
les conditions et consommation atomique. Le manager contrôle aussi le contenu du
reçu. Un booléen, un objet transaction ou un reçu malformé ne suffit pas. Le client
ne peut prouver la persistance réelle d'un store injecté mensonger. En production,
utiliser l'adaptateur PostgreSQL qualifié et son runtime explicitement approuvé.
Les doubles du présent lot ne prouvent ni les verrous ni la durabilité PostgreSQL.
Un commit incertain est un échec, sans échange, retry ou restauration automatique.
Après consommation confirmée, tout échec réseau/JOSE est terminal pour cet appel ;
le record n'est jamais restauré. Repartir d'une nouvelle transaction OIDC.
Aucun jeton d'accès ou de rafraîchissement n'est retourné.

Le transport appartient à l'appelant, qui doit le fermer à la fin de son cycle
de vie. Les clients HTTP par requête ne le ferment pas. Un futur transport réel
devra activer la vérification TLS et désactiver retries et routage arbitraire.
Les doubles peuvent mentir : leur injection est une frontière de confiance,
comme pour le TransactionStore existant. Aucun transport réel n'est créé ici.

## Réseau et validation

Endpoints fixes HTTPS : accounts.google.com/o/oauth2/v2/auth,
oauth2.googleapis.com/token et www.googleapis.com/oauth2/v3/certs.
Pas de discovery dynamique, redirection, netrc ou proxy hérité de l'environnement.
Timeout connexion 3 s ; lecture, écriture et pool 5 s chacun. Ces timeouts HTTPX
ne constituent pas un délai global contre un pair qui envoie lentement des octets.
Une future intégration doit imposer son budget global et sa limitation de débit.

Les requêtes token ET JWKS envoient explicitement Accept-Encoding: identity.
Toute réponse indiquant une compression est refusée, même si le serveur ignore
cette négociation. Les redirections restent interdites.
Réponses JSON uniquement, sans compression, maximum 64 Kio, doublons JSON
refusés. ID token maximum 16 Kio ; JWKS maximum 32 clés avec kid uniques.
JWKS récupéré une fois par validation, sans cache ni refresh automatique. Une clé
inconnue est refusée ; une nouvelle authentification pourra obtenir les nouvelles
clés. Le cache, s'il devient nécessaire, exigera une politique explicite de rotation.

JOSE : seuls alg/kid/typ sont admis dans le header ; jku, x5u, jwk et crit ne
peuvent introduire une autre source de clés. Clé RSA publique de 2048 à 8192 bits,
usage signature/vérification ; aucune clé privée JWKS acceptée. PyJWT vérifie
signature, audience et issuer avec un algorithme fixé par le serveur. Le client
contrôle aussi les types exacts des claims, l'audience et azp (obligatoire pour
plusieurs audiences), nonce, exp, iat, ancienneté maximale, nbf/auth_time présents.
Les vérifications temporelles sont faites explicitement avec l'horloge UTC
injectée et le skew OidcConfig, plutôt qu'avec deux horloges différentes.
La transaction est contrôlée par le manager lors de la consommation et par les
helpers avant échange/validation ; expiration exclusive.
Une consommation déjà confirmée ne peut pas être annulée si le réseau échoue ensuite.
Les deux spellings Google documentés d'issuer sont acceptés après vérification,
puis ramenés à https://accounts.google.com comme clé locale canonique. Aucun
autre issuer ni rapprochement par e-mail n'est accepté.

## Identité professionnelle

`external_identity` est la clé (issuer, subject) issue de la signature vérifiée.
Elle ne contient pas l'e-mail comme identifiant. Les objets sont immuables avec
repr opaque ; leurs constructeurs bruts ne constituent pas une preuve cryptographique.

Dans tous les cas : email présent, syntaxe ASCII conservatrice, email_verified
exactement true, domaine explicitement approuvé. Une liste de domaines personnels
courants est refusée même en cas d'approbation ; cette liste n'est pas exhaustive
et ne remplace pas la revue administrative du caractère professionnel d'un domaine.
Les adresses internationales et syntaxes atypiques sont hors de ce premier profil.

- Claim signé hd présent, exact et concordant avec le domaine approuvé :
  GOOGLE_WORKSPACE, professional_email_verified vrai.
- hd absent : INDEPENDENT_VERIFICATION_REQUIRED, professional_email_verified faux,
  même si email_verified est vrai. Une future preuve indépendante récente de
  possession de la boîte est obligatoire. Ce lot ne propose aucun moyen de
  transformer ce résultat en vérification réussie.
- hd présent mais vide, mal typé ou divergent : refus.

Les deux résultats ont access_authorized faux, et bool(result) est refusé.
Aucun domaine, e-mail, hd ou résultat ne donne une appartenance ni ne prouve un
emploi actuel. La couche d'admission future doit explicitement vérifier
l'assurance de l'e-mail ET l'invitation/liaison locale avant toute session.

## Erreurs et limites de qualification

Erreurs publiques constantes OIDC_CLIENT_REJECTED / OIDC_CLIENT_UNAVAILABLE,
sans cause ou contexte conservé, y compris dans un except actif de l'appelant.
Pas de journalisation applicative. Le traceback formaté ne conserve pas la chaîne
des exceptions du transport/JOSE. Il ne faut pas utiliser un collecteur de locals
non assaini : les frames/arguments, la mémoire et les copies détenues par l'appelant
peuvent toujours contenir des secrets. Aucune garantie d'effacement mémoire.

Nouvelle dépendance déclarée : PyJWT[crypto]==2.15.1, version publiée le
28 septembre 2026, Python >=3.9, bibliothèque maintenue avec backend cryptography
pour RSA. httpx==0.28.1 était déjà déclaré. Aucune installation dans ce lot ;
les dépendances transitives de l'extra crypto devront être résolues et revues
lors d'une installation autorisée. Pas de cryptographie maison.

Les tests de politique utilisent un double JOSE explicitement identifié : ils
ne démontrent pas une signature. Un groupe distinct produit des clés RSA de test
éphémères et vérifie réellement les signatures avec PyJWT/cryptography lorsqu'ils
sont installés ; sinon chaque cas est signalé comme skipped. Aucun appel Google.

Références primaires :
- https://pypi.org/project/PyJWT/2.15.1/
- https://pyjwt.readthedocs.io/en/latest/api.html
- https://developers.google.com/identity/openid-connect/openid-connect
- https://developers.google.com/identity/sign-in/android/backend-auth

## Qualification et corrections 1D

Qualification RSA 1B avant corrections : 86 réussis, 1 ignoré, dont 9 cas RSA
réels réussis, dans D:\projets\industrial-predict-oidc-m1b-venv avec Python 3.12.10,
PyJWT 2.15.1 et cryptography 50.0.2. Le cas ignoré concerne l'absence de dépendance,
non applicable lorsque JOSE est installé ; aucune signature n'est simulée dans
les neuf cas RSA. Aucun appel réel Google.

Les corrections 1D imposent l'orchestration publique et la négociation identity.
Les tests ajoutés couvrent l'ordre consommation/confirmation/réseau, refus,
expiration, rejeu, mauvaise liaison, reçus incohérents, commit incertain,
compression sur les deux endpoints et erreur réelle de signature dans jwt.decode().
Les tests isolés des helpers privés restent des tests internes, pas des exemples
applicatifs. Aucun nouveau registre, contrôleur d'autorisation, route ou session.
