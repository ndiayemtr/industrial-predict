# Contrôle hors ligne — ML 6.2B-2D-3D-2B-2B-3B

Ce module est un modèle déterministe en mémoire. Il ne lance aucune action et
ne collecte aucune preuve réelle. Le script bootstrap, ses gardes et les contrats
existants restent inchangés. Aucun broker opérationnel n'est ajouté.

## Contrats et frontière de confiance

`controller_contract()`, `approval_contract()` et `evidence_envelope()` sont les
fabriques validantes. Les dataclasses brutes ne sont pas des points de validation ;
les méthodes du contrôleur revalident leurs entrées. Objets et résultats ont une
représentation opaque, une conversion booléenne refusée et `execution_authorized`
toujours faux. Les résultats sont des décisions/descriptions, sans commandes,
secret, URL, connexion ou capacité d'exécution.

`Approval` contient référence externe, provenance déclarée, campagne, session,
moteur, ressources exactes via CampaignContract, version PostgreSQL, image,
révision Git, empreintes des neuf artefacts d'exécution requis, opération/phase
unique, fenêtre UTC et conditions exactes fixées par la politique interne.
`approval_fingerprint()` lie l'ensemble des champs par SHA-256 ; ce digest ne
constitue ni une signature ni une authentification humaine.

`ApprovalAuthority.authenticate()` est une interface abstraite SANS implémentation
réelle. Un futur exécuteur indépendant devra authentifier l'approbation humaine
et retourner un verdict lié à l'empreinte, la session, la provenance et aux deux
références. Le noyau refuse absence, booléens, verdict non attesté ou divergent.
Une sous-classe Python peut mentir : les doubles de tests le font explicitement.
Un objet AuthorityVerdict ordinaire n'est donc jamais une preuve cryptographique
ou administrative. L'interface est une frontière de confiance à implémenter, pas
une défense contre du code Python arbitraire ayant accès au processus ou à Docker.

## Transitions

`Controller.request(approbation, autorité, preuve_avant)` produit au maximum une
ActionDescription et passe en PENDING. Une référence attestée est consommée avant
la description, même si une précondition échoue ensuite. `record(id, résultat,
preuve_après)` vérifie les postconditions avant d'avancer. Une seule opération
peut être en attente. L'état public `state` est un instantané immuable ; le
contrôleur et ses registres restent des données locales en mémoire.

Les trois méthodes mutatrices (`request`, `record`, `invalidate`) partagent un
garde de réentrance installé avant tout callback injecté. Un appel imbriqué à
`request` ou `record` est refusé et ferme la session : INVALIDATED avant
description, UNCERTAIN si une description est en attente. Un `invalidate`
imbriqué ferme explicitement la session en INVALIDATED. Un état déjà INVALIDATED
ou UNCERTAIN est préservé. Les appels extérieurs ne peuvent ensuite produire
aucune description ni valider un succès. Après chaque callback, un instantané
d'intégrité est comparé : cycle de vie, phase, sessions, destination, opération
en attente, registres consommés et ancrages temporels doivent être inchangés.
Le bloc finally libère uniquement le garde, sans restaurer un état antérieur.
Ce mécanisme traite les callbacks réentrants séquentiels ; ce n'est pas un verrou
multithread ou interprocessus, ni une protection contre la modification arbitraire
des attributs privés par du code compromis.

| État initial | Opération | État après succès attesté par données injectées |
|---|---|---|
| préparation | recreate | recréation autorisée / reçu de création enregistré |
| recréation autorisée | inspect_new | nouveau conteneur inspecté |
| nouveau conteneur inspecté | bootstrap_local | bootstrap local |
| bootstrap local | configure_tls | configuration TLS |
| configuration TLS | attest_final | attestation finale, COMPLETE |

La recréation est autorisée sur l'ancien ID et son manifeste exact. Son reçu
peut introduire UN nouvel ID de conteneur, différent de l'ancien ; aucune autre
valeur du manifeste ne peut changer. Cet ID est seulement enregistré comme cible
de l'inspection suivante. Une NOUVELLE approbation externe liée au nouvel ID est
nécessaire avant cette inspection, puis à chaque étape suivante. Aucune identité
future inconnue n'est approuvée implicitement pour démarrer PostgreSQL.

CONFIRMED_FAILURE exige ses propres observations après opération et invalide la
session. Sans ces preuves, un échec annoncé devient UNCERTAIN. Résultat incertain,
preuve absente/divergente, délai dépassé ou incohérence après description bloquent
toute nouvelle opération ; aucun retry, arrêt, nettoyage ou rollback n'est émis.
`invalidate()` ferme une session et ne réactive jamais une session incertaine.
La réconciliation n'est volontairement pas implémentée : elle impose une mission
distincte, des preuves réelles et une nouvelle décision externe explicite. Il
n'existe aucune méthode reset/resume pour contourner ce point d'arrêt.
Si un callback invalide explicitement la session pendant `record`, l'état reste
INVALIDATED et le résultat extérieur est UNCERTAIN : le succès n'a pas pu être
établi après la description. Ces deux informations sont distinctes et terminales.

## Temps, anti-rejeu et preuves

`Clock.sample()` est injectée ; aucune horloge globale n'est consultée. Les UTC
doivent être des datetime natifs en timezone.utc et les valeurs monotones des
entiers en nanosecondes, dans le même domaine d'horloge que le collecteur.
La fenêtre est `[not_before, expires_at)`, de dix minutes maximum. Une échéance
monotone est fixée avant l'appel à l'autorité ; l'attente de ce verdict ne la
prolonge pas. Début/fin UTC et délai monotone sont revérifiés avant description
et enregistrement. Un recul de l'une des horloges bloque la session. Une
expiration ne détruit aucune ressource : elle refuse de nouvelles décisions et
rend incertain un résultat non attesté avant l'échéance.

`CLOCK_TOLERANCE` fixe une divergence absolue maximale de **1 milliseconde**
(frontière incluse) entre une durée UTC et sa durée monotone. La comparaison porte
sur chaque progression d'échantillons successifs, la progression depuis le premier
échantillon de session (pour éviter l'accumulation de petites dérives), la durée
de collecte et l'âge depuis la fin de chaque preuve. Les durées négatives sont
toujours refusées, même dans la tolérance. Une horloge fortement divergente
invalide avant description ; après description, le résultat devient UNCERTAIN.
Une preuve incohérente est refusée avant description, avec référence attestée
déjà consommée ; elle rend le résultat UNCERTAIN après description.

Cette politique suppose des paires UTC/monotone acquises avec une précision et
une dérive cumulée compatibles avec 1 ms, dans le même domaine monotone que les
preuves. datetime a une résolution à la microseconde ; les comparaisons sont
faites en nanosecondes entières, sans flottants. Un ajustement de l'horloge système
dépassant la tolérance provoque un arrêt prudent, même si cet ajustement est
légitime. Cette disponibilité limitée est assumée. La tolérance n'ajoute aucune
marge aux dix minutes, à l'expiration stricte ou aux deux bornes de cinq secondes.
Une horloge injectée ou un collecteur mensonger reste hors de cette garantie.

Le registre consomme les IDs d'approbation ET leurs références externes. Il ne
protège que l'instance courante, à usage séquentiel : ni verrou multi-thread,
stockage durable, unicité multi-processus, ni protection après redémarrage. Deux
instances neuves peuvent accepter le même double : un test documente cette limite.
Le futur exécuteur devra assurer l'usage unique atomique, la session non réutilisée
et le refus de reprise après perte d'état ; recréer une instance n'est pas une
procédure autorisée de récupération.

EvidenceEnvelope contient source déclarée, moteur, campagne/ressources, sessions
de contrôle et collecte, phase, avant/après, intervalles UTC/monotones, révision,
empreintes et observations pertinentes. La fraîcheur maximale est cinq secondes ;
les intervalles inversés/futurs ou trop longs sont refusés. Les preuves après
opération doivent débuter après l'émission de la description. Les observations
de tests sont spécifiées indépendamment des contrats ; leurs libellés ne prouvent
ni Docker, ni TLS, ni SQL, ni l'authenticité du collecteur. Elles ne deviennent
jamais une autorisation. Les faits SQL et Docker réels restent à collecter et à
lier aux connexions effectives dans une future mission.

## Confidentialité et prérequis opérationnels

Erreurs constantes, cause/contexte détachés, aucune journalisation. Exceptions
externes remplacées par refus ou incertitude sans diagnostic brut. Cette protection
n'efface pas les erreurs détenues par l'appelant, les sources ou variables locales
des frames. Aucun mot de passe, clé privée ou token n'est accepté par le contrat.

Avant toute activation, il reste à réaliser l'exécuteur de confiance, ses contrôles
d'accès Docker, le collecteur réel, le registre durable/atomique et la gestion
explicite des défaillances de PID 1. Un accord humain, une validation statique et
une preuve réelle ne sont pas interchangeables. Les limites TOCTOU et la compromission
d'un administrateur de l'hôte ne sont pas résolues par ce noyau.
