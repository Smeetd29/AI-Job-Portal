from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class GoldenJob:
    job_id: str
    title: str
    company: str
    description: str
    required_skills: List[str]
    preferred_skills: List[str] = field(default_factory=list)
    category: str = ""
    minimum_experience_years: Optional[float] = 0.0
    required_degree_level: Optional[int] = 1
    education_requirements: List[str] = field(default_factory=list)
    location: str = "Remote"
    work_mode: str = "Remote"
    seniority: str = "Mid"
    eligibility_constraints: List[str] = field(default_factory=list)
    source_type: str = "synthetic_verified"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoldenJob":
        return cls(
            job_id=str(data["job_id"]),
            title=str(data["title"]),
            company=str(data.get("company", "TechCorp")),
            description=str(data["description"]),
            required_skills=[str(s) for s in data.get("required_skills", [])],
            preferred_skills=[str(s) for s in data.get("preferred_skills", [])],
            category=str(data.get("category", "")),
            minimum_experience_years=float(data["minimum_experience_years"]) if data.get("minimum_experience_years") is not None else None,
            required_degree_level=int(data["required_degree_level"]) if data.get("required_degree_level") is not None else None,
            education_requirements=[str(e) for e in data.get("education_requirements", [])],
            location=str(data.get("location", "Remote")),
            work_mode=str(data.get("work_mode", "Remote")),
            seniority=str(data.get("seniority", "Mid")),
            eligibility_constraints=[str(c) for c in data.get("eligibility_constraints", [])],
            source_type=str(data.get("source_type", "synthetic_verified")),
        )


@dataclass
class GoldenResume:
    resume_id: str
    candidate_name: str
    resume_text: str
    candidate_profile: Dict[str, Any]
    source_type: str = "synthetic_verified"

    @property
    def skills(self) -> List[str]:
        return [str(s) for s in self.candidate_profile.get("skills", [])]

    @property
    def experience_years(self) -> Optional[float]:
        exp = self.candidate_profile.get("experience_years")
        return float(exp) if exp is not None else None

    @property
    def seniority(self) -> str:
        return str(self.candidate_profile.get("seniority", "Junior"))

    @property
    def degree_level(self) -> Optional[int]:
        deg = self.candidate_profile.get("degree_level")
        return int(deg) if deg is not None else None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoldenResume":
        return cls(
            resume_id=str(data["resume_id"]),
            candidate_name=str(data.get("candidate_name", "Candidate")),
            resume_text=str(data["resume_text"]),
            candidate_profile=dict(data.get("candidate_profile", {})),
            source_type=str(data.get("source_type", "synthetic_verified")),
        )


@dataclass
class GoldenRecommendation:
    case_id: str
    resume_id: str
    job_id: str
    relevance: int
    relevant_for_recommendation: bool
    reference_reasoning: str
    expected_skill_matches: List[str] = field(default_factory=list)
    expected_missing_required_skills: List[str] = field(default_factory=list)
    eligibility_status: str = "eligible"
    source_type: str = "synthetic_verified"
    hard_negative: bool = False
    pair_type: str = "cross_domain"
    annotator_grades: List[int] = field(default_factory=list)
    annotators_agree: bool = True
    rubric: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoldenRecommendation":
        return cls(
            case_id=str(data["case_id"]),
            resume_id=str(data["resume_id"]),
            job_id=str(data["job_id"]),
            relevance=int(data["relevance"]),
            relevant_for_recommendation=bool(data["relevant_for_recommendation"]),
            reference_reasoning=str(data.get("reference_reasoning", "")),
            expected_skill_matches=[str(s) for s in data.get("expected_skill_matches", [])],
            expected_missing_required_skills=[str(s) for s in data.get("expected_missing_required_skills", [])],
            eligibility_status=str(data.get("eligibility_status", "eligible")),
            source_type=str(data.get("source_type", "synthetic_verified")),
            hard_negative=bool(data.get("hard_negative", False)),
            pair_type=str(data.get("pair_type", "cross_domain")),
            annotator_grades=[int(g) for g in data.get("annotator_grades", [])],
            annotators_agree=bool(data.get("annotators_agree", True)),
            rubric=dict(data.get("rubric", {})),
        )


@dataclass
class GoldenResumeSummary:
    case_id: str
    resume_id: str
    audience: str
    expected_summary: str
    reference_facts: List[str]
    must_include: List[str] = field(default_factory=list)
    must_not_claim: List[str] = field(default_factory=list)
    source_type: str = "synthetic_verified"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoldenResumeSummary":
        return cls(
            case_id=str(data["case_id"]),
            resume_id=str(data["resume_id"]),
            audience=str(data.get("audience", "recruiter")),
            expected_summary=str(data["expected_summary"]),
            reference_facts=[str(f) for f in data.get("reference_facts", [])],
            must_include=[str(m) for m in data.get("must_include", [])],
            must_not_claim=[str(m) for m in data.get("must_not_claim", [])],
            source_type=str(data.get("source_type", "synthetic_verified")),
        )


class GoldenDataLoader:
    """Loads and validates golden dataset files."""

    def __init__(self, dataset_dir: Optional[Path] = None):
        self.dataset_dir = dataset_dir or (Path(__file__).resolve().parent.parent / "datasets")

    def load_jobs(self, filename: str = "golden_jobs.jsonl") -> Dict[str, GoldenJob]:
        path = self.dataset_dir / filename
        jobs = {}
        if not path.exists():
            return jobs
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                item = json.loads(s)
                job = GoldenJob.from_dict(item)
                jobs[job.job_id] = job
        return jobs

    def load_resumes(self, filename: str = "golden_resumes.jsonl") -> Dict[str, GoldenResume]:
        path = self.dataset_dir / filename
        resumes = {}
        if not path.exists():
            return resumes
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                item = json.loads(s)
                resume = GoldenResume.from_dict(item)
                resumes[resume.resume_id] = resume
        return resumes

    def load_recommendations(self, filename: str = "golden_recommendations.jsonl") -> List[GoldenRecommendation]:
        path = self.dataset_dir / filename
        recs = []
        if not path.exists():
            return recs
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                item = json.loads(s)
                recs.append(GoldenRecommendation.from_dict(item))
        return recs

    def load_summaries(self, filename: str = "golden_resume_summaries.jsonl") -> List[GoldenResumeSummary]:
        path = self.dataset_dir / filename
        summaries = []
        if not path.exists():
            return summaries
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                item = json.loads(s)
                summaries.append(GoldenResumeSummary.from_dict(item))
        return summaries

    def load_splits(self, filename: str = "golden_candidate_splits.csv") -> Dict[str, str]:
        """Loads candidate split assignments: {'RES_0001': 'train', ...}."""
        path = self.dataset_dir / filename
        splits: Dict[str, str] = {}
        if not path.exists():
            return splits
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                splits[str(row["candidate_id"])] = str(row["split"])
        return splits

    def get_candidates_for_split(self, split: str, filename: str = "golden_candidate_splits.csv") -> Set[str]:
        splits = self.load_splits(filename)
        return {cid for cid, s in splits.items() if s == split}


def map_education_to_degree_level(edu_text: str) -> int:
    """Maps descriptive education requirements or degrees to 1..4 scale."""
    text = (edu_text or "").lower()
    if any(k in text for k in ["master", "m.sc", "m.tech", "mba", "ph.d", "doctor"]):
        return 3
    if any(k in text for k in ["bachelor", "b.sc", "b.tech", "b.e"]):
        return 2
    if any(k in text for k in ["diploma", "associate"]):
        return 1
    return 1


class SyntheticBenchmarkLoader:
    """
    Loads, adapts, and validates the 200-job, 60-candidate, 12,000-judgment
    Synthetic Benchmark dataset with candidate-level split enforcement.

    Configurable via SYNTHETIC_BENCHMARK_DIR environment variable
    or constructor dataset_dir parameter.
    """

    def __init__(self, dataset_dir: Optional[Path] = None):
        if dataset_dir:
            self.dataset_dir = Path(dataset_dir)
        elif os.environ.get("SYNTHETIC_BENCHMARK_DIR"):
            self.dataset_dir = Path(os.environ["SYNTHETIC_BENCHMARK_DIR"])
        else:
            self.dataset_dir = Path(__file__).resolve().parent.parent / "datasets" / "synthetic_benchmark"

    def load_manifest(self) -> Dict[str, Any]:
        path = self.dataset_dir / "manifest.json"
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_jobs(self) -> Dict[str, GoldenJob]:
        """Loads 200 benchmark jobs from jobs.jsonl (or jobs.csv fallback)."""
        jsonl_path = self.dataset_dir / "jobs.jsonl"
        csv_path = self.dataset_dir / "jobs.csv"
        jobs: Dict[str, GoldenJob] = {}

        if jsonl_path.exists():
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    item = json.loads(s)
                    req_skills = item.get("required_skills", [])
                    if isinstance(req_skills, str):
                        req_skills = json.loads(req_skills)
                    pref_skills = item.get("preferred_skills", [])
                    if isinstance(pref_skills, str):
                        pref_skills = json.loads(pref_skills)

                    job = GoldenJob(
                        job_id=str(item["job_id"]),
                        title=str(item["title"]),
                        company="TechCorp",
                        description=str(item["description"]),
                        required_skills=[str(s) for s in req_skills],
                        preferred_skills=[str(s) for s in pref_skills],
                        category=str(item.get("role_family", "")),
                        minimum_experience_years=float(item.get("min_experience_years", 0.0)),
                        required_degree_level=map_education_to_degree_level(item.get("education_requirement", "")),
                        education_requirements=[str(item.get("education_requirement", ""))],
                        location=str(item.get("location", "Remote")),
                        work_mode=str(item.get("work_mode", "Remote")),
                        seniority=str(item.get("seniority", "Mid")),
                        source_type="synthetic_heuristic",
                    )
                    jobs[job.job_id] = job
        elif csv_path.exists():
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for item in reader:
                    req_skills = json.loads(item["required_skills"]) if item.get("required_skills") else []
                    pref_skills = json.loads(item["preferred_skills"]) if item.get("preferred_skills") else []
                    job = GoldenJob(
                        job_id=str(item["job_id"]),
                        title=str(item["title"]),
                        company="TechCorp",
                        description=str(item["description"]),
                        required_skills=[str(s) for s in req_skills],
                        preferred_skills=[str(s) for s in pref_skills],
                        category=str(item.get("role_family", "")),
                        minimum_experience_years=float(item.get("min_experience_years", 0.0)),
                        required_degree_level=map_education_to_degree_level(item.get("education_requirement", "")),
                        education_requirements=[str(item.get("education_requirement", ""))],
                        location=str(item.get("location", "Remote")),
                        work_mode=str(item.get("work_mode", "Remote")),
                        seniority=str(item.get("seniority", "Mid")),
                        source_type="synthetic_heuristic",
                    )
                    jobs[job.job_id] = job
        return jobs

    def load_resumes(self) -> Dict[str, GoldenResume]:
        """Loads 60 benchmark candidate profiles adapted into GoldenResume format."""
        jsonl_path = self.dataset_dir / "candidates.jsonl"
        csv_path = self.dataset_dir / "candidates.csv"
        resumes: Dict[str, GoldenResume] = {}

        items = []
        if jsonl_path.exists():
            with open(jsonl_path, "r", encoding="utf-8") as f:
                items = [json.loads(line) for line in f if line.strip()]
        elif csv_path.exists():
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    items.append({
                        "candidate_id": row["candidate_id"],
                        "display_name": row["display_name"],
                        "target_role_family": row.get("target_role_family", ""),
                        "current_seniority": row.get("current_seniority", "Junior"),
                        "experience_years": float(row.get("experience_years", 0)),
                        "skills": json.loads(row["skills"]) if row.get("skills") else [],
                        "education": row.get("education", ""),
                        "summary": row.get("summary", ""),
                        "preferred_locations": json.loads(row["preferred_locations"]) if row.get("preferred_locations") else [],
                        "preferred_work_modes": json.loads(row["preferred_work_modes"]) if row.get("preferred_work_modes") else [],
                    })

        for c in items:
            cid = str(c["candidate_id"])
            name = str(c.get("display_name", f"Candidate {cid}"))
            skills = [str(s) for s in c.get("skills", [])]
            exp_yrs = float(c.get("experience_years", 0.0))
            seniority = str(c.get("current_seniority", "Junior"))
            edu_str = str(c.get("education", ""))
            deg_lvl = map_education_to_degree_level(edu_str)
            summary = str(c.get("summary", ""))
            role_family = str(c.get("target_role_family", ""))

            resume_text = (
                f"{name}\n"
                f"{role_family} | {seniority} | {exp_yrs:.0f} years experience\n\n"
                f"Summary:\n{summary}\n\n"
                f"Skills:\n{', '.join(skills)}\n\n"
                f"Experience:\n{exp_yrs:.0f} years of experience in {role_family}.\n\n"
                f"Education:\n{edu_str}\n"
            )

            candidate_profile = {
                "skills": skills,
                "experience_years": exp_yrs,
                "seniority": seniority,
                "degree_level": deg_lvl,
                "target_role_family": role_family,
                "education": edu_str,
                "preferred_locations": c.get("preferred_locations", []),
                "preferred_work_modes": c.get("preferred_work_modes", []),
            }

            res = GoldenResume(
                resume_id=cid,
                candidate_name=name,
                resume_text=resume_text,
                candidate_profile=candidate_profile,
                source_type="synthetic_heuristic",
            )
            resumes[cid] = res

        return resumes

    def load_recommendations(self) -> List[GoldenRecommendation]:
        """Loads 12,000 candidate-job heuristic judgments."""
        path = self.dataset_dir / "synthetic_relevance_judgments.csv"
        recs: List[GoldenRecommendation] = []
        if not path.exists():
            return recs

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cid = str(row["candidate_id"])
                jid = str(row["job_id"])
                grade = int(row["relevance_grade"])
                recs.append(
                    GoldenRecommendation(
                        case_id=f"{cid}_{jid}",
                        resume_id=cid,
                        job_id=jid,
                        relevance=grade,
                        relevant_for_recommendation=(grade >= 2),
                        reference_reasoning=(
                            f"Heuristic score: {row.get('heuristic_relevance_score', 0)}, "
                            f"role_match: {row.get('role_family_match', 0)}, "
                            f"skill_recall: {row.get('skill_recall', 0)}"
                        ),
                        expected_skill_matches=[],
                        expected_missing_required_skills=[],
                        eligibility_status="eligible",
                        source_type="synthetic_heuristic",
                    )
                )
        return recs

    def load_splits(self) -> Dict[str, str]:
        """Loads candidate split assignments: {'CAND001': 'train', ...}."""
        path = self.dataset_dir / "candidate_level_splits.csv"
        splits: Dict[str, str] = {}
        if not path.exists():
            return splits
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                splits[str(row["candidate_id"])] = str(row["split"])
        return splits

    def get_candidates_for_split(self, split: str) -> Set[str]:
        splits = self.load_splits()
        return {cid for cid, s in splits.items() if s == split}

    def get_judgments_for_split(self, split: str) -> List[GoldenRecommendation]:
        split_cands = self.get_candidates_for_split(split)
        all_recs = self.load_recommendations()
        return [r for r in all_recs if r.resume_id in split_cands]

    def compute_split_hashes(self) -> Dict[str, str]:
        splits_path = self.dataset_dir / "candidate_level_splits.csv"
        content = splits_path.read_bytes() if splits_path.exists() else b""
        return {
            "candidate_level_splits_sha256": hashlib.sha256(content).hexdigest(),
        }
