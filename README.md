# Infrastructure Stack

Docker Compose stack for running the full PISA manager service: PostgreSQL, PostgREST, Swagger UI, nginx reverse proxy, and the manager API.

The `manager/` directory is a git submodule pointing to the [manager repo](https://github.com/PISA-Hut/manager).

## Setup

```bash
git clone --recurse-submodules <this-repo-url>
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

- `/manager/` → Rust manager API (port 9000)
- `/postgrest/` → PostgREST auto-REST API (port 3000)
- `/swagger/` → Swagger UI

## Environment Variables

| Variable | Description |
|---|---|
| `DB_USER` | PostgreSQL user |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_NAME` | PostgreSQL database name |
| `AUTHENTICATOR_PASSWORD` | PostgREST role password |
| `SERVER_NAME` | External hostname for API proxy URL |
