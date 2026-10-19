# Catlity QMS

Multi-tenant SaaS platform for quality management and auditing, powered by specialized AI agents that understand industry-specific regulatory standards.

The MVP targets the quality industry (ISO 9001) with built-in extensibility for additional industries (aeronautica, food, etc.).


## Architecture

![General Architecture](docs/diagrams/architecture-general.png)

The platform is composed of:

- **Frontend**: React SPA with Ant Design, authentication via AWS Amplify/Cognito
- **Backend**: REST API built with FastAPI, targeted for ECS/Fargate
- **Database**: Amazon RDS PostgreSQL with multi-tenancy via `tenant_id`
- **Storage**: S3 for documentary evidence, DynamoDB for metadata
- **AI Agents**: 3 specialized agents on Amazon Bedrock with Knowledge Bases
  - Normative Agent (ISO/IATF/GMP regulatory queries)
  - Report Agent (audit report draft generation)
  - Onboarding Agent (new tenant configuration)
- **Dashboard**: Amazon QuickSight embedded with row-level security
- **IaC**: Terraform with mandatory tagging (`Project: catlity-qms`)

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript + AWS Amplify + Ant Design |
| Backend API | FastAPI (Python); ECS/Fargate is the target runtime |
| Database | Amazon RDS PostgreSQL |
| Documents/Evidence | Amazon S3 |
| Metadata | Amazon DynamoDB |
| Authentication | Amazon Cognito |
| AI Agents | Amazon Bedrock + Knowledge Bases |
| Dashboard | Amazon QuickSight |
| IaC | Terraform |
| CI/CD | GitHub Actions (no workflow committed yet) |
| Cost Monitoring | AWS Cost Explorer. AWS Budgets is defined and not applied |

## Repository Structure

```
catlity-qms/
├── frontend/                 # React + TypeScript + Ant Design
├── backend/                  # FastAPI (Python)
│   ├── app/
│   │   ├── main.py          # FastAPI application entry point
│   │   ├── core/            # Config, database, security
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── api/v1/          # API route handlers
│   │   └── services/        # Business logic layer
│   ├── alembic/             # Database migrations
│   ├── tests/               # pytest test suite
│   ├── Dockerfile
│   ├── docker-compose.yml   # Local dev (PostgreSQL + API)
│   ├── requirements.txt
│   └── requirements-dev.txt
├── infra/                    # Terraform modules
├── docs/
│   ├── PLAN.md              # Full implementation plan
│   └── diagrams/            # Architecture diagrams (PNG)
├── knowledge-base/
│   ├── common/              # ISO 9001
│   ├── automotive/          # IATF 16949
│   └── pharmaceutical/      # GMP
├── .github/workflows/       # reserved for CI workflows
├── .gitignore
└── README.md
```

## Local Development Setup

### Prerequisites

- Python 3.12+
- Node.js 22.13+
- Docker and Docker Compose
- Terraform 1.6+
- AWS CLI configured with a valid profile

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Start local PostgreSQL
docker-compose up -d db

# Run migrations
alembic upgrade head

# Start API server (http://localhost:8000)
uvicorn app.main:app --reload

# Run tests
pytest tests/ -v

# Lint
ruff check .
```

Alternatively, run everything with Docker Compose:

```bash
cd backend
docker-compose up
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

#### Data Model

The backend uses a multi-tenant architecture with `tenant_id` on all tables:

- **Tenant** — Organization using the platform
- **User** — Team member linked to a tenant (roles: admin, auditor, auditee, qa_manager)
- **Audit** — Audit session with state machine (planned → in_progress → completed → closed)
- **Finding** — Non-conformity or observation (types: major_nc, minor_nc, observation, improvement_opportunity)
- **CorrectiveAction** — Action plan for a finding
- **Checklist / ChecklistItem** — Audit template questions
- **Evidence** — Documents/photos uploaded to S3

See `docs/diagrams/data-model-erd.png` for the full ER diagram.

#### Authentication & Authorization

Authentication is handled by an Amazon Cognito User Pool. The frontend signs in
through Amplify and sends the resulting JWT as a `Bearer` token on every API
request. The backend validates each token against the pool's JWKS (signature,
issuer, and audience) and derives the caller's identity from Cognito claims.

- **Tenant isolation**: the `custom:tenant_id` claim is required on every token
  and scopes all data access.
- **Roles**: `admin`, `qa_manager`, `auditor`, `auditee` — carried in the
  `custom:role` attribute and mirrored as Cognito groups.
- **Role enforcement**: routes declare `Depends(require_role([...]))`; access is
  granted when the user's role or group matches.

Relevant endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/register` | Provision a user in Cognito and persist the local profile |
| `GET`  | `/api/v1/auth/me` | Return the authenticated principal (tenant, role, groups) |
| `POST` | `/api/v1/audits/` | Create an audit for the token tenant. Roles: `auditor`, `admin`, `qa_manager`. Status is always `planned` |
| `GET`  | `/api/v1/audits/` | List that tenant's audits. Query: `skip`, `limit`, optional `status` and `audit_type` |
| `GET`  | `/api/v1/audits/{audit_id}` | Return one audit when it belongs to the token tenant |
| `PATCH` | `/api/v1/audits/{audit_id}` | Update title, description, audit type, or planned date |

Audit rows stay in PostgreSQL. In local development that database is the Docker Compose Postgres service, not Amazon RDS. These four routes do not call AWS and do not add IAM permissions. They read `custom:tenant_id` from the Cognito JWT the API already validates. There is no delete route. Status changes and auditor assignment are separate API work. This change adds **$0/month**: the User Pool and the Terraform state bucket stay as they are, and VPC, NAT Gateway, and RDS remain unapplied. Check it with `pytest tests/test_audits.py -v` from `backend/`. A passing run does not require `terraform plan` or `terraform apply`.

Required environment variables (see `backend/.env.example`):

```
AWS_REGION=us-east-1
COGNITO_USER_POOL_ID=<pool id from terraform output>
COGNITO_APP_CLIENT_ID=<app client id from terraform output>
```

The Cognito User Pool, groups, and app client are provisioned by the
`infra/modules/cognito` Terraform module. See `docs/diagrams/auth-flow.png`
for the end-to-end sign-in and token validation flow.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # then fill in the Cognito values

# Start dev server (http://localhost:5173)
npm run dev

# Unit tests (Vitest + React Testing Library)
npm test

# Lint and formatting
npm run lint
npm run format:check   # npm run format to fix

# Production build (type-check + bundle into dist/)
npm run build
```

The frontend uses React 19 + TypeScript + Vite with Ant Design as the UI library.
Dependency versions are pinned exactly (`frontend/.npmrc` sets `save-exact=true`).

Environment variables (`frontend/.env.local`, not committed):

| Variable | Source |
|----------|--------|
| `VITE_COGNITO_USER_POOL_ID` | `terraform output -raw cognito_user_pool_id` |
| `VITE_COGNITO_APP_CLIENT_ID` | `terraform output -raw cognito_app_client_id` |
| `VITE_API_BASE_URL` | Backend URL, `http://localhost:8000` by default |

Sign-in uses AWS Amplify against the Cognito User Pool. Tokens are kept in
memory rather than `localStorage` to limit XSS exposure, so a full page reload
ends the session. Registration goes through `POST /api/v1/auth/register` so the
tenant and role are assigned server-side. Without the Cognito variables the app
still runs and shows a configuration warning on the sign-in screen.

### Infrastructure

```bash
cd infra
terraform init
terraform plan
terraform apply
```

## Cost Monitoring

All AWS resources are tagged with `Project: catlity-qms` for filtering in Cost Explorer. The dev budget is $50/month, with alerts at 50%, 80%, and 100%. That budget module is defined in Terraform and has not been applied.

The Cognito deploy is estimated at **$0/month** in `us-east-1`. It applies only `module.cognito`. New user pools use the Essentials tier, which includes 10,000 monthly active users at no charge. The Terraform state bucket (`catlity-qms-terraform-state`) is versioned and encrypted with SSE-S3; at a few kilobytes it stays under $0.01/month. State locking uses an S3 lock file (`use_lockfile`) instead of a DynamoDB table.

VPC, NAT Gateway, and RDS are in the Terraform configuration and were not applied with this change. A NAT Gateway is about $33/month and a `db.t3.micro` instance about $13/month before storage. The apply was limited to `terraform apply -target=module.cognito` to avoid that fixed cost.

## License

Proprietary — Phil Dev <sub><img src="docs/assets/logo-phildev.png" width="20"></sub>
