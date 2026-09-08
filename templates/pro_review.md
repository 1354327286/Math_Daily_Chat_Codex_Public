---
handoff_schema: 1
task_id: $task_id
project: $project_path
status: needs_review
imported_at: $imported_at
request_sha256: $request_sha256
response_sha256: $response_sha256
---

# Web Pro Response Review

- Request: [`$request_path`](../requests/$task_id.md)
- Raw response: [`$response_path`](../responses/$task_id.md)

The raw response is evidence to inspect, not a verified project conclusion. Do not update `research_state.md` from it until the checks below are completed.

## Verification Checklist

- [ ] The response addresses the exact target and uses the same definitions.
- [ ] Every theorem application has the necessary hypotheses.
- [ ] Important citations, theorem numbers, and version-sensitive claims are verified.
- [ ] Limits, completions, descent, base change, and finiteness steps are justified where relevant.
- [ ] The argument is checked for circular reasoning and hidden equivalences.
- [ ] At least one toy case or counterexample search has been considered for strong claims.
- [ ] Claims are classified as proved, conditional, plausible, needs verification, or false.
- [ ] Reusable failures and obstructions are identified.
- [ ] Detailed project files are updated before the compact state page.

## Reviewer Notes

Pending Codex review.

## Approved Local Updates

None yet.
