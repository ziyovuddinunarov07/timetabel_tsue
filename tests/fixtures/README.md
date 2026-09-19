# Source snapshot provenance

`edupage_2026-09-17.json` is a reduced public response captured on 17 September 2026 from TSUE EduPage version 94. Only MR-86/25 and its referenced lesson, teacher, room, subject, period, cycle and subgroup records are retained. No student records, credentials, or production database are included.

The fixture is exclusively for offline regression tests. It must never be used as a production fallback. Tests mutate copies to exercise invalid schemas, unknown cycles, Saturday lessons, subgroups, and missing fields; those mutations are synthetic scenarios, not actual TSUE lessons.
