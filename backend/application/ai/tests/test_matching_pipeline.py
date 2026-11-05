import unittest, numpy as np
from unittest.mock import Mock
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from application.ai.pipeline import MatchingPipeline, ResumeAnalysis
from application.ai.matching import FaissRetriever, CrossEncoderReranker
from application.ai.recommendations import JobRecommendationService, _PreparedRecommendationJob
from application.ai.ranking import WeightedFallbackScorer
from application.ai.schemas import JobDocument, MatchFeatures
from jobs.models import Job
from users.models import CandidateProfile, RecruiterProfile

User = get_user_model()

class TestMatchingPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = MatchingPipeline()

    def test_analyze_resume_contract(self):
        text = "Alex Smith\nSummary: Senior Python dev with 6 years experience.\nSkills: Python, Django, PostgreSQL\nExperience: Built APIs.\nEducation: BS CS"
        file_obj = SimpleUploadedFile("resume.txt", text.encode("utf-8"), content_type="text/plain")
        analysis = self.pipeline.analyze_resume(file_obj, "Python Dev", "Req: Python, Django", "Alex Smith")
        self.assertIsInstance(analysis, ResumeAnalysis)
        self.assertGreaterEqual(analysis.match_score, 50)
        self.assertIn("Python", analysis.key_skills)

    def test_faiss_retriever(self):
        r = FaissRetriever(embedding_dim=4)
        vecs = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
        r.add_documents([1, 2], vecs)
        self.assertEqual(r.search(vecs[0], top_k=1)[0].document_id, 1)

    def test_cross_encoder_reranker(self):
        reranker = CrossEncoderReranker(model_name=None, lazy_load=True)
        score = reranker.predict_pair("Python", "Python dev")
        self.assertGreaterEqual(score, 0.0)
        reranked = reranker.rerank("Python", [(1, "Java", 0.5), (2, "Python dev", 0.4)])
        self.assertEqual(len(reranked), 2)

    def test_cross_encoder_scores_pairs_in_one_batch(self):
        reranker = CrossEncoderReranker(model_name=None, lazy_load=True)
        model = Mock()
        model.predict.return_value = [0.0, 2.0]
        reranker._model = model
        reranker._ensure_model = Mock()

        scores = reranker.score_pairs([
            ("job one", "resume one"),
            ("", "resume with blank job"),
            ("job two", "resume two"),
        ])

        self.assertEqual(scores[1], 0.0)
        self.assertAlmostEqual(scores[0], 0.5)
        self.assertGreater(scores[2], scores[0])
        model.predict.assert_called_once_with([
            ["job one", "resume one"],
            ["job two", "resume two"],
        ])

    def test_recommendations_batch_embeddings_and_cross_encoder_pairs(self):
        pipeline = Mock()
        pipeline.embedding.embed_batch.return_value = np.array(
            [[1, 0], [0, 1], [2, 0], [0, 2]], dtype=np.float32
        )
        pipeline.reranker.score_pairs.return_value = [0.25, 0.75]
        service = JobRecommendationService(pipeline=pipeline)
        jobs = [
            Mock(id=1, title="Python Engineer", category="Engineering"),
            Mock(id=2, title="Data Engineer", category="Data"),
        ]
        prepared = [
            _PreparedRecommendationJob(job, "", JobDocument(raw_text=""), f"job-{job.id}")
            for job in jobs
        ]
        service._prepare_job = Mock(side_effect=prepared)
        service._score_prepared_job = Mock(
            side_effect=lambda item, _resume, _resume_embedding, _ctx, job_embedding, cross_score, title_embedding: (
                item.job.id,
                float(job_embedding[0]),
                cross_score,
                float(title_embedding[0]),
            )
        )

        results = service._score_jobs(jobs, "resume text", Mock(), np.zeros(2), {})

        self.assertEqual(results, [(1, 1.0, 0.25, 0.0), (2, 2.0, 0.75, 0.0)])
        pipeline.embedding.embed_batch.assert_called_once_with([
            "job-1",
            "Python Engineer Engineering",
            "job-2",
            "Data Engineer Data",
        ])
        pipeline.reranker.score_pairs.assert_called_once_with([
            ("job-1", "resume text"),
            ("job-2", "resume text"),
        ])

    def test_fallback_scorer(self):
        scorer = WeightedFallbackScorer()
        score = scorer.score(MatchFeatures(semantic_similarity=0.9, skill_overlap_ratio=1.0))
        self.assertGreater(score, 30.0)

    def test_guardrail_ceiling_constant(self):
        from agents.guardrails import HARD_WEEKLY_APPLICATION_CEILING
        self.assertEqual(HARD_WEEKLY_APPLICATION_CEILING, 25, "Weekly application ceiling must be exactly 25")

class TestRecommendations(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.recruiter = User.objects.create_user(username="rec_t", email="r@t.com", password="p", is_recruiter=True, is_candidate=False)
        RecruiterProfile.objects.create(user=self.recruiter, company_name="TestCorp")
        self.candidate = User.objects.create_user(username="cand_t", email="c@t.com", password="p", is_candidate=True, is_recruiter=False)
        CandidateProfile.objects.create(user=self.candidate, skills="Python")

    def test_candidate_access(self):
        self.client.force_authenticate(user=self.candidate)
        res = self.client.get('/api/ai/recommendations/?min_match=0')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_recruiter_forbidden(self):
        self.client.force_authenticate(user=self.recruiter)
        res = self.client.get('/api/ai/recommendations/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_threshold(self):
        self.client.force_authenticate(user=self.candidate)
        self.assertEqual(self.client.get('/api/ai/recommendations/?min_match=-5').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get('/api/ai/recommendations/?min_match=101').status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_coverage_is_field_agnostic(self):
        from application.ai.ranking import profile_coverage, skill_overlap_ratio
        W = lambda core, proj=(): {**{s.lower(): 1.0 for s in core}, **{s.lower(): 0.5 for s in proj}}
        cands = {"ml": W(["Python", "Django", "LangChain", "Machine Learning", "NLP", "TensorFlow", "LLMs", "PostgreSQL", "Docker"], ["React", "Tailwind CSS"]), "fe": W(["React", "JavaScript", "TypeScript", "HTML", "CSS", "Tailwind CSS", "Redux"], ["Node.js"]), "sales": W(["B2B Sales", "Lead Generation", "CRM", "Salesforce", "Negotiation", "Forecasting"]), "hr": W(["Recruitment", "Onboarding", "Payroll", "HRIS", "Employee Relations"])}
        jobs = {"ml": "AI Engineer. Python, LLMs, LangChain, Machine Learning, Docker.", "fe": "Frontend Developer. React, Tailwind CSS, JavaScript, Redux.", "sales": "Sales Manager. B2B Sales, CRM, Salesforce, Lead Generation, Negotiation.", "hr": "HR Executive. Recruitment, Onboarding, Payroll, HRIS."}
        for c, w in cands.items():
            best = max(jobs, key=lambda j: profile_coverage(w, jobs[j]))
            self.assertEqual(best, c)
        self.assertLess(profile_coverage(cands["ml"], jobs["fe"]), 0.35)
        self.assertLess(skill_overlap_ratio(["React"], ["React"]), 1.0)
        self.assertEqual(skill_overlap_ratio(["React"], []), 0.0)
