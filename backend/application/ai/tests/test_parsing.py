from django.test import SimpleTestCase
from application.ai.parsing import (
    TextCleaner, load_text,
    SectionDetector, ResumeParser, JobParser,
    RESUME_CANONICAL_MAP
)
from application.ai.schemas import ResumeDocument, JobDocument


class TextCleanerTest(SimpleTestCase):
    def setUp(self):
        self.c = TextCleaner()

    def test_cleaner_artifacts_and_whitespace(self):
        self.assertEqual(self.c.fix_encoding_artifacts("pro\ufb01le \u2018it\u2019s\u2019 2019\u20132021"), "profile 'it's' 2019-2021")
        self.assertEqual(self.c.normalize_bullets("• item 1\n* item 2\n- item 3"), "- item 1\n- item 2\n- item 3")
        self.assertEqual(self.c.normalize_whitespace("hello    world\n\n\n\ntest"), "hello world\n\ntest")
        self.assertIn("Cleaned", self.c.clean("  pro\ufb01le Cleaned  "))


class IngestionTest(SimpleTestCase):
    def test_load_text(self):
        self.assertEqual(load_text("raw text"), "raw text")
        self.assertEqual(load_text(b"bytes text"), "bytes text")


class SectionDetectorTest(SimpleTestCase):
    def setUp(self):
        self.det = SectionDetector(RESUME_CANONICAL_MAP)

    def test_heading_detection_and_split(self):
        self.assertTrue(self.det.is_heading("WORK EXPERIENCE"))
        self.assertTrue(self.det.is_heading("Skills:"))
        self.assertFalse(self.det.is_heading("This is a long sentence about my experience at company."))
        splits = self.det.split_sections("Some bio\nEXPERIENCE\nDeveloper\nSKILLS\nPython")
        self.assertEqual(splits[0], (None, "Some bio"))
        self.assertEqual(splits[1], ("EXPERIENCE", "Developer"))
        self.assertEqual(splits[2], ("SKILLS", "Python"))


class ResumeParserTest(SimpleTestCase):
    def test_parse_sections(self):
        text = "SUMMARY\nEngineer\nSKILLS\nPython, Django\nEXPERIENCE\nDev at Co\nEDUCATION\nDegree: BS CS"
        doc = ResumeParser().parse(text)
        self.assertIsInstance(doc, ResumeDocument)
        self.assertIn("Engineer", doc.summary_section)
        self.assertIn("Python", doc.skills_section)
        self.assertIn("Dev at Co", doc.experience_section)
        self.assertIn("BS CS", doc.education_section)


class JobParserTest(SimpleTestCase):
    def test_parse_job(self):
        text = "ABOUT THE ROLE\nBuild APIs\nREQUIREMENTS\nPython\nPREFERRED\nDocker"
        doc = JobParser().parse(text, title="Backend Lead")
        self.assertIsInstance(doc, JobDocument)
        self.assertEqual(doc.title, "Backend Lead")
        self.assertIn("Build APIs", doc.summary_section)
        self.assertIn("Python", doc.required_skills_section)
        self.assertIn("Docker", doc.preferred_skills_section)
