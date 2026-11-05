from unittest.mock import patch

from django.test import SimpleTestCase

from application.ai.intelligence import (
    EvidenceClaim,
    ResumeIntelligenceOutput,
    SkillClaim,
    claim_is_grounded,
    build_resume_insights,
    evidence_is_supported,
)


class ResumeIntelligenceTests(SimpleTestCase):
    def test_evidence_matching_ignores_punctuation_and_whitespace(self):
        source = "Built RESTful APIs,\nusing Django and PostgreSQL."
        self.assertTrue(evidence_is_supported(source, "Built RESTful APIs using Django"))
        self.assertFalse(evidence_is_supported(source, "Built AWS services"))
        self.assertFalse(
            claim_is_grounded(source, "Led a 20-person team", "Built RESTful APIs using Django")
        )

    @patch("application.ai.intelligence.settings.ANTHROPIC_API_KEY", "")
    def test_missing_credentials_uses_explicit_deterministic_fallback(self):
        result = build_resume_insights(
            "Skills: Python, Django\nProjects: Built Django REST APIs."
        )

        self.assertEqual(result["generation_status"], "deterministic_fallback")
        self.assertEqual(result["fallback_reason"], "missing_provider_credentials")
        self.assertTrue(result["verified_skills"])
        self.assertIsNone(result["model"])

    @patch("application.ai.intelligence.settings.ANTHROPIC_API_KEY", "configured")
    @patch("application.ai.intelligence._call_anthropic")
    def test_only_evidence_supported_claims_are_returned(self, call_model):
        call_model.return_value = (
            ResumeIntelligenceOutput(
                skills=[
                    SkillClaim(
                        skill="Django",
                        evidence="Built Django REST APIs",
                        category="framework",
                    ),
                    SkillClaim(
                        skill="AWS",
                        evidence="Built Django REST APIs",
                        category="cloud",
                    ),
                ],
                summary_claims=[
                    EvidenceClaim(
                        claim="Built REST APIs with Django.",
                        evidence="Built Django REST APIs",
                    ),
                    EvidenceClaim(
                        claim="Led a large cloud migration.",
                        evidence="AWS migration",
                    ),
                ],
                strengths=[
                    EvidenceClaim(
                        claim="Built REST APIs with Django",
                        evidence="Built Django REST APIs",
                        employer_value="Demonstrates practical backend experience.",
                    ),
                ],
            ),
            {"latency_ms": 5.0, "input_tokens": 10, "output_tokens": 3, "cost_usd": None},
        )

        result = build_resume_insights("Projects:\nBuilt Django REST APIs.")

        self.assertEqual(result["generation_status"], "llm")
        self.assertEqual([skill["skill"] for skill in result["verified_skills"]], ["Django"])
        self.assertEqual(result["professional_summary"], "Built REST APIs with Django.")
        self.assertEqual(len(result["strengths"]), 1)

    @patch("application.ai.intelligence.settings.ANTHROPIC_API_KEY", "configured")
    @patch("application.ai.intelligence._call_anthropic")
    def test_provider_context_omits_resume_header_and_contact_details(self, call_model):
        call_model.return_value = (
            ResumeIntelligenceOutput(),
            {"latency_ms": 5.0, "input_tokens": 10, "output_tokens": 3, "cost_usd": None},
        )
        build_resume_insights(
            "Jane Candidate\nEmail: jane@example.com\n"
            "Skills:\nPython\nProjects:\nBuilt APIs with Python."
        )

        model_resume_context = call_model.call_args.args[0]
        self.assertNotIn("Jane Candidate", model_resume_context)
        self.assertNotIn("jane@example.com", model_resume_context)
