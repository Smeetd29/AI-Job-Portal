from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_SKILL_RELATIONS = [

    ("react", "javascript", "prerequisite", 0.95),
    ("react", "typescript", "related", 0.90),
    ("react", "next.js", "framework_ecosystem", 0.95),
    ("vue", "javascript", "prerequisite", 0.95),
    ("angular", "typescript", "prerequisite", 0.95),
    ("html5", "css3", "core_web", 0.95),
    ("tailwindcss", "css3", "tooling", 0.90),

    ("django", "python", "prerequisite", 0.95),
    ("fastapi", "python", "prerequisite", 0.95),
    ("flask", "python", "prerequisite", 0.90),
    ("express", "node.js", "prerequisite", 0.95),
    ("spring boot", "java", "prerequisite", 0.95),
    ("asp.net", "c#", "prerequisite", 0.95),
    ("django", "fastapi", "alternative", 0.80),
    ("django", "drf", "ecosystem", 0.95),

    ("postgresql", "sql", "dialect", 0.95),
    ("mysql", "sql", "dialect", 0.95),
    ("redis", "caching", "application", 0.90),
    ("mongodb", "nosql", "paradigm", 0.90),
    ("django", "postgresql", "common_stack", 0.80),

    ("docker", "containers", "paradigm", 0.95),
    ("kubernetes", "docker", "orchestration", 0.95),
    ("terraform", "aws", "infrastructure", 0.85),
    ("aws", "cloud", "paradigm", 0.95),
    ("gcp", "cloud", "paradigm", 0.95),
    ("azure", "cloud", "paradigm", 0.95),

    ("pytorch", "python", "prerequisite", 0.95),
    ("tensorflow", "python", "prerequisite", 0.95),
    ("scikit-learn", "python", "prerequisite", 0.95),
    ("pytorch", "deep learning", "domain", 0.90),
    ("nlp", "machine learning", "domain", 0.90),
    ("faiss", "vector search", "domain", 0.90),
]

class NetworkXSkillGraph:

    def __init__(self, populate_defaults: bool = True):
        self.graph = nx.DiGraph()
        if populate_defaults:
            self._load_defaults()

    def _load_defaults(self) -> None:
        for src, tgt, rel, weight in DEFAULT_SKILL_RELATIONS:
            self.add_skill(src)
            self.add_skill(tgt)
            self.add_relation(src, tgt, relation_type=rel, weight=weight)
            self.add_relation(tgt, src, relation_type="reverse_" + rel, weight=weight * 0.8)

    def add_skill(self, skill: str, category: str = "", attributes: Optional[Dict[str, Any]] = None) -> None:
        node = skill.strip().lower()
        if not node:
            return
        attrs = attributes or {}
        if category:
            attrs["category"] = category
        if node not in self.graph:
            self.graph.add_node(node, **attrs)
        else:
            self.graph.nodes[node].update(attrs)

    def add_relation(
        self,
        source: str,
        target: str,
        relation_type: str = "related",
        weight: float = 1.0,
    ) -> None:
        s = source.strip().lower()
        t = target.strip().lower()
        if not s or not t or s == t:
            return
        self.add_skill(s)
        self.add_skill(t)
        self.graph.add_edge(s, t, relation_type=relation_type, weight=max(0.0, min(1.0, weight)))

    def get_related_skills(
        self,
        skill: str,
        max_hops: int = 1,
        min_weight: float = 0.5,
    ) -> List[Tuple[str, float]]:
        node = skill.strip().lower()
        if node not in self.graph:
            return []
        related: Dict[str, float] = {}
        for target, path in nx.single_source_shortest_path(self.graph, node, cutoff=max_hops).items():
            if target == node:
                continue
            path_weight = 1.0
            for i in range(len(path) - 1):
                edge_data = self.graph.get_edge_data(path[i], path[i + 1], default={"weight": 0.5})
                path_weight *= edge_data.get("weight", 0.5)
            if path_weight >= min_weight:
                related[target] = max(related.get(target, 0.0), path_weight)
        return sorted(related.items(), key=lambda x: x[1], reverse=True)

    def compute_skill_set_proximity(
        self,
        candidate_skills: List[str],
        required_skills: List[str],
    ) -> float:
        if not required_skills:
            return 1.0
        if not candidate_skills:
            return 0.0
        cand_set = {s.strip().lower() for s in candidate_skills if s.strip()}
        req_set = {s.strip().lower() for s in required_skills if s.strip()}
        if not req_set:
            return 1.0
        scores: List[float] = []
        for req in req_set:
            if req in cand_set:
                scores.append(1.0)
                continue
            best_match = 0.0
            if req in self.graph:
                neighbors = self.get_related_skills(req, max_hops=2, min_weight=0.3)
                for rel_skill, rel_weight in neighbors:
                    if rel_skill in cand_set:
                        best_match = max(best_match, rel_weight)
            scores.append(best_match)
        return float(np.mean(scores)) if scores else 0.0

    def export_edge_index(self) -> Tuple[np.ndarray, List[str]]:
        nodes = sorted(list(self.graph.nodes()))
        node_to_idx = {name: idx for idx, name in enumerate(nodes)}
        src_indices: List[int] = []
        dst_indices: List[int] = []
        for u, v in self.graph.edges():
            src_indices.append(node_to_idx[u])
            dst_indices.append(node_to_idx[v])
        if not src_indices:
            edge_index = np.zeros((2, 0), dtype=np.int64)
        else:
            edge_index = np.array([src_indices, dst_indices], dtype=np.int64)
        return edge_index, nodes
