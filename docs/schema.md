# Topic Tree Schema

_Owner: Team — P0-TEAM2. Freeze this on Day 2 — every downstream module (diagnostic,
scheduling, RAG, quiz) builds against this exact shape. A mid-sprint change forces
rework across the whole team._

Shape: `subject -> unit -> topic -> subtopic`, each node carrying a `mastery` field.

```json
{
  "subject": "string",
  "units": [
    {
      "unit": "string",
      "topics": [
        {
          "topic": "string",
          "mastery": 0.0,
          "subtopics": [
            {
              "subtopic": "string",
              "mastery": 0.0
            }
          ]
        }
      ]
    }
  ]
}
```

`mastery` is a float in `[0, 1]`, populated after the diagnostic (P3-SHI6) and
updated by the feedback loop (P7-TEAM3).

## Related DB tables

See `backend/src/db/` — `users`, `documents`, `syllabus_topics`, `sessions`,
`chat_messages`, `quiz_results` (P0-SRE2).
