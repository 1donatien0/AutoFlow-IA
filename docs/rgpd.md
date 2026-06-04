# Conformité RGPD — AutoFlow AI

## Principes (Phases 1–3)

- **Minimisation** : lecture seule emails (sujet, extrait, métadonnées)
- **Finalité** : observation processus, pas d'envoi automatique sans consentement Phase 4+
- **Durée** : rétention `DATA_RETENTION_DAYS` (défaut 90 jours), purge quotidienne par le worker Celery (tâche `purge_expired_events`). Rétention par tenant : à faire
- **Droit d'accès / portabilité** : export JSON complet via `GET /api/v1/organization/export` (page « Données & RGPD »)
- **Droit à l'effacement** : `DELETE /api/v1/organization/data?confirm=true` (conserve le compte et le journal d'audit)
- **Minimisation** : seuls sujet, extrait (≤ 2000 car.), expéditeur et date sont stockés ; plus de copie brute du message
- **Sécurité** : jetons OAuth chiffrés au repos (Fernet), états OAuth signés, secrets par défaut refusés en production
- **Journal** : table `audit_logs` (action, acteur, horodatage), consultable via `GET /api/v1/organization/audit-logs`

## Documents pilote

- DPA (Data Processing Agreement) cabinet ↔ AutoFlow
- Registre des traitements (article 30)
- Mention consentement OAuth Gmail/Outlook (scopes readonly)

## Hébergement cible

- VPS Union Européenne
- Chiffrement transit (TLS) + repos (volume chiffré)
- Sauvegardes PostgreSQL chiffrées

## Contact DPO

À désigner avant bêta commerciale — voir [beta-readiness.md](beta-readiness.md).
