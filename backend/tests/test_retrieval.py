"""Document-diversified retrieval selection — pure logic, no Qdrant."""

from services.retrieval import (
    REFERENCE_WEIGHT,
    apply_doc_type_weights,
    diversify_by_document,
)


def chunk(doc: str, score: float, idx: int = 0) -> dict:
    return {"document_name": doc, "score": score, "chunk_index": idx, "content": f"{doc}-{idx}"}


def make_pool(spec: dict[str, list[float]]) -> list[dict]:
    """spec: {doc_name: [scores...]} → flat pool sorted by score desc."""
    pool = [
        chunk(doc, s, i)
        for doc, scores in spec.items()
        for i, s in enumerate(scores)
    ]
    pool.sort(key=lambda r: r["score"], reverse=True)
    return pool


class TestDiversifyByDocument:
    def test_dominant_doc_cannot_monopolize(self):
        # The measured real-world failure: one keyword-dense doc outranks
        # everything; other docs' best chunks must still reach the judge.
        pool = make_pool({
            "roadmap.pdf": [0.80, 0.79, 0.78, 0.77, 0.76, 0.75, 0.74, 0.73],
            "security-2pager.pdf": [0.70, 0.65],
            "europe-wp.pdf": [0.69],
        })
        picked = diversify_by_document(pool, top_k=6)
        docs = [r["document_name"] for r in picked]
        assert docs.count("roadmap.pdf") == 3          # ceil(6/2) cap
        assert "security-2pager.pdf" in docs
        assert "europe-wp.pdf" in docs
        # Every doc's BEST chunk is present
        assert any(r["score"] == 0.70 for r in picked)
        assert any(r["score"] == 0.69 for r in picked)

    def test_single_document_fills_all_slots(self):
        # A one-doc assessment must not be starved by the cap
        pool = make_pool({"only.pdf": [0.9, 0.8, 0.7, 0.6, 0.5, 0.4]})
        picked = diversify_by_document(pool, top_k=4)
        assert len(picked) == 4
        assert [r["score"] for r in picked] == [0.9, 0.8, 0.7, 0.6]

    def test_top_up_past_cap_when_others_exhausted(self):
        # 2 docs, one tiny: cap would leave slots empty — fill them anyway
        pool = make_pool({
            "big.pdf": [0.9, 0.8, 0.7, 0.6, 0.5],
            "tiny.pdf": [0.4],
        })
        picked = diversify_by_document(pool, top_k=4)
        assert len(picked) == 4
        assert sum(1 for r in picked if r["document_name"] == "big.pdf") == 3
        assert sum(1 for r in picked if r["document_name"] == "tiny.pdf") == 1

    def test_result_sorted_by_similarity(self):
        pool = make_pool({
            "a.pdf": [0.9, 0.5],
            "b.pdf": [0.8, 0.4],
            "c.pdf": [0.7],
        })
        picked = diversify_by_document(pool, top_k=4)
        scores = [r["score"] for r in picked]
        assert scores == sorted(scores, reverse=True)

    def test_small_pool_passthrough(self):
        pool = make_pool({"a.pdf": [0.9], "b.pdf": [0.8]})
        assert diversify_by_document(pool, top_k=8) == pool


class TestDocTypeWeights:
    def test_reference_chunks_down_weighted_and_resorted(self):
        results = [
            {**chunk("generic-guide.pdf", 0.80), "doc_type": "reference"},
            {**chunk("vendor-2pager.pdf", 0.72), "doc_type": "vendor"},
        ]
        weighted = apply_doc_type_weights(results)
        # 0.80 × 0.85 = 0.68 < 0.72 → vendor doc now outranks the generic guide
        assert weighted[0]["document_name"] == "vendor-2pager.pdf"
        assert abs(weighted[1]["score"] - 0.80 * REFERENCE_WEIGHT) < 1e-9

    def test_legacy_chunks_without_doc_type_untouched(self):
        results = [{**chunk("old.pdf", 0.7)}]  # pre-tagging chunk, no doc_type
        weighted = apply_doc_type_weights(results)
        assert weighted[0]["score"] == 0.7

    def test_vendor_chunks_untouched(self):
        results = [{**chunk("v.pdf", 0.5), "doc_type": "vendor"}]
        assert apply_doc_type_weights(results)[0]["score"] == 0.5
