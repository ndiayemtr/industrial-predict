# Comptes professionnels — fondation 2A

Quatre tables ORM, sans connexion à l'import ni enregistrement dans une route :
local_users, external_identities, company_memberships et membership_permissions.
Les modèles sont importés explicitement ; les exports historiques ne changent pas.
Pas de compte implicite, d'e-mail comme clé, de domaine d'entreprise comme accès,
d'invitation opérationnelle, de session ou de CRUD administratif complet.

## Intégrité

- Utilisateur : entier positif, état explicite active/suspended, aucun état par défaut.
- Identité externe : clé exacte (issuer, subject) unique, FK vers un utilisateur.
  Chaînes non vides sans espaces extérieurs au niveau SQL ; le repository réutilise
  en plus les validations structurelles d'identity.py, sans normalisation.
  La somme UTF-8 des deux identifiants est limitée à 2048 octets pour borner la clé
  d'index PostgreSQL ; un dépassement est refusé, jamais tronqué. C'est une limite
  persistante plus restrictive que les deux champs indépendants du contrat pur.
- Appartenance : paire (user_id, company_id) unique, FK vers utilisateur/entreprise,
  CHECK company_id > 0 même si une entreprise historique négative existe,
  état active/inactive et rôle reader/technician/company_admin explicitement choisis.
- Permission : PK (membership_id, permission). Le rôle est répété et lié par FK
  composite au rôle de l'appartenance : impossible de contourner le plafond SQL
  en déclarant une permission company_admin sur une appartenance reader.
  CHECK SQL fermé sur les six permissions et leurs rôles autorisés. Un rôle sans
  ligne de permission n'accorde rien. Les FK sont RESTRICT, sans suppression cascade.

Les noms ORM suivent les tables métier sans schema ; la future destination doit
imposer search_path=public. La révision utilise explicitement public. La portée
ne modifie pas companies, ses colonnes ou ses contraintes historiques.

## Repository et frontière d'autorité

ProfessionalAccountRepository emprunte une Session explicitement fournie. Il ne
crée pas de moteur, ne consulte aucun settings/env, n'effectue aucun commit ou
rollback automatique. L'appelant possède la transaction et doit confirmer son
commit avant toute annonce de réussite durable. Après IntegrityError/flush,
l'appelant doit rollback ; aucun retry, upsert ou rattachement concurrent implicite.
Un échec de commit incertain reste la responsabilité du futur service transactionnel.

find_by_external_identity() implémente LocalIdentityLookup et retourne tous les
liens exacts avec l'état local du compte. resolve_local_identity() existant refuse
les comptes suspendus et les résultats ambigus. La lecture brute du snapshot ne
doit pas être traitée comme une identité authentifiée ni comme une permission.

memberships_for_user() exige un compte actif et reconstruit des CompanyMembership
avec les enums existants. Les appartenances inactives portent un ensemble vide.
Les rôles/permissions inconnus ou incohérents font échouer le snapshot complet.
Les objets ORM d'appartenance sont rafraîchis à la lecture. Ces lectures restent
un snapshot, pas un verrou contre une révocation ultérieure ; la politique de
fraîcheur et le niveau d'isolation appartiendront au service d'autorisation futur.

link_identity(external=VerifiedExternalIdentity(...), user_id=...) n'est possible
qu'avec require_link_authorization injecté côté serveur. Par défaut aucune liaison
n'est autorisée. Ce callback doit autoriser la clé exacte et le compte cible avant
tout SQL, retourner None après succès ou lever une exception. Un booléen libre
n'est pas accepté. Le callback est une dépendance de confiance, pas une preuve
authentifiée ni un mécanisme d'auto-approbation. Aucune autorité opérationnelle
n'est installée dans ce lot. Il ne doit jamais être choisi par le navigateur.

Le repository vérifie et verrouille le compte actif, ajoute la clé externe puis
flush. Un conflit est refusé : aucune fusion par e-mail ni réaffectation de clé.
La vérification cryptographique de l'identité et l'assurance professionnelle sont
des préconditions du futur appelant ; construire un VerifiedExternalIdentity ne
les prouve pas. Une liaison seule n'ajoute ni compte, appartenance ni permission.

Erreurs publiques constantes, contexte/cause détachés même sous except actif,
aucun journal. Les frames/locals et la Session détenue par l'appelant peuvent
conserver les données originales ; pas de garantie d'effacement mémoire.

## Qualification

Tests SQLite uniquement en mémoire, avec FK activées et fonction octet_length
de test. Ils exercent les contraintes mais ne prouvent pas le comportement des
index, collations, verrous, courses ou commits de PostgreSQL. La révision n'est
jamais importée ; AST, empreintes et comparaison avec l'ORM seulement.

Avant utilisation réelle : déploiement administratif explicitement autorisé,
privilèges SQL minimaux, destination/transport/search_path vérifiés, autorité de
liaison réelle et qualification PostgreSQL de l'unicité concurrente, des blocages,
de la suspension concurrente et des commits incertains. Les gardes Alembic restent
inconditionnellement fermées. Aucun Docker, Google, bootstrap, DEV ou P101 raccordé.
