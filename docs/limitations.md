# Known limitations

## Remaining live verification

- One local Strands packet-generation run through Amazon Bedrock Nova 2 Lite succeeded on synthetic project-owned material. Broader provider reliability, quotas, cost behavior, and production credentials are not verified.
- Docker CLI did not respond, so PostgreSQL integration/race and restart testing did not run. SQLite covered deterministic tests only.
- The original system Node binary hung. The bundled Node runtime successfully compiled, linted, built, and served the updated frontend on September 13.

## Product limitations

- Mapping suggestions are `deterministic_keyword_v1`, clearly labeled non-agent behavior.
- Material extraction supports UTF-8 TXT and text-based PDF only. Scans become `needs_text`; OCR is not implemented.
- Timetable CSV import and roster CSV import are not implemented; current endpoints support structured/manual input and the seed.
- Today now uses topic names and approved page checkboxes. Moving a lesson records its destination; automatic scheduling at that destination is not implemented.
- Territory support currently covers United States High School and an England & Wales secondary/sixth-form profile. It adapts terminology, levels, and timezone choices; it does not yet encode curriculum standards, qualifications, grading, or country-specific policy.
- Teacher review now exposes questions, answer keys, rationales, source previews, and content editing as a new revision. Editing citations/objectives and rejecting a draft with a reason remain future work.
- No email, SMS, WhatsApp, parent accounts, grades, voice, multilingual generation, LMS integration, or automatic release exists.
- No production object store adapter, deployment, retention policy, quotas, monitoring backend, or judge reset endpoint exists.
- There is no external teacher evaluation or measured claim about learning outcomes or time saved.

## Security and operations

- Local Compose credentials are development-only and must be replaced outside local use.
- Production must set secure cookies, HTTPS, constrained CORS/reverse proxy behavior, secret management, storage encryption/access policy, rate limits, and data retention.
- Material deletion is not exposed; dependency-safe deletion and retention policy remain future work.
- The worker now supervises a child process with a 300-second deadline and lease renewal. PostgreSQL concurrent ownership/race behavior still requires integration verification.
- PostgreSQL should be used for production concurrency semantics; SQLite is not a deployment target.
