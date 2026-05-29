# Optional prompt — clinical-style Markdown from structured report JSON (post-MVP)

**Input:** JSON from this service (`sections.*` plus `meta` / `quality` as returned by `POST /v1/cases/{id}/reports/generate`).

**Goal:** Turn it into sectioned Markdown suitable for debrief / teaching notes, without inventing clinical facts not present in the JSON.

Use the in-app narrative endpoints (`POST /v1/narratives/generate`) which embed a fixed system instruction and call Gemini with `GEMINI_API_KEY`.

For manual Chat-style testing, paste:

```
System:
You summarize surgical VIDEO ANNOTATION ONLY based strictly on INPUT_JSON.
(…same rules as app/application/narrative.py SYSTEM_INSTRUCTION…)

User:
INPUT_JSON:
```json
{ ... paste report JSON ... }
```
```

Request output Markdown with headings: Case context, Procedural chronology, Performance, Observations (with verbatim timestamps), Flags/Limitations.
