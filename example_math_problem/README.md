# Example Math Problem Workspace

This directory is a fictional example of the research workspace layout.

The real research notes, PDFs, extracted text, memory files, and generated LanceDB indexes are intentionally ignored by git. They should stay local unless you explicitly decide to publish a sanitized snapshot.

Expected local structure:

```text
example_math_problem/
├── research_state.md
├── goal.md
├── progress.md
├── subgoal.md
├── YYYY-MM-DD.md
├── notes/
├── memory/
├── refs/
└── downloads/
```

This directory represents one example mathematical problem. It is not a container for other problems. `research_state.md` keeps the compact current state under six required sections: `Research State`, `Known Theorems`, `Open Problems`, `Failed Attempts`, `Current Goal`, and `References`.

Create another problem as a sibling top-level directory and initialize its `research_state.md` from `templates/research_state.md`.

Use `README.md` and `AGENTS.md` in the repository root for usage and agent behavior.
