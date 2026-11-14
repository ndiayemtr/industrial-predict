# AUTH-B2B-UI-2 — Adaptateur FastAPI raccordé, activation fermée

`appConfig` fournit désormais `FastApiProfessionalAuthBackend`. Sa configuration
et son vérificateur de disponibilité valent **null par défaut dans les builds
livrés** : aucune requête, popup, session ou ouverture métier au démarrage.
Le design de `/connexion` et les guards de préparation restent conservés.

## Correspondance avec AUTH-B2B-API-1

| Contrat FastAPI existant | Utilisation Angular |
|---|---|
| `GET /auth/oidc/google/start` → 302, cookie de binding sécurisé | Navigation popup synchrone après clic, jamais HttpClient/fetch |
| `GET /auth/oidc/google/callback` | Traité exclusivement par FastAPI : PKCE, state, nonce, identité et autorisations serveur ; aucune route callback Angular |
| Bridge du profil navigateur explicitement qualifié | `industrial-predict:b2b-session:v1`, contrôle de l'origine HTTPS exacte, de la fenêtre émettrice et du contexte de connexion |
| `GET /api/v1/auth/me` → 200 JSON no-store | Bearer de session en en-tête ; DTO exact `{userId, displayName, companies}` |
| Entreprise du DTO | `{companyId, displayName, permissions}` ; noms nullables, permissions explicites, jamais inférées du domaine Google |
| `POST /api/v1/auth/logout` → 204 vide no-store | Corps vide, bearer courant uniquement, aucun sélecteur d'utilisateur/entreprise |
| 401 / 403 / 503 | Session absente/expirée ou révoquée / refus / indisponibilité ; aucun compte connecté en cas d'échec |

Le callback navigateur serveur émet :

```text
{kind: "industrial-predict:b2b-session:v1", token_type: "Bearer",
 session_token: <secret opaque canonique base64url de 32 octets>,
 absolute_expires_at: <date ISO UTC serveur>}
```

Les erreurs sont `{kind: "industrial-predict:b2b-session:v1", error: ...}`,
avec `denied`, `cancelled` ou `unavailable` seulement. Aucun profil n'est accepté
dans le message. Les données supplémentaires, ports transférés, mauvaises sources
ou origines, doublons, réponses tardives et callbacks sans tentative sont ignorés.
Une livraison valide déclenche `/me` ; elle ne suffit jamais à établir une session.
Le callback JSON historique ne remplace pas ce bridge navigateur qualifié.

## Disponibilité : blocage explicite avant activation réelle

Deux dépendances distinctes sont nécessaires :

- `PROFESSIONAL_AUTH_CONFIGURATION` : origine HTTPS canonique égale à celle
  d'Angular et version exacte du bridge ; aucun champ `enabled` n'est accepté.
- `PROFESSIONAL_AUTH_READINESS_VERIFIER` : intégration de confiance chargée de
  vérifier réellement le profil serveur sécurisé avant de terminer avec succès.

**Aucune implémentation du second port n'est fournie.** L'API actuelle n'a pas de
contrat de preuve de disponibilité avant connexion. `/health`, OpenAPI, une
configuration frontend ou un 401 de `/me` ne prouvent pas l'exécution du garde de
qualification serveur : la validation du bearer intervient avant ce garde.
Aucun endpoint de disponibilité n'est inventé et aucun probe n'est envoyé.
Une intégration serveur réelle, revue séparément, reste donc nécessaire.
Un double RxJS de réussite dans les tests n'est jamais une procédure d'activation.
Les paramètres URL, cookies et stockages navigateur ne configurent pas ces ports.

## Transport et cycle de vie

Le client Fetch dédié contourne les interceptors globaux. Il ajoute Authorization
uniquement sur les deux chemins d'authentification fixes de la même origine HTTPS.
Les requêtes refusent les redirections, omettent les cookies, désactivent cache et
transfer cache SSR et ne placent ni bearer ni sélecteur dans l'URL ou le corps.
Le client HTTP historique reste inchangé et ne reçoit aucun bearer automatiquement.

Le referrer est limité à la racine de l'origine, avec politique `same-origin`.
Le navigateur doit fournir son en-tête Origin exact sur POST, exigé par FastAPI ;
Angular ne forge pas cet en-tête. Ce comportement exige encore une validation
dans un véritable navigateur HTTPS avec le backend activé, pas seulement un mock.
Les réponses réussies doivent respecter statut, URL, absence de redirection,
no-store, format JSON et DTO attendus. Les erreurs publiques sont assainies, sans
corps serveur ni diagnostics susceptibles de refléter le bearer.

Bearer et profil restent en mémoire. Reload repart sans identité, sans tentative
de récupération persistante. Expiration absolue, refresh 401, refus, reset,
destruction ou retrait de disponibilité effacent les données sensibles.
L'inactivité et la révocation sont décidées par le serveur. Aucun retry automatique.
Le transport HTTP expire après 8 s (avant le délai de sécurité du service à 10 s),
la vérification de disponibilité après 10 s et la popup après 120 s.

Déconnexion : effacement local immédiat, confirmation seulement après 204 vide
ou 401 (session déjà invalide). Erreur, timeout ou réponse incohérente conservent
l'avertissement « déconnexion serveur non confirmée », même lorsque la disponibilité
du transport est retirée. Une erreur réseau ou 503 referme le parcours, sans
tentative de réactivation automatique. Annulation ou fermeture locale ne révoquent
pas à elles seules une session qui aurait déjà été émise côté serveur.

Même une session authentifiée ne débloque pas le Shell ou les anciennes routes
métier : `PREPARATION_ROUTES` et `preparationOnlyGuard` restent inchangés.

## Validation visuelle frontend sans backend ni DevOps

Depuis `D:\projets\industrial-predict\frontend`, dépendances déjà installées :

```powershell
node node_modules/@angular/cli/bin/ng.js serve --host 127.0.0.1 --port 4201 --configuration development --proxy-config proxy.auth-preparation.json
```

Ouvrir `http://127.0.0.1:4201/connexion`. Vérifier desktop, 320 et 375 px : design
préservé, bouton Google désactivé, explication de préparation, aucun débordement
horizontal et aucune requête auth/API dans Network. `/companies` et `/predictions`
doivent revenir à `/connexion`. Le proxy vide ne contacte aucun serveur backend.

Les autres états sont validés par doubles unitaires uniquement : en cours, refus,
profil serveur chargé, expiration, indisponibilité, réseau et déconnexion.
Aucun mode de simulation visuelle ou faux compte n'est livré dans l'application.

```powershell
node node_modules/@angular/cli/bin/ng.js test --watch=false --include="src/app/features/auth/**/*.spec.ts" --include="src/app/app.config.spec.ts"
node node_modules/@angular/cli/bin/ng.js build
```

Ces tests ne qualifient aucune connexion Google réelle. Avant cette validation :
preuve serveur de disponibilité, activation explicite de BrowserAuthProfile et de
ses gardes SQL/TLS/ACL, HTTPS same-origin et routage des chemins existants,
configuration Google/callback, provisioning explicite des identités/appartenances,
cookies de binding et compatibilité popup/COOP doivent être validés. La qualification
DevOps demeure en pause et aucune opération PostgreSQL n'est effectuée dans ce lot.
