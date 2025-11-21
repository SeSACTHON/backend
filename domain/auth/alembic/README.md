# Alembic Migrations

This directory contains database migration files managed by Alembic.

## Structure

- `env.py` - Alembic environment configuration
- `script.py.mako` - Template for new migration files
- `versions/` - Migration version files

## Usage

### Apply migrations (Docker)
Migrations are automatically applied when the container starts (see Dockerfile CMD).

### Create new migration (local development)
```bash
cd domain/auth
alembic revision --autogenerate -m "description of changes"
```

### Apply migrations manually (local)
```bash
cd domain/auth
alembic upgrade head
```

### Rollback migration
```bash
cd domain/auth
alembic downgrade -1  # Go back one version
```

### View migration history
```bash
cd domain/auth
alembic history
alembic current
```

## Migration Files

- `001_initial.py` - Initial schema: users and login_audits tables

