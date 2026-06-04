# Checklist bêta commerciale — Mois 12

## Pilotes

- [ ] 3 cabinets comptables pilotes signés (DPA + consentement lecture seule)
- [ ] 2 semaines d'observation par pilote sans incident
- [ ] NPS pilote ≥ 30

## Produit

- [ ] Dashboard 3+ métriques validées par gérant
- [ ] Classification ≥ 85 % sur échantillon 200 emails
- [ ] ≥ 1 workflow approuvé exécuté en sandbox par pilote
- [ ] Kill switch testé par organisation

## Conformité RGPD

- [ ] Registre des traitements à jour
- [ ] Hébergement VPS UE documenté
- [x] Rétention configurable (30/90/180 jours) — globale via `DATA_RETENTION_DAYS` ; par tenant à faire
- [x] Export / suppression données client (`/api/v1/organization/export`, `/data`)
- [x] Journal audit (`audit_logs`) consultable (page « Données & RGPD »)

## Monitoring & support

- [ ] Healthcheck `/health` (liveness) + `/health/ready` (base) — alerting uptime à brancher
- [ ] Logs structurés API + worker Celery
- [ ] Runbook incident (OAuth, sync, worker)
- [ ] Support email dédié pilotes — SLA 24 h ouvrées

## Commercial

- [ ] Pricing pilote → production défini
- [ ] Page onboarding + formation 1 h
- [ ] Contrat bêta avec clause sortie données

## Stack validée

| Service | Port | Statut attendu |
|---------|------|----------------|
| API FastAPI | 8000 | OK |
| Web Next.js | 3000 | OK |
| PostgreSQL | 5432 | OK |
| Redis | 6379 | OK |
| Celery worker | — | OK |

## Commande lancement bêta

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```
