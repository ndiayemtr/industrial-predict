# UI 4.6.2 - Code métier et simulations isolées

Suivi : UI 4.6.2 validée par l’utilisateur et enregistrée dans la série de commits avant UI 4.7.4. Les résultats et états Git ci-dessous décrivent l’intervention initiale.

17 octobre 2026. Branche `feature/frontend-sites`, HEAD `e8702b0`.
Les travaux UI 4.6 non commités présents au départ sont conservés.
Aucun changement de comportement applicatif ni correction de donnée réelle.
Le site réel id=3 reste une donnée de test ; son code n'est pas corrigé.

## Diagnostic démontré

Examen de SiteCreate/SiteUpdate, SiteFormComponent, SiteCreateComponent,
SiteEditComponent, SitesApiService et du template partagé :

- POST : la création envoie company_id/name/code et la description si fournie.
  Le formulaire retire seulement les espaces périphériques de name/code ;
  aucune concaténation, suffixe ou modification de casse. Le service sérialise
  le DTO sans transformation supplémentaire.
- PATCH : le formulaire compare les valeurs brutes au SiteRead initial. Seuls
  les champs différents sont retenus. Dirty ne suffit pas à inclure code.
  SitesApiService applique en plus sa whitelist name/code/description : aucun
  company_id, identifiant ou horodatage.
- Les textes d'aide sont des paragraphes associés aux champs par ARIA ; ils
  n'alimentent pas les FormControl. Le formateur de libellés d'entreprise ne
  participe pas au code Site envoyé. La mention « rattachement reste inchangé »
  appartient à un message d'erreur, sans affectation à une valeur de formulaire.
- Le champ Code accepte une chaîne métier libre compatible avec les limites
  existantes. Si un suffixe est explicitement saisi, il est transmis littéralement.
  Aucun contrat ne permet de le retirer automatiquement. Une valeur déjà
  suffixée et non modifiée reste intacte, sans être envoyée dans PATCH.

Les quatre nouveaux cas Angular utilisent exclusivement HttpTestingController :

1. Saisie DOM `DEMO-SITE-001` en création : POST et JSON exacts, sans suffixe.
2. Code initial `DEMO-SITE-001`, puis modification DOM nom/description : PATCH
   exact avec uniquement name/description, même si Code est marqué dirty.
3. Même scénario avec code initial `DEMO-SITE-001 (inchangé)` : code source
   conservé, absent du PATCH, aucune correction silencieuse.
4. Saisie explicite du suffixe dans Code : PATCH code exact. Ce test démontre
   une possibilité normale de saisie, pas l'origine de l'incident historique.

Les tests transport existants vérifient aussi serializeBody, whitelist,
valeurs omises/vides/null et absence de conversion des horodatages.
**Aucun défaut d'ajout automatique du suffixe n'est identifié dans les chemins
examinés et les cas testés.** Aucun correctif fonctionnel spéculatif n'est ajouté.

## Limites rétrospectives

La lecture PostgreSQL et FastAPI de l'étape UI 4.6.1 a établi la persistance
réelle du code `DEMO-SITE-001 (inchangé)` pour id=3, avec PETROSEN. Ce constat
historique ne reconstitue ni le POST ni le PATCH d'origine. Les captures d'écran
et les toasts ne prouvent pas une interception HTTP.

En l'absence des corps de requêtes initiaux, il reste impossible de déterminer
quand le suffixe a été introduit, par quelle saisie ou quel client, et de certifier
que le PATCH historique excluait code. Les tests actuels ne remplacent pas ces
traces manquantes et ne prouvent pas rétroactivement l'absence d'une intervention
extérieure au code examiné.

Aucun accès PostgreSQL ni appel au FastAPI réel n'est effectué en UI 4.6.2.
Aucune modification, suppression ou correction du site réel id=3 par cette étape.

## Risque du proxy et choix de simulation

[proxy.conf.json](../frontend/proxy.conf.json) dirige `/api/v1/**` vers
`http://127.0.0.1:8000` dans la configuration de développement Angular.
L'application configure provideHttpClient sans intercepteur de simulation.
HttpTestingController remplace le transport dans les tests uniquement ; il ne
protège pas une session `ng serve` normale.

Une interception de quelques routes dans DevTools ou dans un automate navigateur
peut laisser passer une écriture oubliée, une route différente ou une requête
après perte de l'interception. Ne pas employer un mécanisme avec fallback vers
FastAPI. Ne pas utiliser le proxy Angular normal pour les essais d'écriture.

Un outil indépendant est proposé et testé :
[sites-simulation-server.mjs](../frontend/scripts/sites-simulation-server.mjs).
Il n'est importé ni par Angular ni par le backend, n'ajoute aucune dépendance et
ne modifie ni le proxy ni les budgets.

### Frontière de sécurité du serveur proposé

- Écoute seulement sur 127.0.0.1:8098, distinct des ports Angular/FastAPI.
- Aucune URL amont, aucun client proxy, aucun accès aux paramètres de base,
  aucune lecture de .env, aucune connexion ou persistance PostgreSQL.
- GET Companies/Sites et POST/PATCH Sites sont servis depuis des objets en
  mémoire. Entreprise fictive 9001 ; sites fictifs à partir de 9001. Aucun id=3
  n'est préchargé ni résolu par un autre serveur.
- Toute route API inconnue échoue localement. DELETE/PUT et les routes
  d'écriture non prévues sont refusées ; aucune transmission de secours.
- POST/PATCH nécessitent une origine exacte et un cookie de session aléatoire,
  HttpOnly/SameSite=Strict, délivré par la page locale. Sans session valide :
  réponse 503, sans mutation. L'interface existante traite cette incertitude
  comme une soumission non confirmée et bloque la nouvelle soumission.
- Le cookie est renouvelé à chaque démarrage. Une ancienne session ne permet
  pas de soumettre après redémarrage sans recharger la page.
- CSP `connect-src 'self'` et `form-action 'self'` : les connexions du document
  servi sont limitées à cette origine, sans cible FastAPI autorisée. Pas de CORS
  ouvert. Script externe, objet et framing sont restreints par les en-têtes.
- Bandeau explicite SIMULATION ISOLEE, marqueur HTTP
  `X-Industrial-Predict-Simulation: sites-isolated-v1`, statut et journal locaux.
  Si le bandeau ne peut pas être installé, le démarrage est refusé.
- Le chargement CSS optimisé Angular est rendu synchrone dans la réponse HTML
  simulée, pour éviter son onload inline incompatible avec la CSP stricte.
  Aucun artefact de build ni fichier applicatif n'est réécrit.

La garantie porte sur les requêtes reçues par ce serveur et les connexions du
document ainsi servi. Ce n'est pas une protection globale de tous les onglets
du navigateur : naviguer vers une vraie application sort de cette frontière.
Si l'origine, le marqueur, le bandeau ou la session sont incertains, **ne pas
soumettre**. Une interception partielle ne constitue pas une alternative sûre.

### Procédure reproductible

Depuis `frontend`, séquentiellement :

```powershell
node node_modules/@angular/cli/bin/ng.js test --watch=false
node node_modules/@angular/cli/bin/ng.js build --configuration production --output-path tmp/ui-4.6.2/production
node --test scripts/sites-simulation-server.test.mjs
node scripts/sites-simulation-server.mjs tmp/ui-4.6.2/production/browser
```

1. Si une commande échoue, si le répertoire est absent ou si 8098 est déjà
   occupé, arrêter. Ne pas utiliser un port ou un serveur de remplacement.
2. Lire `http://127.0.0.1:8098/__simulation/status` et vérifier mode
   sites-isolated-v1, upstream=null, persistence=memory-only, run non vide et
   marqueur HTTP. Vérifier la CSP de la page. Un mauvais statut bloque le test.
3. Ouvrir un onglet dédié sur
   `http://127.0.0.1:8098/sites/new?company_id=9001&page=2&page_size=50&search=DEMO`.
   Vérifier le bandeau et Entreprise de simulation - SIM-COMPANY. Ne pas réutiliser
   un onglet sur 4200/8000 ou une référence à PETROSEN. En contexte navigateur
   douteux, utiliser un profil de test vierge, sans service worker/interception
   préexistant, avant tout essai.
4. Créer avec un nom explicitement fictif et un code saisi seul, sans annotation
   telle que « (inchangé) ». Vérifier le POST dans Network, son URL 8098, son
   marqueur de réponse et le journal local.
5. Ouvrir Modifier, changer uniquement nom et description. Vérifier le PATCH
   et son corps exact : name/description, sans code/company_id/dates. Vérifier
   le code affiché et le retour au contexte de liste.
6. Lire `http://127.0.0.1:8098/__simulation/journal` avant l'arrêt. Conserver
   les corps, URLs, réponses et le run du statut comme preuve de cette session.
   Le journal contient des intentions de requête ; rapprocher leur résultat
   des réponses Network, notamment pour les erreurs simulées.
7. Arrêter par Ctrl+C et fermer l'onglet. Toutes les données fictives sont
   perdues. Ne jamais rejouer ces requêtes sur le backend réel.

Le simulateur est volontairement limité aux parcours Sites et références
entreprises : il ne reproduit pas toute la validation SQL/Pydantic, les jokers
ILIKE ou les autres modules. Une taille de corps de 16 Kio est imposée uniquement
à cet outil. Il ne remplace pas les tests des contrats ni une validation réelle
explicitement autorisée.

## Résultats exécutés dans cette étape

| Contrôle | Résultat |
| --- | --- |
| Tests Angular complets | 581 réussites, 42 fichiers ; départ 11:47:33 UTC, durée 21,05 s |
| Build production | Réussi à 11:48:14 UTC, durée 10,534 s ; warning de budget existant |
| Tests Node du serveur isolé | 7 réussites, 0 échec, durée finale 343,35 ms |
| Comparaison SHA-256 JS/CSS avec UI 4.6 | 31 fichiers identiques, aucune différence |
| Poids initial / ensemble JS-CSS | 601 509 / 785 921 octets, inchangés |
| Budget Angular | 500 ko ; dépassement existant +101,51 ko, aucun relèvement |
| `git diff --check` | Réussi |

Les tests Node vérifient notamment POST/GET/PATCH en mémoire, code exact, corps
du journal, refus de session/origine invalide, routes non simulées, DELETE/PUT,
champs PATCH interdits, JSON invalide, corps excessif, absence de fallback,
réinitialisation des données/session et compatibilité CSS sous CSP stricte.

Le navigateur a parcouru création puis modification sur 8098, après contrôle du
statut/en-têtes. Le journal de la session finale contient exactement :

```json
[
  {"method":"POST","path":"/api/v1/sites","body":{"company_id":9001,"name":"Site de simulation UI 4.6.2","code":"DEMO-SITE-001"}},
  {"method":"PATCH","path":"/api/v1/sites/9002","body":{"name":"Site de simulation UI 4.6.2 - Modifié","description":"Description simulée uniquement en mémoire."}}
]
```

La fiche fictive affiche toujours DEMO-SITE-001 ; retour conservé avec
company_id=9001&page=2&page_size=50&search=DEMO. Capture :
`ui-4.6.2-isolated-simulation.jpg` dans le dossier de visualisation de la tâche.
Journal copié sous `frontend/tmp/ui-4.6.2-simulation-journal.json` et statut sous
`frontend/tmp/ui-4.6.2-simulation-status.json`, ignorés par Git.
Ces traces appartiennent à cette simulation, pas au parcours historique du site 3.
Serveur arrêté après les contrôles ; les objets fictifs en mémoire sont perdus.

## Fichiers et état Git

Fichiers propres à UI 4.6.2 :

- Tests complétés : `pages/site-create/site-create.component.spec.ts` et
  `pages/site-edit/site-edit.component.spec.ts`, sous les features Sites.
- Nouveaux outils : `frontend/scripts/sites-simulation-server.mjs` et son test
  `sites-simulation-server.test.mjs`.
- Ce rapport et sa procédure. Aucun autre changement par cette finition.

Les modifications applicatives UI 4.6 préexistantes sont conservées telles quelles.
Pas de changement backend, DTO/API, proxy, dépendance, budget, ni de donnée réelle.
Branche feature/frontend-sites, HEAD e8702b0, index vide : 14 fichiers suivis
modifiés et 8 fichiers nouveaux en comptant UI 4.6. Aucun commit, push ou merge.
UI 4.7 non commencée. Validation attendue avant toute correction supplémentaire.
