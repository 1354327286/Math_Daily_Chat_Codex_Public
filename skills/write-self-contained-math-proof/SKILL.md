---
name: write-self-contained-math-proof
description: Clarify and turn a mathematically closed result from the selected problem's research state into a self-contained proof for human or external-LLM review. Use when the user asks Codex to write, present, export, or polish a standalone proof based on current project progress. Resolve material ambiguity about the statement and deliverable before drafting, and generate the proof only after every dependency is closed.
---

# Write A Self-Contained Math Proof

Write a proof document that stands on its own. Treat project memory as source material, not as the structure or voice of the final exposition.

## Confirm before drafting

Before producing a standalone review proof, make sure the exact statement,
assumptions, proof status, reader, format, and destination are clear. If any of
these is uncertain or project records conflict, briefly summarize the known
state and ask the user the necessary questions together. Wait for the answers
before drafting.

## Resolve the standalone deliverable

Before drafting or creating a proof file, identify:

- the selected problem and exact theorem, proposition, or lemma;
- every assumption, convention, and fixed parameter;
- the intended reader and assumed background;
- the requested form, such as chat proof, Markdown, LaTeX, article section, or
  external-review packet;
- the destination and any length, style, or citation requirements.

Use recent discussion when it fixes these fields uniquely. If a material field
has more than one reasonable interpretation, ask the user for the missing
specification and make no standalone-proof write while waiting. Do not select a
weaker proved statement, change the audience, or choose an output format merely
because it is easier to deliver. A complete request that explicitly asks to
proceed needs no redundant confirmation.

This clarification gate is distinct from the mathematical eligibility gate.
Once the requested deliverable is clear, an unresolved proof dependency is a
mathematical failure of eligibility, not a reason to ask the user to choose a
different theorem.

## Enforce The Eligibility Gate

1. Use the exact theorem, proposition, or lemma fixed by the resolved deliverable. It may be the main goal or a genuinely proved intermediate result.
2. Fix all assumptions, conventions, and the intended level of background.
3. Trace the complete proof dependency chain before drafting prose.
4. Generate a review document only when all of the following hold:
   - every local lemma used in the argument has a closed proof;
   - every external result used materially has a verified statement, source, hypotheses, and applicability check;
   - every construction, comparison, and transition needed for the conclusion has been justified;
   - no material step remains `plausible`, `needs verification`, conditional on an unproved local claim, or otherwise unresolved.
5. Treat hypotheses explicitly included in the theorem statement as hypotheses, not gaps. Never promote an unproved local lemma to an assumption merely to pass this gate.
6. If the gate fails, do not write a proof article with a gap notice or review appendix. Return the argument to the research workflow and state briefly that no closed proof of the requested result is ready for exposition.

## Gather The Mathematics

1. Read the selected problem's `research_state.md`, `goal.md`, `progress.md`, `subgoal.md`, latest daily note, and only the memory and reference files relevant to the target.
2. Extract the final logical dependency chain rather than reproducing the chronology of discovery.
3. Use only established ingredients that passed the eligibility gate.
4. Recover the exact statement and hypotheses of every material external result.
5. Omit failed attempts, abandoned plans, confidence labels, and research-process commentary from the proof document.

## Write The Document

If the user identifies a successful earlier manuscript, read it and use its
expository architecture and proof rhythm as the primary model, not just its
section titles. Map each old technical input to the currently audited input;
preserve the mathematical progression without importing withdrawn arguments
or hypotheses. Explain any departure required by the new dependency chain.

Otherwise use [assets/review-proof-template.md](assets/review-proof-template.md)
as the writing skeleton. Establish the outline before drafting prose; do not
retrofit headings onto an unstructured proof. The default order is:

1. **Title**: name the mathematical result, not the project or workflow.
2. **Abstract**: state the problem, exact scope, main result, and proof mechanism
   in one self-contained paragraph.
3. **Introduction**: motivate the result, state the main theorem with all
   hypotheses, explain its significance, give a proof roadmap, and describe the
   organization of the article.
4. **Preliminaries**: fix conventions and notation, give the definitions needed
   later, and state exact external inputs with citations and applicability
   information.
5. **Main proof sections**: divide the argument at genuine mathematical
   interfaces. State each intermediate result before proving or citing it, and
   place every dependency before its first use. End with the proof of the main
   theorem and explicitly close its conclusion.
6. **References**: list only sources actually used, with exact theorem, section,
   chapter, page, or equation locators when available.
7. **Appendix, if necessary**: include auxiliary calculations, long technical
   lemmas, tables, or background that would interrupt the main argument. Do not
   hide a load-bearing step or a theorem needed to understand the main proof in
   an appendix.

## Enforce Type And Interface Discipline

- State complete definitions rather than names or slogans.  When proving
  membership in a category, verify every defining condition instead of only
  the most visible one.
- Keep mathematical types distinct: modules, sheaves, degree-zero complexes,
  derived objects, and objects with additional structure are not interchangeable.
  If $M$ is a module and $M[0]$ is the associated complex, say so explicitly.
- Define the source, target, and ambient category of every pullback,
  restriction, completion, base-change map, comparison map, and structure
  map before using it.  Do not reuse one symbol for different operations in
  different categories without an explicit comparison.
- Work directly in the manuscript's setting when an abstraction is used only
  once and would force the reader to translate all notation back.  Abstract
  first only when the result is genuinely reusable or materially simplifies
  the proof.
- Separate logically different constructions. Verify the underlying object,
  compatibility of its transition maps, additional structures, and specified
  comparison isomorphisms as distinct steps rather than saying that all
  requirements follow at once.
- Name the final constructed object and identify its category.  Give enough
  local descriptions, transition maps, comparison data, and additional structure
  that the stated object can be recovered from the proof.
- Qualify every uniqueness assertion by the data it fixes.  State whether the
  unique isomorphism must preserve a chosen generic identification, local
  identifications, pointing, or natural transformation; do not imply
  uniqueness among arbitrary extensions unless that stronger statement is
  proved.
- Match quantifiers to the covers and families actually used.  If the proof
  uses a finite atlas, index it in the statement, say which constants are
  uniform, and explain where the covers at later stages come from.

## Control Proof Architecture

- Put every lemma or construction before its first use.  If a later result
  constructs an object assumed by an earlier result, split and reorder the
  results rather than leaving a forward dependency.
- Keep proof paragraphs for the mathematical argument.  Put explanations of
  purpose, later use, and the overall route immediately before or after the
  proof, not inside its final deductions.
- Explain positively what each step accomplishes.  Avoid defensive prose
  whose only function is to list things not claimed or not used, except when
  a negative qualification prevents a genuine mathematical misreading.
- Move general auxiliary algebra or geometry into preliminaries only after
  restating it independently of the main proof's temporary notation.  Let the
  main proof cite the result and explain its role.
- Preliminaries may contain original proofs. Place material by its dependency
  role, not by whether it is original or quoted. Give the core definitions
  needed to read the main proof there; introduce enough terminology before
  the introductory theorem to make that statement readable on its own.
- Make subsection boundaries correspond to mathematical interfaces rather
  than the chronology of drafting.  Number substantial reusable
  constructions, merge adjacent thin subsections, and retain a one-result
  subsection only when the whole subsection sets up and proves that central
  interface.
- Replace vague references and workflow shorthand such as `the common
  object`, `the treating step`, `the later step`, or `the preceding
  construction` by defined objects or precise numbered references.  Do not
  invent terminology that can be confused with an established technical
  term.

## Write For A Reader

- Assume the reader knows the mathematical field but has no access to this repository, its filenames, or earlier chat.
- Do not write phrases such as `the memory shows`, `as recorded in the state file`, `our current subgoal`, or `as discussed earlier`.
- Define every project-specific term and symbol in the document. Restate and prove any original local lemma needed by the argument. Cite borrowed definitions at their introduction, even when reproducing their full content; for verified external results, give the exact used statement and applicability bridge rather than an unnecessary replacement proof.
- Explain why each lemma is introduced and how it advances the theorem.
- When citing a result from another specialty, give an applicability bridge:
  state the exact consequence used, match its hypotheses to the present
  objects, and say what it produces here.  If its terminology or local
  geometry is opaque, include a formula or small model that makes the
  operation understandable, but do not reproduce an unrelated cited proof.
- Use paragraphs with one mathematical purpose. Prefer connected prose over a dump of bullets or status records.
- Use displayed equations for structural identities and align multi-step calculations when alignment clarifies the argument.
- Refer to labeled statements instead of vague phrases such as `the previous result` when more than one result could be meant.
- Do not insert research confidence labels into the proof prose.
- Avoid `clearly`, `obviously`, and `standard` when they conceal a nontrivial inference. Give the argument or an exact citation.
- Do not over-explain routine algebra that the intended reader can reconstruct, but never omit a step on which validity depends.

### Balance statement prose and formulas

- Write theorem and lemma statements as complete mathematical sentences:
  introduce the objects, state the hypotheses, and articulate the conclusion.
  Use formulas for the maps, bounds, identities and quantified relations
  themselves, not as substitutes for the sentence's logical structure.
- A request for more formulas is not a request to shorten the proof or remove
  transitions. Replace the verbose expression of a mathematical relation,
  while preserving the explanation of its role. Conversely, adding prose
  does not mean paraphrasing every formula in full. Use an approved example's
  density when available, not a page-count target.
- Apply a necessity test before a definition test: if a standard phrase is
  already concise, do not invent an abbreviation merely to symbolize it.
  Define new notation only when it materially simplifies repeated use.
- Do not turn a one-off local choice or specialization into a numbered
  definition merely because later proofs use it. State it in the surrounding
  setup or hypotheses unless it is a substantive concept used throughout.
- When the user requests a whole-article style correction, check statements
  and transitions throughout the manuscript, not just the last criticized
  section. A balanced sample passage does not certify the rest of the text.

## Audit Before Delivery

Perform a final pass using only the drafted document, without mentally supplying repository context:

1. Can a reader state the exact target and every assumption?
2. Is every symbol defined before use?
3. Can each material claim be traced to a proof, a stated theorem hypothesis, or an exact verified citation?
4. Are definition changes, base changes, limits, completions, descent, and finiteness steps justified where relevant?
5. Does the roadmap match the proof actually written?
6. Does the final paragraph prove exactly the theorem stated at the beginning?
7. Could another capable LLM review the document without receiving any local project file?
8. Is the proof free of unresolved dependencies and hidden appeals to project memory?

If any audit item fails mathematically, do not deliver the document with a caveat. Return to the research workflow until the proof closes. Otherwise revise the exposition until the readability checks pass.

## Perform The Final Language And Notation Pass

After the mathematical audit and before delivery, reread the manuscript from
the viewpoint of an adjacent-specialty reader who has not seen the project.

1. List the technical terms in order of first appearance. Replace unnecessary
   invented terminology with established language. If a local term is genuinely
   useful, define it explicitly at first use and make clear that it is local
   terminology rather than a standard name.
2. List every mathematical symbol in order of first appearance. Check that each
   is defined before use, has an unambiguous type or ambient object, and is not
   silently reused with another meaning.
3. Look for passages a reader could reasonably misread: unclear pronouns,
   forward references, unnamed maps or objects, unexplained changes of setting,
   missing transitions between sections, and statements whose role in the proof
   is not apparent.
4. Repair every such issue in place. Deliver only after a reader can follow the
   terminology, notation, and logical route without project memory or guesswork.

## Delivery And Persistence

Return the proof itself, not a summary of how it was assembled. For persistent project work or a long proof, save it under `<problem_dir>/notes/` with a descriptive dated filename unless the user requests chat-only output or another location.

Do not update research memory merely because existing mathematics was rewritten. If the eligibility audit uncovers a new mathematical issue, record it in the appropriate detailed memory file and do not produce the review proof yet.
