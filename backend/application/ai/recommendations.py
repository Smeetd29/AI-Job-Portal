from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel, Field
import logging
import re
from typing import Any, List, Optional, Tuple
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from jobs.models import Job
from users.models import User
from rest_framework import permissions, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from application.ai.extraction import match_skill
from application.ai.pipeline import extract_raw_text
from application.ai.pipeline import MatchingPipeline
from application.ai.ranking import profile_coverage
from application.ai.schemas import JobDocument, ResumeDocument
from application.models import Application

class JobRecommendationDTO(BaseModel):
    job_id: int
    title: str
    company: str
    location: str
    job_type: str
    category: str = ""
    match_score: int = Field(ge=0, le=100)
    matched_skills: List[str] = Field(default_factory=list)
    skill_gaps: List[str] = Field(default_factory=list)
    pay_amount: Optional[str] = None
    pay_mode: Optional[str] = None

class RecommendationResponse(BaseModel):
    has_resume: bool = True
    message: Optional[str] = None
    min_match: int = 50
    total_eligible: int = 0
    matched_count: int = 0
    applied_count: int = 0
    results: List[JobRecommendationDTO] = Field(default_factory=list)

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 1800


@dataclass
class _PreparedRecommendationJob:
    job: Job
    cleaned_job: str
    job_doc: JobDocument
    job_text: str


def invalidate_recommendation_cache(candidate_user_id: Optional[int] = None) -> None:
    """Invalidates recommendation cache for a specific user or globally across candidates."""
    try:
        if candidate_user_id:
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern(f"*ai_recs_user_{candidate_user_id}_*")
            else:
                cache.delete(f"ai_recs_user_{candidate_user_id}")
        else:
            if hasattr(cache, 'delete_pattern'):
                cache.delete_pattern("*ai_recs_user_*")
    except Exception as exc:
        logger.debug("Recommendation cache invalidation bypassed: %s", exc)

class JobRecommendationService:

    def __init__(self, pipeline: Optional[MatchingPipeline] = None):
        self.pipeline = pipeline or MatchingPipeline.get_default()

    def get_candidate_resume(self, user: User) -> Optional[Any]:
        profile = getattr(user, 'candidate_profile', None)
        if profile and profile.resume:
            return profile.resume
        return None

    def get_eligible_jobs(self, candidate_user: User):
        now = timezone.now()
        applied_job_ids = Application.objects.filter(
            candidate=candidate_user
        ).values_list('job_id', flat=True)
        return (
            Job.objects.filter(is_active=True)
            .filter(Q(expires_at__gt=now) | Q(expires_at__isnull=True))
            .exclude(id__in=applied_job_ids)
            .select_related('recruiter', 'recruiter__recruiter_profile')
            .order_by('-created_at')
        )

    def _parse_candidate_resume(self, resume_file: Any) -> Tuple[str, ResumeDocument, Any, Any]:
        raw_resume = extract_raw_text(resume_file)
        cleaned_resume = self.pipeline.cleaner(raw_resume)
        resume_doc = self.pipeline.resume_parser.parse(cleaned_resume, raw_text=raw_resume)
        norm, ex = self.pipeline.normalizer.normalize_list, self.pipeline.skill_extractor.extract
        split = lambda t: [x.strip(" -•*\t") for x in re.split(r"[,;|\n]", t or "") if 2 < len(x.strip()) < 40 and len(x.split()) <= 3]

        def _extract_project_tech(proj_text: str) -> List[str]:
            found = set()
            for line in (proj_text or "").splitlines():
                sline = line.strip()
                if not sline:
                    continue
                if "|" in sline:
                    tech_part = sline.split("|", 1)[1].strip()
                    for t in re.split(r"[,;/]", tech_part):
                        cleaned_t = t.strip()
                        if 1 < len(cleaned_t) < 35 and len(cleaned_t.split()) <= 4:
                            found.add(cleaned_t)
                m = re.match(r"^(?:tech(?:nologies| stack)?|tools?|built with|libraries):\s*(.+)$", sline, re.I)
                if m:
                    for t in re.split(r"[,;/]", m.group(1)):
                        cleaned_t = t.strip()
                        if 1 < len(cleaned_t) < 35 and len(cleaned_t.split()) <= 4:
                            found.add(cleaned_t)
            return sorted(found, key=str.lower)

        core = norm(ex(resume_doc.skills_section) + ex(resume_doc.experience_section))
        if len(core) < 4:
            core = norm(core + split(resume_doc.skills_section))
        core_l = {s.lower() for s in core}
        proj_tech = norm(_extract_project_tech(resume_doc.projects_section))
        proj = [s for s in proj_tech if s.lower() not in core_l]
        resume_doc.skill_candidates = core + proj or norm(ex(cleaned_resume))
        resume_doc.years_experience = self.pipeline.experience_extractor.extract(
            resume_doc.experience_section or cleaned_resume
        )
        edu_text = resume_doc.education_section or cleaned_resume
        resume_doc.degree_level = self.pipeline.education_extractor.extract(edu_text)
        res_sen_text = "\n".join(filter(None, [resume_doc.summary_section, resume_doc.experience_section]))
        resume_doc.seniority_label = self.pipeline.seniority_extractor.extract(
            res_sen_text or cleaned_resume,
            years_experience=resume_doc.years_experience,
            degree_level=resume_doc.degree_level,
        )
        profile_text = "\n".join(filter(None, ["Skills: " + ", ".join(resume_doc.skill_candidates), resume_doc.summary_section, resume_doc.experience_section, resume_doc.projects_section]))[:1500]
        role_text = "\n".join(filter(None, [resume_doc.summary_section, (resume_doc.experience_section or "")[:300], ", ".join(resume_doc.skill_candidates[:15])]))[:600]
        ctx = {"w": {**{s.lower(): 1.0 for s in core}, **{s.lower(): 0.7 for s in proj}}, "role": self.pipeline.embedding.embed_text(role_text)}
        return profile_text, resume_doc, self.pipeline.embedding.embed_text(profile_text), ctx

    def _score_single_job(
        self,
        job: Job,
        cleaned_resume: str,
        resume_doc: ResumeDocument,
        emb_res: Any,
        ctx: Any = None,
    ) -> JobRecommendationDTO:
        prepared = self._prepare_job(job)
        emb_job, title_embedding = self.pipeline.embedding.embed_batch([
            prepared.job_text,
            f"{job.title} {job.category}",
        ])
        ce_score = self.pipeline.reranker.predict_pair(prepared.job_text, cleaned_resume)
        return self._score_prepared_job(
            prepared,
            resume_doc,
            emb_res,
            ctx,
            emb_job,
            ce_score,
            title_embedding,
        )

    def _prepare_job(self, job: Job) -> _PreparedRecommendationJob:
        cleaned_job = self.pipeline.cleaner(job.description)
        job_doc = self.pipeline.job_parser.parse(
            clean_text=cleaned_job, title=job.title, raw_text=job.description
        )
        raw_req = getattr(job, "required_skills", None)
        if not raw_req and job_doc.required_skills_section:
            raw_req = self.pipeline.skill_extractor.extract(job_doc.required_skills_section)
        if not raw_req and job_doc.qualifications_section:
            raw_req = self.pipeline.skill_extractor.extract(job_doc.qualifications_section)
        if not raw_req:
            raw_req = self.pipeline.skill_extractor.extract(cleaned_job)
        job_doc.required_skill_candidates = self.pipeline.normalizer.normalize_list(raw_req or [])
        raw_pref = getattr(job, "preferred_skills", None)
        if not raw_pref and job_doc.preferred_skills_section:
            raw_pref = self.pipeline.skill_extractor.extract(job_doc.preferred_skills_section)
        job_doc.preferred_skill_candidates = self.pipeline.normalizer.normalize_list(raw_pref or [])
        job_text = f"{job.title}. {', '.join(job_doc.required_skill_candidates)}. {cleaned_job[:600]}"
        exp_req = "\n".join(filter(None, [job_doc.experience_requirements_section, job_doc.required_skills_section]))
        job_doc.required_years = self.pipeline.experience_extractor.extract(exp_req)
        job_edu = "\n".join(filter(None, [
            job_doc.other_sections.get("education_requirements", ""),
            job_doc.required_skills_section,
            job_doc.qualifications_section,
            cleaned_job,
        ]))
        job_doc.required_degree_level = self.pipeline.education_extractor.extract(job_edu)
        job_sen = f"{job.title}\n{job_doc.summary_section}\n{job_doc.required_skills_section}"
        job_doc.seniority_label = self.pipeline.seniority_extractor.extract(
            job_sen,
            years_experience=job_doc.required_years,
            degree_level=job_doc.required_degree_level,
        )
        return _PreparedRecommendationJob(job, cleaned_job, job_doc, job_text)

    def _score_prepared_job(
        self,
        prepared: _PreparedRecommendationJob,
        resume_doc: ResumeDocument,
        emb_res: Any,
        ctx: Any,
        emb_job: Any,
        ce_score: float,
        title_embedding: Any,
    ) -> JobRecommendationDTO:
        job = prepared.job
        cleaned_job = prepared.cleaned_job
        job_doc = prepared.job_doc
        features = self.pipeline.feature_extractor.extract(
            resume_doc=resume_doc,
            job_doc=job_doc,
            resume_embedding=emb_res,
            job_embedding=emb_job,
            resume_summary_embedding=ctx["role"] if ctx else None,
            job_title_embedding=title_embedding,
            cross_encoder_score=ce_score,
        )
        cov = profile_coverage(ctx["w"], f"{job.title} {', '.join(job_doc.required_skill_candidates + job_doc.preferred_skill_candidates)} {cleaned_job}") if ctx else 1.0
        score = max(0, min(100, int(round(self.pipeline.ranker.score(features)))))
        cand_skills_lower = {s.lower() for s in resume_doc.skill_candidates}
        matched_skills: List[str] = []
        skill_gaps: List[str] = []
        for req in job_doc.required_skill_candidates:
            matched, label = match_skill(req, cand_skills_lower, self.pipeline.normalizer)
            if matched:
                matched_skills.append(label or req)
            else:
                skill_gaps.append(req)
        company = (
            getattr(getattr(job.recruiter, 'recruiter_profile', None), 'company_name', None)
            or job.recruiter.username
        )
        return JobRecommendationDTO(
            job_id=job.id,
            title=job.title,
            company=company,
            location=job.location_type,
            job_type=job.job_type,
            category=job.category or "",
            match_score=score,
            matched_skills=matched_skills[:8],
            skill_gaps=skill_gaps[:6],
            pay_amount=str(job.pay_amount) if job.pay_amount else None,
            pay_mode=job.pay_mode,
        )

    def _score_jobs(
        self,
        jobs: List[Job],
        cleaned_resume: str,
        resume_doc: ResumeDocument,
        emb_res: Any,
        ctx: Any,
    ) -> List[JobRecommendationDTO]:
        prepared_jobs = [self._prepare_job(job) for job in jobs]
        if not prepared_jobs:
            return []

        embedding_texts = [
            text
            for prepared in prepared_jobs
            for text in (prepared.job_text, f"{prepared.job.title} {prepared.job.category}")
        ]
        embeddings = self.pipeline.embedding.embed_batch(embedding_texts)
        cross_encoder_scores = self.pipeline.reranker.score_pairs(
            [(item.job_text, cleaned_resume) for item in prepared_jobs]
        )

        return [
            self._score_prepared_job(
                prepared,
                resume_doc,
                emb_res,
                ctx,
                embeddings[index * 2],
                cross_encoder_scores[index],
                embeddings[index * 2 + 1],
            )
            for index, prepared in enumerate(prepared_jobs)
        ]

    def get_recommendations(
        self,
        candidate_user: User,
        min_match: int = 50,
        force_refresh: bool = False,
    ) -> RecommendationResponse:
        resume_file = self.get_candidate_resume(candidate_user)
        if not resume_file:
            return RecommendationResponse(
                has_resume=False,
                message="Upload a resume to receive AI job recommendations.",
                min_match=min_match,
                total_eligible=0,
                matched_count=0,
                results=[],
            )
        cache_key = f"ai_recs_user_{candidate_user.id}_{getattr(resume_file, 'name', '')}"
        cached_data = None if force_refresh else cache.get(cache_key)
        if cached_data is not None:
            all_recs = [JobRecommendationDTO(**item) for item in cached_data]
        else:
            eligible_jobs = list(self.get_eligible_jobs(candidate_user))
            if not eligible_jobs:
                all_recs = []
            else:
                try:
                    cleaned_res, res_doc, emb_res, ctx = self._parse_candidate_resume(resume_file)
                    all_recs = self._score_jobs(
                        eligible_jobs, cleaned_res, res_doc, emb_res, ctx
                    )
                    all_recs.sort(key=lambda r: r.match_score, reverse=True)
                    cache.set(cache_key, [r.model_dump() for r in all_recs], timeout=CACHE_TTL_SECONDS)
                except Exception as exc:
                    logger.exception(f"Error computing recommendations for user {candidate_user.id}: {exc}")
                    raise APIException(
                        "Recommendation scoring failed. Please retry shortly."
                    ) from exc
        filtered = [r for r in all_recs if r.match_score >= min_match]
        if len(filtered) < 5 and all_recs:
            filtered = all_recs[:5]
        applied_count = Application.objects.filter(candidate=candidate_user).count()
        return RecommendationResponse(
            has_resume=True,
            message=None,
            min_match=min_match,
            total_eligible=len(all_recs),
            matched_count=len(filtered),
            applied_count=applied_count,
            results=filtered,
        )

logger = logging.getLogger(__name__)

class IsCandidateOnly(permissions.BasePermission):
    message = "Only candidates have access to AI job recommendations."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'is_candidate', False)
        )

class JobRecommendationsView(APIView):
    permission_classes = [IsCandidateOnly]

    def get(self, request, *args, **kwargs):
        min_match_raw = request.query_params.get('min_match', '50')
        try:
            min_match = int(min_match_raw)
            if min_match < 0 or min_match > 100:
                return Response(
                    {"detail": "min_match must be an integer between 0 and 100."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (ValueError, TypeError):
            return Response(
                {"detail": "min_match must be a valid integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        force_refresh = request.query_params.get('refresh', '').lower() in ('true', '1')
        service = JobRecommendationService()
        response_dto = service.get_recommendations(
            candidate_user=request.user,
            min_match=min_match,
            force_refresh=force_refresh,
        )
        return Response(response_dto.model_dump(), status=status.HTTP_200_OK)
