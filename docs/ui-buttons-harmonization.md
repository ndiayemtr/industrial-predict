# Harmonisation globale des boutons UI

- Date : 2026-10-19.
- Branche : feature/frontend-equipments, HEAD 37992ff.
- Intervention ajoutée au travail UI 5.5 déjà présent et non commité. Aucun commit, push ou merge.

## Ecarts constatés et corrections

- Nouvel équipement : icône absente, espacement, graisse et bordure différents de Nouvelle entreprise. Réutilisation du même mixin partagé et du SVG 20 x 20, trait 1.75, espacement 8 px. Navigation Angular et sept paramètres de contexte conservés.
- Nouveau site : bordure et graisse différentes de la référence, absence de survol dédié. Réutilisation du même mixin sans changement fonctionnel.
- Boutons de recherche, formulaires, pagination, références et Dashboard : survol parfois absent, appui et transitions non harmonisés. Styles interactifs centralisés dans une feuille SCSS limitée aux actions du Shell. Les boutons secondaires restent clairs et les liens métier ordinaires conservent leur présentation.
- Dashboard : bordure du bouton Appliquer les filtres différente du fond primaire. Alignement sur le token primaire. Les états disabled natifs, y compris via fieldset, et aria-disabled restent gris avec curseur not-allowed, sans survol actif.
- Réessayer et retour 404 : survol auparavant fondé sur le soulignement seul. Même traitement primaire au survol et à l'appui que les autres actions primaires.
- Shell : ajout du retour d'appui et des transitions ; le tiroir garde son contraste sombre et son focus blanc. Le backdrop reste inchangé.
- Focus visible commun, transitions de couleurs de 120 ms et désactivation des transitions avec prefers-reduced-motion. Aucun déplacement ni changement de dimensions pendant l'interaction.
- Aucun tooltip redondant trouvé : aucun ajout ou retrait. Noms accessibles des boutons à icône seule et aides de validation conservés.

## Fichiers de cette intervention uniquement

- frontend/src/styles.scss
- frontend/src/styles/_actions.scss (nouveau, extraction du mixin Companies)
- frontend/src/styles/_buttons.scss (nouveau)
- frontend/src/app/features/companies/styles/_company-actions.scss (réexport compatible)
- frontend/src/app/features/sites/pages/sites-list/sites-list.component.scss
- frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.scss
- frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.html
- frontend/src/app/features/equipments/pages/equipments-list/equipments-list.component.spec.ts
- docs/ui-buttons-harmonization.md (ce rapport)

Les autres modifications UI 5.5 préexistantes sont conservées. Le relevé SHA-256 avant intervention permet de distinguer les huit fichiers source ci-dessus dans frontend/tmp/ui-buttons/changed-files.json.

## Validation

- Tests ciblés : 761 réussis dans 44 fichiers (Companies, Sites, Equipments, Dashboard, Shell et composants partagés).
- Suite Angular complète ensuite : 809 réussis dans 48 fichiers.
- Build production ensuite : réussi. Bundle initial 604,66 ko contre 601,86 ko avant cette intervention, soit environ +2,81 ko. Avertissement existant du budget de 500 ko maintenu ; aucun seuil modifié.
- Test de navigation enrichi : icône décorative, libellé explicite, focus et conservation des sept paramètres lors de la navigation vers la création.
- Navigateur sur le build production avec serveur fictif isolé : référence Companies et actions Sites/Equipments de mêmes couleurs, bordures, graisse 600 et espacement 8 px. Survol primaire sombre et secondaire clair observés après clic ; focus clavier visible sur Nouvel équipement. Contraste texte/fond primaire 5,17:1, survol primaire 15,56:1, secondaire au survol 14,23:1, désactivé 5,48:1.
- Liste Equipments contrôlée à 1440, 1024, 1023, 768, 390 et 320 px : aucun débordement horizontal global. Dashboard contrôlé à 1440 et 320 px, formulaire de création à 320 px et ouverture/fermeture du tiroir mobile. Aides du formulaire toujours présentes.
- Les états d'appui et la préférence de mouvement réduit sont définis dans le SCSS compilé ; aucun maintien d'appui ni émulation de cette préférence n'a été réalisé par l'outil navigateur. Les états de chargement et blocages existants restent couverts par les tests fonctionnels, sans ajout de temporisation ou de logique applicative.
- Aucun avertissement ou erreur console sur les parcours navigateur contrôlés. Journal du serveur fictif : 17 requêtes GET, aucune écriture et aucun accès au backend réel.
- Premier lancement des tests bloqué par EPERM du cache temporaire Windows avant tout test ; relance avec accès autorisé réussie. Aucun contournement dans le code ou la configuration du projet.
- git diff --check et contrôle des nouveaux fichiers : réussis. Index vide. Aucun secret, dump, capture ou journal ajouté au suivi Git.

## Preuves locales et limites

- Journaux, relevé responsive, audit HTTP et captures dans frontend/tmp/ui-buttons/, répertoire ignoré par Git.
- Captures : screenshots/equipments-1440.jpg, equipments-390.jpg, equipments-320.jpg, companies-1440.jpg, dashboard-1440.jpg, shell-320.jpg et create-320.jpg.
- Validation visuelle sur données fictives uniquement ; aucune écriture PostgreSQL, aucune modification backend, Docker, package, contrat API ou règle métier.
- La réserve UI 5.5 sur la validation du dialogue natif d'abandon reste inchangée.
- Etat final attendu : branche feature/frontend-equipments, HEAD 37992ff, modifications non stagées UI 5.5 et harmonisation en attente de validation avant commit.
