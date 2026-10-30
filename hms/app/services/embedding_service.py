import math
from typing import List, Optional
import numpy as np

_model_instance = None

def get_model():
    """
    Lazy-loads the FastEmbed model singleton.
    Downloads BAAI/bge-small-en-v1.5 ONNX model on first use (~130MB),
    cached locally in FastEmbed cache.
    """
    global _model_instance
    if _model_instance is None:
        from fastembed import TextEmbedding
        _model_instance = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _model_instance


def get_embedding(text: str) -> List[float]:
    """
    Computes a 384-dimensional normalized dense embedding for a single string.
    """
    if not text or not text.strip():
        return [0.0] * 384
    model = get_model()
    embeddings = list(model.embed([text]))
    return [float(x) for x in embeddings[0]]


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Computes 384-dimensional normalized dense embeddings for a list of strings in batch.
    """
    if not texts:
        return []
    cleaned_texts = [t if (t and t.strip()) else "empty" for t in texts]
    model = get_model()
    embeddings = list(model.embed(cleaned_texts))
    return [[float(val) for val in vec] for vec in embeddings]


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Computes cosine similarity between two float vectors in Python/NumPy.
    Used for vector search matching when native pgvector distance operator is not installed.
    """
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
