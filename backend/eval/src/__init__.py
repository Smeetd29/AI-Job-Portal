"""
CareerConnect DeepEval Evaluation Framework.
"""
from __future__ import annotations

import sys
from pathlib import Path

eval_dir = Path(__file__).resolve().parent.parent
backend_dir = eval_dir.parent
root_dir = backend_dir.parent
for p in (root_dir, backend_dir, eval_dir):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

__version__ = "1.0.0"
