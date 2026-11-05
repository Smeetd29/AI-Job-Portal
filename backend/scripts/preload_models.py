"""Preloads ML model weights during Docker image build.

Ensures containers never attempt internet downloads at startup or during runtime.
"""
from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("preload_models")

def preload() -> None:
    hf_home = os.getenv("HF_HOME", "/app/.cache/huggingface")
    os.makedirs(hf_home, exist_ok=True)
    logger.info("Pre-downloading model weights to HF_HOME: %s", hf_home)

    try:
        from sentence_transformers import SentenceTransformer
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        logger.info("Downloading SentenceTransformer: %s...", model_name)
        SentenceTransformer(model_name)
        logger.info("Successfully cached %s", model_name)
    except Exception as exc:
        logger.warning("Could not pre-download SentenceTransformer (%s). Offline fallback will be used: %s", model_name, exc)

    try:
        from sentence_transformers import CrossEncoder
        ce_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
        logger.info("Downloading CrossEncoder: %s...", ce_name)
        CrossEncoder(ce_name)
        logger.info("Successfully cached %s", ce_name)
    except Exception as exc:
        logger.warning("Could not pre-download CrossEncoder (%s). Proxy fallback will be used: %s", ce_name, exc)

    logger.info("Model preloading completed.")

if __name__ == "__main__":
    preload()
