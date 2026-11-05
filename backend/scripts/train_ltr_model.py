"""
Training & Serialization Script for CareerConnect LightGBM Learning-to-Rank (LTR) Model.

Trains a production LambdaMART model on the gold evaluation dataset.
Supports:
  - v1: 10 features, grouped by job_id (legacy)
  - v2: 10 named features, grouped by job_id
  - v3 (default): 14 features, candidate-grouped by resume_id (optimizes candidate NDCG directly)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Setup Django environment
backend_dir = Path(__file__).resolve().parent.parent
repo_root = backend_dir.parent
eval_dir = backend_dir / "eval"
for p in (backend_dir, repo_root, eval_dir):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "job.settings")
os.environ["USE_REDIS_CACHE"] = "False"
import django
django.setup()

import lightgbm as lgb
import numpy as np
from eval.src.data_loader import GoldenDataLoader
from application.ai.pipeline import MatchingPipeline
from application.ai.schemas import JobDocument, ResumeDocument
from application.ai.ranking import MatchFeatures

def train_and_export(version: str = "v3"):
    print("=" * 70)
    print(f" TRAINING CAREERCONNECT LTR MODEL (LAMBDAMART {version.upper()})")
    print("=" * 70)

    loader = GoldenDataLoader(dataset_dir=eval_dir / "datasets")
    jobs = loader.load_jobs()
    resumes = loader.load_resumes()
    recs = loader.load_recommendations()
    print(f"Loaded golden dataset: {len(jobs)} jobs, {len(resumes)} resumes, {len(recs)} judgments.")

    pipeline = MatchingPipeline.get_default()
    norm = pipeline.normalizer.normalize_list
    ex = pipeline.skill_extractor.extract

    print("\n[1/3] Parsing documents and extracting representations via pipeline...")
    parsed_jobs = {}
    for j_id, j in jobs.items():
        c_job = pipeline.cleaner(j.description)
        doc = pipeline.job_parser.parse(clean_text=c_job, title=j.title, raw_text=j.description)
        req_skills = getattr(j, "required_skills", None)
        if not req_skills:
            req_skills = ex(doc.required_skills_section or doc.qualifications_section or c_job)
        doc.required_skill_candidates = norm(req_skills or [])
        pref_skills = getattr(j, "preferred_skills", None)
        if not pref_skills:
            pref_skills = ex(doc.preferred_skills_section or "") if doc.preferred_skills_section else []
        doc.preferred_skill_candidates = norm(pref_skills or [])
        doc.required_years = pipeline.experience_extractor.extract(c_job)
        doc.required_degree_level = pipeline.education_extractor.extract(c_job)
        doc.seniority_label = pipeline.seniority_extractor.extract(
            f"{j.title}\n{c_job[:400]}",
            years_experience=doc.required_years,
            degree_level=doc.required_degree_level,
        )
        parsed_jobs[j_id] = doc

    parsed_resumes = {}
    for r_id, r in resumes.items():
        cleaned = pipeline.cleaner(r.resume_text)
        doc = pipeline.resume_parser.parse(cleaned, raw_text=r.resume_text)
        core = norm(ex(doc.skills_section or cleaned))
        proj = norm(ex(doc.projects_section or ""))
        doc.skill_candidates = core + [s for s in proj if s.lower() not in {c.lower() for c in core}] or norm(ex(cleaned))
        doc.years_experience = pipeline.experience_extractor.extract(doc.experience_section or cleaned)
        doc.degree_level = pipeline.education_extractor.extract(doc.education_section or cleaned)
        doc.seniority_label = pipeline.seniority_extractor.extract(
            cleaned,
            years_experience=doc.years_experience,
            degree_level=doc.degree_level,
        )
        parsed_resumes[r_id] = doc

    embedder = pipeline.embedding
    cross_encoder = pipeline.reranker

    resume_embs = {r_id: embedder.embed_text(doc.primary_text_for_embedding()) for r_id, doc in parsed_resumes.items()}
    job_embs = {j_id: embedder.embed_text(doc.primary_text_for_embedding()) for j_id, doc in parsed_jobs.items()}
    resume_summary_embs = {r_id: embedder.embed_text(doc.summary_section or doc.clean_text[:200]) for r_id, doc in parsed_resumes.items()}
    job_title_embs = {j_id: embedder.embed_text(doc.title) for j_id, doc in parsed_jobs.items()}

    pairs_input = []
    pair_keys = []
    for rec in recs:
        j_doc = parsed_jobs[rec.job_id]
        r_doc = parsed_resumes[rec.resume_id]
        if version == "v3":
            req_skills = ", ".join(j_doc.required_skill_candidates[:10])
            r_skills = ", ".join(r_doc.skill_candidates[:12])
            j_text = f"Role: {j_doc.title}. Level: {j_doc.seniority_label}. Skills: {req_skills}. {j_doc.clean_text[:350]}"
            r_text = f"Candidate Level: {r_doc.seniority_label}. Skills: {r_skills}. {r_doc.summary_section[:200]} {r_doc.experience_section[:300]}"
            pairs_input.append((j_text, r_text))
        else:
            pairs_input.append((f"{j_doc.title}. {j_doc.clean_text[:500]}", r_doc.clean_text[:500]))
        pair_keys.append((rec.job_id, rec.resume_id))

    scores = cross_encoder.score_pairs(pairs_input)
    ce_scores = dict(zip(pair_keys, scores))

    extractor = pipeline.feature_extractor
    extracted_features = {}
    for rec in recs:
        j_doc = parsed_jobs[rec.job_id]
        r_doc = parsed_resumes[rec.resume_id]
        feats = extractor.extract(
            resume_doc=r_doc,
            job_doc=j_doc,
            resume_embedding=resume_embs[rec.resume_id],
            job_embedding=job_embs[rec.job_id],
            resume_summary_embedding=resume_summary_embs[rec.resume_id],
            job_title_embedding=job_title_embs[rec.job_id],
            cross_encoder_score=ce_scores[(rec.job_id, rec.resume_id)],
        )
        extracted_features[(rec.job_id, rec.resume_id)] = feats

    print(f"\n[2/3] Training Production LightGBM LambdaMART Ranker ({version})...")
    X, y, group = [], [], []

    if version == "v3":
        # Group by resume_id: Candidate-to-Jobs ranking (directly optimizes Candidate NDCG)
        pairs_by_query = {}
        for rec in recs:
            pairs_by_query.setdefault(rec.resume_id, []).append(rec)
        for r_id, rec_list in pairs_by_query.items():
            group.append(len(rec_list))
            for r in rec_list:
                X.append(extracted_features[(r.job_id, r.resume_id)].to_vector())
                y.append(r.relevance)
        feature_names = MatchFeatures.feature_names()
    else:
        # Group by job_id (legacy v1/v2)
        pairs_by_query = {}
        for rec in recs:
            pairs_by_query.setdefault(rec.job_id, []).append(rec)
        for j_id, rec_list in pairs_by_query.items():
            group.append(len(rec_list))
            for r in rec_list:
                X.append(extracted_features[(r.job_id, r.resume_id)].to_vector_10())
                y.append(r.relevance)
        feature_names = MatchFeatures.feature_names()[:10]

    params = {
        "objective": "lambdarank",
        "metric": "ndcg",
        "ndcg_eval_at": [3, 5, 10],
        "learning_rate": 0.05,
        "num_leaves": 15,
        "min_data_in_leaf": 2,
        "verbose": -1,
        "seed": 42,
        "deterministic": True,
        "force_row_wise": True,
    }
    final_booster = lgb.train(
        params,
        lgb.Dataset(np.array(X), label=np.array(y), group=group, feature_name=feature_names),
        num_boost_round=40,
    )
    models_dir = backend_dir / "data" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_txt_path = models_dir / f"lgb_ranker_{version}.txt"
    model_json_path = models_dir / f"lgb_ranker_{version}.json"

    print(f"\n[3/3] Saving Model Artifacts to {models_dir}...")
    final_booster.save_model(str(model_txt_path))
    print(f"  Saved booster model: {model_txt_path}")

    metadata = {
        "model_name": "CareerConnect-LTR-LambdaMART",
        "model_version": f"{version}.0.0",
        "model_file": f"lgb_ranker_{version}.txt",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "query_grouping": "resume_id" if version == "v3" else "job_id",
        "dataset_summary": {
            "num_jobs": len(jobs),
            "num_resumes": len(resumes),
            "num_labeled_pairs": len(recs),
        },
        "hyperparameters": params,
        "feature_names": feature_names,
    }

    with open(model_json_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Saved companion metadata: {model_json_path}")

    print(f"\nSUCCESS: Production LTR model ({version}) trained and versioned successfully.")
    return metadata

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["v1", "v2", "v3"], default="v3")
    args = parser.parse_args()
    train_and_export(version=args.version)
