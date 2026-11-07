# P101-DEV-4A - simulation explicite, sans analyse DEV

Le panneau est intégré entre les filtres et l'historique de `/predictions`.
Il réutilise uniquement le contexte entreprise/site/équipement déjà résolu par
la page. Ce contexte sert de libellé à la démonstration : les mesures réelles de
l'équipement ne sont jamais analysées. Ce n'est pas un contrôle d'autorisation B2B.

Les types UI sont séparés des modèles de prédictions persistées. Les fixtures
locales sont dans `p101-simulation.fixtures.ts`, hors façade et service API.
Le runner local émet après 450 ms pour rendre l'état en cours perceptible.
Il ne possède aucune dépendance HTTP, endpoint, stockage local ou backend.
Les fixtures sont des exemples de présentation, pas des réponses HTTP ni un
portage du moteur statistique. Leurs valeurs ne sont jamais fusionnées dans
le tableau, le total, les filtres ou l'état de la façade de l'historique.

Scénarios sélectionnables : anomalie (70 °C, moyenne 65, seuil 3, écart 5,
indice 1), aucune anomalie (65 °C, écart 0, indice 0), abstention pour trois
références sur dix, rejet pour provenance volontairement incomplète, erreur
locale. Les champs statistiques indisponibles restent non disponibles ; les
abstentions/rejets ne reçoivent aucun indice. Les indices ne sont pas présentés
comme probabilités de panne. Le marquage « Simulation - données fictives » et
la provenance fictive restent visibles dans tous les états.

Une modification du contexte, sa remise à zéro ou une nouvelle vérification
du contexte par la page annule la simulation et efface son résultat. Changer
le scénario efface aussi l'exemple précédent. Pendant l'exécution, action et
sélecteur sont désactivés. Une génération et la désinscription empêchent un ancien
résultat de réapparaître après changement d'équipement ou destruction du panneau.
Une émission unique est retenue ; erreurs, exceptions et fin sans résultat ont
une présentation constante, sans message technique brut.

## Recette visuelle à effectuer sur un environnement déjà autorisé

Ne démarrer aucun service DEV sans autorisation humaine distincte. Cette recette
n'implique aucune écriture PostgreSQL ; les GET de références/historique restent
ceux de la page existante. Vérifier préalablement l'identité DEV selon la procédure
habituelle et utiliser exclusivement le frontend DEV autorisé sur 4201.

1. Ouvrir `/predictions` sans sélection : badge permanent et action désactivée.
2. Sélectionner entreprise, site et équipement avec les sélecteurs existants.
   Vérifier le libellé du panneau et conserver le nombre de lignes de l'historique.
3. Choisir « Anomalie détectée - indice 1 », cliquer « Simuler une analyse » :
   état en cours, puis valeurs 70 / 65 / 3 / 5 °C et indice 1, sans pourcentage.
4. Répéter pour indice 0, abstention, rejet et erreur. Aucun indice ne doit être
   attribué aux trois derniers états ; aucun résultat ne doit apparaître dans
   le tableau de prédictions enregistrées.
5. Pendant une simulation, changer d'équipement/contexte ou retirer la sélection :
   retour initial, aucun résultat tardif associé au nouvel équipement.
6. Vérifier détails/provenance, clavier, focus, affichage étroit et lisibilité
   du badge. Dans Réseau, le clic de simulation ne doit produire aucune requête.
   Les sélections et actualisations de l'historique peuvent toujours produire
   leurs GET habituels. Ne pas lancer de calcul historique RUL/Health Score.

Les tests jsdom examinent DOM, transitions et séparation HTTP avec des fixtures.
Ils ne remplacent pas une vérification de rendu dans un navigateur. Aucun serveur
DEV n'est nécessaire à leur exécution, ni démarré par ce lot.
