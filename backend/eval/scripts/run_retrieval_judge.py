from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Sequence

from eval.src.data_loader import GoldenDataLoader, GoldenRecommendation
from eval.src.retrieval_judge import RetrievalJudge


def select_stratified_sample(
    recommendations: Sequence[GoldenRecommendation],
    per_grade: int,
    seed: int = 42,
) -> List[GoldenRecommendation]:
    if per_grade <= 0:
        raise ValueError("per_grade must be positive.")

    rng = random.Random(seed)
    sample: List[GoldenRecommendation] = []
    for grade in range(4):
        grade_cases = sorted(
            (case for case in recommendations if case.relevance == grade),
            key=lambda case: case.case_id,
        )
        sample.extend(rng.sample(grade_cases, min(per_grade, len(grade_cases))))
    rng.shuffle(sample)
    return sample


def _dataset_version(dataset_dir: Path) -> str:
    digest = hashlib.sha256()
    for filename in (
        "golden_resumes.jsonl",
        "golden_jobs.jsonl",
        "golden_recommendations.jsonl",
    ):
        digest.update(filename.encode("utf-8"))
        digest.update((dataset_dir / filename).read_bytes())
    return f"golden-{digest.hexdigest()[:16]}"


def run_judge_sample(
    per_grade: int = 5,
    seed: int = 42,
    output_path: Optional[Path] = None,
    loader: Optional[GoldenDataLoader] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Path:
    data_loader = loader or GoldenDataLoader()
    jobs = data_loader.load_jobs()
    resumes = data_loader.load_resumes()
    recommendations = data_loader.load_recommendations()
    sample = select_stratified_sample(recommendations, per_grade, seed)
    judge = RetrievalJudge(
        dataset_version=_dataset_version(data_loader.dataset_dir),
        api_key=api_key,
        model=model,
    )

    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = Path(__file__).resolve().parents[1] / "artifacts" / f"retrieval_judge_{timestamp}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    status_counts = {}
    with output_path.open("x", encoding="utf-8") as output:
        for case in sample:
            resume = resumes.get(case.resume_id)
            job = jobs.get(case.job_id)
            if resume is None or job is None:
                raise ValueError(f"Dataset case {case.case_id} references a missing resume or job.")
            result = judge.evaluate_pair(
                candidate_profile=resume.candidate_profile,
                job_description=asdict(job),
                case_id=case.case_id,
            )
            status_counts[result.status] = status_counts.get(result.status, 0) + 1
            record = {
                "case_id": case.case_id,
                "resume_id": case.resume_id,
                "job_id": case.job_id,
                "synthetic_reference_grade": case.relevance,
                "judge_result": asdict(result),
            }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote {len(sample)} stratified judge results to {output_path}")
    print(f"Statuses: {json.dumps(status_counts, sort_keys=True)}")
    print("Synthetic reference grades are diagnostic only; human agreement is not measured.")
    return output_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a stratified, optional Anthropic relevance-judge sample."
    )
    parser.add_argument("--per-grade", type=int, default=5, help="Pairs sampled from each synthetic grade (default: 5).")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic sampling seed.")
    parser.add_argument("--output", type=Path, help="New JSONL output path; existing files are never overwritten.")
    parser.add_argument("--model", help="Anthropic model override; otherwise uses ANTHROPIC_MODEL.")
    args = parser.parse_args(argv)
    run_judge_sample(args.per_grade, args.seed, args.output, model=args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
