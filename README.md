# Catlity QMS

Multi-tenant SaaS platform for quality management and auditing, powered by specialized AI agents that understand industry-specific regulatory standards.

The MVP targets the quality industry (ISO 9001) with built-in extensibility for additional industries (aeronautica, food, etc.).


## Architecture

![General Architecture](docs/diagrams/architecture-general.png)

The platform is composed of:

- **Frontend**: React SPA with Ant Design, authentication via AWS Amplify/Cognito
- **Backend**: REST API built with FastAPI, targeted for ECS/Fargate
- **Database**: Amazon RDS PostgreSQL with multi-tenancy via `tenant_id`
- **Storage**: S3 for documentary evidence (Intelligent-Tiering), DynamoDB for evidence metadata
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
- **User** — Team member linked to a tenant (roles: admin, lead_auditor, auditor, auditee, qa_manager)
- **Audit** — Audit session with state machine (planned → in_progress → completed → closed). Each transition stores `status_changed_at`. See `docs/diagrams/audit-state-machine.png`.
- **Finding** — Non-conformity or observation (types: major_nc, minor_nc, observation, improvement_opportunity). Lifecycle: open → in_progress → resolved → verified → closed, with a rejection from resolved back to in_progress. Each transition stores `status_changed_at`. See `docs/diagrams/finding-lifecycle.png`.
- **CorrectiveAction** — Action plan linked to a finding. One finding can hold several actions. The client sets description, due date, completion date, and optional effectiveness.
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
- **Roles**: `admin`, `qa_manager`, `lead_auditor`, `auditor`, `auditee` — carried in the
  `custom:role` attribute and mirrored as Cognito groups.
- **Role enforcement**: routes declare `Depends(require_role([...]))`; access is
  granted when the user's role or group matches.

Relevant endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/register` | Provision a user in Cognito and persist the local profile |
| `GET`  | `/api/v1/auth/me` | Return the authenticated principal (tenant, role, groups) |
| `POST` | `/api/v1/audits/` | Create an audit for the token tenant. Roles: `auditor`, `admin`, `lead_auditor`. Status is always `planned`. A `qa_manager` cannot create |
| `GET`  | `/api/v1/audits/` | List that tenant's audits. Query: `skip`, `limit`, optional `status`, `audit_type`, and `mine` |
| `GET`  | `/api/v1/audits/{audit_id}` | Return one audit when it belongs to the token tenant |
| `PATCH` | `/api/v1/audits/{audit_id}` | Update title, description, audit type, or planned date. A `qa_manager` can only view |
| `PATCH` | `/api/v1/audits/{audit_id}/auditor` | Assign `auditor_id`. Role: `lead_auditor`. The user must be an active `auditor` of the same tenant |
| `PATCH` | `/api/v1/audits/{audit_id}/status` | Move one step forward: `planned` → `in_progress` → `completed` → `closed`. The assigned auditor, or a tenant `admin`, may move it. Invalid transitions return 422 and each change stores `status_changed_at` |
| `GET`  | `/api/v1/auditors/` | List active auditors of the token tenant. Roles: `lead_auditor`, `admin` |
| `POST` | `/api/v1/audits/{audit_id}/findings` | Create a finding on an audit of the token tenant. Roles: `auditor`, `admin`, `lead_auditor`. Status is always `open` and `assignee_id` stays empty. Types: `major_nc`, `minor_nc`, `observation`, `improvement_opportunity` |
| `GET`  | `/api/v1/audits/{audit_id}/findings` | List findings of that audit. Query: `skip`, `limit` |
| `GET`  | `/api/v1/findings` | List the tenant's findings. Query: `skip`, `limit`, optional `finding_type`, `audit_id`, and `status` |
| `PATCH` | `/api/v1/findings/{finding_id}` | Update title, description, type, severity, or clause reference. Status, assignee, and the parent audit stay unchanged. A `qa_manager` or `auditee` cannot edit |
| `PATCH` | `/api/v1/findings/{finding_id}/status` | Move one allowed step. The assigned auditee, or an admin, moves `open` → `in_progress` → `resolved`. An `auditor`, `lead_auditor`, or admin verifies (`resolved` → `verified`), rejects (`resolved` → `in_progress`), or closes (`verified` → `closed`). Invalid transitions return 422 and each change stores `status_changed_at` |
| `POST` | `/api/v1/findings/{finding_id}/corrective-actions` | Create an action on a finding of the token tenant. The assigned auditee, or an admin, may create it. Status stays `pending` and `responsible_id` stays empty |
| `GET`  | `/api/v1/findings/{finding_id}/corrective-actions` | List that finding's actions. Query: `skip`, `limit`. Any authenticated role of the tenant can read |
| `GET`  | `/api/v1/corrective-actions/{action_id}` | Return one action when it belongs to the token tenant |
| `PATCH` | `/api/v1/corrective-actions/{action_id}` | Update description, due date, completion date, or effectiveness. Status, action type, responsible, and the parent finding stay unchanged |
| `DELETE` | `/api/v1/corrective-actions/{action_id}` | Delete one action. The assigned auditee, or an admin, may delete it |

Audit rows stay in PostgreSQL. In local development that database is the Docker Compose Postgres service, not Amazon RDS. These routes do not call AWS on each request and do not add IAM permissions. They read `custom:tenant_id` and `custom:role` from the Cognito JWT the API already validates. There is no delete route and no `lead_auditor_id` column. The executing auditor is `auditor_id`, which already existed. The `lead_auditor` role is a new group in the existing Cognito module. Applying that group updates User Pool `us-east-1_oa6gNvB4B` only, with `terraform apply -target=module.cognito`. A Cognito group has no monthly charge. VPC, NAT Gateway, and RDS remain unapplied, so this change stays at **$0/month**. Check the API with `pytest tests/test_audits.py tests/test_audit_status.py tests/test_audit_assignment.py -v` from `backend/`. A passing run does not require `terraform apply`.

Finding rows use the `findings` table that already exists in that same schema. Create, list, and descriptive update add no AWS resource and no IAM permission, and they do not change User Pool `us-east-1_oa6gNvB4B`. These routes do not assign `assignee_id`. Check them with `pytest tests/test_findings.py -v` from `backend/`.

Status changes are a separate route. Migration `003` adds nullable `status_changed_at` on `findings`, the same kind of column audits already store. That migration is not applied to Amazon RDS. The route still reads `custom:tenant_id` and `custom:role` from the Cognito JWT the API already validates. VPC, NAT Gateway, and RDS stay unapplied, so findings stay at **$0/month**. The dev User Pool remains `us-east-1_oa6gNvB4B`. Check the lifecycle with `pytest tests/test_finding_status.py -v` from `backend/`. That run uses in-memory SQLite and does not need Docker or `terraform apply`. See `docs/diagrams/finding-lifecycle.png`.

Corrective actions use the `corrective_actions` table that already points at `findings`. Migration `004` adds nullable `effectiveness` (`String(255)`) and is not applied to Amazon RDS. The routes add no AWS resource and no IAM permission. A finding can hold several actions. The assigned auditee, or an admin, creates, edits, and deletes them. Any authenticated role of the tenant can read them. VPC, NAT Gateway, and RDS stay unapplied, so this stays at **$0/month**. The dev User Pool remains `us-east-1_oa6gNvB4B`. Check it with `pytest tests/test_corrective_actions.py -v` from `backend/`. That run uses in-memory SQLite and does not need Docker or `terraform apply`.

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

The Audits screen calls the local API (`/api/v1/audits` and `/api/v1/auditors`)
with the Cognito ID token. It adds no AWS resource and no IAM permission.
Estimated cost stays **$0/month**. RDS and NAT remain unapplied. The dev User
Pool is `us-east-1_oa6gNvB4B`.

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

Evidence storage is `module.evidence`. It was applied with `terraform apply -target=module.evidence`. The dev names are the S3 bucket `catlity-qms-dev-evidence` and the DynamoDB table `catlity-qms-dev-evidence`. The bucket uses SSE-S3, versioning, and a lifecycle rule that moves objects to Intelligent-Tiering on day 0. Noncurrent versions expire after 90 days. Objects under 128 KB stay in the Frequent Access tier and do not pay the monitoring fee. The table is on-demand, with partition key `tenant_id` and sort key `evidence_id`, encrypted with the AWS owned key. Point-in-time recovery is off. Public access is blocked, and the bucket policy denies HTTP plus any principal other than the reserved role `catlity-qms-dev-backend-task`, the principal running Terraform, and the account root. That role is not created yet. An empty bucket and an idle on-demand table are **$0/month**. In `us-east-1`, later usage is about $0.023 per GB-month in the Frequent Access tier, $0.0125 in Infrequent Access, $0.004 in Archive Instant Access, and $0.0025 per 1,000 monitored objects. DynamoDB on-demand is about $1.25 per million writes, $0.25 per million reads, and $0.25 per GB-month. One gigabyte of evidence and a few thousand metadata items stay under $0.10/month, inside the $50 dev budget. The bucket and the table now exist in `us-east-1`. A full `terraform apply` would also create the NAT Gateway and RDS. The identity that runs Terraform needs `s3:CreateBucket`, the evidence bucket `PutBucket*` calls, `dynamodb:CreateTable`, `DescribeTable`, and `TagResource`. The diagram source is `docs/diagrams/evidence-storage-architecture.drawio`.

VPC, NAT Gateway, and RDS are in the Terraform configuration and were not applied with this change. A NAT Gateway is about $33/month and a `db.t3.micro` instance about $13/month before storage. The apply was limited to `terraform apply -target=module.cognito` to avoid that fixed cost.

## License

Proprietary — Phil Dev <sub><img src="docs/assets/logo-phildev.png" width="20"></sub>
