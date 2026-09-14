# Devpost submission copy

## Elevator pitch

Class Catch-Up turns a missed lesson into a source-grounded, teacher-approved catch-up packet, then guides each learner through explanations, practice, and help.

## Project story

### Inspiration

Missing one lesson can leave a learner trying to reconstruct what happened from scattered notes, while teachers repeat the same explanation for every absence. We wanted catch-up work to fit the lesson that was actually taught and to preserve the teacher's authority over what reaches a learner.

### What it does

A teacher uploads school-owned lesson material, defines topics once, confirms the scope actually covered, and records an absence. A Strands agent receives only that confirmed context and uses server-scoped tools to retrieve evidence, draft a four-step catch-up packet, validate every citation and quiz item, and save it for review. The teacher can inspect answers and rationales, edit a new immutable revision, and approve the exact version. Only then does the learner receive an assignment with Watch, visual Map, and Read explanations, practice, submission, and a help request that returns to the teacher.

### How we built it

The interface uses React 19, TypeScript, and Vite. FastAPI, SQLAlchemy, and Alembic provide tenant and role scoping, server-side sessions, CSRF protection, immutable packet revisions, idempotent jobs, learner progress, and audit events. A durable Python worker runs Strands Agents SDK 1.55.1 with Amazon Nova 2 Lite through Amazon Bedrock. The agent can call only five narrow tools; it cannot browse, execute code, approve work, or publish assignments. Deterministic validation checks the packet schema, approved source membership, exact supporting excerpts, lesson revision, absence, and enrollment before publication.

### Challenges we ran into

The hardest part was separating persuasive AI output from trustworthy school workflow. We had to keep uploaded text as evidence rather than instructions, distinguish fixture content from live model output, prevent provider failures from appearing successful, and make teacher approval an application rule rather than a model decision. We also designed a fresh synthetic learner state for each demo browser while preserving that learner's progress across reloads.

### Accomplishments that we're proud of

We completed a real local Strands run through Amazon Bedrock in which Nova 2 Lite called four scoped tools, produced a cited draft, passed deterministic validation, and saved the teacher-review revision. The repository records that provenance separately from seeded fixtures. The full teacher-to-learner workflow is usable on desktop and mobile, and 24 backend tests plus frontend lint and production build checks pass.

### What we learned

Useful agents need boundaries more than broad access. Source scope, deterministic validators, idempotency, explicit failure states, and human approval made the model useful without letting it decide authorization or publication. We also learned that the best teacher experience asks for material and topic setup once, then only a quick confirmation of what actually happened in class.

### What's next for Class Catch-Up

Next we will move the container to a durable AWS workload with an IAM role, managed PostgreSQL, and private object storage; evaluate Amazon Bedrock AgentCore; run concurrency and restart tests against PostgreSQL; and conduct a small teacher usability study before any real student data is introduced.

## Built with

Strands Agents SDK, Amazon Bedrock, Amazon Nova 2 Lite, Python, FastAPI, React, TypeScript, Vite, SQLAlchemy, Alembic, PostgreSQL, SQLite, Docker, Pydantic, PyPDF

## Testing instructions

1. Open the live demo. It starts in Teacher school setup with synthetic data and no credential form.
2. Select the school profile and choose **Enter my class** to open Materials.
3. Inspect the approved fractions source and topic mapping, then continue to Review.
4. Review the packet's steps, citations, quiz answers, rationales, revision, and provenance label.
5. Use the circular role control to open the drawer and choose Student.
6. Open the assignment marked **Not opened**. Switch among Watch, Map, and Read; complete the steps and questions; submit; and request help.
7. Return to Teacher and open Exceptions to see the learner's submitted state and help request.

Each new browser receives a fresh synthetic learner assignment. Reloading the same browser preserves that learner's server-side progress. No real student information is used.

## Links and media

- Repository: https://github.com/adetorojeremiahfadesayo/class-catch-up
- Live demo: https://pay-cave-provider-dress.trycloudflare.com
- Architecture upload: `docs/architecture.png`
- Project thumbnail: `docs/submission-thumbnail.png`
- Suggested gallery images: `docs/screenshots/teacher-territory-onboarding.png`, `docs/screenshots/teacher-review.png`, and `docs/screenshots/student-mobile.png`
