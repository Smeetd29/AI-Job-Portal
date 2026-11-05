from __future__ import annotations

from pathlib import Path
import re
import unicodedata
import io
from typing import Dict, List, Optional, Tuple

from application.ai.schemas import JobDocument, ResumeDocument

_BULLET_CHARS: str = (
    "\u2022\u00B7\u25AA\u25CF\u25E6\u2043\u2219"
    "\u25B8\u25B9\u25C6\u25C8\u2605\u2606"
    "\u25A0\u25A1\u25BA\u25BB"
)
_BULLET_LINE_RE = re.compile(
    r"^[ \t]*[" + re.escape(_BULLET_CHARS) + r"\*]\s*",
    re.MULTILINE,
)

_PAGE_NUM_RE = re.compile(r"^\s*[-–]?\s*\d{1,4}\s*[-–]?\s*$", re.MULTILINE)

_FORM_FEED_RE = re.compile(r"\f")

_EXCESS_NEWLINES_RE = re.compile(r"\n{3,}")

_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")

_TRAILING_SPACE_RE = re.compile(r"[ \t]+$", re.MULTILINE)

_LIGATURES: List[tuple[str, str]] = [
    ("\ufb03", "ffi"),
    ("\ufb04", "ffl"),
    ("\ufb00", "ff"),
    ("\ufb01", "fi"),
    ("\ufb02", "fl"),
]

_QUOTE_DASH_MAP: List[tuple[str, str]] = [
    ("\u2019", "'"),
    ("\u2018", "'"),
    ("\u201c", '"'),
    ("\u201d", '"'),
    ("\u2013", "-"),
    ("\u2014", "--"),
    ("\u2026", "..."),
]

class TextCleaner:

    def fix_encoding_artifacts(self, text: str) -> str:
        for ligature, replacement in _LIGATURES:
            text = text.replace(ligature, replacement)
        for src, dst in _QUOTE_DASH_MAP:
            text = text.replace(src, dst)
        text = unicodedata.normalize("NFC", text)
        return text

    def remove_page_numbers(self, text: str) -> str:
        return _PAGE_NUM_RE.sub("", text)

    def normalize_bullets(self, text: str) -> str:
        return _BULLET_LINE_RE.sub("- ", text)

    def normalize_whitespace(self, text: str) -> str:
        text = _FORM_FEED_RE.sub("\n\n", text)
        text = _TRAILING_SPACE_RE.sub("", text)
        text = _MULTI_SPACE_RE.sub(" ", text)
        text = _EXCESS_NEWLINES_RE.sub("\n\n", text)
        return text.strip()

    def clean(self, text: str) -> str:
        if not text:
            return ""
        text = self.fix_encoding_artifacts(text)
        text = self.remove_page_numbers(text)
        text = self.normalize_bullets(text)
        text = self.normalize_whitespace(text)
        return text

def clean_text(text: str) -> str:
    return TextCleaner().clean(text)

def _docx_text(doc):
    return "\n".join([q.text for q in doc.paragraphs if q.text] + ["  ".join(c.text for c in r.cells) for t in doc.tables for r in t.rows])

def _extract_pdf_pages(reader) -> str:
    pages_text = []
    for page in reader.pages:
        try:
            t = page.extract_text(extraction_mode="layout")
        except Exception:
            t = page.extract_text()
        if t:
            pages_text.append(t)
    full = "\n".join(pages_text)
    # Fix glued tokens common in LaTeX PDF kerning
    full = re.sub(r"([a-zA-Z])([|])", r"\1 \2", full)
    full = re.sub(r"([|])([a-zA-Z])", r"\1 \2", full)
    return full

def load_text(path):
    if isinstance(path, (bytes, bytearray)):
        if path.startswith(b"%PDF"):
            import pypdf
            return _extract_pdf_pages(pypdf.PdfReader(io.BytesIO(path)))
        if path.startswith(b"PK"):
            import docx
            return _docx_text(docx.Document(io.BytesIO(path)))
        return path.decode("utf-8", errors="replace")
    p = Path(path)
    if not p.is_file():
        return str(path)
    s = p.suffix.lower()
    if s == ".pdf":
        import pypdf
        return _extract_pdf_pages(pypdf.PdfReader(str(p)))
    if s in (".docx", ".doc"):
        import docx
        return _docx_text(docx.Document(str(p)))
    return p.read_text(encoding="utf-8", errors="replace")

_RESUME = {
    'summary': 'summary|professional summary|career summary|executive summary|objective|career objective|professional objective|personal statement|about|about me|profile|professional profile|overview|introduction|highlights',
    'skills': 'skills|technical skills|core competencies|competencies|key skills|technical expertise|expertise|areas of expertise|technologies|technology stack|tech stack|tools|tools and technologies|tools & technologies|programming languages|languages and frameworks|technical proficiencies|proficiencies|skills and technologies|technical knowledge|technology|key competencies|software skills',
    'experience': 'experience|work experience|professional experience|employment history|employment|career history|work history|professional background|relevant experience|internship|internships|industry experience|positions held|career experience|experience & activities|experience and activities|activities & experience|activities and experience|work experience & activities|work experience and activities|leadership & experience|leadership and experience',
    'projects': 'projects|personal projects|academic projects|side projects|open source|open source projects|notable projects|key projects|selected projects|portfolio',
    'education': 'education|academic background|academic qualifications|academics|educational background|educational qualifications|degrees',
    'certifications': 'certifications|certification|certificates|professional certifications|licenses|licenses and certifications|accreditations|training and certifications',
    'achievements': 'achievements|awards|honors|honours|accomplishments|recognition|awards and honors|honors and awards|awards & honors',
}
_JOB = {
    'summary': 'about|about us|overview|company overview|about the role|about this role|about the job|about the position|job summary|position summary|role summary|the role|role overview',
    'responsibilities': "responsibilities|key responsibilities|your responsibilities|role & responsibilities|role and responsibilities|what you'll do|what you will do|your role|duties|job duties|day-to-day|day to day|scope of work|what you'll be doing|what the role involves|the job",
    'required_skills': "requirements|required skills|must have|required qualifications|technical requirements|minimum qualifications|minimum requirements|basic qualifications|key requirements|core requirements|what we need|what we're looking for|what we are looking for|we're looking for",
    'preferred_skills': 'preferred|nice to have|preferred skills|preferred qualifications|bonus|good to have|additional qualifications|desirable|desirable skills|it would be great if',
    'qualifications': 'qualifications|who you are|ideal candidate|what you bring|you should have|your qualifications|candidate requirements|your background',
    'experience_requirements': 'experience|experience requirements|required experience|years of experience',
    'education_requirements': 'education|education requirements|educational requirements',
}
RESUME_CANONICAL_MAP = {h: k for k, v in _RESUME.items() for h in v.split("|")}
JOB_CANONICAL_MAP = {h: k for k, v in _JOB.items() for h in v.split("|")}

_STRIP_NON_ALPHANUM = re.compile(r"[^A-Za-z0-9]")

_SENTENCE_ENDERS = frozenset(".;?!")

class SectionDetector:

    def __init__(self, canonical_map: Dict[str, str]) -> None:
        self._canonical_map = canonical_map
        self._canonical_lower: Dict[str, str] = {
            k.lower(): v for k, v in canonical_map.items()
        }

    def is_heading(self, line: str, *, preceded_by_blank: bool = True) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if len(stripped) > 65:
            return False
        if stripped[-1] in _SENTENCE_ENDERS:
            return False
        core = stripped.rstrip(":").strip()
        if not core:
            return False
        if core.lower() in self._canonical_lower:
            return True
        alpha_only = re.sub(r"[^A-Za-z]", "", core)
        word_count = len(core.split())
        if (
            len(alpha_only) >= 3
            and word_count <= 7
            and alpha_only.isupper()
            and "," not in core
        ):
            return True
        if (
            preceded_by_blank
            and stripped.endswith(":")
            and word_count <= 4
        ):
            return True
        return False

    def normalize_heading(self, line: str) -> str:
        return line.strip().rstrip(":").strip()

    def to_canonical(self, heading: str) -> Optional[str]:
        return self._canonical_lower.get(heading.lower())

    def split_sections(self, text: str) -> List[Tuple[Optional[str], str]]:
        lines = text.split("\n")
        sections: List[Tuple[Optional[str], str]] = []
        current_heading: Optional[str] = None
        current_content: List[str] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            preceded_by_blank = (i == 0) or (not lines[i - 1].strip())
            if stripped and self.is_heading(stripped, preceded_by_blank=preceded_by_blank):
                content_str = "\n".join(current_content).strip()
                if current_heading is not None or content_str:
                    sections.append((current_heading, content_str))
                current_heading = self.normalize_heading(stripped)
                current_content = []
            else:
                current_content.append(line)
        content_str = "\n".join(current_content).strip()
        if current_heading is not None or content_str:
            sections.append((current_heading, content_str))
        return sections

def _bucket(detector, text, keys):
    accum = {k: [] for k in keys}
    other = {}
    for heading, content in detector.split_sections(text):
        if heading is None:
            if content.strip():
                other["preamble"] = content.strip()
            continue
        canon = detector.to_canonical(heading)
        if canon in accum:
            accum[canon].append(content)
        else:
            k = heading.lower()
            other[k] = other[k] + "\n\n" + content if k in other else content
    return {k: "\n\n".join(p for p in v if p.strip()) for k, v in accum.items()}, other

class ResumeParser:
    def __init__(self, detector: Optional[SectionDetector] = None) -> None:
        self._detector = detector or SectionDetector(RESUME_CANONICAL_MAP)

    def parse(self, clean_text: str, raw_text: str = "") -> ResumeDocument:
        j, other = _bucket(self._detector, clean_text, ("summary", "skills", "experience", "projects", "education", "certifications", "achievements"))
        return ResumeDocument(raw_text=raw_text or clean_text, clean_text=clean_text, summary_section=j["summary"], skills_section=j["skills"], experience_section=j["experience"], projects_section=j["projects"], education_section=j["education"], certifications_section=j["certifications"], achievements_section=j["achievements"], other_sections=other)

class JobParser:
    def __init__(self, detector: Optional[SectionDetector] = None) -> None:
        self._detector = detector or SectionDetector(JOB_CANONICAL_MAP)

    def parse(
        self,
        clean_text: str,
        title: str = "",
        raw_text: str = "",
    ) -> JobDocument:
        j, other = _bucket(self._detector, clean_text, ("summary", "responsibilities", "required_skills", "preferred_skills", "qualifications", "experience_requirements", "education_requirements"))
        if j["education_requirements"]:
            other.setdefault("education_requirements", j["education_requirements"])
        return JobDocument(raw_text=raw_text or clean_text, title=title, clean_text=clean_text, summary_section=j["summary"], responsibilities_section=j["responsibilities"], required_skills_section=j["required_skills"], preferred_skills_section=j["preferred_skills"], qualifications_section=j["qualifications"], experience_requirements_section=j["experience_requirements"], other_sections=other)
