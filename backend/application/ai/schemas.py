from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

DEGREE_LEVELS: Dict[str, int] = {
    "associate":  1,
    "diploma":    1,
    "bachelor":   2,
    "bachelors":  2,
    "bachelor's": 2,
    "b.s.":       2,
    "b.s":        2,
    "bs":         2,
    "b.a.":       2,
    "b.a":        2,
    "ba":         2,
    "b.eng.":     2,
    "b.eng":      2,
    "beng":       2,
    "b.e.":       2,
    "b.e":        2,
    "be":         2,
    "b.tech.":    2,
    "b.tech":     2,
    "btech":      2,
    "bca":        2,
    "master":     3,
    "masters":    3,
    "master's":   3,
    "m.s.":       3,
    "m.s":        3,
    "ms":         3,
    "m.a.":       3,
    "m.a":        3,
    "mba":        3,
    "m.eng.":     3,
    "m.eng":      3,
    "meng":       3,
    "m.tech.":    3,
    "m.tech":     3,
    "mtech":      3,
    "mca":        3,
    "phd":        4,
    "ph.d.":      4,
    "ph.d":       4,
    "doctoral":   4,
    "doctorate":  4,
}

@dataclass
class EducationEntry:
    degree: str = ""
    institution: str = ""
    dates: str = ""
    cgpa: str = ""
    degree_level: Optional[int] = None

@dataclass
class ResumeDocument:

    raw_text: str
    clean_text: str = ""

    summary_section: str = ""
    skills_section: str = ""
    experience_section: str = ""
    projects_section: str = ""
    education_section: str = ""
    certifications_section: str = ""
    achievements_section: str = ""
    other_sections: Dict[str, str] = field(default_factory=dict)

    skill_candidates: List[str] = field(default_factory=list)
    years_experience: Optional[float] = None
    degree_level: Optional[int] = None
    education_details: List[EducationEntry] = field(default_factory=list)
    seniority_label: str = ""

    def section_texts(self) -> Dict[str, str]:
        named = {
            "summary":        self.summary_section,
            "skills":         self.skills_section,
            "experience":     self.experience_section,
            "projects":       self.projects_section,
            "education":      self.education_section,
            "certifications": self.certifications_section,
            "achievements":   self.achievements_section,
        }
        result = {k: v for k, v in named.items() if v and v.strip()}
        result.update(
            {k: v for k, v in self.other_sections.items() if v and v.strip()}
        )
        return result

    def primary_text_for_embedding(self) -> str:
        priority = [
            self.skills_section,
            self.experience_section,
            self.summary_section,
            self.projects_section,
            self.education_section,
        ]
        text = "\n\n".join(s for s in priority if s and s.strip())
        return text or self.clean_text or self.raw_text

@dataclass
class JobDocument:

    raw_text: str
    title: str = ""
    clean_text: str = ""

    summary_section: str = ""
    responsibilities_section: str = ""
    required_skills_section: str = ""
    preferred_skills_section: str = ""
    qualifications_section: str = ""
    experience_requirements_section: str = ""
    other_sections: Dict[str, str] = field(default_factory=dict)

    required_skill_candidates: List[str] = field(default_factory=list)
    preferred_skill_candidates: List[str] = field(default_factory=list)
    required_years: Optional[float] = None
    required_degree_level: Optional[int] = None
    seniority_label: str = ""

    def section_texts(self) -> Dict[str, str]:
        named = {
            "summary":                self.summary_section,
            "responsibilities":       self.responsibilities_section,
            "required_skills":        self.required_skills_section,
            "preferred_skills":       self.preferred_skills_section,
            "qualifications":         self.qualifications_section,
            "experience_requirements": self.experience_requirements_section,
        }
        result = {k: v for k, v in named.items() if v and v.strip()}
        result.update(
            {k: v for k, v in self.other_sections.items() if v and v.strip()}
        )
        return result

    def primary_text_for_embedding(self) -> str:
        priority = [
            self.responsibilities_section,
            self.required_skills_section,
            self.summary_section,
            self.preferred_skills_section,
            self.qualifications_section,
        ]
        text = "\n\n".join(s for s in priority if s and s.strip())
        return text or self.clean_text or self.raw_text

    def all_skill_candidates(self) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for skill in self.required_skill_candidates + self.preferred_skill_candidates:
            key = skill.lower()
            if key not in seen:
                seen.add(key)
                result.append(skill)
        return result

@dataclass
class RetrievalResult:
    document_id: int
    score: float

@dataclass
class RerankResult:
    document_id: int
    cross_encoder_score: float
    retrieval_score: float

@dataclass
class MatchFeatures:
    semantic_similarity: float = 0.0
    skill_overlap_ratio: float = 0.0
    skill_coverage_weighted: float = 0.0
    experience_match: float = 0.0
    education_match: float = 0.0
    seniority_match: float = 0.0
    cross_encoder_score: float = 0.0
    title_similarity: float = 0.0
    graph_skill_coverage: float = 0.0
    section_coverage: float = 0.0
    strict_seniority_match: float = 1.0
    experience_gap: float = 0.5
    required_skill_coverage: float = 0.0
    title_keyword_overlap: float = 0.0
    signed_seniority_gap: float = 0.0
    years_gap: float = 0.0
    must_have_skill_coverage: float = 0.0
    nice_to_have_skill_coverage: float = 1.0
    role_family_match: float = 0.5

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    def to_vector(self) -> List[float]:
        """Vector of all 19 features for LambdaMART v5."""
        return self.to_vector_14() + [
            self.signed_seniority_gap,
            self.years_gap,
            self.must_have_skill_coverage,
            self.nice_to_have_skill_coverage,
            self.role_family_match,
        ]

    def to_vector_14(self) -> List[float]:
        """Vector of 14 features for LambdaMART v3/v4."""
        return [
            self.semantic_similarity,
            self.skill_overlap_ratio,
            self.skill_coverage_weighted,
            self.experience_match,
            self.education_match,
            self.seniority_match,
            self.cross_encoder_score,
            self.title_similarity,
            self.graph_skill_coverage,
            self.section_coverage,
            self.strict_seniority_match,
            self.experience_gap,
            self.required_skill_coverage,
            self.title_keyword_overlap,
        ]

    def to_vector_10(self) -> List[float]:
        """Backwards-compatible 10-feature vector for LambdaMART v1/v2."""
        return [
            self.semantic_similarity,
            self.skill_overlap_ratio,
            self.skill_coverage_weighted,
            self.experience_match,
            self.education_match,
            self.seniority_match,
            self.cross_encoder_score,
            self.title_similarity,
            self.graph_skill_coverage,
            self.section_coverage,
        ]

    @staticmethod
    def feature_names() -> List[str]:
        return MatchFeatures.feature_names_14() + [
            "signed_seniority_gap",
            "years_gap",
            "must_have_skill_coverage",
            "nice_to_have_skill_coverage",
            "role_family_match",
        ]

    @staticmethod
    def feature_names_14() -> List[str]:
        return [
            "semantic_similarity",
            "skill_overlap_ratio",
            "skill_coverage_weighted",
            "experience_match",
            "education_match",
            "seniority_match",
            "cross_encoder_score",
            "title_similarity",
            "graph_skill_coverage",
            "section_coverage",
            "strict_seniority_match",
            "experience_gap",
            "required_skill_coverage",
            "title_keyword_overlap",
        ]

    @staticmethod
    def feature_names_10() -> List[str]:
        return [
            "semantic_similarity",
            "skill_overlap_ratio",
            "skill_coverage_weighted",
            "experience_match",
            "education_match",
            "seniority_match",
            "cross_encoder_score",
            "title_similarity",
            "graph_skill_coverage",
            "section_coverage",
        ]

@dataclass
class MatchPointEvidence:
    point: str
    evidence: str

@dataclass
class GapEvidence:
    point: str

@dataclass
class MatchExplanation:
    candidate_summary: str = ""
    matching_points: List[MatchPointEvidence] = field(default_factory=list)
    gaps: List[GapEvidence] = field(default_factory=list)
    recommendation: str = ""
    explanation_text: str = ""

@dataclass
class MatchResult:
    job_id: int
    candidate_id: Optional[int] = None
    final_score: float = 0.0
    features: MatchFeatures = field(default_factory=MatchFeatures)
    explanation: MatchExplanation = field(default_factory=MatchExplanation)
    model_version: str = "fallback_v1"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
