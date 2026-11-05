from django.test import SimpleTestCase

from application.ai.extraction import (
    SkillExtractionPipeline, SkillNormalizer, SeniorityExtractor, ExperienceExtractor,
    EducationExtractor, match_skill
)

class TestSkillExtractionBulletList(SimpleTestCase):

    def setUp(self):
        self.pipeline = SkillExtractionPipeline()

    def test_simple_bullet_list(self):
        text = (
            "- Python\n"
            "- Django\n"
            "- PostgreSQL\n"
        )
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("python", result_lower)
        self.assertIn("django", result_lower)
        self.assertIn("postgresql", result_lower)

    def test_unicode_bullet_list(self):
        text = (
            "\u2022 React\n"
            "\u25E6 TypeScript\n"
            "\u2043 Node.js\n"
        )
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("react", result_lower)
        self.assertIn("typescript", result_lower)
        self.assertIn("node.js", result_lower)

    def test_asterisk_bullet_list(self):
        text = "* Docker\n* Kubernetes\n* Terraform\n"
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("docker", result_lower)
        self.assertIn("kubernetes", result_lower)
        self.assertIn("terraform", result_lower)

    def test_stop_words_not_extracted_as_bullets(self):
        text = "- experience\n- skills\n- Python\n"
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertNotIn("experience", result_lower)
        self.assertNotIn("skills", result_lower)
        self.assertIn("python", result_lower)

    def test_single_item_returns_list(self):
        result = self.pipeline.extract("- FastAPI")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].lower(), "fastapi")

class TestSkillExtractionCommaList(SimpleTestCase):

    def setUp(self):
        self.pipeline = SkillExtractionPipeline()

    def test_simple_comma_list(self):
        result_lower = {s.lower() for s in self.pipeline.extract(
            "Python, Django, PostgreSQL, Docker"
        )}
        self.assertIn("python", result_lower)
        self.assertIn("django", result_lower)
        self.assertIn("postgresql", result_lower)
        self.assertIn("docker", result_lower)

    def test_prose_sentence_not_split(self):
        text = "We work with Python and build scalable systems."
        result = self.pipeline.extract(text)
        result_lower = {s.lower() for s in result}
        self.assertNotIn("systems", result_lower)
        self.assertNotIn("scalable", result_lower)

    def test_slash_separated_list(self):
        result_lower = {s.lower() for s in self.pipeline.extract("Linux/macOS/Windows")}
        self.assertIn("linux", result_lower)
        self.assertIn("macos", result_lower)
        self.assertIn("windows", result_lower)

    def test_pipe_separated_list(self):
        result_lower = {s.lower() for s in self.pipeline.extract("Git | GitHub | GitLab")}
        self.assertIn("git", result_lower)
        self.assertIn("github", result_lower)
        self.assertIn("gitlab", result_lower)

class TestSkillExtractionLabelPrefix(SimpleTestCase):

    def setUp(self):
        self.pipeline = SkillExtractionPipeline()

    def test_programming_languages_label(self):
        result_lower = {s.lower() for s in self.pipeline.extract(
            "Programming Languages: Python, Go, Rust"
        )}
        self.assertIn("python", result_lower)
        self.assertIn("go", result_lower)
        self.assertIn("rust", result_lower)

    def test_frameworks_label(self):
        result_lower = {s.lower() for s in self.pipeline.extract(
            "Frameworks: Django, FastAPI, Flask"
        )}
        self.assertIn("django", result_lower)
        self.assertIn("fastapi", result_lower)
        self.assertIn("flask", result_lower)

    def test_multiple_label_lines(self):
        text = (
            "Languages: Python, TypeScript\n"
            "Databases: PostgreSQL, Redis\n"
        )
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("python", result_lower)
        self.assertIn("typescript", result_lower)
        self.assertIn("postgresql", result_lower)
        self.assertIn("redis", result_lower)

    def test_label_with_ampersand(self):
        result_lower = {s.lower() for s in self.pipeline.extract(
            "Tools & Technologies: Docker, Terraform, Ansible"
        )}
        self.assertIn("docker", result_lower)
        self.assertIn("terraform", result_lower)
        self.assertIn("ansible", result_lower)

class TestSkillExtractionProseFallback(SimpleTestCase):

    def setUp(self):
        self.pipeline = SkillExtractionPipeline()

    def test_using_trigger(self):
        text = "Join our team to build scalable APIs using Django REST Framework and PostgreSQL."
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("django rest framework", result_lower,
                      msg=f"Multi-word not found in {result_lower}")
        self.assertIn("postgresql", result_lower)

    def test_experience_with_trigger(self):
        text = "You have experience with Kubernetes, Terraform, and AWS."
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("kubernetes", result_lower)
        self.assertIn("terraform", result_lower)
        self.assertIn("aws", result_lower)

    def test_knowledge_of_trigger(self):
        text = "Strong knowledge of React, TypeScript and GraphQL required."
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("react", result_lower)
        self.assertIn("typescript", result_lower)
        self.assertIn("graphql", result_lower)

    def test_generic_words_not_extracted(self):
        text = (
            "Work with our team to build scalable systems "
            "and collaborate with developers."
        )
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        forbidden = {"team", "scalable", "systems", "developers", "collaborate"}
        intersection = forbidden & result_lower
        self.assertFalse(intersection,
                         msg=f"False positives: {intersection}")

    def test_no_trigger_phrase_returns_empty(self):
        text = "We are a fast-growing startup looking for talented engineers."
        result = self.pipeline.extract(text)
        self.assertEqual(result, [])

    def test_empty_input_returns_empty(self):
        self.assertEqual(self.pipeline.extract(""), [])
        self.assertEqual(self.pipeline.extract("   \n  "), [])

    def test_extract_from_prose_direct(self):
        text = "Proficiency in TensorFlow and PyTorch is required."
        result_lower = {s.lower() for s in self.pipeline.extract_from_prose(text)}
        self.assertIn("tensorflow", result_lower)
        self.assertIn("pytorch", result_lower)

class TestSkillExtractionMultiWord(SimpleTestCase):

    def setUp(self):
        self.pipeline = SkillExtractionPipeline()

    def test_django_rest_framework_preserved_in_prose(self):
        text = "Experience with Django REST Framework and PostgreSQL."
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("django rest framework", result_lower,
                      msg=f"Multi-word split; got: {result_lower}")

    def test_machine_learning_preserved_in_prose(self):
        text = "Expertise in machine learning and deep learning."
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("machine learning", result_lower)
        self.assertIn("deep learning", result_lower)

    def test_multi_word_in_comma_list(self):
        text = "Django REST Framework, FastAPI, Flask"
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("django rest framework", result_lower,
                      msg=f"Multi-word split in comma list; got: {result_lower}")

    def test_multi_word_in_bullet_list(self):
        text = "- Django REST Framework\n- machine learning\n- deep learning\n"
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("django rest framework", result_lower)
        self.assertIn("machine learning", result_lower)

class TestSkillExtractionModePriority(SimpleTestCase):

    def setUp(self):
        self.pipeline = SkillExtractionPipeline()

    def test_structured_result_suppresses_prose(self):
        text = (
            "Python, Django, PostgreSQL\n"
            "Join our team using various tools and systems."
        )
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("python", result_lower)
        self.assertIn("django", result_lower)
        self.assertNotIn("systems", result_lower)
        self.assertNotIn("tools", result_lower)

    def test_empty_section_triggers_prose_fallback(self):
        text = "We are looking for experience with FastAPI and Redis."
        result_lower = {s.lower() for s in self.pipeline.extract(text)}
        self.assertIn("fastapi", result_lower)
        self.assertIn("redis", result_lower)

class TestSkillExtractionDeduplication(SimpleTestCase):

    def setUp(self):
        self.pipeline = SkillExtractionPipeline()

    def test_duplicate_same_case(self):
        text = "Python, Django, Python, Flask"
        result = self.pipeline.extract(text)
        result_lower = [s.lower() for s in result]
        self.assertEqual(result_lower.count("python"), 1)

    def test_duplicate_different_case(self):
        text = "python, Python, PYTHON, Django"
        result = self.pipeline.extract(text)
        result_lower = [s.lower() for s in result]
        self.assertEqual(result_lower.count("python"), 1)
        self.assertEqual(result_lower.count("django"), 1)

class TestRegressionMatching(SimpleTestCase):
    def test_seniority_not_principal_from_reception_staff(self):
        label = SeniorityExtractor().extract("Mediqueue - Medical Token System. Workflows for reception staff and doctors.", 0.0)
        self.assertNotEqual(label, "principal")

    def test_experience_ignores_future_dates(self):
        years = ExperienceExtractor().extract("College of Engineering 2024 – 2028\nB.Tech in CS")
        self.assertIsNone(years)

    def test_education_extracts_btech(self):
        level = EducationExtractor().extract("Dwarkadas Sanghavi College 2024 – 2028\nB.Tech in Computer Science")
        self.assertEqual(level, 2)

    def test_skill_matcher_compound(self):
        matched, _ = match_skill("TensorFlow or PyTorch", {"python", "tensorflow"})
        self.assertTrue(matched)

    def test_skill_aliases_normalize_to_one_canonical_value(self):
        normalizer = SkillNormalizer()
        self.assertEqual(
            normalizer.normalize_list(
                ["js", "JavaScript", "k8s", "Kubernetes", "postgres", "PostgreSQL"]
            ),
            ["JavaScript", "Kubernetes", "PostgreSQL"],
        )

    def test_skill_matcher_rejects_misleading_near_matches(self):
        self.assertEqual(match_skill("Java", {"javascript"}), (False, None))
        self.assertEqual(match_skill("JavaScript", {"java"}), (False, None))
        self.assertEqual(match_skill("AWS", {"AWS S3"}), (False, None))

    def test_skill_matcher_does_not_count_negated_skill_evidence(self):
        extractor = SkillExtractionPipeline()
        negated_skills = extractor.extract("Python, but no Django experience")
        self.assertIn("Python", negated_skills)
        self.assertFalse(match_skill("Django", {skill.lower() for skill in negated_skills})[0])

from application.ai.parsing import (
    TextCleaner, load_text,
    SectionDetector, ResumeParser, JobParser,
    RESUME_CANONICAL_MAP
)
from application.ai.schemas import ResumeDocument, JobDocument, MatchFeatures
from application.ai.graph import NetworkXSkillGraph

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

class SchemaTest(SimpleTestCase):
    def test_resume_and_job_documents(self):
        r = ResumeDocument(raw_text="bio", summary_section="summary", skills_section="python")
        self.assertEqual(r.raw_text, "bio")
        self.assertEqual(r.section_texts()["summary"], "summary")

        j = JobDocument(raw_text="", title="Engineer", required_skills_section="python", preferred_skills_section="docker")
        self.assertEqual(j.title, "Engineer")
        self.assertEqual(j.section_texts()["required_skills"], "python")

    def test_match_features_defaults(self):
        f = MatchFeatures(semantic_similarity=0.8)
        self.assertEqual(f.semantic_similarity, 0.8)
        self.assertEqual(f.skill_overlap_ratio, 0.0)

class SkillGraphTest(SimpleTestCase):
    def test_skill_graph_relations_and_export(self):
        g = NetworkXSkillGraph(populate_defaults=True)
        related = dict(g.get_related_skills("react", max_hops=1))
        self.assertIn("javascript", related)

        prox = g.compute_skill_set_proximity(["django"], ["django"])
        self.assertEqual(prox, 1.0)

        edge_index, nodes = g.export_edge_index()
        self.assertEqual(edge_index.shape[0], 2)
