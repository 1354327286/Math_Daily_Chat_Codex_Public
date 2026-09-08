---
name: query-memory
description: Search the selected problem's Markdown memory for earlier conclusions, examples, counterexamples, failed paths, subgoal states, and notes. Use when prior work may clarify a claim, subgoal, proof attempt, or choice of next direction.
---

# Query Memory

Recover relevant prior work from the selected problem directory and explain how it affects the current question.

## Procedure

1. Identify the selected `<problem_dir>` from `projects.json` and the current mathematical topic.
2. Form a concrete query from the current claim, obstruction, or decision.
   Use the compact state and current subgoal first, following `AGENTS.md`'s
   progressive startup order. Search headings and read complete relevant
   entries; do not load whole progress or memory logs merely to orient.
3. Search the smallest relevant set first:
   - `memory/immediate_conclusions.md`
   - `memory/toy_examples.md`
   - `memory/counterexamples.md`
   - `memory/failed_paths.md`
   - `memory/subgoals_state.md`
   - recent daily notes and `notes/`
4. Use `rg --no-ignore` because problem data may be ignored by Git. Scope the search to `<problem_dir>` and exclude generated LanceDB data.
5. Read the surrounding sections of the strongest matches rather than relying on isolated search snippets.
6. Recheck old claims against newer dated entries and the current `research_state.md`. Preserve historical records when they have been superseded.
7. Summarize the useful findings, their dates and confidence labels, and their effect on the current work.

## Output

Return a concise human-readable summary containing:

- the query and files searched;
- the useful prior findings;
- any conflict or superseded result;
- the implication for the present claim or next action.

Do not write a log merely because memory was searched. When the retrieval materially changes the research state or exposes a reusable conflict, record the mathematical outcome in the appropriate detailed memory file and, if useful, append a dated event to `memory/events.md`.

If no useful prior work is found, say so clearly and continue with the appropriate proof, example, counterexample, or literature workflow.
