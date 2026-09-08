---
handoff_schema: 1
task_id: $task_id
created_at: $created_at
project: $project_path
project_title: $project_title_json
user_authorized: true
---

# Mathematical Research Task for Web Pro

## Exact Target

$question

## Conversation Mode

Use this packet to begin an iterative mathematical research conversation about the exact target above. Treat the local context below as potentially useful working material, not automatically verified truth.

- Discuss the problem over as many turns as useful.
- Ask for clarification when a definition, hypothesis, or intended conclusion is genuinely ambiguous.
- Explore partial lemmas, examples, counterexamples, references, and alternative proof plans without forcing every reply into a final report.
- Revise earlier suggestions openly when an obstruction is found.
- Keep track of hypotheses, unresolved gaps, dependencies, and failed routes during the conversation.
- Do not produce the final handoff format merely because this file contains it.

## Finalization Trigger

Only when the user explicitly asks for a `final research handoff`, `最终交接稿`, or an equivalent final consolidation, return one self-contained Markdown document using every section in the contract below. The final document should incorporate the useful parts of the whole conversation, not merely summarize the most recent reply.

## Final Research Handoff Contract

1. `Verdict`: proved, partially proved, inconclusive, or probably false, with confidence.
2. `Precise Restatement and Assumptions`.
3. `Proof or Main Argument`, with the key logical steps visible.
4. `Dependency Audit`: external results used, exact hypotheses, source or theorem number when known, and verification status.
5. `Gap Audit`: missing implications, definition mismatches, finiteness or convergence issues, and any unverified steps.
6. `Counterexample and Toy-Case Checks`.
7. `Failed or Unproductive Routes Worth Recording`.
8. `Recommended Next Step`.
9. `References`, distinguishing verified citations, unverified citations, and search suggestions.
10. `Conversation-Derived Additions`: useful claims, examples, or obstructions that were not present in the initial packet.

## Local Context

$context
