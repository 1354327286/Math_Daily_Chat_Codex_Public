import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class DetachedWorkflowPolicyTests(unittest.TestCase):
    def test_root_policy_preserves_daily_shorthand_but_gates_detached_work(self):
        agents = read("AGENTS.md")
        compact = " ".join(agents.split())
        self.assertIn("## Detached Work Boundary", agents)
        self.assertIn("Ordinary mathematical discussion may resolve informal pronouns", compact)
        self.assertIn("ask the user for the missing specification", compact)
        self.assertIn("make no detached-work write while waiting", compact)
        self.assertIn("needs no redundant confirmation", compact)

    def test_pro_export_requires_authorized_resolved_specification(self):
        skill = read("skills/pro-research-handoff/SKILL.md")
        script = read("scripts/pro_handoff.py")
        self.assertIn("## Resolve the handoff specification before writing", skill)
        self.assertIn("Do not create a provisional request", skill)
        self.assertIn("--user-authorized", skill)
        self.assertIn("if not user_authorized:", script)
        self.assertIn('"user_authorized": True', script)

    def test_standalone_and_delegated_work_ask_instead_of_switching_targets(self):
        proof = read("skills/write-self-contained-math-proof/SKILL.md")
        recursive = read("skills/recursive-proving/SKILL.md")
        self.assertIn("## Resolve the standalone deliverable", proof)
        self.assertIn("make no standalone-proof write while waiting", proof)
        self.assertIn("ask a focused question before spawning anything", recursive)
        self.assertIn("do not silently continue sequentially instead", recursive)

    def test_transport_and_manuscript_work_have_specialized_gates(self):
        bundle = read("docs/problem_bundle.md")
        review = read("skills/review-latex-math-manuscript/SKILL.md")
        self.assertIn("## Clarify the transport operation", bundle)
        self.assertIn("Do not create an archive", bundle)
        self.assertIn("If more than one", review)
        self.assertIn("before compiling, generating files, or editing", review)

    def test_skill_ui_prompts_name_the_skill(self):
        proof_ui = read("skills/write-self-contained-math-proof/agents/openai.yaml")
        review_ui = read("skills/review-latex-math-manuscript/agents/openai.yaml")
        self.assertIn("$write-self-contained-math-proof", proof_ui)
        self.assertIn("$review-latex-math-manuscript", review_ui)


if __name__ == "__main__":
    unittest.main()
