# Two-school comparison

The main workflow helps a family investigate two real schools it is already considering.
It complements the original discovery prototype, which remains at `/discover`.
The comparison uses one bounded OpenRouter web-research request for each batch of
uncached school names, then applies the requirement logic deterministically. The
discovery prototype remains separate.

## Workflow

1. Fetch `/schools` for available requirement topics.
2. Enter two distinct school names, a deciding concern and one or more requirements.
3. Submit `/compare` with stable client ids, school names, requirements and recorded observations.
4. Review evidence, individual must-have assessments and follow-up questions.
5. Record a response or observation, resubmit, and review the changed statuses.

The frontend uses `/api/schools` and `/api/compare`; Next.js proxies to the backend
with a timeout and no caching. Notes remain in page memory. The backend does not
save prompts or notes. Live evidence is cached by normalized school name in a
bounded process-global cache shared by users on the same instance, and the cache
is cleared on restart or redeploy. The family context is sent to OpenRouter for the live research request;
do not include identifying child details. OpenRouter fetches current web results through its `openrouter:web_search`
server tool; the backend only validates source URLs returned by the model and does
not fetch those URLs itself.

## Evidence rules

| Evidence | Can resolve a requirement? | Presentation |
| --- | --- | --- |
| Fictional seed snippet | No | Demo, with no invented verification date |
| Another parent's experience | No | Individual account and context |
| School response recorded by the parent | Yes | Recorded by parent, not independently verified |
| Published information added by the parent | Yes | Requires an HTTP/S source link; not independently verified |
| Family's own observation | Yes | Parent-recorded observation |
| Live web research | Yes, when a source directly addresses the requirement | Source lead retrieved via OpenRouter; verify with the school |

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
  "school_ids": ["school-1-tao-nan", "school-2-nanyang"],
  "school_names": ["Tao Nan School", "Nanyang Primary School"],
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
`assessments`, `questions`, `context` and `notice`. When no useful live source is
found, the cell is unknown. The complete schema is at `/docs` or `/openapi.json` on
the backend.

To record information, resubmit the request with an entry in `observations`:

```json
{
  "id": "note-1",
  "school_id": "school-1-tao-nan",
  "requirement_id": "quiet-space",
  "source_type": "school_response",
  "source_label": "School office response",
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

The original seed loader is retained only for the discovery demo. The comparison
workflow accepts school names and researches uncached names at request time. Programme names
or educator counts alone must not be treated as proof that a child's particular
arrangement is available. Preserve the distinction between a published policy, an
individual account, a live research lead and a confirmed arrangement.

Live research is intentionally bounded to one request per batch of new schools, at
most three results per search and eight total search results. Once a school is in
the process cache, changing notes or context does not call OpenRouter again. A
requirement not covered when that school was first researched remains unknown
rather than causing a second API call. Set `OPENROUTER_API_KEY` and optionally
`OPENROUTER_MODEL` in the backend environment; never commit either value.
