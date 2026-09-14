# Evaluation

Validation date: 2026-09-12

## Automated results

- Backend: 17 tests passed.
- Frontend: Oxlint passed with no findings.
- Frontend: TypeScript and Vite production build passed.
- Migrations: revisions `0001` through `0005` applied to a clean SQLite smoke database.
- Synthetic seed: succeeded on a fresh migrated database.
- Runtime: API `/health` returned 200 and Vite returned 200.

SQLite is used only for the current automated run. PostgreSQL-specific race behavior remains unverified because Docker did not respond in this environment.

## Acceptance matrix

| Case | Status | Evidence |
|---|---|---|
| Normal absence | Passed locally | A live local Strands + Bedrock draft passed validation, then teacher approval → learner portal → progress/help completed on synthetic data. |
| Same date, two classes/periods | Tested in model/API structure | Unique class/date/period constraint and exact day query; P1/P2 isolation is exercised in daily tests. A PostgreSQL integration race test remains. |
| Partly covered | Passed | Test confirms only the retained topic is stored and used by the queued job. |
| Moved lesson / unconfirmed scope | Partial | Validation and explicit unconfirmed blocker implemented; unconfirmed test passes. Destination collision requires broader integration coverage. |
| No supporting material | Implemented, provider branch untested | `flag_content_gap` and non-publishable validation exist; the successful live model run used sufficient evidence. |
| Invalid citation / wrong class source | Passed | Packet validation rejects out-of-scope citation; teacher and student source checks deny cross-scope access. |
| Bad answer key / ambiguity | Passed structurally | Schema rejects absent answer keys; review edits create a new revision. Human ambiguity quality is not automated. |
| Double save / double click / retry | Passed | Replayed idempotency key returns original receipt and leaves one job; publication is revision-state guarded. |
| Revision race | Passed | Stale packet hash returns 409; stale lesson revision returns 409. PostgreSQL concurrent transaction test remains. |
| Attendance corrected | Passed | Post-publication present correction supersedes the active assignment; pre-publication checks use current revision. |
| Provider timeout or outage | Partial | Timeouts/retries and truthful failure states implemented; missing-provider test passes. A live forced timeout is not run. |
| Worker killed and restarted | Passed locally | Expired lease is reclaimed with the same job and no duplicate artifact. |
| Student A requests Student B ID | Passed by scope contract | Student assignment lookup includes tenant plus enrollment-derived student ID and returns 404 otherwise. |
| Malicious uploaded text | Partial | Agent tools enforce fixed scope and have no shell/browser; dedicated adversarial prompt test remains. |
| Browser reload/backend restart | Partial | Fresh FastAPI client sees persisted state; local API/web smoke passed. PostgreSQL process restart remains blocked. |
| Wrong local-date boundary | Implemented, not fully integration-tested | Occurrences use explicit class-local `date` plus period; no UTC date derivation occurs in selection. |

## Manual browser evidence

- `docs/screenshots/teacher-review.png`: desktop review view with explicit fixture provenance.
- `docs/screenshots/student-mobile.png`: 390 px student packet with source links.
- Desktop width 1280: viewport and document width matched.
- Mobile width 390: viewport and document width matched; no horizontal overflow.
- Browser flow confirmed teacher approval followed by Ada assignment delivery and no visible `answer_key`.
- First-login browser flow confirmed both territory choices, US Grade/Period controls, England & Wales Year/Lesson controls, persisted Year 10 selection, and the teacher introduction in Ada's portal.
- `docs/screenshots/teacher-territory-onboarding.png` and `docs/screenshots/student-territory-welcome.png` capture the new experience.

## External evaluation

No teacher usability review has been conducted. The under-30-second daily interaction target and any learning/workload outcomes are unverified.


## Review follow-up validation — 2026-09-13

- Full backend suite: 23 passed, one upstream Starlette/AnyIO deprecation warning (81.18 seconds).
- New regressions cover saved attendance/planning scope, persisted completion and answers, submission prerequisites and answer immutability, help after resolution, false page labels/direct excerpts, exhausted worker leases, and supervisor deadline termination.
- TypeScript compilation, Oxlint, Vite production build, and Python compilation passed using the bundled Node and project Python runtimes.
- A real spawned supervisor child processed a local queued job with provider configuration intentionally empty, returning `retry_wait provider_not_configured`. This verifies the process wiring and truthful failure path, not Bedrock.
- Browser verification used an isolated SQLite database and synthetic learners. Attendance persisted after browser reload. Source preview, quiz answer review, editing into revision 2, exact publication, student completion/answers/submission/help, and teacher resolution all worked. The dashboard retained submitted status after resolution.
- Desktop screenshot inspection confirmed the Exceptions and progress layout. A new mobile-width inspection was not performed for this revision.
- PostgreSQL races, teacher time savings, production deployment, and public submission remain unverified. One local live model generation is recorded separately.

## Live Bedrock evidence — 2026-09-14

- Amazon Nova 2 Lite completed one local Strands packet job over synthetic teacher-approved material.
- The persisted run used four scoped tools, passed deterministic citation validation, and saved a four-step, three-question draft.
- Browser verification showed the `STRANDS RUN` provenance label, teacher approval, delivery to Ada's synthetic account, and the learner Watch/See/Read presentation.
- A separate broader-scope retry failed visibly after invalid candidates and SQLite contention; no fixture replaced that failure. The local SQLite connection now waits for short write contention, and the supervisor closes any orphaned running `AgentRun` as failed. PostgreSQL concurrency remains unverified.
