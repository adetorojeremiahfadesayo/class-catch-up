# Class Catch-Up — Devpost submission copy

## Tagline

Teacher-reviewed catch-up work grounded in the exact lesson material a learner missed.

## Track

Good Neighbor Agents

## Inspiration

When a learner misses one lesson, the recovery work is deceptively expensive. A teacher must reconstruct what was actually covered, find the right pages, create an explanation and practice, check the result, deliver it, and respond when the learner gets stuck. Generic AI worksheets make this faster by giving up the part that matters: alignment with the real lesson and the teacher's judgment.

## What it does

Class Catch-Up turns a confirmed absence into a source-grounded catch-up packet. The teacher uploads class material once, confirms the topics and pages actually covered, and marks the learner absent. A bounded Strands workflow retrieves only approved source segments and prepares a cited four-step packet with three checks for understanding. Deterministic validators reject unsupported citations or malformed work. The packet remains a draft until the teacher reviews and approves the exact revision. The learner then receives it in a focused portal, can save progress, submit answers, and request help; the teacher sees that exception without having to monitor every step.

## How we built it

The client is React 19, TypeScript, and Vite. FastAPI owns authentication, tenant and class scope, materials, immutable packet revisions, learner assignments, and help requests. SQLAlchemy and Alembic support PostgreSQL, with SQLite used for the verified local demo. A durable polling worker claims idempotent jobs with leases and bounded retries. Strands Agents SDK exposes five server-scoped tools for reading the confirmed lesson, retrieving approved material, validating a packet, saving a draft, and flagging a content gap. Deterministic code owns authorization, citations, publication, and teacher approval.

## Challenges

The hardest part was preserving useful agent behavior without letting the model define its own evidence or authority. Uploaded text is treated as evidence rather than instructions. The model can propose content, but it cannot broaden source scope, publish work, or turn missing evidence into success. Provider failure is recorded as failure rather than replaced with fixture output.

## Accomplishments

- A coherent teacher-to-learner workflow with responsive teacher and student interfaces.
- Source and page selection, stable citation segments, immutable revisions, exact-hash approval, and scoped learner access.
- Durable, idempotent packet jobs with leases, retry bounds, and explicit failure states.
- Twenty-four backend tests plus frontend lint and production build checks passing locally.
- A real local Strands SDK custom-tool execution recorded over synthetic evidence.
- A live local Strands packet run through Amazon Bedrock Nova 2 Lite that used scoped tools, passed deterministic validation, and produced a teacher-review draft.
- A learner explanation page that presents the same approved packet as Watch, See, or Read while preserving source citations and shared progress.

## What we learned

An education agent should reduce coordination work while leaving educational judgment with the teacher. Clear provenance is part of the interface: fixture or teacher-edited packets must never look like live model output, and a working SDK tool call must not be overstated as a provider-driven run.

## What's next

Validate PostgreSQL concurrency under worker restarts, deploy the portal for judge access, and conduct a teacher usability study before making learning or time-saving claims.

## Honest demo note

The local demonstration uses synthetic school data and keeps fixture provenance explicit. The repository contains evidence of both a custom-tool-only Strands spike and one successful model-driven Strands packet run through Bedrock. Production deployment, real student data, PostgreSQL concurrency, and measured learning impact are not represented as complete.

## Submission checklist

- [x] Public repository URL: https://github.com/adetorojeremiahfadesayo/class-catch-up
- [x] MIT license in repository root
- [x] README and setup instructions
- [x] Architecture diagram: `docs/architecture.svg`
- [ ] Public demo video, maximum 5 minutes
- [ ] AWS Builder ID
- [ ] Devpost project submitted before the deadline
- [ ] Optional live demo URL
