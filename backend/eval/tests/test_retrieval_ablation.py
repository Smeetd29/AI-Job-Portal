import pytest

from eval.src.retrieval_ablation import BM25Index, reciprocal_rank_fusion, tokenize


def test_tokenizer_preserves_technical_skill_tokens():
    assert tokenize("C++, C#, Node.js, and FastAPI") == [
        "c++",
        "c#",
        "node.js",
        "and",
        "fastapi",
    ]


def test_bm25_ranks_exact_skill_match_above_unrelated_document():
    index = BM25Index(
        ["python-job", "java-job"],
        [
            "Python Django REST APIs PostgreSQL",
            "Java Spring Boot Kafka",
        ],
    )

    assert index.rank("Python Django") == ["python-job", "java-job"]


def test_bm25_validates_input_lengths_and_parameters():
    with pytest.raises(ValueError, match="equal lengths"):
        BM25Index(["job"], [])
    with pytest.raises(ValueError, match="k1 > 0"):
        BM25Index(["job"], ["Python"], k1=0)


def test_reciprocal_rank_fusion_combines_rankings_and_deduplicates():
    ranking = reciprocal_rank_fusion(
        [["a", "b", "b", "c"], ["b", "a", "d"]],
        rank_constant=0,
    )

    assert ranking[:2] == ["a", "b"]
    assert len(ranking) == 4


def test_reciprocal_rank_fusion_rejects_negative_rank_constant():
    with pytest.raises(ValueError, match="rank_constant"):
        reciprocal_rank_fusion([["job"]], rank_constant=-1)
