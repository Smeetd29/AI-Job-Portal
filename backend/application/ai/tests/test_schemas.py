import unittest

from django.test import SimpleTestCase

from application.ai.schemas import JobDocument, MatchFeatures, ResumeDocument
from application.ai.graph import NetworkXSkillGraph


class SchemaTest(SimpleTestCase):
    def test_resume_and_job_documents(self):
        resume = ResumeDocument(raw_text="bio", summary_section="summary", skills_section="python")
        self.assertEqual(resume.raw_text, "bio")
        self.assertEqual(resume.section_texts()["summary"], "summary")

        job = JobDocument(raw_text="", title="Engineer", required_skills_section="python", preferred_skills_section="docker")
        self.assertEqual(job.title, "Engineer")
        self.assertEqual(job.section_texts()["required_skills"], "python")

    def test_match_features_defaults(self):
        features = MatchFeatures(semantic_similarity=0.8)
        self.assertEqual(features.semantic_similarity, 0.8)
        self.assertEqual(features.skill_overlap_ratio, 0.0)


class SkillGraphTest(unittest.TestCase):
    def test_skill_graph_relations_and_export(self):
        graph = NetworkXSkillGraph(populate_defaults=True)
        related = dict(graph.get_related_skills("react", max_hops=1))
        self.assertIn("javascript", related)

        proximity = graph.compute_skill_set_proximity(["django"], ["django"])
        self.assertEqual(proximity, 1.0)

        edge_index, _ = graph.export_edge_index()
        self.assertEqual(edge_index.shape[0], 2)
