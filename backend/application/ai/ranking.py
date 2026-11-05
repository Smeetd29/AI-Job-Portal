from __future__ import annotations

import json
import logging
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set
import numpy as np

from application.ai.extraction import SENIORITY_ORDINAL, evaluate_skill_coverage
from application.ai.schemas import JobDocument, MatchFeatures, ResumeDocument

def profile_coverage(weights, job_text):
    t = job_text.lower()
    tot = min(sum(weights.values()) or 1.0, 10.0)
    hit = sum(w for s, w in weights.items() if re.search(r"(?<![\w.])" + re.escape(s) + r"(?![\w])", t))
    return min(1.0, hit / tot / 0.3)

def semantic_similarity(resume_embedding: np.ndarray, job_embedding: np.ndarray) -> float:
    score = float(np.dot(resume_embedding, job_embedding))
    return max(0.0, min(1.0, (score - 0.1) / 0.5))

def skill_overlap_ratio(
    resume_skills: List[str],
    required_skills: List[str],
    embedder: Optional[Any] = None,
) -> float:
    if not required_skills:
        return 0.0
    ratio, _, _ = evaluate_skill_coverage(required_skills, resume_skills, embedder=embedder)
    return ratio * len(required_skills) / (len(required_skills) + 2)

def skill_coverage_weighted(
    resume_skills: List[str],
    required_skills: List[str],
    preferred_skills: List[str],
    required_weight: float = 0.75,
    preferred_weight: float = 0.25,
    embedder: Optional[Any] = None,
) -> float:
    req_score = skill_overlap_ratio(resume_skills, required_skills, embedder=embedder)
    pref_score = skill_overlap_ratio(resume_skills, preferred_skills, embedder=embedder) if preferred_skills else req_score
    return req_score * required_weight + pref_score * preferred_weight

def experience_match(
    candidate_years: Optional[float],
    required_years: Optional[float],
) -> float:
    if required_years is None:
        if candidate_years is not None:
            return min(1.0, 0.85 + 0.15 * min(candidate_years, 2.0) / 2.0)
        return 0.85
    if candidate_years is None:
        return 0.5
    if required_years <= 0:
        return 1.0
    ratio = candidate_years / required_years
    if ratio >= 1.0:
        return min(1.0, 0.9 + 0.1 * min(ratio, 2.0) / 2.0)
    return max(0.0, ratio * 0.9)

def education_match(
    candidate_degree: Optional[int],
    required_degree: Optional[int],
) -> float:
    if required_degree is None:
        return 1.0 if candidate_degree is not None else 0.85
    if candidate_degree is None:
        return 0.5
    diff = candidate_degree - required_degree
    if diff >= 0:
        return 1.0
    return max(0.0, 1.0 + diff * 0.25)

def seniority_match(
    candidate_seniority: str,
    required_seniority: str,
) -> float:
    if not candidate_seniority or not required_seniority:
        return 0.5
    cand_ord = SENIORITY_ORDINAL.get(candidate_seniority.lower(), 0)
    req_ord = SENIORITY_ORDINAL.get(required_seniority.lower(), 0)
    if cand_ord == 0 or req_ord == 0:
        return 0.5
    distance = abs(cand_ord - req_ord)
    if distance == 0:
        return 1.0
    return max(0.1, 0.7 ** distance)

def normalize_cross_encoder_score(raw_score: float) -> float:
    return 1.0 / (1.0 + math.exp(-raw_score))

def title_similarity(
    resume_summary_embedding: Optional[np.ndarray],
    job_title_embedding: Optional[np.ndarray],
) -> float:
    if resume_summary_embedding is None or job_title_embedding is None:
        return 0.5
    score = float(np.dot(resume_summary_embedding, job_title_embedding))
    return max(0.0, min(1.0, (score + 1.0) / 2.0))

def graph_skill_coverage(
    resume_skills: List[str],
    required_skills: List[str],
    graph: Optional[Any] = None,
    threshold: float = 0.5,
) -> float:
    if not required_skills:
        return 1.0
    if graph is not None and hasattr(graph, "compute_skill_set_proximity"):
        return float(graph.compute_skill_set_proximity(resume_skills, required_skills))
    resume_lower: Set[str] = {s.lower() for s in resume_skills}
    overlap = len(resume_lower & {s.lower() for s in required_skills})
    return overlap / len(required_skills)

def section_coverage(
    resume_sections: dict,
    job_sections: dict,
) -> float:
    if not job_sections:
        return 0.5
    section_mapping = {
        "responsibilities": ["experience", "projects"],
        "required_skills": ["skills"],
        "preferred_skills": ["skills"],
        "qualifications": ["education", "certifications"],
        "experience_requirements": ["experience"],
        "summary": ["summary"],
    }
    covered = 0
    total = 0
    for job_key, job_text in job_sections.items():
        if not job_text or not job_text.strip():
            continue
        total += 1
        resume_keys = section_mapping.get(job_key, [job_key])
        for rk in resume_keys:
            if rk in resume_sections and resume_sections[rk] and resume_sections[rk].strip():
                covered += 1
                break
    if total == 0:
        return 0.5
    return covered / total

class FeatureExtractor:

    def __init__(
        self,
        graph: Optional[Any] = None,
        graph_threshold: float = 0.5,
        embedder: Optional[Any] = None,
    ) -> None:
        self._graph = graph
        self._graph_threshold = graph_threshold
        self._embedder = embedder

    def extract(
        self,
        resume_doc: ResumeDocument,
        job_doc: JobDocument,
        resume_embedding: Optional[np.ndarray] = None,
        job_embedding: Optional[np.ndarray] = None,
        resume_summary_embedding: Optional[np.ndarray] = None,
        job_title_embedding: Optional[np.ndarray] = None,
        cross_encoder_score: float = 0.0,
    ) -> MatchFeatures:
        return MatchFeatures(
            semantic_similarity=semantic_similarity(
                resume_embedding, job_embedding,
            ) if resume_embedding is not None and job_embedding is not None else 0.5,
            skill_overlap_ratio=skill_overlap_ratio(
                resume_doc.skill_candidates,
                job_doc.required_skill_candidates,
                embedder=self._embedder,
            ),
            skill_coverage_weighted=skill_coverage_weighted(
                resume_doc.skill_candidates,
                job_doc.required_skill_candidates,
                job_doc.preferred_skill_candidates,
                embedder=self._embedder,
            ),
            experience_match=experience_match(
                resume_doc.years_experience,
                job_doc.required_years,
            ),
            education_match=education_match(
                resume_doc.degree_level,
                job_doc.required_degree_level,
            ),
            seniority_match=seniority_match(
                resume_doc.seniority_label,
                job_doc.seniority_label,
            ),
            cross_encoder_score=normalize_cross_encoder_score(cross_encoder_score),
            title_similarity=title_similarity(
                resume_summary_embedding,
                job_title_embedding,
            ),
            graph_skill_coverage=graph_skill_coverage(
                resume_doc.skill_candidates,
                job_doc.required_skill_candidates,
                graph=self._graph,
                threshold=self._graph_threshold,
            ),
            section_coverage=section_coverage(
                resume_doc.section_texts(),
                job_doc.section_texts(),
            ),
            strict_seniority_match=self._strict_seniority(resume_doc, job_doc),
            experience_gap=self._experience_gap(resume_doc, job_doc),
            required_skill_coverage=self._required_skill_coverage(resume_doc, job_doc),
            title_keyword_overlap=self._title_keyword_overlap(resume_doc, job_doc),
            signed_seniority_gap=self._signed_seniority_gap(resume_doc, job_doc),
            years_gap=self._years_gap(resume_doc, job_doc),
            must_have_skill_coverage=self._must_have_skill_coverage(resume_doc, job_doc),
            nice_to_have_skill_coverage=self._nice_to_have_skill_coverage(resume_doc, job_doc),
            role_family_match=self._role_family_match(resume_doc, job_doc),
        )

    def _signed_seniority_gap(self, resume_doc: ResumeDocument, job_doc: JobDocument) -> float:
        c_ord = SENIORITY_ORDINAL.get((resume_doc.seniority_label or "").lower(), 2)
        j_ord = SENIORITY_ORDINAL.get((job_doc.seniority_label or "").lower(), 2)
        return float(c_ord - j_ord) / 4.0

    def _years_gap(self, resume_doc: ResumeDocument, job_doc: JobDocument) -> float:
        c_yrs = resume_doc.years_experience or 0.0
        j_yrs = job_doc.required_years or 0.0
        return max(-1.0, min(1.0, float(c_yrs - j_yrs) / 10.0))

    def _must_have_skill_coverage(self, resume_doc: ResumeDocument, job_doc: JobDocument) -> float:
        req = job_doc.required_skill_candidates
        if not req:
            return 1.0
        c_skills = {s.lower() for s in resume_doc.skill_candidates}
        hits = sum(1 for s in req if s.lower() in c_skills or any(c in s.lower() for c in c_skills))
        return hits / float(len(req))

    def _nice_to_have_skill_coverage(self, resume_doc: ResumeDocument, job_doc: JobDocument) -> float:
        pref = job_doc.preferred_skill_candidates
        if not pref:
            return 1.0
        c_skills = {s.lower() for s in resume_doc.skill_candidates}
        hits = sum(1 for s in pref if s.lower() in c_skills or any(c in s.lower() for c in c_skills))
        return hits / float(len(pref))

    def _role_family_match(self, resume_doc: ResumeDocument, job_doc: JobDocument) -> float:
        j_title_lower = (job_doc.title or "").lower()
        r_text_lower = (resume_doc.clean_text or "").lower()
        # Common domain roots
        matches = 0
        for domain in ["frontend", "backend", "data", "machine learning", "devops", "cloud", "qa", "security", "mobile", "full stack"]:
            if domain in j_title_lower and domain in r_text_lower:
                matches += 1
        return 1.0 if matches > 0 else 0.5

    def _strict_seniority(self, resume_doc: ResumeDocument, job_doc: JobDocument) -> float:
        c_ord = SENIORITY_ORDINAL.get((resume_doc.seniority_label or "").lower(), 1)
        j_ord = SENIORITY_ORDINAL.get((job_doc.seniority_label or "").lower(), 1)
        if c_ord < j_ord and (j_ord - c_ord) >= 2:
            return 0.0
        elif c_ord > j_ord and (c_ord - j_ord) >= 2:
            return 0.2
        elif c_ord == j_ord:
            return 1.0
        return 0.7

    def _experience_gap(self, resume_doc: ResumeDocument, job_doc: JobDocument) -> float:
        c_yrs = resume_doc.years_experience or 0.0
        j_yrs = job_doc.required_years or 0.0
        gap = c_yrs - j_yrs
        return max(0.0, min(1.0, (gap + 5.0) / 10.0))

    def _required_skill_coverage(self, resume_doc: ResumeDocument, job_doc: JobDocument) -> float:
        req_skills = job_doc.required_skill_candidates
        if not req_skills:
            return 1.0
        c_skills_set = {s.lower() for s in resume_doc.skill_candidates}
        hits = sum(1 for s in req_skills if s.lower() in c_skills_set or any(c in s.lower() for c in c_skills_set))
        return hits / float(len(req_skills))

    def _title_keyword_overlap(self, resume_doc: ResumeDocument, job_doc: JobDocument) -> float:
        j_title_tokens = set(job_doc.title.lower().split())
        r_text_tokens = set((resume_doc.clean_text or "").lower().split())
        return len(j_title_tokens & r_text_tokens) / max(1, len(j_title_tokens))

DEFAULT_WEIGHTS: Dict[str, float] = {"semantic_similarity": 0.15, "skill_overlap_ratio": 0.20, "skill_coverage_weighted": 0.10, "experience_match": 0.10, "education_match": 0.05, "seniority_match": 0.05, "cross_encoder_score": 0.25, "title_similarity": 0.10}

class WeightedFallbackScorer:

    def __init__(self, weights: Dict[str, float] | None = None) -> None:
        self._weights = dict(weights or DEFAULT_WEIGHTS)
        total = sum(self._weights.values())
        if abs(total - 1.0) > 0.01:
            self._weights = {k: v / total for k, v in self._weights.items()}

    def score(self, features: MatchFeatures) -> float:
        feature_dict = features.to_dict()
        weighted_sum = 0.0
        for name, weight in self._weights.items():
            value = feature_dict.get(name, 0.0)
            weighted_sum += value * weight
        score = weighted_sum * 100.0
        return max(0.0, min(100.0, round(score, 1)))

    @property
    def model_version(self) -> str:
        return "fallback_v1"

logger = logging.getLogger(__name__)

class LightGBMRanker:

    def __init__(self) -> None:
        self._model = None
        self._metadata: Dict[str, Any] = {}
        self._model_path: Optional[str] = None

    @classmethod
    def from_path(cls, model_path: str) -> "LightGBMRanker":
        instance = cls()
        instance.load(model_path)
        return instance

    @classmethod
    def from_model(cls, model: Any, metadata: Optional[Dict[str, Any]] = None) -> "LightGBMRanker":
        instance = cls()
        instance._model = model
        instance._metadata = dict(metadata or {})
        return instance

    def load(self, model_path: str) -> None:
        try:
            import lightgbm as lgb
        except ImportError:
            raise ImportError(
                "lightgbm is required for LTR ranking. "
                "Run: pip install lightgbm"
            )
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"LTR model not found: {model_path}")
        self._model_path = model_path
        if path.suffix == ".txt":
            self._model = lgb.Booster(model_file=str(path))
        else:
            import pickle
            with open(path, "rb") as f:
                self._model = pickle.load(f)
        meta_path = path.with_suffix(".json")
        if meta_path.exists():
            with open(meta_path) as f:
                self._metadata = json.load(f)
        logger.info(
            "LTR model loaded from %s (version: %s)",
            model_path, self.model_version,
        )

    def score(self, features: MatchFeatures) -> float:
        if self._model is None:
            raise RuntimeError("No LTR model loaded. Call load() first.")
        if self._model.num_feature() == 10:
            vector = np.array([features.to_vector_10()], dtype=np.float64)
        elif self._model.num_feature() == 14:
            vector = np.array([features.to_vector_14()], dtype=np.float64)
        else:
            vector = np.array([features.to_vector()], dtype=np.float64)
        raw_score = self._model.predict(vector)[0]
        calib = self._metadata.get('calibration', {})
        if calib and 'a' in calib:
            raw_score = float(calib.get('a', 1.0)) * raw_score + float(calib.get('b', 0.0))
        normalised = 1.0 / (1.0 + np.exp(-raw_score))
        score = float(normalised) * 100.0
        return max(0.0, min(100.0, round(score, 1)))

    def batch_score(self, features_list: List[MatchFeatures]) -> List[float]:
        if self._model is None:
            raise RuntimeError("No LTR model loaded. Call load() first.")
        if not features_list:
            return []
        if self._model.num_feature() == 10:
            vectors = np.array([f.to_vector_10() for f in features_list], dtype=np.float64)
        elif self._model.num_feature() == 14:
            vectors = np.array([f.to_vector_14() for f in features_list], dtype=np.float64)
        else:
            vectors = np.array([f.to_vector() for f in features_list], dtype=np.float64)
        raw_scores = self._model.predict(vectors)
        calib = self._metadata.get('calibration', {})
        if calib and 'a' in calib:
            raw_scores = float(calib.get('a', 1.0)) * raw_scores + float(calib.get('b', 0.0))
        normalised = 1.0 / (1.0 + np.exp(-raw_scores))
        scores = normalised * 100.0
        return [
            max(0.0, min(100.0, round(float(s), 1)))
            for s in scores
        ]

    @property
    def model_version(self) -> str:
        if self._metadata.get("version"):
            return self._metadata["version"]
        if self._model_path:
            return Path(self._model_path).stem
        return "ltr_unknown"

    @property
    def metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)
