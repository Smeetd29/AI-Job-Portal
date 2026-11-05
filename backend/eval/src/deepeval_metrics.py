from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    GEval,
)
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, LLMTestCaseParams


class MockOfflineJudge(DeepEvalBaseLLM):
    """
    Offline/Mock LLM Judge for DeepEval metrics used EXCLUSIVELY in unit tests.
    This mock verifies API integration plumbing without calling paid external APIs.
    It must NEVER be presented as real evaluation evidence.
    """

    def __init__(self, model_name: str = "mock-judge"):
        self.model_name = model_name
        super().__init__(model_name)

    def load_model(self) -> Any:
        return None

    def generate(self, prompt: str) -> str:
        # Return a valid structured JSON score strictly for unit test assertion verification
        return '{"score": 1.0, "reason": "Test mock score for harness plumbing verification only."}'

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        return self.model_name


@dataclass
class DeepEvalCaseResult:
    case_id: str
    faithfulness_score: Optional[float]
    answer_relevancy_score: Optional[float]
    geval_score: Optional[float]
    passed: bool
    judge_mode: str  # "online_llm", "blocked_missing_credentials", or "test_mock"
    status: str      # "COMPLETED", "BLOCKED", "ERROR"
    reasons: Dict[str, str] = field(default_factory=dict)


def is_llm_api_configured() -> bool:
    """Checks if an external LLM judge API key is present in environment."""
    return bool(
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
    )


def build_deepeval_test_case(
    input_text: str,
    actual_output: str,
    expected_output: Optional[str] = None,
    retrieval_context: Optional[List[str]] = None,
    context: Optional[List[str]] = None,
) -> LLMTestCase:
    """Builds a verified DeepEval LLMTestCase instance."""
    return LLMTestCase(
        input=input_text,
        actual_output=actual_output,
        expected_output=expected_output,
        retrieval_context=retrieval_context or [],
        context=context or retrieval_context or [],
    )


class DeepEvalMetricHarness:
    """
    Wraps DeepEval metrics with strict credential validation.
    When API credentials are not configured, marks evaluation as BLOCKED
    rather than fabricating scores or presenting mocks as genuine results.
    """

    def __init__(
        self,
        faithfulness_threshold: float = 0.80,
        relevancy_threshold: float = 0.75,
        geval_threshold: float = 0.75,
        model_override: Optional[Any] = None,
        allow_test_mock: bool = False,
    ):
        self.faithfulness_threshold = faithfulness_threshold
        self.relevancy_threshold = relevancy_threshold
        self.geval_threshold = geval_threshold
        self.allow_test_mock = allow_test_mock

        if is_llm_api_configured() and model_override != "mock":
            self.is_online = True
            self.judge_model = model_override
            self.judge_mode = "online_llm"
        elif self.allow_test_mock:
            self.is_online = True
            self.judge_model = MockOfflineJudge()
            self.judge_mode = "test_mock"
        else:
            self.is_online = False
            self.judge_model = None
            self.judge_mode = "blocked_missing_credentials"

        # Initialize metrics if online or in mock test mode
        if self.is_online:
            self.faithfulness_metric = FaithfulnessMetric(
                threshold=self.faithfulness_threshold,
                model=self.judge_model,
            )
            self.relevancy_metric = AnswerRelevancyMetric(
                threshold=self.relevancy_threshold,
                model=self.judge_model,
            )
            self.geval_metric = GEval(
                name="Recommendation & Summary Quality",
                criteria="Evaluate whether the generated explanation or summary is faithful to the context and relevant to the task.",
                evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
                threshold=self.geval_threshold,
                model=self.judge_model,
            )
        else:
            self.faithfulness_metric = None
            self.relevancy_metric = None
            self.geval_metric = None

    def evaluate_test_case(
        self,
        case_id: str,
        test_case: LLMTestCase,
    ) -> DeepEvalCaseResult:
        if not self.is_online:
            return DeepEvalCaseResult(
                case_id=case_id,
                faithfulness_score=None,
                answer_relevancy_score=None,
                geval_score=None,
                passed=False,
                judge_mode="blocked_missing_credentials",
                status="BLOCKED",
                reasons={
                    "status": "BLOCKED: External LLM API credentials (OPENAI_API_KEY) are not configured. "
                              "Per strict evaluation requirements, mock scores are not substituted for genuine LLM evaluation."
                },
            )

        # Real DeepEval execution (or test mock if explicitly enabled in unit tests)
        reasons = {}
        try:
            self.faithfulness_metric.measure(test_case)
            faith_score = float(self.faithfulness_metric.score if self.faithfulness_metric.score is not None else 0.0)
            reasons["faithfulness"] = str(self.faithfulness_metric.reason or "")
        except Exception as exc:
            faith_score = 0.0
            reasons["faithfulness"] = f"Error: {exc}"

        try:
            self.relevancy_metric.measure(test_case)
            rel_score = float(self.relevancy_metric.score if self.relevancy_metric.score is not None else 0.0)
            reasons["relevancy"] = str(self.relevancy_metric.reason or "")
        except Exception as exc:
            rel_score = 0.0
            reasons["relevancy"] = f"Error: {exc}"

        try:
            self.geval_metric.measure(test_case)
            geval_score = float(self.geval_metric.score if self.geval_metric.score is not None else 0.0)
            reasons["geval"] = str(self.geval_metric.reason or "")
        except Exception as exc:
            geval_score = 0.0
            reasons["geval"] = f"Error: {exc}"

        passed = (
            faith_score >= self.faithfulness_threshold
            and rel_score >= self.relevancy_threshold
            and geval_score >= self.geval_threshold
        )

        return DeepEvalCaseResult(
            case_id=case_id,
            faithfulness_score=faith_score,
            answer_relevancy_score=rel_score,
            geval_score=geval_score,
            passed=passed,
            judge_mode=self.judge_mode,
            status="COMPLETED",
            reasons=reasons,
        )


STOPWORDS = {
    "with", "from", "that", "this", "have", "been", "were", "what", "when",
    "where", "which", "will", "would", "could", "should", "their", "there",
    "these", "those", "about", "above", "after", "again", "against", "among",
    "because", "before", "below", "between", "both", "during", "each", "further",
    "into", "more", "most", "other", "some", "such", "than", "then", "through",
    "under", "until", "very", "while", "also", "only", "many", "much",
}


class DeterministicGroundednessChecker:
    """
    Evaluates factual consistency, entity coverage, and token groundedness
    without invoking an external LLM judge. Formulas are strictly deterministic.
    """

    @staticmethod
    def compute_context_groundedness(output_text: str, context_texts: List[str]) -> Tuple[float, str]:
        """Calculates substantive content-term overlap ratio against supplied source context."""
        context_str = " ".join(context_texts).lower()
        if not context_str:
            return 1.0, "No context provided."

        words = [
            w.lower() for w in re.findall(r"\b[A-Za-z0-9_+#.-]+\b", output_text)
            if len(w) > 3 and w.lower() not in STOPWORDS
        ]
        if not words:
            return 0.0, "Output text contains no extractable content terms."

        supported = sum(1 for w in words if w in context_str)
        ratio = supported / float(len(words))
        return round(ratio, 4), f"{supported}/{len(words)} substantive content terms found in context."

    @staticmethod
    def compute_query_term_coverage(output_text: str, query_text: str) -> Tuple[float, str]:
        """Calculates fraction of substantive query terms addressed in the generated output."""
        query_words = [
            w.lower() for w in re.findall(r"\b[A-Za-z0-9_+#.-]+\b", query_text)
            if len(w) > 3 and w.lower() not in STOPWORDS
        ]
        if not query_words:
            return 1.0, "No substantive query terms."

        output_lower = output_text.lower()
        matched = sum(1 for w in query_words if w in output_lower)
        ratio = matched / float(len(query_words))
        return round(ratio, 4), f"{matched}/{len(query_words)} query terms addressed in output."
