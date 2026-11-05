from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from application.ai.explanation import EvidenceGenerator
from application.ai.extraction import (
    EducationExtractor,
    ExperienceExtractor,
    SeniorityExtractor,
    SkillExtractionPipeline,
    SkillNormalizer,
)
from application.ai.graph import NetworkXSkillGraph
from application.ai.matching import (
    CrossEncoderReranker,
    FaissRetriever,
    SentenceTransformerEmbedding,
)
from application.ai.parsing import JobParser, ResumeParser, clean_text, load_text
from application.ai.ranking import (
    FeatureExtractor,
    LightGBMRanker,
    WeightedFallbackScorer,
)
from application.ai.schemas import (
    JobDocument,
    MatchResult,
    ResumeDocument,
    RetrievalResult,
)


@dataclass
class AIConfig:
    use_local_embeddings: bool = True
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    hf_api_key: Optional[str] = None
    hf_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    cross_encoder_model: Optional[str] = None
    skill_match_threshold: float = 0.55
    faiss_index_path: Optional[str] = None
    ltr_model_path: Optional[str] = None
    skill_graph_path: Optional[str] = None

    @classmethod
    def default(cls) -> "AIConfig":
        cfg = cls()
        models_dir = Path(__file__).resolve().parent.parent.parent / "data" / "models"
        v5 = models_dir / "lgb_ranker_v5.txt"
        v4 = models_dir / "lgb_ranker_v4.txt"
        if v5.exists():
            cfg.ltr_model_path = str(v5)
        elif v4.exists():
            cfg.ltr_model_path = str(v4)
        return cfg

    @classmethod
    def from_django_settings(cls) -> "AIConfig":
        return cls.default()

class MatchPoint(BaseModel):
    point: str = Field(description="Concrete way candidate matches job requirements")
    evidence: str = Field(description="Evidence from resume backing this match")

class GapPoint(BaseModel):
    point: str = Field(description="Job requirement not clearly covered by resume")

class ResumeAnalysis(BaseModel):
    candidate_summary: str = Field(description="2-3 sentence overview of candidate")
    key_skills: List[str] = Field(default_factory=list, description="Skills extracted from resume")
    experience_highlights: List[str] = Field(default_factory=list, description="Key roles/projects")
    education_summary: str = Field(default="", description="Summary of candidate education")
    match_score: int = Field(ge=0, le=100, description="Overall fit score 0-100")
    matching_points: List[MatchPoint] = Field(default_factory=list, description="Match points")
    gaps: List[GapPoint] = Field(default_factory=list, description="Missing requirements")
    recommendation: str = Field(description="Recommendation to hiring manager")
    explanation: str = Field(default="", description="Optional AI-generated explanation")

class AIServiceError(Exception):
    pass

logger = logging.getLogger(__name__)

def extract_raw_text(file_field: Any) -> str:
    if file_field is None:
        raise AIServiceError("No resume file attached.")
    name = getattr(file_field, "name", "") or ""
    data: bytes = b""
    if hasattr(file_field, "open"):
        try:
            file_field.open("rb")
        except Exception:
            pass
    if hasattr(file_field, "read"):
        content = file_field.read()
        if hasattr(file_field, "seek"):
            file_field.seek(0)
        data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
    elif isinstance(file_field, Path):
        if not file_field.exists():
            raise AIServiceError(f"File not found: {file_field}")
        data = file_field.read_bytes()
        name = file_field.name
    elif isinstance(file_field, str):
        p = Path(file_field)
        if p.exists() and p.is_file():
            data = p.read_bytes()
            name = p.name
        else:
            return file_field
    elif isinstance(file_field, (bytes, bytearray)):
        data = bytes(file_field)
    else:
        raise AIServiceError(f"Unsupported file type: {type(file_field)}")
    suffix = Path(name).suffix.lower() if name else ""
    if suffix in (".pdf", ".docx", ".doc") or data.startswith(b"%PDF"):
        try:
            return load_text(data)
        except Exception as exc:
            logger.warning("Document extraction failed: %s", exc)
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            text = data.decode(enc)
            if text.strip():
                return text
        except UnicodeDecodeError:
            continue
    raise AIServiceError("Could not extract readable text from resume.")

def build_candidate_summary(resume_doc: ResumeDocument, candidate_name: str = "") -> str:
    langs = []
    primary = []
    secondary = []
    core_languages = {
        "python", "java", "go", "golang", "c++", "c", "javascript", "typescript",
        "kotlin", "rust", "c#", "scala", "ruby", "swift", "php", "sql",
    }
    generic_utilities = {"git", "postman", "jira", "excel", "confluence"}

    for s in resume_doc.skill_candidates:
        s_low = s.lower()
        if len(s) > 1:
            if s_low in generic_utilities:
                secondary.append(s)
            elif s_low in core_languages:
                langs.append(s)
            else:
                primary.append(s)

    text_lower = (resume_doc.clean_text or "").lower()
    if text_lower:
        import re
        def _freq(skill: str) -> int:
            return len(re.findall(r"\b" + re.escape(skill.lower()) + r"\b", text_lower))
        primary.sort(key=_freq, reverse=True)
        langs.sort(key=_freq, reverse=True)

    picked = []
    for l in langs[:2]:
        picked.append(l)
    for p in primary:
        if len(picked) >= 6:
            break
        if p not in picked:
            picked.append(p)
    for s in secondary:
        if len(picked) >= 6:
            break
        if s not in picked:
            picked.append(s)

    top_skills = picked or (resume_doc.skill_candidates[:5] if resume_doc.skill_candidates else [])
    skills_str = ", ".join(top_skills) or "software engineering"

    name_str = candidate_name or 'The candidate'
    sen = f" ({resume_doc.seniority_label.title()} level)" if resume_doc.seniority_label else ""

    degree_str = ""
    if resume_doc.education_details and resume_doc.education_details[0].degree:
        degree_str = f" Holds {resume_doc.education_details[0].degree}."
    elif resume_doc.degree_level:
        degree_names = {1: "an Associate Degree", 2: "a Bachelor's Degree", 3: "a Master's Degree", 4: "a Doctorate"}
        deg = degree_names.get(resume_doc.degree_level)
        if deg:
            degree_str = f" Holds {deg}."

    if resume_doc.years_experience and resume_doc.years_experience >= 1.0:
        return (
            f"{name_str} has {resume_doc.years_experience:.0f}+ years of experience{sen} "
            f"specializing in {skills_str}.{degree_str}"
        )
    return (
        f"{name_str} is an early-career candidate{sen} with hands-on "
        f"project experience in {skills_str}.{degree_str}"
    )

def build_education_summary(resume_doc: ResumeDocument) -> str:
    if resume_doc.education_details and resume_doc.education_details[0].degree:
        ed = resume_doc.education_details[0]
        edu_summary = ed.degree
        if ed.institution:
            edu_summary += f", {ed.institution}"
        meta_items = []
        if ed.dates:
            meta_items.append(ed.dates)
        if ed.cgpa:
            meta_items.append(f"CGPA: {ed.cgpa}")
        if meta_items:
            edu_summary += f" ({', '.join(meta_items)})"
        return edu_summary
    degree_names = {1: "Associate Degree", 2: "Bachelor's Degree", 3: "Master's Degree", 4: "Doctorate"}
    return degree_names.get(resume_doc.degree_level, "Educational background listed in resume.")

def build_recommendation(match_score: int) -> str:
    if match_score >= 70:
        return "Strong match for the requirements. Recommend interview."
    return "Promising candidate with relevant fundamentals. Review missing requirements before interview."

def build_experience_highlights(resume_doc: ResumeDocument) -> list[str]:
    if resume_doc.years_experience and resume_doc.years_experience >= 1.0:
        return [
            f"{resume_doc.years_experience:.0f}+ years of professional experience "
            f"({resume_doc.seniority_label.title()} seniority level)."
        ]
    return [
        f"Early-career candidate with hands-on project and academic engineering experience "
        f"({resume_doc.seniority_label.title()} seniority level)."
    ]

logger = logging.getLogger(__name__)

class MatchingPipeline:

    _default_instance: Optional["MatchingPipeline"] = None

    def __init__(self, config: Optional[AIConfig] = None):
        self.config = config or AIConfig.default()
        self.cleaner = clean_text
        self.resume_parser = ResumeParser()
        self.job_parser = JobParser()
        self.skill_extractor = SkillExtractionPipeline()
        self.normalizer = SkillNormalizer()
        self.experience_extractor = ExperienceExtractor()
        self.education_extractor = EducationExtractor()
        self.seniority_extractor = SeniorityExtractor()
        self.embedding = SentenceTransformerEmbedding(
            model_name=self.config.local_embedding_model,
            lazy_load=True,
        )
        self.retriever = FaissRetriever(embedding_dim=self.embedding.embedding_dim)
        self.reranker = CrossEncoderReranker(
            model_name=self.config.cross_encoder_model,
            lazy_load=True,
        )
        self.graph = NetworkXSkillGraph()
        self.feature_extractor = FeatureExtractor(graph=self.graph, embedder=self.embedding)
        self.evidence_generator = EvidenceGenerator()
        if self.config.ltr_model_path and Path(self.config.ltr_model_path).exists():
            self.ranker = LightGBMRanker.from_path(self.config.ltr_model_path)
        else:
            self.ranker = WeightedFallbackScorer()

    @classmethod
    def get_default(cls) -> "MatchingPipeline":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def analyze_resume(
        self,
        file_field: Any,
        job_title: str,
        job_description: str,
        candidate_name: str = "",
        job_id: Optional[int] = None,
        candidate_id: Optional[int] = None,
    ) -> ResumeAnalysis:
        job_title = job_title or ""
        job_description = job_description or ""
        raw_resume = extract_raw_text(file_field)
        cleaned_resume = self.cleaner(raw_resume)
        cleaned_job = self.cleaner(job_description)
        resume_doc = self.resume_parser.parse(clean_text=cleaned_resume, raw_text=raw_resume)
        job_doc = self.job_parser.parse(clean_text=cleaned_job, title=job_title, raw_text=job_description)
        core_skills = self.skill_extractor.extract(resume_doc.skills_section)
        proj_skills = self.skill_extractor.extract(resume_doc.projects_section)
        all_candidate_skills = list(core_skills)
        seen_lower = {s.lower() for s in core_skills}
        for s in proj_skills:
            if s.lower() not in seen_lower:
                all_candidate_skills.append(s)
                seen_lower.add(s.lower())
        if not all_candidate_skills:
            all_candidate_skills = self.skill_extractor.extract(cleaned_resume)
        resume_doc.skill_candidates = self.normalizer.normalize_list(all_candidate_skills)
        req_text = "\n".join(filter(None, [job_doc.required_skills_section, job_doc.qualifications_section]))
        raw_req = self.skill_extractor.extract(req_text) if req_text else []
        if not raw_req:
            raw_req = self.skill_extractor.extract(cleaned_job)
        job_doc.required_skill_candidates = self.normalizer.normalize_list(raw_req)
        raw_pref = self.skill_extractor.extract(job_doc.preferred_skills_section) if job_doc.preferred_skills_section else []
        job_doc.preferred_skill_candidates = self.normalizer.normalize_list(raw_pref)
        resume_doc.years_experience = self.experience_extractor.extract(
            resume_doc.experience_section or cleaned_resume
        )
        exp_req_text = "\n".join(filter(None, [
            job_doc.experience_requirements_section,
            job_doc.required_skills_section,
        ]))
        job_doc.required_years = self.experience_extractor.extract(exp_req_text)
        edu_text = resume_doc.education_section or cleaned_resume
        resume_doc.degree_level = self.education_extractor.extract(edu_text)
        resume_doc.education_details = self.education_extractor.extract_details(edu_text)
        job_edu_text = "\n".join(filter(None, [
            job_doc.other_sections.get("education_requirements", ""),
            job_doc.required_skills_section,
            job_doc.qualifications_section,
            cleaned_job,
        ]))
        job_doc.required_degree_level = self.education_extractor.extract(job_edu_text)
        res_sen_text = "\n".join(filter(None, [resume_doc.summary_section, resume_doc.experience_section]))
        resume_doc.seniority_label = self.seniority_extractor.extract(
            res_sen_text or cleaned_resume,
            years_experience=resume_doc.years_experience,
            degree_level=resume_doc.degree_level,
        )
        job_sen_text = f"{job_title}\n{job_doc.summary_section}\n{job_doc.required_skills_section}"
        job_doc.seniority_label = self.seniority_extractor.extract(
            job_sen_text,
            years_experience=job_doc.required_years,
            degree_level=job_doc.required_degree_level,
        )
        emb_res = self.embedding.embed_text(cleaned_resume[:1000])
        emb_job = self.embedding.embed_text(cleaned_job[:1000])
        ce_score = self.reranker.predict_pair(cleaned_job, cleaned_resume)
        features = self.feature_extractor.extract(
            resume_doc=resume_doc,
            job_doc=job_doc,
            resume_embedding=emb_res,
            job_embedding=emb_job,
            cross_encoder_score=ce_score,
        )
        match_score = int(round(self.ranker.score(features)))
        points_ev, gaps_ev = self.evidence_generator.generate(features, resume_doc, job_doc)
        return ResumeAnalysis(
            candidate_summary=build_candidate_summary(resume_doc, candidate_name),
            key_skills=resume_doc.skill_candidates[:12],
            experience_highlights=build_experience_highlights(resume_doc),
            education_summary=build_education_summary(resume_doc),
            match_score=match_score,
            matching_points=[MatchPoint(point=p.point, evidence=p.evidence) for p in points_ev],
            gaps=[GapPoint(point=g.point) for g in gaps_ev],
            recommendation=build_recommendation(match_score),
            explanation=f"Evaluated via {self.ranker.model_version} across 10 semantic and qualification features.",
        )

    def match_candidates_for_job(
        self,
        job_title: str,
        job_description: str,
        candidate_pool: List[Tuple[int, str, str]],
        top_k: int = 10,
    ) -> List[MatchResult]:
        if not candidate_pool:
            return []
        cleaned_job = self.cleaner(job_description)
        job_doc = self.job_parser.parse(clean_text=cleaned_job, title=job_title, raw_text=job_description)
        req_text = "\n".join(filter(None, [job_doc.required_skills_section, job_doc.qualifications_section]))
        raw_req = self.skill_extractor.extract(req_text) if req_text else []
        job_doc.required_skill_candidates = self.normalizer.normalize_list(raw_req or self.skill_extractor.extract(cleaned_job))
        job_emb = self.embedding.embed_text(cleaned_job[:1000])
        cand_ids = [c[0] for c in candidate_pool]
        cand_texts = [self.cleaner(c[2]) for c in candidate_pool]
        cand_embs = self.embedding.embed_batch([t[:1000] for t in cand_texts])
        from application.ai.matching import HybridRetriever, BM25_AVAILABLE
        retriever = HybridRetriever(embedding_dim=self.embedding.embedding_dim, use_bm25=BM25_AVAILABLE)
        retriever.add_documents(cand_ids, cand_embs, texts=cand_texts)
        retrievals: List[RetrievalResult] = retriever.search(job_emb, top_k=min(len(cand_ids), top_k * 2), query_text=cleaned_job)
        retrieved_ids = {r.document_id: r.score for r in retrievals}
        rerank_input = [
            (c_id, cand_texts[cand_ids.index(c_id)], retrieved_ids[c_id])
            for c_id in retrieved_ids
        ]
        rerank_results = self.reranker.rerank(cleaned_job, rerank_input, top_k=top_k)
        results: List[MatchResult] = []
        for rk in rerank_results:
            c_idx = cand_ids.index(rk.document_id)
            c_text = cand_texts[c_idx]
            res_doc = self.resume_parser.parse(clean_text=c_text, raw_text=candidate_pool[c_idx][2])
            core = self.skill_extractor.extract(res_doc.skills_section)
            proj = self.skill_extractor.extract(res_doc.projects_section)
            combined = list(core) + [s for s in proj if s.lower() not in {x.lower() for x in core}]
            res_doc.skill_candidates = self.normalizer.normalize_list(combined or self.skill_extractor.extract(c_text))
            res_doc.years_experience = self.experience_extractor.extract(res_doc.experience_section)
            res_doc.degree_level = self.education_extractor.extract(res_doc.education_section or c_text)
            res_doc.seniority_label = self.seniority_extractor.extract(
                res_doc.summary_section or c_text,
                years_experience=res_doc.years_experience,
                degree_level=res_doc.degree_level,
            )
            features = self.feature_extractor.extract(
                resume_doc=res_doc,
                job_doc=job_doc,
                resume_embedding=cand_embs[c_idx],
                job_embedding=job_emb,
                cross_encoder_score=rk.cross_encoder_score,
            )
            score = self.ranker.score(features)
            results.append(
                MatchResult(
                    job_id=0,
                    candidate_id=rk.document_id,
                    final_score=score,
                    features=features,
                    model_version=self.ranker.model_version,
                )
            )
        results.sort(key=lambda x: x.final_score, reverse=True)
        return results[:top_k]

def analyze_resume(
    file_field: Any,
    job_title: str,
    job_description: str,
    candidate_name: str = "",
    job_id: Optional[int] = None,
    candidate_id: Optional[int] = None,
) -> ResumeAnalysis:
    return MatchingPipeline.get_default().analyze_resume(
        file_field=file_field,
        job_title=job_title,
        job_description=job_description,
        candidate_name=candidate_name,
        job_id=job_id,
        candidate_id=candidate_id,
    )
