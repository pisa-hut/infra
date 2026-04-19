# Infrastructure Stack

Docker Compose stack for the full PISA service: PostgreSQL, PostgREST, Swagger UI, nginx reverse proxy, manager API, and frontend.

Git submodules:
- `manager/` → [manager repo](https://github.com/pisa-hut/manager)
- `frontend/` → [frontend repo](https://github.com/pisa-hut/frontend)

## Setup

```bash
git clone --recurse-submodules https://github.com/pisa-hut/infra.git
# or if already cloned:
git submodule update --init
```

## Usage

```bash
cp .env.example .env
# Edit .env with your values
docker compose up --build
```

## Services

All services are exposed via nginx on port **7777**:

| Path | Service | Description |
|---|---|---|
| `/` | Frontend | React web UI |
| `/manager/` | Manager API | Business logic (task claiming, lifecycle, upload) |
| `/postgrest/` | PostgREST | Auto-generated CRUD API from PostgreSQL schema |
| `/swagger/` | Swagger UI | API documentation |

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DB_USER` | PostgreSQL user | |
| `DB_PASSWORD` | PostgreSQL password | |
| `DB_NAME` | PostgreSQL database name | |
| `AUTHENTICATOR_PASSWORD` | PostgREST role password | |
| `SERVER_NAME` | External hostname for API proxy URL | |
| `LISTEN_ADDR` | Bind address (`0.0.0.0` for public) | `127.0.0.1` |
| `PISA_DATA_DIR` | Host path for scenario file storage | `/opt/pisa` |
