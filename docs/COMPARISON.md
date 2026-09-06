# Two-school comparison

The main workflow helps a family investigate two schools it is already considering.
It complements the original discovery prototype, which remains at `/discover`.
The comparison is deterministic and makes no LLM calls, regardless of `MODEL_PROVIDER`.

## Workflow

1. Fetch `/schools` for the fictional school catalogue and available requirement topics.
2. Select two distinct schools, a deciding concern and one or more requirements.
3. Submit `/compare` with the selected schools, requirements and recorded observations.
4. Review evidence, individual must-have assessments and follow-up questions.
5. Record a response or observation, resubmit, and review the changed statuses.

The frontend uses `/api/schools` and `/api/compare`; Next.js proxies to the backend
with a timeout and no caching. Notes remain in page memory. The backend does not
save requests. Source URLs are references only, never fetched.

## Evidence rules

| Evidence | Can resolve a requirement? | Presentation |
| --- | --- | --- |
| Fictional seed snippet | No | Demo, with no invented verification date |
| Another parent's experience | No | Individual account and context |
| School response recorded by the parent | Yes | Recorded by parent, not independently verified |
| Published information added by the parent | Yes | Requires an HTTP/S source link; not independently verified |
| Family's own observation | Yes | Parent-recorded observation |

The user supplies an explicit assessment: `supports`, `does_not_support` or
`unclear`. The system does not infer a definitive conclusion from prose.
For commute, recorded minutes override that assessment: a journey at or below the
specified limit supports the requirement; above it does not. Missing minutes remain
unknown. Another parent's journey remains contextual, even when it includes minutes.

Each cell is evaluated independently:

- Supporting and opposing direct evidence together produce `conflicting`.
- Opposing direct evidence produces `not_met`.
- Supporting direct evidence produces `supported`.
- Otherwise the result is `unknown`.

Dates provide context; newer sources do not automatically erase disagreement.
Remove an obsolete note explicitly. No arbitrary freshness cutoff is applied.

A school with any unmet must-have is labelled `unmet_requirement`. Unresolved or
conflicting must-haves produce `needs_confirmation`. Only when all must-haves are
supported does the summary become `requirements_supported`. A comparison without
must-haves is labelled `preferences_only`. Preferences never compensate for a
must-have, and the schools retain their selected order. There is no overall score,
winner, school-quality inference or personal admission prediction.

Follow-up questions prioritise must-haves, include the family's specific details,
and ask for clarification of conflicts or alternatives for unmet requirements.

## API example

`POST /compare` accepts:

```json
{
  "school_ids": ["riverside_ps", "maple_grove_ps"],
  "context": "We need a quiet space our child can access when overwhelmed.",
  "requirements": [
    {
      "id": "quiet-space",
      "topic": "quiet_space",
      "priority": "must_have",
      "details": "An accessible quiet space during the school day",
      "max_minutes": null
    }
  ],
  "observations": []
}
```

The response includes `schools`, `rows` (one cell per school per requirement),
`assessments`, `questions`, `context` and `notice`. With only demo evidence, all
cells are unknown. The complete schema is at `/docs` or `/openapi.json` on the backend.

To record information, resubmit the request with an entry in `observations`:

```json
{
  "id": "note-1",
  "school_id": "riverside_ps",
  "requirement_id": "quiet-space",
  "source_type": "school_response",
  "source_label": "Fictional open-house response used to test the workflow",
  "source_url": null,
  "observed_on": "2026-09-01",
  "summary": "Example only: staff described how a child can request a sensory break.",
  "outcome": "supports",
  "commute_minutes": null
}
```

This simulates parent-recorded evidence; it is not a claim about any real school.
For a commute requirement, use `topic: commute`, supply `max_minutes` (1–180), and
record `commute_minutes` (1–300). Dates must be valid and cannot be in the future
in Singapore. Published-source links must be HTTP/S URLs.

Requests validate school membership, two distinct schools, unique requirement ids
and topics, note references, unique note ids, field lengths, numeric limits and
source types. Unknown fields are rejected. Validation responses omit input values.
Changing a requirement's details or commute limit in the UI creates a new identity
so old notes are excluded; changing priority alone retains applicable notes.
The UI discloses exclusions before submitting edits.

## Extending the evidence base

The seed loader deliberately marks every catalogue entry as fictional. A real-data
integration should supply school identifiers and dated source records with explicit
provenance. Programme names or educator counts alone must not be treated as proof
that a child's particular arrangement is available. Preserve the distinction
between a published policy, an individual account and a confirmed arrangement.
