from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
import jsonschema


class DatasetValidationError(Exception):
    """Raised when a golden dataset fails schema or semantic validation."""
    pass


class DatasetValidator:
    """Enforces structural, relational, and business constraints on evaluation datasets."""

    def __init__(self, dataset_dir: Path | None = None, schema_file: Path | None = None):
        eval_root = Path(__file__).resolve().parent.parent
        self.dataset_dir = dataset_dir or (eval_root / "datasets")
        self.schema_file = schema_file or (eval_root / "schemas" / "evaluation_case.schema.json")
        self.schema: Dict = {}
        if self.schema_file.exists():
            with open(self.schema_file, "r", encoding="utf-8") as f:
                self.schema = json.load(f)

    def validate_all(self) -> Dict[str, int]:
        """Validates all golden datasets and returns record counts."""
        jobs_path = self.dataset_dir / "golden_jobs.jsonl"
        resumes_path = self.dataset_dir / "golden_resumes.jsonl"
        recs_path = self.dataset_dir / "golden_recommendations.jsonl"
        summaries_path = self.dataset_dir / "golden_resume_summaries.jsonl"

        for p in [jobs_path, resumes_path, recs_path, summaries_path]:
            if not p.exists():
                raise DatasetValidationError(f"Missing required golden dataset file: {p}")

        job_ids = self.validate_jobs(jobs_path)
        resume_ids = self.validate_resumes(resumes_path)
        recs_count = self.validate_recommendations(recs_path, job_ids, resume_ids)
        summaries_count = self.validate_summaries(summaries_path, resume_ids)

        return {
            "jobs_count": len(job_ids),
            "resumes_count": len(resume_ids),
            "recommendations_count": recs_count,
            "summaries_count": summaries_count,
        }

    def validate_jobs(self, path: Path) -> Set[str]:
        job_schema = self.schema.get("definitions", {}).get("golden_job")
        job_ids: Set[str] = set()

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                try:
                    data = json.loads(s)
                except json.JSONDecodeError as exc:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Invalid JSON: {exc}")

                if job_schema:
                    try:
                        jsonschema.validate(data, job_schema)
                    except jsonschema.ValidationError as exc:
                        raise DatasetValidationError(f"{path.name}:{line_no}: Schema error: {exc.message}")

                jid = data["job_id"]
                if jid in job_ids:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Duplicate job_id: '{jid}'")
                job_ids.add(jid)

        if len(job_ids) == 0:
            raise DatasetValidationError(f"{path.name} is empty.")
        return job_ids

    def validate_resumes(self, path: Path) -> Set[str]:
        resume_schema = self.schema.get("definitions", {}).get("golden_resume")
        resume_ids: Set[str] = set()

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                try:
                    data = json.loads(s)
                except json.JSONDecodeError as exc:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Invalid JSON: {exc}")

                if resume_schema:
                    try:
                        jsonschema.validate(data, resume_schema)
                    except jsonschema.ValidationError as exc:
                        raise DatasetValidationError(f"{path.name}:{line_no}: Schema error: {exc.message}")

                rid = data["resume_id"]
                if rid in resume_ids:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Duplicate resume_id: '{rid}'")
                resume_ids.add(rid)

        if len(resume_ids) == 0:
            raise DatasetValidationError(f"{path.name} is empty.")
        return resume_ids

    def validate_recommendations(self, path: Path, job_ids: Set[str], resume_ids: Set[str]) -> int:
        rec_schema = self.schema.get("definitions", {}).get("golden_recommendation")
        case_ids: Set[str] = set()
        pair_keys: Set[Tuple[str, str]] = set()

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                try:
                    data = json.loads(s)
                except json.JSONDecodeError as exc:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Invalid JSON: {exc}")

                if rec_schema:
                    try:
                        jsonschema.validate(data, rec_schema)
                    except jsonschema.ValidationError as exc:
                        raise DatasetValidationError(f"{path.name}:{line_no}: Schema error: {exc.message}")

                cid = data["case_id"]
                if cid in case_ids:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Duplicate case_id: '{cid}'")
                case_ids.add(cid)

                rid = data["resume_id"]
                jid = data["job_id"]
                if rid not in resume_ids:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Referenced resume_id '{rid}' not found in golden_resumes.")
                if jid not in job_ids:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Referenced job_id '{jid}' not found in golden_jobs.")

                pair = (rid, jid)
                if pair in pair_keys:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Duplicate resume-job pair: {pair}")
                pair_keys.add(pair)

                rel = data["relevance"]
                expected_bool = (rel >= 2)
                actual_bool = data["relevant_for_recommendation"]
                if actual_bool != expected_bool:
                    raise DatasetValidationError(
                        f"{path.name}:{line_no}: Consistency violation: relevance={rel} but relevant_for_recommendation={actual_bool} (expected {expected_bool})"
                    )

        if len(case_ids) == 0:
            raise DatasetValidationError(f"{path.name} is empty.")
        return len(case_ids)

    def validate_summaries(self, path: Path, resume_ids: Set[str]) -> int:
        sum_schema = self.schema.get("definitions", {}).get("golden_resume_summary")
        case_ids: Set[str] = set()

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                try:
                    data = json.loads(s)
                except json.JSONDecodeError as exc:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Invalid JSON: {exc}")

                if sum_schema:
                    try:
                        jsonschema.validate(data, sum_schema)
                    except jsonschema.ValidationError as exc:
                        raise DatasetValidationError(f"{path.name}:{line_no}: Schema error: {exc.message}")

                cid = data["case_id"]
                if cid in case_ids:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Duplicate case_id: '{cid}'")
                case_ids.add(cid)

                rid = data["resume_id"]
                if rid not in resume_ids:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Referenced resume_id '{rid}' not found in golden_resumes.")

        if len(case_ids) == 0:
            raise DatasetValidationError(f"{path.name} is empty.")
        return len(case_ids)


class SyntheticBenchmarkValidator:
    """Enforces structural, relational, and split integrity on the 200-job synthetic benchmark."""

    def __init__(self, dataset_dir: Path | None = None):
        eval_root = Path(__file__).resolve().parent.parent
        self.dataset_dir = dataset_dir or (eval_root / "datasets" / "synthetic_benchmark")

    def validate_all(self) -> Dict[str, Any]:
        """Validates all files in the synthetic benchmark dataset."""
        jobs_path = self.dataset_dir / "jobs.jsonl"
        candidates_path = self.dataset_dir / "candidates.jsonl"
        judgments_path = self.dataset_dir / "synthetic_relevance_judgments.csv"
        splits_path = self.dataset_dir / "candidate_level_splits.csv"

        for p in [jobs_path, candidates_path, judgments_path, splits_path]:
            if not p.exists():
                raise DatasetValidationError(f"Missing required synthetic benchmark file: {p.name}")

        job_ids = self.validate_jobs(jobs_path)
        cand_ids = self.validate_candidates(candidates_path)
        judgments_count, grade_dist = self.validate_judgments(judgments_path, job_ids, cand_ids)
        split_counts = self.validate_splits(splits_path, cand_ids)

        return {
            "jobs_count": len(job_ids),
            "candidates_count": len(cand_ids),
            "judgments_count": judgments_count,
            "grade_distribution": grade_dist,
            "split_counts": split_counts,
        }

    def validate_jobs(self, path: Path) -> Set[str]:
        job_ids: Set[str] = set()
        required_fields = {"job_id", "title", "description", "required_skills"}

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                try:
                    data = json.loads(s)
                except json.JSONDecodeError as exc:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Invalid JSON: {exc}")

                missing = required_fields - set(data.keys())
                if missing:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Missing required fields: {missing}")

                jid = str(data["job_id"]).strip()
                if not jid:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Empty job_id")
                if jid in job_ids:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Duplicate job_id: '{jid}'")
                job_ids.add(jid)

        if len(job_ids) != 200:
            raise DatasetValidationError(f"{path.name}: Expected 200 jobs, found {len(job_ids)}")
        return job_ids

    def validate_candidates(self, path: Path) -> Set[str]:
        cand_ids: Set[str] = set()
        required_fields = {"candidate_id", "display_name", "skills", "current_seniority"}

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                s = line.strip()
                if not s:
                    continue
                try:
                    data = json.loads(s)
                except json.JSONDecodeError as exc:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Invalid JSON: {exc}")

                missing = required_fields - set(data.keys())
                if missing:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Missing required fields: {missing}")

                cid = str(data["candidate_id"]).strip()
                if not cid:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Empty candidate_id")
                if cid in cand_ids:
                    raise DatasetValidationError(f"{path.name}:{line_no}: Duplicate candidate_id: '{cid}'")
                cand_ids.add(cid)

        if len(cand_ids) != 60:
            raise DatasetValidationError(f"{path.name}: Expected 60 candidates, found {len(cand_ids)}")
        return cand_ids

    def validate_judgments(self, path: Path, job_ids: Set[str], cand_ids: Set[str]) -> Tuple[int, Dict[int, int]]:
        import csv
        seen_pairs: Set[Tuple[str, str]] = set()
        grade_dist: Dict[int, int] = {}
        total = 0

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {"candidate_id", "job_id", "relevance_grade"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise DatasetValidationError(f"{path.name}: Header missing required fields {required}")

            for row_no, row in enumerate(reader, 2):
                cid = row["candidate_id"].strip()
                jid = row["job_id"].strip()

                if cid not in cand_ids:
                    raise DatasetValidationError(f"{path.name}:{row_no}: Unknown candidate_id '{cid}'")
                if jid not in job_ids:
                    raise DatasetValidationError(f"{path.name}:{row_no}: Unknown job_id '{jid}'")

                pair = (cid, jid)
                if pair in seen_pairs:
                    raise DatasetValidationError(f"{path.name}:{row_no}: Duplicate pair {pair}")
                seen_pairs.add(pair)

                try:
                    grade = int(row["relevance_grade"])
                    if not (0 <= grade <= 3):
                        raise ValueError()
                except ValueError:
                    raise DatasetValidationError(f"{path.name}:{row_no}: Invalid relevance_grade '{row.get('relevance_grade')}' (must be 0..3)")

                grade_dist[grade] = grade_dist.get(grade, 0) + 1
                total += 1

        if total != 12000:
            raise DatasetValidationError(f"{path.name}: Expected 12,000 judgments, found {total}")
        return total, grade_dist

    def validate_splits(self, path: Path, cand_ids: Set[str]) -> Dict[str, int]:
        import csv
        split_cands: Dict[str, Set[str]] = {"train": set(), "validation": set(), "test": set()}

        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {"candidate_id", "split"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise DatasetValidationError(f"{path.name}: Header missing required fields {required}")

            for row_no, row in enumerate(reader, 2):
                cid = row["candidate_id"].strip()
                sp = row["split"].strip()

                if cid not in cand_ids:
                    raise DatasetValidationError(f"{path.name}:{row_no}: Unknown candidate_id '{cid}' in splits")
                if sp not in split_cands:
                    raise DatasetValidationError(f"{path.name}:{row_no}: Invalid split name '{sp}' (must be train, validation, or test)")

                if cid in split_cands[sp]:
                    raise DatasetValidationError(f"{path.name}:{row_no}: Duplicate candidate '{cid}' in split '{sp}'")

                split_cands[sp].add(cid)

        # Leakage checks
        train_val_leakage = split_cands["train"] & split_cands["validation"]
        train_test_leakage = split_cands["train"] & split_cands["test"]
        val_test_leakage = split_cands["validation"] & split_cands["test"]

        if train_val_leakage:
            raise DatasetValidationError(f"Data leakage between train and validation: {train_val_leakage}")
        if train_test_leakage:
            raise DatasetValidationError(f"Data leakage between train and test: {train_test_leakage}")
        if val_test_leakage:
            raise DatasetValidationError(f"Data leakage between validation and test: {val_test_leakage}")

        all_split_cands = split_cands["train"] | split_cands["validation"] | split_cands["test"]
        missing_cands = cand_ids - all_split_cands
        if missing_cands:
            raise DatasetValidationError(f"Candidates missing from splits: {missing_cands}")

        expected = {"train": 42, "validation": 6, "test": 12}
        counts = {sp: len(cands) for sp, cands in split_cands.items()}
        for sp, exp_count in expected.items():
            if counts[sp] != exp_count:
                raise DatasetValidationError(f"Split '{sp}': Expected {exp_count} candidates, found {counts[sp]}")

        return counts


def main():
    validator = DatasetValidator()
    try:
        counts = validator.validate_all()
        print("Dataset Validation PASSED!")
        for k, v in counts.items():
            print(f"  - {k}: {v}")
        sys.exit(0)
    except DatasetValidationError as exc:
        print(f"Dataset Validation FAILED: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
