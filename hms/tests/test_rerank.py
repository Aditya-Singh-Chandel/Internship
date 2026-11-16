"""Cross-encoder re-ranking: ordering, cut-off, scores, and falling back to vector order on failure.
The model is faked (no download); test_rerank_with_real_model uses the real one if it is cached or downloadable."""
import pytest

from app.services import document_service, rerank_service


def hit(content, sim, title=None):
    return {"content": content, "similarity_score": sim, "hotel_name": "The Mayfair", "metadata": {"title": title} if title else {}}


class FakeModel:
    """Scores a passage by how many query words it contains, so the expected order is obvious."""

    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def rerank(self, query, documents, batch_size=32):
        self.calls.append((query, list(documents)))
        if self.fail:
            raise RuntimeError("onnx exploded")
        words = query.lower().split()
        return [float(sum(w in d.lower() for w in words)) * 4 - 2 for d in documents]


@pytest.fixture
def fake(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(rerank_service, "get_model", lambda: model)
    return model


def test_reorders_by_cross_encoder_score_not_vector_score(fake):
    hits = [hit("pool opens at 7", 0.9), hit("breakfast is served 7-10 in the garden room", 0.5), hit("parking", 0.8)]
    out = rerank_service.rerank("breakfast garden", hits, top_k=2)
    assert [h["content"] for h in out] == ["breakfast is served 7-10 in the garden room", "pool opens at 7"]


def test_keeps_vector_score_and_adds_a_0_to_1_rerank_score(fake):
    out = rerank_service.rerank("breakfast", [hit("breakfast at 7", 0.42), hit("spa", 0.3)], top_k=2)
    assert out[0]["similarity_score"] == 0.42
    assert all(0.0 <= h["rerank_score"] <= 1.0 for h in out)
    assert out[0]["rerank_score"] > out[1]["rerank_score"]


def test_the_model_reads_the_title_with_the_chunk(fake):
    rerank_service.rerank("pets", [hit("Small dogs welcome.", 0.5, title="Policy: pets")], top_k=1)
    assert fake.calls[0][1] == ["The Mayfair - Policy: pets\nSmall dogs welcome."]


def test_falls_back_to_vector_order_when_the_model_fails(monkeypatch):
    monkeypatch.setattr(rerank_service, "get_model", lambda: FakeModel(fail=True))
    hits = [hit("a", 0.9), hit("b", 0.8), hit("c", 0.7)]
    assert [h["content"] for h in rerank_service.rerank("q", hits, top_k=2)] == ["a", "b"]


def test_falls_back_to_vector_order_when_the_model_cannot_load(monkeypatch):
    monkeypatch.setattr(rerank_service, "get_model", lambda: None)
    hits = [hit("a", 0.9), hit("b", 0.8)]
    assert rerank_service.rerank("q", hits, top_k=1) == [hits[0]]


def test_empty_inputs(fake):
    assert rerank_service.rerank("q", [], top_k=3) == []
    assert rerank_service.rerank("  ", [hit("a", 0.9)], top_k=3) == [hit("a", 0.9)]
    assert fake.calls == []


def test_search_fetches_a_wide_pool_then_cuts_to_top_k(monkeypatch, fake):
    seen = {}

    def vector_search(db, query, hotel_id, top_k, access_level):
        seen["pool"] = top_k
        return [hit(f"chunk {i}", 1 - i / 100) for i in range(top_k)]

    monkeypatch.setattr(document_service, "_vector_search", vector_search)
    monkeypatch.setattr(document_service.settings, "RERANK_CANDIDATES", 30)
    out = document_service.search_chunks(None, "chunk", top_k=8, rerank=True)
    assert seen["pool"] == 30 and len(out) == 8 and len(fake.calls) == 1


def test_search_without_rerank_is_plain_vector_search(monkeypatch, fake):
    monkeypatch.setattr(document_service, "_vector_search", lambda db, q, h, k, a: [hit("x", 0.5)] * k)
    assert len(document_service.search_chunks(None, "q", top_k=4, rerank=False)) == 4
    assert fake.calls == []


def test_rerank_with_real_model():
    if rerank_service.get_model() is None:
        pytest.skip("re-ranker model not available offline")
    hits = [hit("The rooftop pool is open 7am to 9pm.", 0.8), hit("Breakfast is served from 7 to 10 in the garden room.", 0.6)]
    assert rerank_service.rerank("When is breakfast served?", hits, top_k=1)[0]["content"].startswith("Breakfast")


def test_the_model_reads_at_most_the_configured_number_of_characters(monkeypatch, fake):
    monkeypatch.setattr(rerank_service.settings, "RERANK_MAX_CHARS", 50)
    rerank_service.rerank("pets", [hit("x" * 500, 0.5, title="Policy: pets")], top_k=1)
    assert len(fake.calls[0][1][0]) == 50 and fake.calls[0][1][0].startswith("The Mayfair - Policy: pets")
