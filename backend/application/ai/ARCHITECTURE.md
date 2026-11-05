# Production-Grade AI Resume ↔ Job Matching System Architecture

## 1. System Overview

The `application/ai/` subsystem provides a modular, production-grade Machine Learning semantic matching and ranking architecture. It moves beyond basic keyword matching to deliver an end-to-end ML retrieval, reranking, and learning-to-rank pipeline.

```text
Resume PDF/DOCX/Text
        ↓
Document Ingestion & Cleaning (application/ai/ingestion/)
        ↓
Section Detection & Parsing (application/ai/parsing/)
        ↓
Structured ResumeDocument & JobDocument (application/ai/schemas/)
        ↓
Semantic Extraction (application/ai/extraction/)
(skills, experience, education, seniority — no NER)
        ↓
Transformer Bi-Encoder Embeddings (application/ai/embeddings/)
(SentenceTransformerEmbedder / all-MiniLM-L6-v2)
        ↓
FAISS Candidate Retrieval (application/ai/retrieval/)
(FaissRetriever / IndexFlatIP Scalable Top-K)
        ↓
Transformer Cross-Encoder Reranking (application/ai/reranking/)
(CrossEncoderReranker / deep cross-attention)
        ↓
Feature Engineering (application/ai/features/)
(10 tabular signals: semantic, skills, exp, edu, seniority, reranker, graph)
        ↓
Learning-to-Rank Model (application/ai/ranking/)
(LightGBM LambdaMART / fallback ranker)
        ↓
Final Match Score & Evidence/Gaps (application/ai/explanation/)
(EvidenceGenerator / TemplateExplainer / Optional LLMExplainer)
        ↓
Recruiter Feedback Logging (application/ai/feedback/)
        ↓
Hard-Negative Mining & Training Data (application/ai/training/)
        ↓
Evaluation & Retraining Loop (application/ai/evaluation/)
(NDCG@K, MRR, MAP metrics)
```

---

## 2. Modular Subpackage Map

Every module is isolated behind clean interfaces, adheres to the 200–300 line maximum constraint, and keeps ML logic out of Django views:

| Subpackage | Component | Description |
|---|---|---|
| `ingestion/` | `PDFLoader`, `DOCXLoader`, `TextLoader`, `clean_text` | Multi-format document text extraction and normalisation. |
| `schemas/` | `ResumeDocument`, `JobDocument`, `MatchFeatures`, `MatchResult` | Strongly-typed dataclasses and Pydantic models. |
| `parsing/` | `SectionDetector`, `ResumeParser`, `JobParser` | Canonical section segmentation (`skills`, `experience`, `education`, etc.). |
| `extraction/` | `SkillExtractionPipeline`, `ExperienceExtractor`, `EducationExtractor`, `SeniorityExtractor` | Domain-vocab extraction without NER; handles prose and lists. |
| `embeddings/` | `SentenceTransformerEmbedder` | 384-dim bi-encoder embeddings with thread-safe lazy loading and offline fallback. |
| `retrieval/` | `FaissRetriever` | Scalable Top-K candidate/job retrieval using FAISS `IndexFlatIP` with ID mapping. |
| `reranking/` | `CrossEncoderReranker` | Fine-grained cross-attention scoring. Score is an explicit feature, not raw probability. |
| `graph/` | `NetworkXSkillGraph` | Skill taxonomy graph with topological distance and PyG `(2, E)` `export_edge_index()` for GNN/GAT readiness. |
| `features/` | `FeatureExtractor`, `feature_functions` | 10 engineered signals: semantic similarity, skill overlap, weighted coverage, experience fit, education level, seniority, cross-encoder, title similarity, graph proximity, section coverage. |
| `ranking/` | `LightGBMRanker`, `WeightedFallbackScorer` | LightGBM LambdaMART LTR ranker with deterministic calibrated fallback. |
| `explanation/` | `EvidenceGenerator`, `TemplateExplainer`, `LLMExplainer` | Deterministic evidence/gap generation. Optional LLM only explains existing evidence; never invents facts. |
| `feedback/` | `FeedbackCollector`, `MatchFeedback` | Recruiter interaction tracking (`view`, `shortlist`, `reject`, `hire`). |
| `training/` | `HardNegativeMiner`, `DatasetGenerator`, `ModelTrainer` | Mined hard negatives, query-grouped datasets, versioned LambdaMART models. |
| `evaluation/` | `LTREvaluator` | Standard IR evaluation: NDCG@5, NDCG@10, Mean Reciprocal Rank (MRR), Mean Average Precision (MAP). |
| `pipeline/` | `MatchingPipeline` | Central orchestrator for single-pair analysis and multi-candidate workflows. |
| `tests/` | Unit and integration test suites | 100% test coverage across all components. |

---

## 3. Public API Contract (Frozen)

Exposed via `application/ai/pipeline/__init__.py` and `application/ai_service.py`:

```python
def analyze_resume(
    file_field: Any,
    job_title: str,
    job_description: str,
    candidate_name: str = "",
    job_id: Optional[int] = None,
    candidate_id: Optional[int] = None,
) -> ResumeAnalysis:
```

### Return Schema (`ResumeAnalysis`):
- `match_score`: Integer in `[0, 100]`.
- `key_skills`: Extracted technology and domain skills.
- `matching_points`: Array of `{ point: str, evidence: str }`.
- `gaps`: Array of `{ point: str }`.
- `candidate_summary`: Human-readable candidate overview.
- `education_summary`: Degree and university summary.
- `experience_highlights`: Key bullet points extracted from work experience.
- `recommendation`: Actionable recommendation for the hiring manager.
- `explanation`: Model version and evaluation summary.
