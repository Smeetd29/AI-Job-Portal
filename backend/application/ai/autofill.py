from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field
import datetime
import re
from typing import Any, List, Optional, Tuple
from typing import List, Optional, Tuple
from typing import Any, Dict, Tuple
import logging
from typing import Any, Dict, Optional

from application.ai.extraction import EducationExtractor
from application.ai.extraction import ExperienceExtractor
from application.ai.extraction import SkillNormalizer
from application.ai.extraction import SkillExtractionPipeline
from application.ai.schemas import ResumeDocument

from application.ai.parsing import clean_text
from application.ai.parsing import ResumeParser
from application.ai.pipeline import extract_raw_text

T = TypeVar("T")

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

class ExtractedField(BaseModel, Generic[T]):
    value: Optional[T] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    source_section: Optional[str] = None
    source_text: Optional[str] = None
    extraction_method: str = "generic"

    @classmethod
    def empty(cls, method: str = "empty") -> "ExtractedField[T]":
        return cls(
            value=None,
            confidence=0.0,
            confidence_level=ConfidenceLevel.UNKNOWN,
            extraction_method=method,
        )

    @classmethod
    def make(
        cls,
        value: Optional[T],
        confidence: float,
        source_section: Optional[str] = None,
        source_text: Optional[str] = None,
        method: str = "extracted",
    ) -> "ExtractedField[T]":
        if value is None:
            return cls.empty(method)
        if confidence >= 0.85:
            level = ConfidenceLevel.HIGH
        elif confidence >= 0.60:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW
        return cls(
            value=value,
            confidence=round(confidence, 2),
            confidence_level=level,
            source_section=source_section,
            source_text=source_text[:200] if source_text else None,
            extraction_method=method,
        )

class ContactAutofill(BaseModel):
    full_name: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())
    email: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())
    phone: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())
    location: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())
    linkedin: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())
    github: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())

class EducationAutofill(BaseModel):
    degree: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())
    field_of_study: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())
    institution: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())
    start_year: ExtractedField[int] = Field(default_factory=lambda: ExtractedField[int].empty())
    graduation_year: ExtractedField[int] = Field(default_factory=lambda: ExtractedField[int].empty())
    cgpa: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())
    academic_level: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())
    grading_system: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str].empty())

class ExperienceEntry(BaseModel):
    company: str
    role: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    responsibilities: List[str] = Field(default_factory=list)
    evidence: str = ""

class ProjectEntry(BaseModel):
    title: str
    technologies: List[str] = Field(default_factory=list)
    description: str = ""

class AutofillData(BaseModel):
    contact: ContactAutofill = Field(default_factory=ContactAutofill)
    education: EducationAutofill = Field(default_factory=EducationAutofill)
    skills: ExtractedField[List[str]] = Field(default_factory=lambda: ExtractedField[List[str]].empty())
    professional_experience: List[ExperienceEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    years_professional_experience: ExtractedField[float] = Field(
        default_factory=lambda: ExtractedField[float].empty()
    )

class AutofillResult(BaseModel):
    autofill_data: AutofillData
    mapped_form_data: Dict[str, Any] = Field(default_factory=dict)
    field_provenance: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    field_confidence: Dict[str, str] = Field(default_factory=dict)
    conflicts: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    summary_message: str = "Autofill completed successfully."

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
_PHONE_CLEAN_RE = re.compile(r"[^\d+]")
_LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:[a-zA-Z0-9_-]+\.)?linkedin\.com\s*/\s*(?:in|pub)\s*/\s*([A-Za-z0-9_\-\s/]+)",
    re.IGNORECASE
)
_GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com\s*/\s*([A-Za-z0-9_\-\s]+)",
    re.IGNORECASE
)

def validate_email(email_str: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not email_str:
        return False, None
    cleaned = email_str.strip().strip(".,;:()<>[]\"'")
    if _EMAIL_REGEX.match(cleaned):
        return True, cleaned.lower()
    return False, None

def validate_phone(phone_str: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not phone_str:
        return False, None
    raw = phone_str.strip()
    digits_only = re.sub(r"\D", "", raw)
    if 7 <= len(digits_only) <= 15:
        if raw.startswith("+"):
            return True, f"+{digits_only}"
        return True, raw
    return False, None

def validate_linkedin_url(url_str: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not url_str:
        return False, None
    clean = url_str.strip()
    m = _LINKEDIN_RE.search(clean)
    if m:
        raw_handle = m.group(1).strip()
        raw_handle = raw_handle.split("?")[0].split("#")[0].strip()
        clean_handle = re.sub(r"\s+", "", raw_handle).strip("/")
        if clean_handle:
            return True, f"https://linkedin.com/in/{clean_handle}"
    return False, None

def validate_github_url(url_str: Optional[str]) -> Tuple[bool, Optional[str]]:
    if not url_str:
        return False, None
    clean = url_str.strip()
    m = _GITHUB_RE.search(clean)
    if m:
        raw_handle = m.group(1).strip()
        raw_handle = raw_handle.split("?")[0].split("#")[0].strip()
        clean_handle = re.sub(r"\s+", "", raw_handle).strip("/")
        if clean_handle:
            return True, f"https://github.com/{clean_handle}"
    return False, None

def validate_cgpa(grade_str: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    if not grade_str:
        return False, None, None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:/\s*(\d+))?", grade_str)
    if not match:
        return False, None, None
    val_float = float(match.group(1))
    max_scale = float(match.group(2)) if match.group(2) else None
    if "%" in grade_str or (max_scale and max_scale == 100) or val_float > 10.0:
        if 0.0 <= val_float <= 100.0:
            return True, f"{val_float:.1f}%", "Percentage"
        return False, None, None
    if max_scale == 4 or (val_float <= 4.0 and "gpa" in grade_str.lower() and "cgpa" not in grade_str.lower()):
        if 0.0 <= val_float <= 4.0:
            return True, f"{val_float:.2f}", "GPA"
    if 0.0 <= val_float <= 10.0:
        return True, f"{val_float:.2f}", "CGPA"
    return False, None, None

def validate_graduation_year(year_val: Any) -> Tuple[bool, Optional[int]]:
    if not year_val:
        return False, None
    try:
        y = int(str(year_val).strip())
        current_year = datetime.date.today().year
        if (current_year - 50) <= y <= (current_year + 10):
            return True, y
    except (ValueError, TypeError):
        pass
    return False, None

def validate_degree(degree_str: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    if not degree_str:
        return False, None, None
    clean = degree_str.strip()
    lower = clean.lower()
    if re.search(r"\b(?:ph\.?d|doctorate|doctor of philosophy)\b", lower):
        return True, clean, "PhD"
    if re.search(r"\b(?:m\.?tech|mtech|m\.?e|m\.?s|ms|m\.?sc|msc|mba|master|masters)\b", lower):
        return True, clean, "Master"
    if re.search(r"\b(?:b\.?tech|btech|b\.?e|b\.?s|bs|b\.?sc|bsc|bca|bba|bachelor|bachelors)\b", lower):
        return True, clean, "Bachelor"
    if re.search(r"\b(?:diploma|associate)\b", lower):
        return True, clean, "Diploma"
    return False, None, None

def validate_clean_skills(skills: List[str]) -> List[str]:
    cleaned = []
    seen = set()
    noise_re = re.compile(
        r"^(?:cgpa|gpa|grade|university|college|school|phone|email|linkedin|github|\+?\d[\d\s-]{6,}|\d{4})$",
        re.IGNORECASE,
    )
    for s in skills:
        item = s.strip()
        if not item or len(item) < 2 or len(item) > 40:
            continue
        if noise_re.match(item) or not any(c.isalpha() for c in item):
            continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(item)
    return cleaned

_MAJOR_KEYWORDS = [
    "computer science", "information technology", "data science", "artificial intelligence",
    "machine learning", "software engineering", "electronics", "electrical", "mechanical",
    "civil", "biotechnology", "business administration", "commerce", "physics", "mathematics"
]

class AutofillFieldExtractor:

    def __init__(self) -> None:
        self.skill_pipeline = SkillExtractionPipeline()
        self.normalizer = SkillNormalizer()
        self.education_extractor = EducationExtractor()
        self.experience_extractor = ExperienceExtractor()

    def extract_contact(self, raw_text: str, resume_doc: ResumeDocument) -> ContactAutofill:
        header_lines = [line.strip() for line in raw_text[:1000].splitlines() if line.strip()][:10]
        header_blob = "\n".join(header_lines)
        name_val: Optional[str] = None
        name_conf = 0.0
        name_src = ""
        for line in header_lines[:5]:
            clean_l = re.sub(r"[^\w\s]", "", line).strip()
            tokens = clean_l.split()
            if 2 <= len(tokens) <= 4 and all(t.isalpha() for t in tokens):
                lower_l = clean_l.lower()
                if not any(k in lower_l for k in [
                    "resume", "curriculum", "cv", "page", "developer", "engineer",
                    "student", "summary", "experience", "education", "impactful",
                    "scalable", "systems", "seeking", "roles", "candidate", "project"
                ]):
                    name_val = " ".join(t.capitalize() for t in tokens)
                    name_conf = 0.95
                    name_src = line
                    break
        email_val: Optional[str] = None
        email_conf = 0.0
        email_src = ""
        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", header_blob)
        if not email_match:
            email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b", raw_text)
        if email_match:
            is_valid, clean_e = validate_email(email_match.group(0))
            if is_valid:
                email_val = clean_e
                email_conf = 0.95
                email_src = email_match.group(0)
        phone_val: Optional[str] = None
        phone_conf = 0.0
        phone_src = ""
        phone_match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{4,6}", header_blob)
        if not phone_match:
            phone_match = re.search(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{4,6}", raw_text[:2000])
        if phone_match:
            is_valid, clean_p = validate_phone(phone_match.group(0))
            if is_valid:
                phone_val = clean_p
                phone_conf = 0.90
                phone_src = phone_match.group(0)
        li_match = re.search(
            r"(?:https?://)?(?:[a-zA-Z0-9_-]+\.)?linkedin\.com\s*/\s*(?:in|pub)\s*/\s*[A-Za-z0-9_\-\s/]+?(?=\s*[|,\n]|\s{2,}|\s*$)",
            raw_text,
            re.IGNORECASE,
        )
        li_val, li_conf, li_src = None, 0.0, ""
        if li_match:
            is_v, clean_li = validate_linkedin_url(li_match.group(0))
            if is_v:
                li_val, li_conf, li_src = clean_li, 0.95, li_match.group(0).strip()
        gh_match = re.search(
            r"(?:https?://)?(?:www\.)?github\.com\s*/\s*[A-Za-z0-9_\-\s]+?(?=\s*[|,\n]|\s{2,}|\s*$)",
            raw_text,
            re.IGNORECASE,
        )
        gh_val, gh_conf, gh_src = None, 0.0, ""
        if gh_match:
            is_v, clean_gh = validate_github_url(gh_match.group(0))
            if is_v:
                gh_val, gh_conf, gh_src = clean_gh, 0.95, gh_match.group(0).strip()
        return ContactAutofill(
            full_name=ExtractedField.make(name_val, name_conf, "preamble", name_src, "header_parser"),
            email=ExtractedField.make(email_val, email_conf, "preamble", email_src, "regex"),
            phone=ExtractedField.make(phone_val, phone_conf, "preamble", phone_src, "regex"),
            linkedin=ExtractedField.make(li_val, li_conf, "preamble", li_src, "regex"),
            github=ExtractedField.make(gh_val, gh_conf, "preamble", gh_src, "regex"),
        )

    def extract_education(self, resume_doc: ResumeDocument) -> EducationAutofill:
        sec_text = resume_doc.education_section or ""
        for k, v in resume_doc.other_sections.items():
            if any(term in k.lower() for term in ["edu", "acad", "school", "college", "cgpa", "gpa", "b.tech", "20", "19"]):
                sec_text += f"\n{k}\n{v}"
        if len(sec_text.strip()) < 20 and resume_doc.raw_text:
            sec_text = resume_doc.raw_text
        entries = resume_doc.education_details or self.education_extractor.extract_details(sec_text)
        deg_val, inst_val, grad_val, cgpa_val, level_val, grade_sys_val, major_val = None, None, None, None, None, None, None
        deg_conf, inst_conf, grad_conf, cgpa_conf, major_conf = 0.0, 0.0, 0.0, 0.0, 0.0
        src_snippet = ""
        if entries:
            top_edu = entries[0]
            src_snippet = f"{top_edu.degree} {top_edu.institution} {top_edu.dates}".strip()
            for entry in entries:
                if not deg_val and entry.degree:
                    is_v, clean_d, level = validate_degree(entry.degree)
                    if is_v:
                        deg_val, level_val, deg_conf = clean_d, level, 0.95
                if not inst_val and entry.institution and len(entry.institution) >= 4:
                    inst_val = entry.institution
                    inst_conf = 0.90
                if not cgpa_val and entry.cgpa:
                    is_v, clean_g, g_sys = validate_cgpa(entry.cgpa)
                    if is_v:
                        cgpa_val, grade_sys_val, cgpa_conf = clean_g, g_sys, 0.95
                if not grad_val and entry.dates:
                    year_matches = re.findall(r"\b(20\d{2}|19\d{2})\b", entry.dates)
                    if year_matches:
                        is_v, g_yr = validate_graduation_year(year_matches[-1])
                        if is_v:
                            grad_val, grad_conf = g_yr, 0.90
        if not grad_val and sec_text:
            year_matches = re.findall(r"\b(20\d{2})\b", sec_text)
            if year_matches:
                is_v, g_yr = validate_graduation_year(year_matches[-1])
                if is_v:
                    grad_val, grad_conf = g_yr, 0.85
        if not cgpa_val and sec_text:
            is_v, clean_g, g_sys = validate_cgpa(sec_text)
            if is_v:
                cgpa_val, grade_sys_val, cgpa_conf = clean_g, g_sys, 0.85
        search_blob = f"{deg_val or ''} {sec_text}".lower()
        for kw in _MAJOR_KEYWORDS:
            if kw in search_blob:
                major_val = kw.title()
                major_conf = 0.85
                break
        return EducationAutofill(
            degree=ExtractedField.make(deg_val, deg_conf, "education", src_snippet, "degree_parser"),
            field_of_study=ExtractedField.make(major_val, major_conf, "education", sec_text[:100], "keyword_match"),
            institution=ExtractedField.make(inst_val, inst_conf, "education", src_snippet, "institution_parser"),
            graduation_year=ExtractedField.make(grad_val, grad_conf, "education", src_snippet, "date_parser"),
            cgpa=ExtractedField.make(cgpa_val, cgpa_conf, "education", src_snippet, "grade_parser"),
            academic_level=ExtractedField.make(level_val, deg_conf, "education", src_snippet, "level_derivation"),
            grading_system=ExtractedField.make(grade_sys_val, cgpa_conf, "education", src_snippet, "grade_system_derivation"),
        )

    def extract_experience(self, resume_doc: ResumeDocument) -> Tuple[List[ExperienceEntry], ExtractedField[float]]:
        exp_sec = resume_doc.experience_section or ""
        entries: List[ExperienceEntry] = []
        blocks = [b.strip() for b in exp_sec.split("\n\n") if b.strip()]
        for block in blocks:
            lower = block.lower()
            if any(k in lower for k in ["committee", "student club", "college team", "chapter", "hackathon"]):
                continue
            if any(k in lower for k in ["software engineer", "developer", "intern", "consultant", "architect", "analyst"]):
                lines = [l.strip() for l in block.splitlines() if l.strip()]
                role_line = lines[0] if lines else "Engineer"
                comp_line = lines[1] if len(lines) > 1 else "Company"
                entries.append(
                    ExperienceEntry(
                        company=comp_line,
                        role=role_line,
                        evidence=block[:150],
                    )
                )
        years = resume_doc.years_experience or 0.0
        conf = 0.90 if entries else 0.80
        years_field = ExtractedField.make(years, conf, "experience", exp_sec[:100], "experience_extractor")
        return entries, years_field

    def extract_projects(self, resume_doc: ResumeDocument) -> List[ProjectEntry]:
        proj_sec = resume_doc.projects_section or ""
        if not proj_sec:
            return []
        projects: List[ProjectEntry] = []
        raw_items = [item.strip() for item in re.split(r"\n(?=[A-Z0-9][\w\s\-—|]{3,40}\n)", proj_sec) if item.strip()]
        for item in raw_items[:6]:
            lines = [l.strip() for l in item.splitlines() if l.strip()]
            if not lines:
                continue
            title_line = re.sub(r"^[•\-\*]\s*", "", lines[0])
            title = title_line.split("|")[0].split("—")[0].strip()
            techs = self.skill_pipeline.extract(item)
            desc = " ".join(lines[1:]) if len(lines) > 1 else ""
            projects.append(ProjectEntry(title=title, technologies=techs[:8], description=desc[:200]))
        return projects

    def extract_skills(self, resume_doc: ResumeDocument) -> ExtractedField[List[str]]:
        raw_skills = resume_doc.skill_candidates
        if not raw_skills:
            raw_skills = self.skill_pipeline.extract(resume_doc.skills_section or "")
        normalized = self.normalizer.normalize_list(raw_skills)
        clean = validate_clean_skills(normalized)
        conf = 0.95 if clean else 0.0
        return ExtractedField.make(clean, conf, "skills", ", ".join(clean[:10]), "skill_taxonomy")

class ApplicationFormMapper:

    @staticmethod
    def _is_mappable(field: ExtractedField[Any]) -> bool:
        if field.value is None:
            return False
        return field.confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)

    @classmethod
    def map_to_form(cls, data: AutofillData) -> Tuple[Dict[str, Any], Dict[str, Dict[str, Any]], Dict[str, str]]:
        form_data: Dict[str, Any] = {}
        provenance: Dict[str, Dict[str, Any]] = {}
        confidences: Dict[str, str] = {}
        def record(form_key: str, extracted: ExtractedField[Any], transform=None) -> None:
            if not cls._is_mappable(extracted):
                return
            val = transform(extracted.value) if transform else extracted.value
            if val is not None and str(val).strip():
                form_data[form_key] = val
                provenance[form_key] = {
                    "value": str(val),
                    "confidence": extracted.confidence,
                    "confidence_level": extracted.confidence_level.value,
                    "source_section": extracted.source_section,
                    "source_text": extracted.source_text,
                    "extraction_method": extracted.extraction_method,
                }
                confidences[form_key] = extracted.confidence_level.value
        record("full_name", data.contact.full_name)
        record("email", data.contact.email)
        record("phone_number", data.contact.phone)
        record("linkedin_profile", data.contact.linkedin)
        record("github_profile", data.contact.github)
        record("university_name", data.education.institution)
        record("academic_level", data.education.academic_level)
        record("major", data.education.field_of_study)
        record("graduation_year", data.education.graduation_year)
        record("grading_system", data.education.grading_system)
        record("overall_grade", data.education.cgpa)
        if data.education.field_of_study.value and "engineering" in data.education.field_of_study.value.lower():
            form_data.setdefault("stream", "Engineering")
        elif data.education.degree.value and "tech" in data.education.degree.value.lower():
            form_data.setdefault("stream", "Engineering")
        record("skills", data.skills, transform=lambda sk_list: ", ".join(sk_list) if sk_list else None)
        if data.education.field_of_study.value and cls._is_mappable(data.education.field_of_study):
            form_data.setdefault("area_of_interest", data.education.field_of_study.value)
        return form_data, provenance, confidences

logger = logging.getLogger(__name__)

class ResumeAutofillService:

    def __init__(self) -> None:
        self.parser = ResumeParser()
        self.extractor = AutofillFieldExtractor()

    def process(self, file_source: Any, candidate_user: Optional[Any] = None) -> AutofillResult:
        try:
            raw_text = extract_raw_text(file_source)
        except Exception:
            raw_text = ""
        if not raw_text or not raw_text.strip():
            return AutofillResult(
                autofill_data=AutofillData(),
                mapped_form_data={},
                field_provenance={},
                field_confidence={},
                conflicts={},
                summary_message="No readable text found in resume file.",
            )
        cleaned = clean_text(raw_text)
        resume_doc = self.parser.parse(clean_text=cleaned, raw_text=raw_text)
        contact = self.extractor.extract_contact(raw_text, resume_doc)
        education = self.extractor.extract_education(resume_doc)
        exp_entries, years_field = self.extractor.extract_experience(resume_doc)
        projects = self.extractor.extract_projects(resume_doc)
        skills_field = self.extractor.extract_skills(resume_doc)
        autofill_data = AutofillData(
            contact=contact,
            education=education,
            skills=skills_field,
            professional_experience=exp_entries,
            projects=projects,
            years_professional_experience=years_field,
        )
        conflicts: Dict[str, Dict[str, Any]] = {}
        if candidate_user is not None:
            self._resolve_profile_conflicts(autofill_data, candidate_user, conflicts)
        form_data, provenance, confidences = ApplicationFormMapper.map_to_form(autofill_data)
        return AutofillResult(
            autofill_data=autofill_data,
            mapped_form_data=form_data,
            field_provenance=provenance,
            field_confidence=confidences,
            conflicts=conflicts,
            summary_message="Resume parsed and application fields populated successfully.",
        )

    def _resolve_profile_conflicts(
        self,
        data: AutofillData,
        user: Any,
        conflicts: Dict[str, Dict[str, Any]],
    ) -> None:
        profile_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        if not profile_name and getattr(user, 'username', ''):
            profile_name = user.username
        if profile_name:
            res_name = data.contact.full_name.value
            if res_name and res_name.lower() != profile_name.lower():
                conflicts["full_name"] = {
                    "profile_value": profile_name,
                    "resume_value": res_name,
                    "resolution": "profile_preferred",
                }
            data.contact.full_name = ExtractedField.make(
                profile_name, 1.0, "user_profile", f"User account: {profile_name}", "profile_identity"
            )
        profile_email = getattr(user, "email", None)
        if profile_email:
            res_email = data.contact.email.value
            if res_email and res_email.lower() != profile_email.lower():
                conflicts["email"] = {
                    "profile_value": profile_email,
                    "resume_value": res_email,
                    "resolution": "profile_preferred",
                }
            data.contact.email = ExtractedField.make(
                profile_email, 1.0, "user_profile", f"Verified email: {profile_email}", "profile_identity"
            )
        cand_prof = getattr(user, "candidate_profile", None)
        profile_phone = getattr(cand_prof, "phone", None) if cand_prof else None
        if profile_phone:
            res_phone = data.contact.phone.value
            if res_phone and res_phone != profile_phone:
                conflicts["phone_number"] = {
                    "profile_value": profile_phone,
                    "resume_value": res_phone,
                    "resolution": "profile_preferred",
                }
            data.contact.phone = ExtractedField.make(
                profile_phone, 1.0, "user_profile", f"Profile phone: {profile_phone}", "profile_identity"
            )
