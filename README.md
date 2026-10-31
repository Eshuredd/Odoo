# SubCadence

A subscription management and recurring billing platform for the Odoo × Make-A-Ton hackathon. The planned workflow connects catalog configuration, quotations, subscription activation, recurring invoices, partial payments, reports, and customer self-service.

**Stage 1 is complete in scope:** backend configuration, SQLite foundation, two typed models, Alembic migrations, and a database-aware health endpoint. Authentication begins in Stage 2. Business APIs and the frontend are deferred.

## Architecture and stack

FastAPI routes delegate persistence to request-scoped SQLAlchemy 2.x sessions. Configuration uses Pydantic v2 and pydantic-settings. SQLite uses WAL, foreign-key enforcement, a 5-second busy timeout, and explicit transactions. Alembic owns schema changes. pytest/httpx tests use temporary databases. Python 3.11+ is required; Python 3.12 is used for local verification. No Docker, database server, paid APIs, or application-runtime internet access is required.

The repository root is the `subcadence/` project root from the brief, even if the local checkout directory has a different name.

```text
.
├── backend/
│   ├── app/
│   │   ├── api/v1/         # Versioned router and health endpoint
│   │   ├── core/           # Environment settings
│   │   ├── db/             # Metadata, UTC type, engine and sessions
│   │   ├── models/         # User, UserRole and AuditLog
│   │   ├── schemas/        # Package reserved for later request/response schemas
│   │   ├── services/       # Package reserved for later business services
│   │   ├── static/swagger-ui/ # Vendored offline API docs assets and licenses
│   │   └── main.py         # App factory, lifespan, server entry point
│   ├── alembic/versions/   # Initial migration
│   ├── tests/             # Health, configuration and real SQLite tests
│   ├── scripts/           # Reserved; no seed or billing scripts yet
│   ├── data/              # Ignored local database; tracked .gitkeep only
│   ├── alembic.ini
│   └── pyproject.toml
├── docs/
│   ├── REQUIREMENTS.md
│   ├── DECISIONS.md
│   └── API_CONTRACT.md
├── .env.example
└── .gitignore
```

## Local setup

Run these commands from `backend/`. Dependencies require internet or a local package cache during installation. The editable install is the supported development setup, because configuration/data/migrations live beside the source tree.

Windows PowerShell:

```powershell
cd backend
py -3.12 -m venv ..\.venv
..\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
Copy-Item ..\.env.example ..\.env
python -m alembic upgrade head
subcadence-api
```

If PowerShell policy prevents activation, invoke the virtual environment directly without changing policy: `..\.venv\Scripts\python.exe -m pip install -e ".[test]"`, `..\.venv\Scripts\python.exe -m alembic upgrade head`, and `..\.venv\Scripts\subcadence-api.exe`.

Linux/macOS:

```bash
cd backend
python3 -m venv ../.venv
source ../.venv/bin/activate
python -m pip install -e '.[test]'
cp ../.env.example ../.env
python -m alembic upgrade head
subcadence-api
```

Use any available Python 3.11+ interpreter when `py -3.12` is unavailable. Do not overwrite an existing local `.env` when repeating setup.

## Configuration

Settings load `.env` from the repository root regardless of working directory; environment variables take precedence. Never commit `.env`. [.env.example](.env.example) includes all Stage 1 and reserved Stage 2 settings:

| Setting | Local default / meaning |
| --- | --- |
| `DATABASE_URL` | `sqlite:///data/subcadence.db`; relative paths resolve from `backend/` |
| `API_HOST`, `API_PORT` | `127.0.0.1`, `8000`; used by `subcadence-api` |
| `CORS_ORIGINS` | JSON array, default `["http://localhost:3000"]`; explicit HTTP(S) origins, no trailing slash or wildcards |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Empty; reserved for Stage 2 seeding, no account created now |
| `AUTH_SECRET_KEY` | Empty; no default secret; Stage 2 must require a locally generated secret before auth |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` | Optional reserved settings; port 587; no email sent in Stage 1 |

Standard SQLite and `sqlite+pysqlite` URLs are supported; URI/query-string modes and external databases are deliberately excluded. Parent directories are created as needed. WAL/SHM companion files are expected and ignored by Git. WAL improves reader/writer coexistence; writes still serialize.

## Run, migrate, and test

With the environment activated, from `backend/`:

```bash
# Apply schema before using application tables.
python -m alembic upgrade head
python -m alembic current

# Start with API_HOST and API_PORT from settings.
subcadence-api

# Or run a development server with explicit host/port and reload.
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Run isolated tests; never migrates the developer's application database.
python -m pytest
python -m compileall -q app alembic tests

# Check metadata matches the migrated database.
python -m alembic check

# After adding future models: import them in app/models/__init__.py,
# generate a revision, review it, then apply it.
python -m alembic revision --autogenerate -m "describe schema change"
python -m alembic upgrade head
```

`uvicorn` command-line flags control its binding; it does not consume our `API_HOST`/`API_PORT` settings automatically. The `subcadence-api` entry point does.

Health: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health). Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Documentation assets are bundled locally, so `/docs` also works offline. The health endpoint executes `SELECT 1`, returning `{"status":"ok","service":"subcadence-api"}` or a sanitized HTTP 503 for database access failure. It checks connectivity, not schema readiness. The app never calls `metadata.create_all()` or runs migrations at startup.

## Models and transaction behavior

`User` stores an auto-incrementing ID, required case-insensitively unique email (`NOCASE`, ASCII case folding), required password hash, checked admin/staff/customer role, active flag defaulting to true, and UTC created/updated timestamps. Stage 1 has no password input, hashing, login, or seed flow. `updated_at` is maintained for ORM updates; future raw SQL writers must maintain it explicitly.

`AuditLog` stores an auto-incrementing ID, nullable actor reference, required action/entity/entity ID, UTC timestamp, and JSON detail. Actor deletion sets the reference to NULL while preserving the event. Structured audit services arrive later. Replace JSON detail values when updating; nested in-place mutations are not tracked.

Each request receives a fresh session. Services will explicitly use `with session.begin():` to commit or roll back writes; closing a session rolls back pending work. SQLAlchemy emits an explicit BEGIN so transactional DDL and rollback behavior are predictable. Future callers may request an immediate write transaction before any query:

```python
with engine.connect().execution_options(sqlite_begin_mode="IMMEDIATE") as connection:
    with connection.begin():
        # Future transactional writes go here.
        ...
```

This is transaction support only; no billing engine is implemented.

## Planned stages and contract

Stage 2 adds authentication, password handling with argon2-cffi, and role/ownership enforcement. Later stages add catalog/plans, quotations, subscription lifecycle, idempotent recurring billing and discounts, invoices/payments/overdue tracking, reports, and customer access. Detailed sequencing after Stage 2 is to be supplied. Future demo/seed data is **synthetic**. No real credentials or personal data belong in the repository.

The frontend will use Next.js, TypeScript, and Tailwind, integrating exported Google Stitch designs. It will be implemented later; no frontend files are generated now.

See [requirements](docs/REQUIREMENTS.md), [decisions and unresolved rules](docs/DECISIONS.md), and the [planned API contract](docs/API_CONTRACT.md). Financial rules mandate INR integer paise, basis-point rates, half-up rounding, half-open billing periods, pricing snapshots, no proration, idempotency, no skipped periods, zero-write dry runs, and one transaction per subscription. Pause/expiration semantics and other detailed business rules remain explicitly unresolved.
