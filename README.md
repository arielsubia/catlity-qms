# Catlity QMS

Plataforma SaaS multi-tenant para gestión de calidad y auditorías, asistida por agentes de IA especializados que conocen las normativas específicas de cada industria.

El MVP está orientado a la industria automotriz (IATF 16949) con capacidad de extensión a otras industrias (farmacéutica, alimentaria, etc.).

A Phil Dev project.

## Arquitectura

![Arquitectura General](docs/diagrams/exports/architecture-general.png)

La plataforma se compone de:

- **Frontend**: SPA React con Ant Design, autenticación vía AWS Amplify/Cognito
- **Backend**: API REST con FastAPI desplegada en ECS/Fargate
- **Base de datos**: Amazon RDS PostgreSQL con multi-tenancy por `tenant_id`
- **Almacenamiento**: S3 para evidencia documental, DynamoDB para metadatos
- **Agentes IA**: 3 agentes especializados en Amazon Bedrock con Knowledge Bases
  - Agente Normativo (consultas ISO/IATF/GMP)
  - Agente de Informes (generación de borradores de auditoría)
  - Agente de Onboarding (configuración de nuevos tenants)
- **Dashboard**: Amazon QuickSight embebido con row-level security
- **IaC**: Terraform con tagging obligatorio (`Project: catlity-qms`)

## Stack Tecnológico

| Capa | Tecnología |
|------|------------|
| Frontend | React + TypeScript + AWS Amplify + Ant Design |
| Backend API | FastAPI (Python) en ECS/Fargate |
| Base de datos | Amazon RDS PostgreSQL |
| Documentos/evidencia | Amazon S3 |
| Metadatos | Amazon DynamoDB |
| Autenticación | Amazon Cognito |
| Agentes IA | Amazon Bedrock + Knowledge Bases |
| Dashboard | Amazon QuickSight |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Diagramas | draw.io (.drawio) |
| Monitoreo costos | AWS Cost Explorer + AWS Budgets |

## Estructura del Repositorio

```
catlity-qms/
├── frontend/                 # React + TypeScript + Ant Design
├── backend/                  # FastAPI (Python)
├── infra/                    # Terraform modules
├── docs/
│   ├── PLAN.md              # Plan de implementación completo
│   └── diagrams/            # Archivos .drawio
│       └── exports/         # PNGs exportados
├── knowledge-base/
│   ├── common/              # ISO 9001
│   ├── automotive/          # IATF 16949
│   └── pharmaceutical/      # GMP
├── .github/workflows/       # CI/CD pipelines
├── .gitignore
└── README.md
```

## Local Development Setup

### Prerrequisitos

- Python 3.12+
- Node.js 20+
- Docker y Docker Compose
- Terraform 1.6+
- AWS CLI configurado con perfil válido

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
docker-compose up -d  # PostgreSQL local
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Infraestructura

```bash
cd infra/environments/dev
terraform init
terraform plan
terraform apply
```

## Diagramas

Los diagramas de arquitectura están en `docs/diagrams/` en formato `.drawio` (editables con [draw.io](https://app.diagrams.net/)). Cada módulo tiene su propio diagrama documentando la arquitectura, modelo de datos o flujos de usuario.

## Monitoreo de Costos

Todos los recursos AWS están etiquetados con `Project: catlity-qms` para filtrar en Cost Explorer. Se configuran alertas de AWS Budgets al 50%, 80% y 100% del presupuesto mensual.

## Licencia

Propietario — Phil Dev.
