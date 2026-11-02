"""Tests for the skill catalog scanner. Run: python -m unittest discover -s tests -v"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import scan_skills  # noqa: E402


def write_skill(root: Path, folder: str, frontmatter: str, body: str = "# Skill\n") -> Path:
    skill_dir = root / folder
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")
    return skill_dir


class FrontmatterTests(unittest.TestCase):
    def test_plain_and_quoted_scalars(self) -> None:
        meta = scan_skills.parse_frontmatter(
            "---\nname: demo\ndescription: 'One line. Use when testing.'\n---\nbody"
        )
        self.assertEqual(meta["name"], "demo")
        self.assertEqual(meta["description"], "One line. Use when testing.")

    def test_folded_block_scalar(self) -> None:
        text = (
            "---\n"
            "name: demo\n"
            "description: >\n"
            "  First part.\n"
            "  Second part.\n"
            "---\n"
        )
        self.assertEqual(scan_skills.parse_frontmatter(text)["description"], "First part. Second part.")

    def test_literal_block_scalar_keeps_newlines(self) -> None:
        text = "---\nname: demo\ndescription: |\n  line one\n  line two\n---\n"
        self.assertEqual(scan_skills.parse_frontmatter(text)["description"], "line one\nline two")

    def test_missing_frontmatter_returns_empty(self) -> None:
        self.assertEqual(scan_skills.parse_frontmatter("# no frontmatter\n"), {})

    def test_double_quote_escapes(self) -> None:
        meta = scan_skills.parse_frontmatter('---\nname: demo\ndescription: "a \\"b\\" c"\n---\n')
        self.assertEqual(meta["description"], 'a "b" c')


class DiscoverTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_finds_nested_skills_and_skips_skill_children(self) -> None:
        write_skill(self.root, "alpha", "name: alpha\ndescription: first")
        write_skill(self.root / "group", "beta", "name: beta\ndescription: second")
        write_skill(self.root / "alpha" / "nested", "gamma", "name: gamma\ndescription: third")

        found = {path.name for path in scan_skills.discover_skills(self.root, max_depth=3)}
        self.assertEqual(found, {"alpha", "beta"})

    def test_first_root_wins_on_duplicate_name(self) -> None:
        high = self.root / "high"
        low = self.root / "low"
        write_skill(high, "demo", "name: demo\ndescription: high priority")
        write_skill(low, "demo", "name: demo\ndescription: low priority")

        skills, warnings = scan_skills.load_catalog([high, low], max_depth=3)
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0]["description"], "high priority")
        self.assertTrue(any("duplicate" in warning for warning in warnings))

    def test_warns_when_name_does_not_match_folder(self) -> None:
        write_skill(self.root, "folder-name", "name: other-name\ndescription: demo")
        _, warnings = scan_skills.load_catalog([self.root], max_depth=3)
        self.assertTrue(any("mismatch" in warning for warning in warnings))

    def test_warns_when_description_missing(self) -> None:
        write_skill(self.root, "demo", "name: demo")
        _, warnings = scan_skills.load_catalog([self.root], max_depth=3)
        self.assertTrue(any("description" in warning for warning in warnings))


class RankingTests(unittest.TestCase):
    def test_ranks_matching_skill_first(self) -> None:
        query = "make a pptx deck from these notes"
        deck = scan_skills.lexical_score(query, "deck-builder", "Build editable pptx slide decks.")
        other = scan_skills.lexical_score(query, "video-tools", "Transcode video files.")
        self.assertGreater(deck, other)

    def test_name_match_outweighs_description_match(self) -> None:
        named = scan_skills.lexical_score("run the audit", "audit", "does things")
        described = scan_skills.lexical_score("run the audit", "other", "audit things")
        self.assertGreater(named, described)

    def test_chinese_bigrams_produce_overlap(self) -> None:
        score = scan_skills.lexical_score("把销售数据做成PPT", "deck-builder", "生成汇报PPT和幻灯片")
        self.assertGreater(score, 0)

    def test_empty_query_scores_zero(self) -> None:
        self.assertEqual(scan_skills.lexical_score("   ", "demo", "description"), 0)


class CliTests(unittest.TestCase):
    def test_json_output_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_skill(root, "demo", "name: demo\ndescription: Use when testing the scanner")

            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = scan_skills.main(["--path", temp, "--no-defaults", "--format", "json"])

            payload = json.loads(buffer.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual([skill["name"] for skill in payload["skills"]], ["demo"])
            self.assertIn("path", payload["skills"][0])

    def test_strict_fails_on_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            write_skill(Path(temp), "demo", "name: demo")
            with redirect_stdout(io.StringIO()):
                code = scan_skills.main(["--path", temp, "--no-defaults", "--strict"])
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
