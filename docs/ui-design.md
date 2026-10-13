# UI Design - Industrial Predict AI

## Objectif

Définir les règles visuelles et UX d'Industrial Predict AI afin de garantir une interface professionnelle, cohérente et adaptée aux usages industriels.

Le design doit permettre à un utilisateur de comprendre rapidement :

- l'état global du parc industriel ;
- les équipements nécessitant une attention ;
- les niveaux de risque ;
- les prédictions disponibles ;
- les recommandations de maintenance ;
- les actions prioritaires.

---

## Principes généraux

L'interface doit être :

- professionnelle ;
- claire ;
- sobre ;
- lisible ;
- orientée données ;
- adaptée aux environnements industriels ;
- cohérente entre les différentes pages ;
- utilisable principalement sur desktop et tablette.

Les informations critiques doivent être visibles immédiatement.

La couleur ne doit jamais être le seul moyen de transmettre une information.

---

## Structure globale

L'application utilise une structure SaaS classique :

```text
┌─────────────────┬──────────────────────────────────────┐
│                 │                                      │
│     Sidebar     │             Header                   │
│                 │                                      │
│                 ├──────────────────────────────────────┤
│                 │                                      │
│                 │          Contenu principal           │
│                 │                                      │
│                 │                                      │
└─────────────────┴──────────────────────────────────────┘
```
