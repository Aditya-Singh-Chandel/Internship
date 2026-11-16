"""
Second-stage re-ranking of knowledge-base search results with a cross-encoder.

Why: the first stage (bi-encoder, embedding_service) turns the query and every chunk into vectors SEPARATELY and
compares them with cosine similarity. That is fast enough to scan every chunk, but the two texts never "see" each
other, so near-misses (the right hotel's breakfast FAQ vs. another chunk that merely mentions breakfast) are often
ranked in the wrong order. A cross-encoder reads the query and one chunk TOGETHER in a single transformer pass and
outputs one relevance score. It is far more accurate but too slow to run on every chunk, so it only re-orders the
few dozen candidates the vector search already found ("retrieve wide, re-rank narrow").

The model runs locally on CPU through fastembed's ONNX runtime (the same library as the embeddings), downloads once
into FASTEMBED_CACHE_PATH, and is loaded lazily on the first search. If it cannot load or fails at runtime, search
falls back to the vector order instead of breaking the chatbot.
"""
import logging
import math
import threading
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_name: Optional[str] = None
_failed_model: Optional[str] = None  # a model that failed to load is not retried on every search
_lock = threading.Lock()


def get_model():
    """Lazily loads the cross-encoder (thread-safe; FastAPI runs sync routes in a thread pool). None if unavailable."""
    global _model, _model_name, _failed_model
    if _model is not None and _model_name == settings.RERANK_MODEL:
        return _model
    if _failed_model == settings.RERANK_MODEL:
        return None
    with _lock:
        if _model is None or _model_name != settings.RERANK_MODEL:
            try:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                _model = TextCrossEncoder(model_name=settings.RERANK_MODEL)
                _model_name = settings.RERANK_MODEL
            except Exception:
                logger.exception("Re-ranker %s could not be loaded; using vector order", settings.RERANK_MODEL)
                _failed_model = settings.RERANK_MODEL
                return None
    return _model


def _sigmoid(x: float) -> float:
    # Cross-encoders output an unbounded logit; squash it to 0..1 so it reads like the other relevance scores.
    return 1.0 / (1.0 + math.exp(-max(min(x, 50.0), -50.0)))


def passage_text(hit: Dict[str, Any]) -> str:
    """What the cross-encoder reads for a chunk: its title (often the only place the topic is named) and the start of its
    text, capped at settings.RERANK_MAX_CHARS (the model still receives the whole chunk; only the scoring reads less)."""
    title = (hit.get("metadata") or {}).get("title")
    content = hit.get("content") or ""
    passage = f"{hit.get('hotel_name') or ''} - {title}\n{content}" if title else content
    return passage[:settings.RERANK_MAX_CHARS]


def rerank(query: str, hits: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """
    Re-orders `hits` (vector-search results) by cross-encoder relevance to `query` and returns the best `top_k`.
    Each returned hit keeps its first-stage `similarity_score` and gains `rerank_score` (0..1).
    On any failure the hits come back in their original order, cut to top_k.
    """
    if not hits or not query or not query.strip():
        return hits[:top_k]
    model = get_model()
    if model is None:
        return hits[:top_k]
    try:
        scores = list(model.rerank(query, [passage_text(h) for h in hits], batch_size=32))
    except Exception:
        logger.exception("Re-ranking failed; using vector order")
        return hits[:top_k]

    for hit, score in zip(hits, scores):
        hit["rerank_score"] = round(_sigmoid(float(score)), 4)
    return sorted(hits, key=lambda h: h["rerank_score"], reverse=True)[:top_k]
