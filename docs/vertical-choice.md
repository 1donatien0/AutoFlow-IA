# Choix du vertical — AutoFlow AI

**Date de décision** : 2026-06-04  
**Vertical retenu** : **Cabinets comptables (PME 5–30 salariés)**

## Scorecard (synthèse 6 candidats)

| Critère (poids) | Compta | Marketing | Ingénierie | BTP | Juridique | Immobilier |
|-----------------|--------|-----------|------------|-----|-----------|------------|
| Accessibilité décideur (15%) | 4 | 4 | 3 | 3 | 3 | 4 |
| Volume emails/docs (25%) | 5 | 4 | 4 | 4 | 4 | 4 |
| Douleur mesurable h/sem (25%) | 5 | 4 | 4 | 5 | 4 | 3 |
| Willingness to pay (20%) | 5 | 3 | 4 | 4 | 4 | 3 |
| Complexité intégrations (15%) | 4 | 3 | 3 | 2 | 3 | 3 |
| **Score pondéré** | **4.65** | 3.55 | 3.70 | 3.85 | 3.70 | 3.35 |

## Justification

1. Volume élevé d'emails clients répétitifs (relances, pièces, statuts).
2. Top 10 Phase 0 : 6/10 tâches sont compta-centric.
3. ROI observation immédiat : relances + classement + réponses statut.
4. Intégrations Phase 1 réalistes : Gmail/Outlook + Excel (+ outil facturation en Phase 4).

## Personas

### Persona 1 — Gérant cabinet

- 12 collaborateurs, 400 dossiers clients
- Veut réduire charge relances et emails « où en êtes-vous ? »
- Craint erreurs conformité → **lecture seule** Phase 1–3

### Persona 2 — Collaborateur comptable

- Traite 30–50 emails/jour, classe par dossier manuellement
- Utilise Excel pour suivi relances

## 5 workflows types à valider en Phase 1

1. **Demande devis / lettre de mission** : email entrant → brouillon réponse
2. **Relance facture** : email sortant récurrent, même structure
3. **Demande pièces manquantes** : modèle répété par dossier
4. **Question statut déclaration** : FAQ implicite, 30×/mois
5. **Export Excel suivi** : pièce jointe .xlsx + email client

## Connecteurs prioritaires

| Phase | Connecteurs |
|-------|-------------|
| 1 | Gmail, Outlook, import Excel (CSV/xlsx metadata) |
| 4 | Microsoft 365, Google Workspace, outil facturation (Pennylane / Sage API stub) |
| 8+ | HubSpot si cabinet commercial ; Slack interne |

## Hypothèses à invalider en pilote

- Classification email >85 % précision sur 5 catégories
- Estimation « 11 h/mois relances » corrélée au ressenti gérant
- Consentement RGPD lecture seule obtenu >80 % des pilotes

## Références Phase 0

- [Guide interviews](phase0/interview-guide.md)
- [Registre 50 problèmes](phase0/problems-registry.md)
- [Top 10 tâches](phase0/top10-repetitive-tasks.md)
