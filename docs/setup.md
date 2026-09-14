# Setup

## Prerequisites

- Python 3.13 managed by `uv`
- PostgreSQL 17 (the supplied Compose file is the reference local setup)
- Node.js 24 LTS or Bun 1.4+
- Optional for live generation: AWS credentials with Bedrock invocation access, an account-available model ID, and its region

## Configure

Copy `.env.example` to `.env`.

For local Compose, make `DATABASE_URL` use the same password configured in `infra/compose.yaml`. Do not reuse the checked-in local-only Compose password outside local development.

For a real model-driven run, set:

```text
AWS_REGION=<enabled-region>
BEDROCK_MODEL_ID=<model-id-confirmed-in-that-account>
```

Use the normal boto3 credential chain (environment, shared profile, `aws login`, or workload role). Do not put credentials in `.env.example` or source control.

## Start

```powershell
docker compose -f infra\compose.yaml up -d postgres
uv sync --directory services\api
uv run --directory services\api python -m alembic upgrade head

$env:DEMO_TEACHER_PASSWORD = "<choose-local-password>"
$env:DEMO_STUDENT_PASSWORD = "<choose-local-password>"
uv run --directory services\api python scripts\generate_fraction_fixture.py
uv run --directory services\api python -m app.seed

uv run --directory services\api uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
uv run --directory services\api python -m app.worker
```

In a third terminal:

```powershell
cd apps\web
bun install
bun run dev
```

Open `http://127.0.0.1:5173`.

The seed creates usernames `teacher.demo` and `<first-name>.demo` for Ada, Bola, Chidi, Dami, Eniola, and Femi. Passwords are the values supplied to the seed command and are never embedded in the web build.

## Verify

```powershell
uv run --directory services\api python -m pytest -q
uv run --directory services\api python -m compileall -q app migrations spikes
cd apps\web
bun run lint
bun run build
```

To verify migrations independently, point `DATABASE_URL` at a clean database and run `python -m alembic upgrade head` through `uv`.

## Live Strands check

`spikes/strands_tool_spike.py` proves the local Strands custom-tool path and writes `artifacts/runtime-spike/strands-tool-call.json`. The separate `artifacts/runtime-spike/bedrock-strands-packet-run.json` records one successful local model-driven packet job.

Start the worker only after `AWS_REGION` and `BEDROCK_MODEL_ID` are set and credentials have been verified. Without them, the worker records `provider_not_configured`, moves the job to visible retry state, and creates no packet.
