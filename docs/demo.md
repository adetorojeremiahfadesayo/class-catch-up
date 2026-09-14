# 90-second demo

## Before recording

1. Start PostgreSQL, API, worker, and web client.
2. Run migrations and the synthetic seed.
3. If demonstrating live generation, verify Bedrock access with the configured model before recording. Keep that run visually distinct from the fixture packet.
4. Reset the demo database between takes.

## Script

1. **0:00-0:14 — Introduce the teacher.** On first sign-in, enter the teacher welcome, select JSS 1A, and choose either United States High School or England & Wales Secondary / Sixth Form. Show the Grade/Period or Year/Lesson preview.
2. **0:14-0:28 — Today.** Enter the configured class. Show the local date, exact period/lesson, planned topic names and page previews, and six fictional learners.
3. **0:28-0:42 — Confirm reality.** Choose Partly covered, retain only equivalent fractions and its approved segment, mark Ada absent, and save once. Show the preparation status.
4. **0:42-0:54 — Agent evidence.** If Bedrock is configured, show the `AgentRun` and scoped tool activity separately. Otherwise say generation is blocked and use the clearly labeled fixture packet.
5. **0:54-1:08 — Review.** Show direct versus generated content, citations, three questions, the provenance label, and approve the exact revision/hash.
6. **1:08-1:22 — Student.** Sign in as Ada. Show the teacher introduction and territory context, open the packet/source, complete the steps, answer the questions, submit, and request help.
7. **1:22-1:30 — Exceptions.** Return as the teacher and show Ada's submitted work and help request, then resolve the request.

## Claims

Say:

- "The local Strands SDK tool execution is proven."
- "This packet is model-generated" only when its UI provenance says `Live Strands run`.
- "Delivered" means available in the authenticated portal.

Do not claim measured learning improvement, teacher-time reduction, production deployment, real messaging, or real student use.
