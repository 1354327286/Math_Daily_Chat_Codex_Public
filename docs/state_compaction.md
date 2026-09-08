# State compaction at research milestones

This is a session-driven workflow over the existing project files. It does not
start a scheduled monitor or an autonomous research run.

## When to propose

After recording substantive progress and refreshing the current state, check
the selected project's `research_state.md`. Propose compaction only when both
conditions hold:

- Its UTF-8 file size exceeds **24 KiB (24,576 bytes)**.
- A substantive milestone has been recorded: for example a scoped lemma is
  closed, an audited counterexample is established, a proof route is closed
  with an exact reusable failure, a manuscript revision is completed, or a
  reviewed external result materially changes the next goal.

A new date, routine formatting, another inconclusive wave, or merely crossing
250 lines is not a milestone. Do not invent a result to trigger maintenance.
Until a milestone, a large-state diagnostic is an internal navigation warning;
continue ordinary work using targeted retrieval.

The read-only helper can provide conditional reminder text:

```powershell
python scripts/check_research_state.py <problem_dir> --milestone "<recorded outcome>"
```

The agent supplies the milestone from actual evidence; the helper checks size,
not mathematical truth. It does not send a message, record consent, or modify files.

## Reminder and user agreement

At a natural milestone or closeout, tell the user the project, current size,
recorded outcome, and proposed scope. For example:

> This project's state page is now 31 KiB. The scoped lemma has reached a
> recorded conclusion, so this is a good point to consolidate the state.
> May I archive the original and compact this state page, preserving its exact
> target, assumptions, confidence, open obligations and evidence links?

Use the app's question mechanism when appropriate. Continue unrelated authorized
research while awaiting an answer. Do not create an archive, draft a compressed
state, or rewrite the state for this compaction before agreement arrives.
Ordinary updates that record newly established research remain authorized.

Record the proposal and subsequent response as a short dated entry in the
existing `memory/events.md`, identifying the state path, measured size, milestone
and its evidence link. Do not create a second status database. Skip such writes
in an explicitly read-only conversation.

- Do not repeat an outstanding proposal in later turns or sessions.
- If declined or deferred, wait for another substantive milestone or an explicit
  request before suggesting again. Respect a longer user-specified deferral.
- An affirmative reply covers the named state and its necessary archive,
  navigation checks and maintenance log. It does not cover other projects,
  deleting historical notes, changing mathematical claims, or resuming research.
- An explicit request to compact already supplies agreement. This workflow's
  standing authorization to remind is not consent to each future compaction.

## Execute after agreement

1. Re-read the state and compare its current target, assumptions, confidence,
   blockers and key source restrictions with current subgoals and relevant
   recent detailed records. If substantive conclusions conflict, resolve the
   evidence or ask about the exact conflict; do not choose a different theorem.
2. Preserve the original bytes in a unique dated directory under `notes/`.
   Never overwrite an earlier archive. Record original path, relative-link
   base and SHA-256 in its receipt; verify the archived hash before rewriting.
3. Keep all six state sections. Retain the exact target and hypotheses,
   current audit status, key established inputs, unresolved obligations,
   relevant failed routes and one current goal. Link to detailed evidence.
   Aim for about **8–12 KiB**, allowing more when the precise scope needs it;
   never truncate mathematics just to reach a size target.
4. Compare the retained content against the original and detailed evidence;
   preserve user pauses, frozen contracts and withdrawn-result warnings.
   Record the maintenance date separately from the mathematical audit date.
5. Run `python scripts/check_research_state.py <problem_dir> --check-links`.
   Verify archive integrity and local links, and append the result and the
   user's agreement to the existing maintenance event. Report before/after
   size and any unresolved issue. A navigation check is not a proof audit.

If the state changes after approval but before the rewrite, re-read the change
and rebuild the compaction from current evidence; never overwrite concurrent
user work. Materially changed scope requires resolving that scope first.
