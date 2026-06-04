# AutoFlow AI

Plateforme d'observation et d'automatisation intelligente des processus PME.

**Promesse** : *Montrez-moi comment vous travaillez, et je vous montrerai ce que vous pouvez automatiser.*

Boucle produit : **Observer → Comprendre → Suggérer → Automatiser**

## Stack

| Couche | Technologie |
|--------|-------------|
| API | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, PyJWT |
| Web | Next.js 16, React 19, TypeScript, Tailwind CSS 4 |
| BDD | SQLite (dev) · PostgreSQL 16 (Docker / prod) |
| Queue | Redis, Celery (workflows + purge RGPD quotidienne) |
| NLP | Heuristiques + spaCy (fr, optionnel), LLM OpenAI (optionnel) |

## Démarrage rapide (sans Docker)

**Prérequis** : Python 3.11+, Node 20.9+.

```bash
cp .env.example .env                 # à la racine — lu automatiquement par l'API

# API (SQLite : apps/api/autoflow.db)
cd apps/api
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Web (autre terminal)
cd apps/web
npm install
npm run dev
```

- API : http://localhost:8000/docs (désactivé quand `ENVIRONMENT=production`)
- Web : http://localhost:3000 → « Créer un compte » → Intégrations → « Charger données démo »

## Avec Docker (PostgreSQL, Redis, worker Celery)

```bash
cp .env.example .env
docker compose -f infra/docker/docker-compose.yml up -d --build
```

Les migrations Alembic sont appliquées au démarrage de l'API. PostgreSQL et Redis
n'écoutent que sur `127.0.0.1`.

## Tests et qualité

```bash
cd apps/api
pip install -r requirements-dev.txt
ruff check app tests
pytest -q                                              # SQLite
TEST_DATABASE_URL=postgresql+asyncpg://... pytest -q   # PostgreSQL
pip-audit -r requirements.txt

cd apps/web
npm run typecheck && npm run build && npm audit
```

La CI GitHub Actions (`infra/ci/github-ci.yml`, à déplacer dans `.github/workflows/ci.yml`) exécute tout cela à chaque push / PR.

## Migrations

```bash
cd apps/api
alembic upgrade head                                   # appliquer
alembic revision --autogenerate -m "description"       # après modification des modèles
```

Base créée avant la v0.2 (via `create_all`) : la recréer, ou `alembic stamp head`
après avoir vérifié que le schéma correspond.

## Mise en production — points obligatoires

- `ENVIRONMENT=production` : l'API refuse de démarrer si `JWT_SECRET_KEY` / `API_SECRET_KEY`
  sont absents, par défaut ou < 32 caractères (`openssl rand -hex 32`).
- `DEMO_MODE=false`, `AUTO_CREATE_TABLES=false`, `CORS_ORIGINS` / `FRONTEND_URL` / `API_PUBLIC_URL`
  sur les vrais domaines (HTTPS).
- `ENCRYPTION_KEY` dédiée recommandée (chiffrement des jetons OAuth).
- Image web de production : `docker build --target runner --build-arg NEXT_PUBLIC_API_URL=https://api... apps/web`.

## Structure

```
apps/api/     # Backend FastAPI (+ tests/, alembic/)
apps/web/     # Dashboard Next.js
packages/shared/
docs/         # Phase 0, vertical, RGPD, bêta, audit
infra/docker/
```

## Phases implémentées

| Phase | Module API | Description |
|-------|------------|-------------|
| 0 | `docs/` | Étude marché, vertical compta |
| 1 | `observation` | Auth, Gmail/Outlook, classification, dashboard |
| 2 | `process_mining` | Découverte workflows |
| 3 | `suggestions` | Suggestions chiffrées, drafts workflows |
| 4 | `workflows` | Celery, exécution |
| 5 | `agents` | 4 agents métier |
| 6 | `predictive` | Scores + explications |
| — | `organization` | Export / effacement RGPD, journal d'audit |
| 12 | `docs/beta-readiness.md` | Checklist bêta |

## Vertical cible (Phase 0)

Cabinets comptables PME — voir [docs/vertical-choice.md](docs/vertical-choice.md).

## Auteur

**Donatien Byakombe**

## Licence

Tous droits réservés — usage interne / pilote. Contactez l'auteur pour toute utilisation ou distribution en dehors de ce cadre.
