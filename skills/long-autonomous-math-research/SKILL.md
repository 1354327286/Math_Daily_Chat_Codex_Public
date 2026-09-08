---
name: long-autonomous-math-research
description: Run a durable, multi-wave mathematical proof or counterexample campaign with a user-confirmed frozen contract, one directory per run, one file per wave, exact failure logging, forced continuation while success remains unmet, and adversarial verification. Use only when the user explicitly asks for long autonomous research, sustained proof search, a prolonged research campaign, or invokes `$long-autonomous-math-research`; do not trigger for ordinary discussion, a single proof check, routine literature search, or note cleanup.
---

# Long Autonomous Math Research

Use the repository's normal project files as authoritative research state. Keep
run-local history in one dedicated directory; do not create a competing project
dashboard, silently change the target, append dozens of waves to one note, or
stop merely because the current routes became difficult.

## Confirm before starting

Before creating a run, make sure the exact target, assumptions, current status,
success criteria, execution mode, permissions, limits, and stop conditions are
clear. If anything is uncertain or conflicting, briefly summarize the known
state and ask the user the necessary questions together. Wait for the answers
before creating files or launching research work.

## Confirm the run contract before writing

1. Select the registered `<problem_dir>` and follow the parent `AGENTS.md`
   session-startup reading order.
2. Read relevant `memory/`, `notes/`, daily notes, and references read-only.
3. Draft a run contract containing:
   - exact target with all quantifiers;
   - assumptions and conventions;
   - complete affirmative and negative success criteria;
   - useful but insufficient outcomes;
   - execution mode: `single-turn` or `persistent-goal`;
   - user-authorized web, compute, remote, subagent, and reporting boundaries;
   - resource limits and lawful stop conditions.
4. Show the contract to the user and obtain explicit confirmation before
   creating the run directory, editing project state, launching tools, or
   opening proof routes. A user message that already supplies the complete
   contract and explicitly says to begin counts as confirmation.
5. If anything material is unclear or conflicting, summarize it and ask all
   necessary questions together. Make zero persistent writes while waiting.

Invoking this skill does not itself authorize a persistent Codex goal,
subagents, remote compute, browser automation, or external handoff. Request the
needed authority in the contract. Use persistent goal tooling only after the
user explicitly chooses `persistent-goal`; omit a token budget unless the user
specifies one.

## Create one run directory

After confirmation, create:

```text
<problem_dir>/notes/autonomous_runs/<run_id>/
├── contract.md
├── index.md
├── checkpoint.md
├── waves/
│   ├── wave-001-<slug>.md
│   └── wave-002-<slug>.md
├── audits/
└── artifacts/
```

Use a stable `<run_id>` of `YYYY-MM-DD_<ascii-slug>`. Copy and complete the
templates under `assets/`, including `Run format version: 2`. Keep `contract.md` immutable except for explicitly
dated, user-approved amendments. Keep `index.md` compact: one row per wave and
links to details. Rewrite `checkpoint.md` as the current run-local resume page.
Write each wave exactly once under `waves/`; do not append detailed waves to
`contract.md`, `index.md`, or the top-level `notes/` directory.

Use `audits/` for run-local hostile audits and independent reconstructions. Use
`artifacts/` only for small run-local certificates or manifests. Put reusable
mathematics and substantial computations in the normal project destinations.

Legacy files matching `notes/autonomous_run_*.md` are read-only inputs. Do not
move or rewrite them automatically. When resuming a legacy run, show a new
contract that cites the legacy file, obtain confirmation, then continue in the
new directory layout.

Unversioned run directories and explicit version 1 contracts are historical
format 1 as well. The validator reads their old wave names and status labels
without converting them into audited success. Missing historical index entries
are compatibility warnings; a stale checkpoint is still an error. Never edit
an old contract or bulk-rename waves just to pass version-2 checks. For renewed
research under a legacy contract, preserve it and resolve a separately authorized
version-2 continuation contract, using prior work as evidence.

## Resume from current evidence

Before resuming, read the frozen contract, compact project state, current
subgoal, checkpoint, latest wave and relevant index entries. Compare targets,
assumptions, claim withdrawals and user pause/resume evidence. Project maintenance
does not resume a run. Do not replace a broad frozen target with a newer narrower
project task or interpret an old completion label as current certification.

After each wave, update detailed evidence, index, project state when needed,
and checkpoint together. Record a dated `Recovery review` in the checkpoint.
Then obtain current fingerprints without writing:

```powershell
python scripts/check_autonomous_runs.py <problem_dir> --print-context <run_id>
```

Copy those fields into the checkpoint only after reading and reconciling the
evidence. On resumption run:

```powershell
python scripts/check_autonomous_runs.py <problem_dir> --resume-run <run_id>
```

This separate check requires format 2, active status, a recovery review, and
matching project-state, subgoal, contract and wave-inventory fingerprints.
Changed bytes require inspecting the change, not repeating every old proof audit.
Hashes only detect changes; they neither prove mathematical agreement nor grant
authorization. A paused or completed run cannot pass merely by refreshing hashes.
When a user decision occurs after the last wave, preserve that wave and record
the dated decision/evidence in the checkpoint; do not manufacture another wave.
Add `Post-wave decision: [dated decision](audits/<dated-decision>.md)` pointing
to an actual run-local record of the user's pause or resumption. This permits
an operational status change after an unfinished wave; it cannot upgrade
mathematical success or reopen a completed theorem automatically.

## Keep normal project state authoritative

| Content | Destination |
| --- | --- |
| Frozen contract and run-local resume state | `notes/autonomous_runs/<run_id>/` |
| Approach-family registry and active gaps | `memory/subgoals_state.md` |
| Closed routes, exact obstructions, reopen conditions | `memory/failed_paths.md` |
| Proved or conditional consequences | `memory/immediate_conclusions.md` |
| Counterexamples and witnesses | `memory/counterexamples.md` |
| Commands, certificates, environment events | `memory/events.md` |
| Compact current project snapshot | `research_state.md` |

Before opening a route, inspect `memory/failed_paths.md`. Identify the closest
prior route and the materially new lemma, construction, source, invariant,
certificate, or scope. Do not reopen a closed route with only new notation or a
fresh agent.

## Work in waves

Start with genuinely different mathematical mechanisms. For each route:

1. State its local claim and hypotheses.
2. Check prior routes and exact sources.
3. Build toy examples and likely counterexamples.
4. Attempt the proof or construction through the first decisive gap.
5. Test suspicious implications in both directions.
6. Return a proved lemma, construction, counterexample, exact obstruction, or
   sharply delimited partial result.
7. Record the result and a `reopen only if` condition when closing the route.

After each wave, write one wave file, add one index row, update detailed project
memory first, then update `checkpoint.md`. Do not call a route "one lemma away"
when the missing lemma is comparable in strength to the frozen target.

Use subagents only when the user explicitly authorized them and higher-level
instructions permit them. Keep independent early routes informationally
separate. Do not create user-owned Codex tasks unless the user explicitly asks.

## Enforce the continuation gate

Before yielding, pausing, or closing after every wave, record these fields in
the wave file and `checkpoint.md`:

- whether an audited success criterion is met;
- the exact lawful stop condition, or `none`;
- the next decisive action;
- the run status;
- the exact resume instruction if execution is interrupted.

If success is unmet and no lawful stop condition applies, keep status `active`
and begin the next wave while the current execution can safely continue. The
number of completed waves, mathematical difficulty, a fixed-range computation,
or exhaustion of the first portfolio is never a stop condition.

When all active routes reach exact obstructions, do not pause automatically.
Apply this continuation ladder:

1. Execute any already-recorded discriminating calculation or source check.
2. Decompose the smallest missing theorem into independently testable subgoals.
3. Generate materially different mechanisms, not cosmetic variants.
4. Investigate the opposite statement and explicit counterexamples.
5. Use exact literature search, computation, or formalization when authorized
   and when it answers a named finite question.
6. Ask the user only when progress truly requires a mathematical choice, new
   authority, unavailable source, or external-state change.

Needing a new theorem is a research subgoal, not by itself a blocker.

## Use the strict run state machine

Use only these run statuses; they are operational run states, not mathematical
claim labels:

- `active`: success unmet and research can continue;
- `complete_affirmative`: affirmative criterion met and all required audits pass;
- `complete_negative`: negative criterion met and all required audits pass;
- `awaiting_user_decision`: a concrete mathematical choice or new authority is
  required from the user;
- `paused_by_user`: the user explicitly asked to pause or stop;
- `blocked_external`: an unavailable source, permission, environment, or
  external-state change prevents all safe in-scope progress;
- `interrupted_runtime`: execution ended because of a product, context, machine,
  or explicitly agreed resource boundary, while the mathematical run remains
  resumable.

Use these exact stop-condition codes in wave files and `checkpoint.md`:

| Status | Stop-condition code |
| --- | --- |
| `active` | `none` |
| `complete_affirmative`, `complete_negative` | `audited_success` |
| `awaiting_user_decision` | `user_decision` |
| `paused_by_user` | `user_pause` |
| `blocked_external` | `external_block` |
| `interrupted_runtime` | `runtime_boundary` |

For every non-active status, also record concrete stop-condition evidence. For
`active`, record evidence as `none`.

Never write a generic `paused` or use it as a synonym for stalled. Mathematical
difficulty, failed routes, or an unproved new theorem do not justify
`blocked_external`. For a persistent Codex goal, follow the product's stricter
blocked threshold before marking the goal blocked.

In `single-turn` mode, a turn boundary is `interrupted_runtime`, not a research
pause or completion. In `persistent-goal` mode, keep pursuing the active goal
across resumptions until a lawful terminal or waiting state applies.

## Verify candidate results

Before `complete_affirmative`, `complete_negative`, or promoting a load-bearing
lemma:

1. Self-audit definitions, quantifiers, hypotheses, citations, edge cases, and
   all limit, descent, completion, base-change, and finiteness steps.
2. Run a hostile audit that tries to refute the claim and locates the first
   unsupported implication.
3. Run an independent reconstruction from the exact statement and key ideas
   without exposing the proof text.
4. Seek external audit when available and authorized. Do not call another
   instance of the same model family externally independent.

Use the parent project's claim-status vocabulary. Record the audit level and do
not assign more confidence than the weakest premise.

## Control computation and search

- Write code only for a named finite question that discriminates between routes.
- Record source file, command, timeout, output, served route, and environment.
- Preserve the smallest useful witness or certificate.
- Treat finite computation as evidence only for its certified range.
- Follow parent reference and web policies. Do not activate optional semantic
  indexing, remote compute, or external handoff without authority.

## Close, wait, or interrupt safely

Before entering any state other than `active`:

1. Apply the continuation gate and cite the exact lawful condition.
2. Finish or deliberately terminate tool sessions.
3. Write the final wave file and update `index.md` plus `checkpoint.md`.
4. Update detailed project memory before `research_state.md`.
5. Report the exact criterion reached, results, closed routes, blocker, next
   decisive action, resume instruction, and audit level.
6. Run:

```powershell
python .\scripts\check_autonomous_runs.py <problem_dir>
```

Never declare completion because approaches stalled or a budget is nearly
exhausted. Never pause merely because every current route needs new mathematics.
