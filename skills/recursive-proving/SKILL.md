---
name: recursive-proving
description: Clarify and explore several already-screened proof plans through explicitly authorized subagents in parallel or recursively. Use only when the user requests deeper parallel work or explicitly authorizes subagents after direct attempts expose distinct obstructions; do not delegate an ambiguous target or silently replace requested delegation with sequential work.
---

# Recursive Proving

Deepen existing plans without discarding the work that led to them.

## Preconditions

- The user explicitly authorized subagent delegation for this target.
- The selected problem and exact target are unambiguous.
- Each assigned plan has already received a direct screening pass.
- The plans have distinct questions that can be investigated independently.
- Suitable subagent tools are available in the current environment.

If the user explicitly requested parallel or recursive delegation but the
problem, target, assumptions, plans, assignment boundaries, or requested output
is ambiguous, ask a focused question before spawning anything. Do not create a
partial assignment and do not silently continue sequentially instead. A clear
request needs no redundant confirmation.

If delegation was only an internal possibility rather than a user-authorized
mode, do not invoke this skill; continue sequentially in the current task. If
the specification is clear but subagent tools are unavailable, report that
environmental limitation without changing the mathematical target.

## Procedure

1. Read `AGENTS.md` and the selected problem's current state, goal, subgoals, recent note, and relevant memory.
2. Define one bounded assignment per plan. Include the full target, assumptions, assigned plan, known obstructions, relevant local files, required output, acceptance boundary, and confidence labels.
3. Ask each subagent to investigate its assignment and return a concise report with proved claims, conditional claims, failed routes, references, and unresolved gaps.
4. Do not create user-owned Codex tasks for internal subtasks. Use the available subagent or multi-agent tools.
5. Wait for all required reports. Audit their claims in the current task before incorporating them into project memory.
6. Reconcile conflicting reports by checking definitions, assumptions, and evidence.
7. If a route succeeds, assemble a readable proof draft and mark any remaining verification obligations.
8. If all routes fail, synthesize the exact common and route-specific failures.

## Persistence

The coordinating Codex instance owns file updates. After auditing the reports, append substantive outcomes to:

- `memory/subgoals_state.md` for per-plan status;
- `memory/immediate_conclusions.md` for reusable proved consequences;
- `memory/failed_paths.md` for failed routes;
- `memory/search_results.md` for useful literature findings;
- the current daily note for the research narrative.

Update `subgoal.md` and then `research_state.md` only when their current snapshot changes. Do not run this skill as an automatic iteration loop.
