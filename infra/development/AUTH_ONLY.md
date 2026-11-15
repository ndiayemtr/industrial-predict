# AUTH-B2B-ACT-2 — lancement FastAPI explicitement auth-only

Implémentation préparée, aucun environnement activé. Le lanceur reste `manage.py`.
Sans option, `api` conserve b2b-preparation et uniquement les deux diagnostics.
Le contrat du profil privé DEV, les migrations et la matrice candidate sont
inchangés. Le candidat n'est toujours pas un profil de lancement.

## Sélection et prérequis

Seule combinaison nouvelle acceptée : action `api`, `--runtime-profile auth-only`,
`--role ui47_app`, profil DEV officiel. Bundle, sélection de révision/migration et
campagne de qualification sont refusés. Les autres actions ne peuvent sélectionner
auth-only, avant lecture du profil privé. Un champ runtime_profile=auth-only dans
le fichier DEV de base est refusé : il doit rester préparatoire.

Créer **ultérieurement, après approbation**, dans le répertoire privé approuvé
`D:\integration\industrial-predict\development` :

- `auth-only.json`, objet exact à quatre champs, sans doublons ni clés inconnues.
- `google-client-secret.txt`, secret client Google serveur uniquement, ASCII
  visible sans espace, 1–4096 caractères, avec au plus une fin de ligne finale.
  Aucun chemin de secret configurable, fichier redirigé hors répertoire, variable
  d'environnement ou fallback .env. ACL NTFS privées à faire vérifier par
  l'opérateur ; le code ne certifie pas ces ACL Windows.

Modèle de configuration **non activé**, valeurs Google à fournir dans le fichier
privé seulement. L'origine et le port ci-dessous sont proposés, non déployés :

```json
{
  "profile": "auth-only",
  "origin": "https://localhost:4443",
  "approved_domains": ["DOMAINE_WORKSPACE_APPROUVE"],
  "oidc": {
    "issuer": "https://accounts.google.com",
    "client_id": "CLIENT_WEB_GOOGLE_APPROUVE",
    "callback_url": "https://localhost:4443/auth/oidc/google/callback",
    "signature_algorithms": ["RS256"],
    "deployment_mode": "development",
    "allow_http_loopback_callback": false,
    "transaction_ttl_seconds": 300,
    "clock_skew_seconds": 0,
    "max_id_token_age_seconds": 300
  }
}
```

Les paramètres sont validés par OidcConfig et GoogleOidcClient existants : origine
HTTPS canonique, callback exact, issuer Google, RS256, domaines professionnels
explicites et cohérence temporelle. Aucune requête Google ne vérifie le client au
démarrage ; son acceptation distante ne sera connue que lors du vrai callback.
Une configuration valide ne provisionne ni utilisateur, ni appartenance, ni grant.
Modifier la configuration OIDC impose un redémarrage explicitement autorisé.

## Contrôles et surface

1. Profil privé officiel, destination exacte, CA et son SHA-256, sslmode=verify-full
   vérifiés avant lecture du secret Google ou du mot de passe SQL.
2. Un seul moteur officiel, toujours ui47_app, echo=False/hide_parameters=True.
   Le même SqlRuntime alimente stores, gardes et routes. Aucune connexion à une
   autre base, aucun moteur de repli, migration, GRANT ou provisioning.
3. Avant montage puis sur les requêtes : identité/cluster/instance/base/role,
   révision b2b_0002_analyze, propriétaires, séquences, privilèges historiques,
   matrice candidate complète (PUBLIC/héritages/excès inclus), cinq fonctions,
   signatures/empreintes/search_path/propriétaire/ACL. Transactions de contrôle
   READ ONLY, statement_timeout 15s, lock_timeout 5s, toujours ROLLBACK.
4. Seul install_google_b2b(..., browser_profile=BrowserAuthProfile(...)) est appelé.
   Aucune importation app.main/core.database, aucun ancien CRUD ; b2b_runtime
   métier reste absent. Les routes ajoutées tardivement restent filtrées.
5. Routes : GET `/health`, `/__dev/identity`, `/api/v1/auth/readiness`,
   `/auth/oidc/google/start`, `/auth/oidc/google/callback`, `/api/v1/auth/me` ;
   POST `/api/v1/auth/logout`. Pas de docs/OpenAPI activées par ce lanceur.
6. Readiness rejoue les gardes et chargeur secret, sans session ni Google. 200
   no-store signifie prêt localement ; dérive, secret absent ou garde refusé :
   503. Ni readiness, ni domaine Google ne valent admission d'un utilisateur.
   PKCE/state/nonce, identité issuer/subject, entreprises et révocation restent
   entièrement ceux des composants existants.
7. Uvicorn écoute seulement 127.0.0.1:8001, access_log=False, niveau warning.
   Les erreurs du CLI n'affichent que leur type. Moteur libéré après arrêt ou
   échec de montage ; transport Google fermé par le lifespan existant.

Les droits CRUD industriels historiques sont toujours contrôlés, sans modification
de leur contrat ; cela ne les rend pas accessibles par HTTP. Aucun droit nouveau
sur les objets industriels n'est attribué dans ce lot.

## HTTPS futur et commande opérateur non exécutée

Le lanceur ne crée ni certificat ni proxy HTTPS. Il autorise les forwarded headers
uniquement depuis 127.0.0.1 (jamais `*`). Le proxy local approuvé doit terminer le
HTTPS, préserver Host exact, **remplacer** les forwarded headers reçus du client,
fournir X-Forwarded-Proto=https et ne router vers FastAPI que les cinq chemins auth
et les diagnostics autorisés. Ne jamais exposer directement 8001 au réseau.
La confiance dans les processus loopback locaux fait partie de cette frontière.
Sans cette chaîne, les routes OIDC/auth refusent l'origine HTTP ; aucun repli HTTP.
Exclure query callback, Authorization, cookies et corps des logs proxy.

Après autorisations réelles séparées pour SQL/ACL, fichiers privés, HTTPS, Google
et lancement du runtime (cette commande ouvre des connexions PostgreSQL réelles) :

```powershell
Set-Location D:\projets\industrial-predict
& '.\backend\.venv\Scripts\python.exe' -B '.\infra\development\manage.py' api --config 'D:\integration\industrial-predict\development\config.json' --runtime-profile auth-only --role ui47_app
```

Les cinq fonctions et les 16 accords doivent déjà être qualifiés/approuvés et
installés ; leur absence arrête le lancement, sans installation automatique.
La qualification DevOps en pause n'est pas relancée par cette commande.
Le lanceur Angular existant reste fermé et refusera ces ACL après attribution :
son routage HTTPS et la configuration Angular sont des opérations séparées.
Aucun contournement du proxy/garde Angular n'est livré dans ACT-2.

Vérifications futures HTTPS : readiness 200, health runtime_mode=auth-only,
/me sans bearer 401, anciens CRUD 404. Puis seulement sous autorisation Google :
popup → callback → profil serveur → logout confirmé, ancien bearer 401.
L'identité et une entreprise doivent être provisionnées explicitement auparavant.

Retour fermé : arrêter le service et retirer sa sélection explicite. Ne pas
forcer b2b-preparation à accepter les ACL candidates ; son refus reste normal
tant que celles-ci sont installées. Aucun REVOKE, restauration ou nettoyage
automatique n'est exécuté lors de l'arrêt.

## Validation hors DEV

Depuis la racine, tests exclusivement synthétiques ; aucun fichier privé existant
n'est chargé. Le mock catalogue exécute les vrais contrôles existants sur les
objets simulés, les routes sont exercées en ASGI sans serveur réseau :

```powershell
$env:PYTHONPATH = 'backend;infra/development'
& '.\backend\.venv\Scripts\python.exe' -B -m unittest -q test_auth_launcher test_manage.RuntimePreparationTests test_b2b_activation.ActivationTests.test_cli_candidate_cannot_launch_any_other_action_or_read_private_config
git diff --check
```

Sous sandbox Windows, la paire de sockets privée d'asyncio peut être bloquée ;
exécuter uniquement ces tests avec l'autorisation locale correspondante. Leurs
protections interdisent ensuite tout accès SQL, Google ou Docker réel. Ne pas
utiliser la commande opérateur pour simplement vérifier le logiciel.

Résultat ACT-2 : **27 tests ciblés réussis**, comprenant le nouveau lanceur,
RuntimePreparationTests existants et le refus CLI du profil candidat. Les
contrôles complets de catalogue/ACL/fonctions sont réellement exécutés sur leurs
doubles ; aucune qualification PostgreSQL réelle ou connexion Google n'en découle.
`git diff --check` est également vérifié. Aucune suite globale n'est relancée.
