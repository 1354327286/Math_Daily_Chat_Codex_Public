---
name: pro-research-handoff
description: Clarify, package, export, import, and audit a narrow unresolved mathematical research gap for Web Pro with a detached-work gate, anti-drift map, evidence boundaries, and a final-return gate. Use when the user asks to hand a project gap to Pro or Web Pro, export or submit a Pro packet, import a returned Pro answer, or review an existing Pro relay task.
---

# Pro research handoff

Use this workflow only after local project state identifies a genuine open,
load-bearing gap. Do not use it for a settled result, a broad exploratory
brainstorm, or a handoff without a precise target.

## Confirm before handoff

Before preparing or submitting a Pro task, make sure the exact gap, assumptions,
current status, requested deliverable, permitted substitutions, included
context, and packet-only versus browser-submission boundary are clear. If
anything is uncertain or conflicting, briefly summarize the known state and ask
the user the necessary questions together. Wait for the answers before writing
or submitting.

## Resolve the handoff specification before writing

Read the current project state read-only, then identify:

- the selected problem and exact mathematical target, including fixed
  parameters and hypotheses;
- the top-level objective and where this target sits in its dependency map;
- the requested Pro deliverable, such as a proof, counterexample, sharp
  obstruction, restricted theorem, source audit, or prioritized research plan;
- permitted routes, prohibited substitutions, and acceptance criteria;
- the local files to include and any material explicitly excluded;
- whether the user requests only a local packet or also browser submission.

Use recent discussion when it determines every field uniquely. If a material
field has more than one reasonable interpretation, ask the user a focused
question. Do not create a provisional request, write a manifest, delegate, or
open/submit through the browser while waiting. Do not silently weaken the
target or substitute a different deliverable. A complete user request that
explicitly says to proceed needs no redundant confirmation.

The exporter flag `--user-authorized` records that the user requested the
export. It does not resolve ambiguity or authorize browser submission.

## Orient and narrow

1. Read the repository `AGENTS.md`, `projects.json`, and the target project's `research_state.md`, `goal.md`, `progress.md`, `subgoal.md`, and current-obstruction notes.
2. Identify the exact theorem scope, fixed parameters, and non-negotiable boundaries (for example, blow-up-only/fixed generic fibre, or fixed finite `(j,m)`).
3. Separate established results, conditional lemmas, numerical evidence, failed approaches, and the one remaining load-bearing arrow.
4. State the top-level objective and an explicit anti-drift constraint. Explain where the requested result fits in the end-to-end dependency map.
5. Narrow the question to the earliest decisive unresolved obstruction; defer downstream limits, normalizations, or alternatives that cannot resolve that obstruction.

## Export

Use the selected problem's `<problem_dir>/handoff/` relay. Use the root `inbox/`
instead when material spans projects, is not assigned, or is an unprocessed
external report. Preserve inbox originals and record audited outcomes separately
in every affected problem.

Build a self-contained conversation starter containing the exact theorem target,
claim statuses, known failures, permitted entry points, prohibited substitutions,
and relevant project files. Include only relevant extra context.

```powershell
python .\scripts\pro_handoff.py export <problem_dir> --question-file <utf8-question-file> --context <problem-relative-file> --user-authorized
```

For a short target, use `--question "..."`. The exporter automatically includes
the state dashboard, goal, progress, subgoals, and latest dated note when present.
Use repeated `--context` arguments only for files under the selected problem and
`--no-latest-note` when the newest note is irrelevant or excessive.

Verify that the request exists, its manifest and hash agree, the context count is
sensible, and status is `ready_for_web`. Give the user the exact generated request
path. Web submission is manual unless the user explicitly requests browser
automation; never claim submission merely because export succeeded.

The initial packet must state the requested deliverable and acceptance criteria
while permitting questions, corrections, partial attempts, and multiple proof
directions. Ask first for an audit and research plan. Require a stabilized
`final research handoff` or `最终交接稿` before treating the return as ready for
local mathematical audit.

## Import and audit a final return

Preserve the returned Markdown unedited, then import it:

```powershell
python .\scripts\pro_handoff.py import <problem_dir> <task_id> <response-file>
```

If more than one project, task, or candidate response matches the user's
request, ask which one to import. Do not select by filename recency alone.

Read the original request, raw response, and generated review checklist. Treat
the response as evidence, not project truth. Check:

- whether it answers the exact target with unchanged definitions and scope;
- every useful claim as `proved`, `conditional`, `plausible`, `needs verification`, or `false`;
- theorem hypotheses, important citations, limits, completions, descent, base change, finiteness, and possible circularity;
- reusable failed routes, counterexamples, and unresolved claims.

Write audited results to the appropriate detailed project files first. Refresh
`research_state.md` only if the current snapshot changed, and preserve rejected
or unresolved claims in review notes. After completing the checklist, mark the
task reviewed:

```powershell
python .\scripts\pro_handoff.py review <problem_dir> <task_id> --summary "short audit outcome"
```

Use `python .\scripts\pro_handoff.py status <problem_dir>` to inspect one problem,
or omit `<problem_dir>` to scan all registered problems. Never treat `task_id` as
a mathematical problem ID or pass it to reference-search tools.

## Efficiency plan

- Start from project dashboards and the newest obstruction notes; do not reread unrelated research history.
- Reuse prior handoff structure, but regenerate the target/scope section from current state.
- Stop after a verified upload-ready packet if no Pro response has arrived; exporting a packet is not mathematical progress.

## Pitfalls and fixes

- Symptom: Pro proposes a broader but easier result. Cause: missing fixed target or anti-drift constraint. Fix: state exclusions explicitly and map the requested arrow to the overall theorem.
- Symptom: sampled optimization or a conditional lemma is treated as a theorem. Cause: evidence levels were flattened. Fix: label proof, conditional claim, numerical evidence, and failure separately.
- Symptom: an alteration, rig-etale cover, rationalization, or coarse coinvariant argument is substituted for an integral/fixed-generic-fibre/finite-coefficient target. Fix: put the exact no-substitution rule near the beginning and repeat it in acceptance criteria.
- Symptom: handoff considered complete after export. Fix: preserve the audit-first and final-report gate.

## Verification checklist

- The packet identifies one precise open question and its top-level project relation.
- The user explicitly authorized export after every material ambiguity was resolved.
- The requested Pro deliverable and acceptance criteria are explicit.
- Scope boundaries and disallowed substitutions are explicit.
- Every supplied claim carries an honest status.
- Context files are current and relevant.
- Export is `ready_for_web` and manifest/hash verification succeeded.
- Project state is unchanged pending a reviewed final return.
- Everything under `<problem_dir>/handoff/` except `.gitkeep` remains private and uncommitted.
