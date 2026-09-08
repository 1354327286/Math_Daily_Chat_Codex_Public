import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.generate_tex_reader import (
    ReaderConverter,
    locate_pdf_reference,
    locate_reference,
    sha256,
    source_tree_sha256,
    tikzcd_to_katex,
    validate_reader_math,
)


class GenerateTexReaderTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name) / "problem"
        self.notes = self.project / "notes"
        self.refs = self.project / "refs"
        source_dir = self.refs / "sources" / "paper"
        paper_dir = self.refs / "papers"
        source_dir.mkdir(parents=True)
        paper_dir.mkdir()
        self.notes.mkdir()
        self.reference = source_dir / "main.tex"
        self.reference.write_text(
            """\\newtheorem{theorem}{Theorem}[section]
\\newtheorem{definition}[theorem]{Definition}
\\begin{document}
\\section{Setup}
\\begin{definition}\\label{def:test}
Test definition.
\\end{definition}
\\end{document}
""",
            encoding="utf-8",
        )
        self.pdf = paper_dir / "paper.pdf"
        self.pdf.write_bytes(b"test PDF placeholder")
        (self.refs / "catalog.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "references": [
                        {
                            "id": "test",
                            "title": "Test paper",
                            "authors": ["A. Author"],
                            "arxiv_id": "2601.00001",
                            "source_url": "https://arxiv.org/abs/2601.00001v1",
                            "tex_main": "sources/paper/main.tex",
                            "txt_fallback": None,
                            "pdf": "papers/paper.pdf",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.source = self.notes / "proof.tex"
        self.source.write_text(
            """\\documentclass{article}
\\newcommand{\\Hart}{\\operatorname{Hart}}
\\newcommand{\\cD}{\\mathcal D}
\\newcommand{\\id}{\\operatorname{id}}
\\title{Closed result}
\\author{}
\\begin{document}
\\maketitle
\\section{Statement}
See \\cite[Definition~1.1]{Ref}.
Compare \\S2 while retaining the symbol $\\Sigma_n$.
\\begin{theorem}[Test theorem]
\\label{thm:main}
The conclusion holds.
\\begin{enumerate}[label=\\textup{(\\roman*)}]
\\item First case.
\\item Second case.
\\end{enumerate}
\\[
\\Hart_{\\cD}\\lhook\\joinrel\\longrightarrow\\id
\\]
\\begin{equation}
x=y
\\label{eq:numbered}
\\end{equation}
See \\eqref{eq:numbered}.
\\end{theorem}
\\begin{proof}
The claim follows.
\\end{proof}
See \\cite[\\href{https://stacks.math.columbia.edu/tag/07NG}{Tag~07NG}]
{MissingRef}.
\\small
\\begin{thebibliography}{9}
\\bibitem{Ref} A. Author, \\emph{Test paper}, arXiv:2601.00001v1,
\\url{https://arxiv.org/abs/2601.00001v1}.
\\end{thebibliography}
\\end{document}
""",
            encoding="utf-8",
        )
        build = self.notes / "build_test"
        build.mkdir()
        (build / "proof.aux").write_text(
            "\\newlabel{thm:main}{{1.1}{1}}\n"
            "\\newlabel{eq:numbered}{{1.2}{1}}\n",
            encoding="utf-8",
        )
        self.output = self.notes / "proof.reader.md"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_generates_derived_reader_without_changing_tex(self):
        before = self.source.read_bytes()
        with mock.patch(
            "scripts.generate_tex_reader.pdf_pages",
            return_value=(
                "We use Definition 1.1 in the introduction.",
                "Definition 1.1. Test definition.",
            ),
        ):
            rendered = ReaderConverter(self.source, self.output, self.project).convert()
        self.assertEqual(self.source.read_bytes(), before)
        self.assertIn(f"source-sha256: {sha256(self.source)}", rendered)
        self.assertIn("do-not-edit: true", rendered)
        self.assertIn("../refs/papers/paper.pdf#page=2", rendered)
        self.assertIn("[local PDF](../refs/papers/paper.pdf)", rendered)
        self.assertIn("[source text](../refs/sources/paper/main.tex)", rendered)
        self.assertIn("[public source](https://arxiv.org/abs/2601.00001v1)", rendered)
        self.assertIn("<!-- reader-statement-start:theorem -->", rendered)
        self.assertIn("<!-- reader-statement-end -->", rendered)
        self.assertIn("<!-- reader-list-start:enumerate:lower-roman-parenthesized -->", rendered)
        self.assertIn("<!-- reader-list-end -->", rendered)
        self.assertIn("<!-- reader-proof-start -->", rendered)
        self.assertIn("<!-- reader-proof-end -->", rendered)
        self.assertIn(r"\operatorname{Hart}_{\mathcal D}\hookrightarrow\operatorname{id}", rendered)
        self.assertNotIn(r"\Hart", rendered)
        self.assertNotIn(r"\lhook\joinrel", rendered)
        self.assertNotIn(r"\cite", rendered)
        self.assertNotIn(r"\small", rendered)
        self.assertIn(r"Compare §2 while retaining the symbol $\Sigma_n$.", rendered)
        self.assertNotIn("§igma", rendered)
        self.assertIn("[MissingRef, Tag 07NG](https://stacks.math.columbia.edu/tag/07NG)", rendered)
        self.assertIn('<a id="eq:numbered"></a>', rendered)
        self.assertIn(r"\tag{1.2}", rendered)
        self.assertIn("[(1.2)](#eq:numbered)", rendered)

    def test_prefers_newest_aux_build(self):
        old_aux = self.notes / "build_test" / "proof.aux"
        new_build = self.notes / "build_new"
        new_build.mkdir(parents=True)
        new_aux = new_build / "proof.aux"
        new_aux.write_text(
            "\\newlabel{thm:main}{{2.4}{1}}\n"
            "\\newlabel{eq:numbered}{{2.5}{1}}\n",
            encoding="utf-8",
        )
        source_time = self.source.stat().st_mtime + 10
        os.utime(self.source, (source_time, source_time))
        os.utime(old_aux, (source_time + 1, source_time + 1))
        os.utime(new_aux, (source_time + 2, source_time + 2))
        rendered = ReaderConverter(self.source, self.output, self.project).convert()
        self.assertIn("#### Theorem 2.4 (Test theorem)", rendered)
        self.assertIn(r"\tag{2.5}", rendered)

    def test_rejects_stale_aux(self):
        aux = self.notes / "build_test" / "proof.aux"
        source_time = self.source.stat().st_mtime + 10
        os.utime(self.source, (source_time, source_time))
        os.utime(aux, (source_time - 1, source_time - 1))
        with self.assertRaisesRegex(ValueError, "stale LaTeX aux file"):
            ReaderConverter(self.source, self.output, self.project)

    def test_discovers_nested_build_artifacts(self):
        nested = self.notes / "build" / "review"
        nested.mkdir(parents=True)
        aux = nested / "proof.aux"
        aux.write_text("\\newlabel{thm:main}{{3.2}{1}}\n", encoding="utf-8")
        aux_time = self.source.stat().st_mtime + 20
        os.utime(aux, (aux_time, aux_time))
        (nested / "proof.pdf").write_bytes(b"PDF placeholder")
        rendered = ReaderConverter(self.source, self.output, self.project).convert()
        self.assertIn("#### Theorem 3.2 (Test theorem)", rendered)
        self.assertIn("[Compiled PDF](build/review/proof.pdf)", rendered)

    def test_preserves_public_urls_without_catalog_match_and_text_accents(self):
        converter = ReaderConverter(self.source, self.output, self.project)
        converter.bibitems["Uncatalogued"] = r'''Ansch\"utz, L\"utkebohmert, IH\'ES.
\url{https://example.org/published-proof}'''
        rendered = "\n".join(converter.reference_section())
        self.assertIn("Anschütz, Lütkebohmert, IHÉS.", rendered)
        self.assertIn("[https://example.org/published-proof](https://example.org/published-proof)", rendered)
        converter.raw = converter.raw.replace(r"\title{Closed result}", r"\title{First and\\Second}")
        self.assertEqual(converter.title(), "First and Second")

    def test_starred_headings_preserve_theorem_counters(self):
        # This replacement document has no compiled labels; discard the old fixture.
        (self.notes / "build_test" / "proof.aux").unlink()
        self.source.write_text(r"""\documentclass{article}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{definition}[theorem]{Definition}
\title{Test}
\begin{document}
\section{First}
\begin{definition}
First definition.
\end{definition}
\subsection*{The two descent
problems}
\section*{Unnumbered discussion}
\begin{definition}
Second definition in the first numbered section.
\end{definition}
\section{Second}
\begin{definition}
First definition in the second numbered section.
\end{definition}
\end{document}
""", encoding="utf-8")
        rendered = ReaderConverter(self.source, self.output, self.project).convert()
        self.assertIn("### The two descent problems", rendered)
        self.assertIn("## Unnumbered discussion", rendered)
        self.assertIn("#### Definition 1.2", rendered)
        self.assertIn("#### Definition 2.1", rendered)
        self.assertNotIn(r"\subsection", rendered)
        self.assertNotIn(r"\section", rendered)

    def test_preserves_numbered_align_and_unlabelled_definitions(self):
        self.source.write_text(r"""\documentclass{article}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{definition}[theorem]{Definition}
\title{Test}
\author{}
\begin{document}
\section{First}
\begin{definition}
First definition.
\end{definition}
\begin{theorem}
\label{thm:main}
Statement.
\end{theorem}
\medskip\noindent\emph{A \v Cech comparison.}
\begin{align}
x&=y\label{eq:first}\\
z&=w\label{eq:second}
\end{align}
\begin{align*}
a&=b\\
 &=c
\end{align*}
\[
x\simeq\RHom_A(M,N)\longrightarrow\RHom_A(N,M).
\]
\section{Second}
\begin{definition}
Second definition.
\end{definition}
\end{document}
""", encoding="utf-8")
        aux = self.notes / "build_test" / "proof.aux"
        aux.write_text(
            "\\newlabel{thm:main}{{1.2}{1}}\n"
            "\\newlabel{eq:first}{{1.1}{1}}\n"
            "\\newlabel{eq:second}{{1.2}{1}}\n",
            encoding="utf-8",
        )
        rendered = ReaderConverter(self.source, self.output, self.project).convert()
        self.assertIn("#### Definition 1.1", rendered)
        self.assertIn("#### Theorem 1.2", rendered)
        self.assertIn("#### Definition 2.1", rendered)
        self.assertIn("*A Čech comparison.*", rendered)
        self.assertNotIn(r"\medskip", rendered)
        self.assertIn(r"\begin{align}", rendered)
        self.assertIn(r"x&=y\tag{1.1}\\", rendered)
        self.assertIn(r"z&=w\tag{1.2}", rendered)
        self.assertIn(r"\begin{align*}", rendered)
        self.assertIn(r"\simeq R\!\operatorname{Hom}", rendered)
        self.assertIn(r"\longrightarrow R\!\operatorname{Hom}", rendered)
        self.output.write_text(rendered, encoding="utf-8")
        self.assertIn("0 errors", validate_reader_math(self.output))

    def test_finds_numbered_reference_environment(self):
        self.assertEqual(locate_reference(self.reference, "Definition~1.1"), "L5-L7")

    def test_finds_pdf_page_for_numbered_locator(self):
        with mock.patch(
            "scripts.generate_tex_reader.pdf_pages",
            return_value=(
                "We use Definition 1.1 in the introduction.",
                "Definition 1.1. Test definition.",
            ),
        ):
            self.assertEqual(locate_pdf_reference(self.pdf, "Definition~1.1"), "page=2")

    def test_prefers_specific_statement_and_actual_section_heading(self):
        with mock.patch(
            "scripts.generate_tex_reader.pdf_pages",
            return_value=(
                "5.1 Analytic objects\nContents",
                "Proposition 2.1. Formal blow-ups.",
                "5.1 Analytic objects\nMain text",
            ),
        ):
            self.assertEqual(locate_pdf_reference(self.pdf, r"\S2, Proposition~2.1"), "page=2")
            self.assertEqual(locate_pdf_reference(self.pdf, "Section~5.1"), "page=3")

    def test_expands_input_and_hashes_the_source_tree(self):
        included = self.notes / "included.tex"
        included.write_text(
            """\\documentclass{article}
\\title{Included result}
\\author{}
\\begin{document}
Included body.
\\end{document}
""",
            encoding="utf-8",
        )
        entry = self.notes / "review.tex"
        entry.write_text("\\input{included.tex}\n", encoding="utf-8")
        rendered = ReaderConverter(entry, self.notes / "review.reader.md", self.project).convert()
        digest = source_tree_sha256(entry, self.project)
        self.assertIn("# Included result", rendered)
        self.assertIn(f"source-sha256: {digest}", rendered)
        self.assertNotEqual(digest, sha256(entry))

    def test_converts_one_row_tikzcd_to_katex_arrows(self):
        source = r'''\begin{tikzcd}[column sep=large]
A \arrow[r,"f","\sim"'] & B & C \arrow[l,"g"',"\sim"] .
\end{tikzcd}'''
        rendered = tikzcd_to_katex(source)
        self.assertNotIn("tikzcd", rendered)
        self.assertIn(r"A \xrightarrow[\sim]{f} B", rendered)
        self.assertIn(r"B \xleftarrow[g]{\sim} C", rendered)

    def test_rejects_tikzcd_that_cannot_be_preserved(self):
        source = "\\begin{tikzcd} A \\\\ B \\end{tikzcd}"
        with self.assertRaisesRegex(ValueError, "one-row tikzcd"):
            tikzcd_to_katex(source)

    def test_full_reader_math_audit_rejects_katex_errors(self):
        invalid = self.notes / "invalid.reader.md"
        invalid.write_text("$$\\begin{tikzcd}A\\end{tikzcd}$$\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "reader math validation failed"):
            validate_reader_math(invalid)


if __name__ == "__main__":
    unittest.main()
