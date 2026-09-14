# Implementation plan: absence-to-catch-up agent

Version: 1.0 | Prepared: 2026-09-12 | Status: implementation-ready plan; no application built.
Working name: Class Catch-Up (placeholder, not a settled brand).
Target track: Agents for Humans / Professional Agents.

## 1. Instructions to the implementing agent

Read this entire plan before editing. Inspect the chosen repository, its AGENTS.md and existing stack. Preserve user work. Create a fresh project only when implementation is authorized; this document itself authorizes no deployment, registration, paid infrastructure or messaging to real users. Use an existing stack where compatible; otherwise use the defaults below. Do not spawn additional agents unless authorized.

Execute phases in order. Maintain IMPLEMENTATION_STATUS.md with phase, completed evidence, unresolved issues and next action. Finish each vertical slice before adding scope. Use synthetic student records and teacher-owned sample materials. Never label a mock, cached fixture or failed provider call as a live success. Make reasonable reversible implementation choices without repeatedly asking; report blockers requiring credentials, budget or product decisions precisely.

Product promise: A teacher uploads materials and a teaching schedule once. After confirming what was taught and marking a student absent, an agent prepares a source-linked catch-up path. The teacher approves it; the student receives it in a portal, completes the work and checks understanding; only unresolved needs appear on the teacher dashboard.

## 2. Demo story before implementation

One teacher, one class, six fictional learners, three lessons on fractions.
1. Teacher opens Today: correct class, local date and period; proposed topic and page links appear.
2. Teacher selects Partly covered, removes fraction addition, retains equivalent fractions, and marks Ada absent. Save once.
3. A real Strands run reads confirmed lesson scope and relevant material segments, prepares a draft and records tool activity.
4. Teacher reviews the explanation, cited reading, worked example and three questions; approves the exact packet revision.
5. Ada's portal now shows the assigned packet. A source link opens the relevant PDF page. Ada answers questions and requests help on one step.
6. Teacher dashboard shows submitted work and one help request. Replaying the attendance save creates no duplicate assignment.

Target demonstration: 90 seconds excluding generation wait, transparently edited if needed. Show a real run separately from seeded demo data. Do not claim improved learning or reduced teacher workload without observation.

## 3. Scope and priorities

P0 required:
- Teacher and student roles with server-side class/assignment authorization.
- Text-based PDF and plain-text material upload; syllabus/topic list paste; weekly timetable form or CSV import.
- Agent-proposed lesson/material mapping, reviewed by teacher; bulk approval and clear unmatched-topic flags.
- One daily lesson/attendance screen: Covered / Partly covered / Moved / Not yet confirmed.
- Exact lesson occurrence lookup by class + local date + period; confirmed actual scope overrides plan.
- Durable absence job, real Strands generation, source-linked packet, teacher review and revision-bound approval.
- Portal delivery, student step progress, three teacher-reviewed multiple-choice questions, help request.
- Teacher exception dashboard and evidence trail.

P1 only after P0 works: grounded student questions, print view, editable topic extraction from timetable PDF, teacher-timed reminders inside the portal.
P2 defer: live classroom recording, WhatsApp/email/SMS, OCR/scanned books, PPTX/DOCX ingestion (ask user to export PDF), full LMS integration, automated grades, parent accounts, voice, multilingual generation, adaptive curriculum, automatic packet release, AgentCore migration.
A teacher can upload an entire text PDF within limits, but only confirmed relevant segments enter generation. Do not promise arbitrary file support.

## 4. Architecture decisions

Default: React + TypeScript + Vite frontend; Python FastAPI backend; Strands Python SDK; PostgreSQL; S3-compatible private material storage. Local development: Docker Compose PostgreSQL and local private filesystem behind the same storage interface. One backend worker polls a durable jobs table; no Redis/Celery required for MVP. Use database full-text retrieval plus confirmed segment IDs; no vector database needed initially.

Use Amazon Bedrock through Strands if account/model access is available; read model ID/region from environment and verify with a tiny real call. Do not hardcode an assumed available model or SDK version. Pin the versions actually tested in lock files. Verify SDK invocation, structured output and timeout APIs against current docs before coding.

The Strands SDK is an in-process library; the app owns its scheduler, database and durable workflow. Use custom scoped tools; do not enable shell, Python execution, arbitrary browsing or automatically discovered tools.

Suggested layout:
apps/web/src/{teacher,student,shared}
services/api/app/{routes,auth,models,schemas,materials,lessons,attendance,packets,jobs,agents}
services/api/tests/{unit,integration,e2e_fixtures}
infra/compose.yaml
docs/{architecture,setup,demo,evaluation,limitations}.md

Auth: server-managed sessions using an established library, secure HttpOnly cookies and password hashing; CSRF protection for writes. Provision demo accounts from local environment/seed command, never embed usable credentials in frontend assets or public source. No self-selected teacher role. Student access is limited to their assignments and cited excerpts; teachers to their classes. A class-scoped teacher login is sufficient; no admin panel needed.

## 5. Data contract

Every owned record has tenant_id, opaque id and created_at; scope is enforced in service queries, not supplied by the model. Store timestamps in UTC and class timezone separately (default Africa/Lagos).

| Entity | Required fields and constraints |
|---|---|
| User / Enrollment | role, class_id, student_id; unique enrollment |
| Class | owner_teacher_id, name, subject, timezone |
| Material | class_id, filename, content_hash, storage_key, version, extraction_status; 20 MB/file initial limit |
| Segment | material_version_id, page_1_based or text section, text, content_hash; stable IDs per version |
| Topic | class_id, title, teacher-approved objectives |
| TimetableSlot | class_id, weekday, start/end local time, effective dates |
| LessonOccurrence | class_id, local_date, period_key, planned_topic_ids, actual_topic_ids, segment_ids, coverage_status, revision; unique class/date/period |
| Attendance | lesson_id, student_id, status present/absent/unknown, revision; unique lesson/student |
| PacketJob | lesson_id, lesson_revision, state, attempts, lease_until, error_code, idempotency_key |
| PacketRevision | lesson_id/revision, material_version_ids, payload, validation_results, status, reviewer_id, approved_hash, generation_run_id |
| Assignment | student_id, lesson_id, packet_revision_id, state, delivered_at, superseded_at; one active assignment per student/lesson |
| Progress / Attempt | assignment_id, step_id, event/status, answer, correctness; no answer key in student GET payload |
| Exception | scope/student/lesson, reason, severity, open/resolved, source_event_id |
| AgentRun / AuditEvent | actor, scoped IDs, tools, timestamps, model config, outcome; exclude credentials and unnecessary student data |

Generate one shared draft per confirmed lesson revision, then assign it to absent students. Do not make identical model calls per learner. Student-specific progress is separate.

Packet schema: title; objectives; ordered steps [read, explain, worked_example, practice]; each content block has citations [{segment_id, page_or_section, supporting_excerpt}]; estimated_minutes marked estimate; three MCQs with stable IDs, options, server-only answer_key, rationale and citations. Practice is formative; no school grade is calculated. Teacher can edit draft and questions; every edit produces a new revision requiring approval.

## 6. Mapping and daily teacher flow

Onboarding:
1. Create class and roster (CSV or manual); paste topic sequence; enter recurring timetable.
2. Upload materials. Validate MIME/file size, extract text by page in a bounded worker, preserve pages. A textless/scanned document becomes needs_text, with an explanation and option to paste text.
3. Agent proposes topic-to-segment mappings using actual extracted IDs. Unknown dates/objectives remain unassigned; never invent them.
4. Teacher sees a review table with topic, dates, suggested pages and source previews; accepts or changes mappings. Timetable provides proposed occurrence dates, not proof of teaching.

Daily screen:
- Class selector, local date, period selector, topic card, coverage controls and roster together.
- Covered confirms listed topics and source segments.
- Partly covered requires selecting covered objectives/segments or editing a proposed mapping. Free-text note may suggest changes but teacher confirms them.
- Moved asks for destination date/period; current occurrence has no taught content. Do not overwrite attendance on an existing destination occurrence.
- Save atomically persists confirmed coverage, attendance and job intent. If coverage is unconfirmed, absences persist but generation is blocked with a visible reason.
- Multiple periods on one date are separate occurrences. Holidays or no occurrence require teacher selection; the agent cannot infer a lesson from calendar date alone.

Usability target: daily extra interaction under 30 seconds for a preconfigured class; measure with a teacher, do not report it as achieved from automated tests.

## 7. State transitions and invariants

Material: uploaded -> extracting -> ready | needs_text | failed.
Job: queued -> running (lease) -> succeeded | retry_wait | failed | cancelled.
Packet: draft -> needs_review -> approved -> published; revisions can be superseded. Invalid output becomes needs_revision and cannot publish.
Assignment: assigned -> opened -> in_progress -> submitted; teacher separately marks reviewed. Help requested is an independent flag; correct quiz answers are not proof of mastery.

- Job key is lesson_id + confirmed revision + packet schema version. Transactionally insert with a unique key.
- Teacher approval checks exact current revision/hash and material versions. Publish rejects stale approval.
- Publication writes assignments and audit events in one transaction and rechecks current absence and enrollment. Delivered means available in the student's portal; it does not mean read or emailed.
- Changing absence to present before publication prevents assignment. After publication, withdraw it with an audit trail; preserve prior progress.
- Scope/material edits invalidate unapproved drafts. Approved/published packets are immutable; create a reviewed replacement, mark the old assignment superseded, preserve attempts and alert affected learners. Never silently replace completed work.
- Worker claims with row locking/lease; crashed leases can be retried. Three bounded attempts with backoff; no duplicated side effects. Bound provider request duration and total job duration. Expose manual retry without changing failed runs to success.
- Material deletion used by active packets is blocked until dependencies are withdrawn or an explicit retention policy is implemented.

## 8. Strands responsibilities and tool boundaries

One bounded agent per job, constructed with server-bound class and lesson context. Tools:
- read_confirmed_lesson(): returns actual approved scope and allowed segment IDs.
- retrieve_material_segments(query, segment_ids): retrieves only allowed class/material versions; output has source IDs/pages.
- validate_packet(candidate): validates schema, citation existence, scope IDs, question structure and source membership.
- save_packet_draft(candidate, expected_lesson_revision): creates draft only, using compare-and-swap revision check.
- flag_content_gap(reason, relevant_segment_ids): records a teacher exception without inventing content.

Agent sequence: inspect lesson -> retrieve relevant evidence -> compose structured candidate -> validate -> repair once if needed -> save draft or flag gap. Log real tool calls and persisted draft ID. The model never determines student authorization, absence dates, deadlines, approval or publication.

Deterministic citation checks prove source existence and membership, not semantic truth. Require teacher preview for factual correctness and question answer keys. A bounded secondary model review may flag contradictions but is not a substitute for review. Generated explanations/examples must be marked as generated from source material; direct excerpts identified separately. Reject unsupported curriculum facts rather than filling from web knowledge.

If P1 Q&A is implemented, scope retrieval to the published packet's material versions, cite evidence, abstain if absent, and expose a help-request action. Do not leak answer keys or other students' records into model context.

## 9. API sketch

All writes require authenticated scoped access; use idempotency keys for workflow triggers.
POST /classes; POST /classes/{id}/roster/import
POST /classes/{id}/materials; GET /materials/{id}/status
POST /classes/{id}/mapping-proposals; PATCH /mapping-proposals/{id}/approve
GET /classes/{id}/day?date=YYYY-MM-DD
PUT /lessons/{id}/session (coverage + attendance + expected_revision)
GET /jobs/{id}; POST /jobs/{id}/retry
GET /teacher/packets/{id}; PATCH /teacher/packets/{id} (new revision)
POST /teacher/packets/{id}/approve-and-publish (expected hash/revision)
GET /student/assignments; GET /student/assignments/{id}
POST /student/assignments/{id}/progress
POST /student/assignments/{id}/attempts
POST /student/assignments/{id}/help
GET /teacher/exceptions; POST /teacher/exceptions/{id}/resolve
GET /sources/{segment_id} (authorized excerpt/page stream, not public bucket URL)

Return 409 for stale edits, 422 for invalid content, 403/404 for unauthorized access and explicit job failure states. Student responses exclude answer keys, internal prompts and teacher-only review notes.

## 10. Build phases and exit gates

A. Runtime spike, 1-2 hours: inspect repo; configure model; execute one real Strands custom tool, validate a tiny source-linked output and persist it. Record exact setup and trace. If credentials unavailable, mark blocked and continue deterministic foundations; never call a fixture a passed spike.
B. Foundations, 3-4 hours: schema/migrations, auth, roster and seed fixture; teacher/student access checks pass. Local startup documented.
C. Material mapping, 3-4 hours: PDF/TXT extraction, source viewer, timetable, mapping proposal/review. Upload fractions fixture and confirm page mapping. Unreadable PDF produces actionable state.
D. Daily trigger, 3 hours: occurrence/attendance combined save, coverage revisions, durable worker and deduplication. Repeated save yields one draft job; partial coverage excludes untaught topic.
E. Packet and approval, 4 hours: real agent composition, validators, review/editor, transactional portal publication. Stale revision is rejected; student sees exactly approved content.
F. Student and exceptions, 3 hours: source-linked steps, attempts, progress, help requests and teacher dashboard. One complete cross-role journey survives reload/restart.
G. Verification and handoff, 3-4 hours: run matrix below, deployment/runbook, source/license review, architecture, screenshots, demo recording and setup retest.

Estimate: 20-24 focused engineering hours, not guaranteed elapsed time. September 12 is already late in the event. Freeze P0 on September 13; aim for a reviewable submission by September 14 18:00 WAT, seven hours before the currently published cutoff. Earlier target Sep 13 20:00 WAT is preferable if feasible. Recheck deadline before submission.

If behind: cut Q&A, printing, model-based timetable parsing and reminders first. Keep manual topic mapping plus agent suggestions, PDF/TXT, actual coverage, attendance trigger, real Strands generation, approval, portal delivery and progress. Never cut authorization, source evidence or truthful failure states to make the demo appear complete.

## 11. Required acceptance matrix

| Case | Passing evidence |
|---|---|
| Normal absence | Correct confirmed lesson -> real draft -> teacher approval -> student portal -> progress -> teacher view |
| Same date, two classes/periods | Each absent learner receives only the correct occurrence |
| Partly covered | Untaught objective absent from packet and questions |
| Moved lesson / unconfirmed scope | No invented lesson; explicit blocked state until confirmed |
| No supporting material | Content gap; no publishable fabricated packet |
| Invalid citation / wrong class source | Validation rejects; source endpoint denies cross-class access |
| Bad answer key / ambiguity | Review edit supported; publication requires new revision approval |
| Double save / double click / retry | One active assignment; stable job key; no duplicate publication |
| Revision race | Old approval returns 409; original record preserved |
| Attendance corrected | No assignment before publish; withdrawn with history after publish |
| Provider timeout or outage | Bounded retry; visible failure; zero fabricated success |
| Worker killed and restarted | Lease expires; recovery creates no duplicate artifact |
| Student A requests Student B ID | Server denies; same for files/progress/attempts |
| Malicious text in uploaded PDF | Cannot trigger external fetch, reveal secrets or bypass scoped tools |
| Browser reload/backend restart | Persisted packet/approval/progress remain consistent |
| Wrong local-date boundary | UTC conversion does not select adjacent day's lesson |

Use unit tests for selection, state transitions and validation; integration tests with real PostgreSQL for races and permissions; one browser E2E journey plus negative authorization checks. Capture at least one real provider run separately from deterministic fixture tests. Manually inspect teacher and student screens on phone and desktop. Ask a teacher to review one generated packet if access is available; record lack of external review otherwise.

## 12. Deployment and operation

First deliver runnable local Compose setup with environment example, migrations and seed command. For hosting, choose an already authorized provider with persistent PostgreSQL and private file storage; avoid provisioning billable infrastructure without approved budget. Worker must survive HTTP request end and restarts. Run migrations once, check health/readiness, verify HTTPS/session settings, complete cross-role live journey and restart persistence test. Do not claim deployed from a successful build or README link.

Set file-size, per-account generation and provider token limits. Log run IDs, latency and failures without raw student identifiers or full documents. Use synthetic demo records; no real student onboarding in hackathon scope. A public judge demo needs isolated/resettable data and bounded generation, never access to teacher uploads. Keep unpublished packets inaccessible. Actual school use needs separate data-retention and deployment review.

## 13. Handoff and completion definition

Required artifacts: source, tested dependency locks, environment template, migrations, owned/licensed sample PDF, reproducible seed data, README, architecture diagram, test/evaluation results, actual runtime proof, known limitations and demo script. Include BUILD_PROVENANCE.md documenting any reused starter code/materials and what was newly created.

Definition of done: teacher can perform the demo story using the UI; real Strands creates a grounded draft; teacher-approved revision reaches only the correct student; student action changes durable progress; teacher sees actual exceptions; duplicate/revision/outage tests pass; another person can follow setup. Report separately: implemented, tested locally, tested live, simulated, blocked.

Hackathon submission checklist (verify again at submission): public MIT/Apache repository with setup, architecture diagram, <=5-minute public YouTube/Vimeo working demo, description, AWS Builder ID and judge test access. AgentCore is optional. Published cutoff is September 14 17:00 PDT = September 15 01:00 WAT. Credit request cutoff has already passed; do not assume credits are available. Do not submit or publish a blog on the user's behalf merely because this plan exists.

## 14. Sources and prior research

Verified 2026-09-12:
- Rules: https://agentsforhumans.devpost.com/rules
- Strands Python quickstart: https://strandsagents.com/docs/user-guide/quickstart/python/
- Strands execution model: https://strandsagents.com/docs/user-guide/quickstart/overview/
- Scoped tools: https://strandsagents.com/docs/user-guide/concepts/tools/

Local product research: openai-inspiration.md and ideas.md in this directory, checked 2026-09-10. They support exploration, not validated demand or adoption. Current concept and daily teacher flow were specified by the user in this conversation. Stack, scope, timing and architecture above are proposed engineering decisions rather than sponsor requirements.
