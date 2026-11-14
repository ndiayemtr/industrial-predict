# AUTH-B2B-UI-1 — Parcours frontend préparé, backend non activé

Le provider PROFESSIONAL_AUTH_BACKEND vaut null dans tous les builds livrés.
La page /connexion ne fait aucun appel HTTP, n'ouvre aucune popup et n'affiche
aucun compte connecté. Le bouton Google reste désactivé. Aucun paramètre URL,
localStorage/sessionStorage ou /health ne peut activer le parcours.

## Contrats examinés et limites exactes

| Élément | Contrat existant | Utilisation frontend |
|---|---|---|
| GET /auth/oidc/google/start | FastAPI b2b_login.py ; redirection 302, cookie __Host- de binding, HTTPS | Chemin constant, navigation popup à la suite du clic ; jamais HttpClient/fetch |
| GET /auth/oidc/google/callback | FastAPI ; vérification code/state/binding, réponse JSON no-store avec token_type=Bearer, session_token et absolute_expires_at | Le callback reste au backend, aucune route Angular ne l'intercepte |
| Bearer API | Secret opaque canonique base64url de 32 octets, pas un JWT Google | Mémoire privée du service seulement |
| Identité et entreprises | Fondations CurrentCaller serveur, aucune route de profil publiée | Port loadProfile non branché ; aucun endpoint /me inventé |
| Révocation | Store serveur existant, aucune route HTTP de déconnexion publiée | Port revokeSession non branché ; aucun endpoint /logout inventé |
| Retour popup | Aucun postMessage fourni par le callback JSON actuel | Bridge proposé ci-dessous, non opérationnel côté serveur |

Il est impossible de terminer aujourd'hui une connexion réelle avec ces seuls
endpoints. Un JSON affiché par une popup n'envoie pas de postMessage. Aucun
scraping du document JSON, injection de script dans le callback, deuxième échange
de code ou faux succès n'est utilisé pour masquer ce manque.

## Port d'intégration à approuver avant activation

ProfessionalAuthBackend est un contrat interne Angular, pas une API déclarée
existante. Un futur adaptateur devra implémenter readiness (signal explicitement
qualifié), loadProfile et revokeSession à partir de véritables contrats HTTP
protégés, revus séparément. Il devra mapper les DTO serveur en projection
ProfessionalProfile : userId, displayName nullable, companies contenant companyId,
displayName nullable et permissions explicites. Ces champs ne sont pas supposés
exister dans une réponse FastAPI actuelle. Aucun domaine email ne donne de droit.

L'adaptateur devra transmettre le bearer uniquement aux routes HTTPS d'auth
approuvées sur la même origine, sans logs, persistence, retry ou diffusion aux
CRUD historiques. Aucun interceptor global ajoutant Authorization n'est livré.
Un provider explicitement écrit dans un lot futur est nécessaire ; aucun switch
de démonstration ou adaptateur de simulation n'est livré dans l'application.

Proposition de retour navigateur, à implémenter/revoir côté serveur :

```text
{
  kind: "industrial-predict:b2b-session:v1",
  token_type: "Bearer",
  session_token: <secret opaque issu par le serveur>,
  absolute_expires_at: <date ISO UTC serveur>
}
```

Alternativement : `{kind: "industrial-predict:b2b-session:v1", error: "denied"}`,
error limité à denied/cancelled/unavailable. Aucun profil ou grant dans le message.
Le futur bridge devra envoyer uniquement à l'origine Angular HTTPS exacte,
préserver les garanties OIDC/backend, appliquer no-store/no-referrer et une CSP
adaptée, et ne jamais mettre de token dans une URL. Le callback JSON actuel a
une CSP default-src 'none' : ce lot ne le modifie pas et ne prétend pas qu'un
bridge fonctionne déjà. L'architecture retenue est strictement same-origin HTTPS.

Le frontend contrôle origine ET référence exacte de la popup, refuse les ports
transférés, les données ambiguës/supplémentaires et les secrets non canoniques.
Un message valide déclenche seulement le chargement du profil authentifié côté
serveur ; aucun état connecté n'est établi depuis le seul message.

## États et cycle de vie

Initial → indisponible (par défaut) ou non connecté (adaptateur futur prêt).
Clic → popup → chargement du profil → session vérifiée. Ou refus, annulation,
popup bloquée, fermeture, timeout, erreur réseau/503. Aucun retry automatique.
Les requêtes de profil/révocation sont bornées à 10 secondes, la popup à 120 s.
Les clics multiples, callbacks répétés et réponses tardives sont ignorés.

Le service efface bearer et profil sur expiration absolue, 401 d'une session
établie, refus/incohérence, reset ou destruction ; il nettoie popup, listeners,
timers et abonnements. Une baisse du signal de readiness efface aussi la session.
Une horloge navigateur ne remplace pas l'expiration/autorisation serveur : les
durées d'inactivité et la révocation restent décidées par le serveur. Vérifier la
session recharge le profil via le port ; aucun jeton n'est récupéré après reload.

Déconnexion : état local effacé immédiatement, succès annoncé seulement après
révocation serveur (ou 401 indiquant une session déjà invalide). Sur erreur,
l'interface dit explicitement que la révocation n'est pas confirmée. Effacement
local, fermeture de popup ou annulation après émission ne garantissent pas une
révocation distante : une session émise peut subsister jusqu'à son échéance.
Le futur raccordement backend devra traiter ce risque et les commits incertains.

PREPARATION_ROUTES et preparationOnlyGuard restent inchangés. Même une session
valide dans les tests unitaires ne débloque ni le Shell ni les anciennes pages
métier. Aucune nouvelle permission ou origine n'est autorisée par l'UI.

## Validation visuelle frontend, sans backend et sans DevOps

Depuis D:\projets\industrial-predict\frontend, avec node_modules déjà installé :

```powershell
node node_modules/@angular/cli/bin/ng.js serve --host 127.0.0.1 --port 4201 --configuration development --proxy-config proxy.auth-preparation.json
```

Ouvrir http://127.0.0.1:4201/connexion. Vérifier desktop, 320 px, 375 px : panneau
bleu compact sur mobile, titre et bouton visibles sans débordement horizontal,
bouton désactivé, message de préparation, aucune requête auth/API dans Network.
Les URL /companies et /predictions doivent revenir à /connexion sans chargement
métier. Le fichier proxy vide sert uniquement à cette validation : aucun proxy
vers 8000/8001 et aucun lancement du gestionnaire DEV, de Docker ou PostgreSQL.
Les états connectés/refusés sont couverts par doubles unitaires ; aucun panneau
de simulation visuelle ni faux utilisateur n'est accessible dans l'application.

## Vérifications ciblées

```powershell
node node_modules/@angular/cli/bin/ng.js test --watch=false --include="src/app/features/auth/**/*.spec.ts" --include="src/app/app.config.spec.ts"
node node_modules/@angular/cli/bin/ng.js build
```

Aucune connexion Google réelle n'est validée par ces tests. Restent à approuver :
contrats profil/révocation et bridge, assemblage serveur fermé par défaut, HTTPS
same-origin, cookies de binding, politiques Google/Workspace, provisioning
explicite des identités/entreprises/grants, privilèges SQL et qualification réelle.
La qualification DevOps demeure en pause ; ce lot ne la reprend pas.
