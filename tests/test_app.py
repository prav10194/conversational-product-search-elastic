"""Runs with no Elasticsearch and no Claude key: both are faked.
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["CREDS_FILE"] = "/nonexistent"

from app import config, main  # noqa: E402
from app.search import build_request, run_search  # noqa: E402
from app.understand import QueryPlan, clean, rule_based  # noqa: E402

config.ANTHROPIC_API_KEY = None
PRODUCTS = json.loads((Path(__file__).parent.parent / "data" / "products.json").read_text())


class FakeIndices:
    def __init__(self, semantic):
        self.semantic = semantic

    def get_mapping(self, index):
        return {index: {"mappings": {"_meta": {"semantic": self.semantic}}}}


class FakeES:
    """Applies the filters from the request to the real catalog so results are believable."""

    def __init__(self, semantic=False, fail_rrf=False):
        self.indices = FakeIndices(semantic)
        self.fail_rrf = fail_rrf
        self.requests, self.logged = [], []

    def search(self, index, **body):
        self.requests.append(body)
        if self.fail_rrf and "retriever" in body:
            raise RuntimeError("rrf needs a license")
        filters = body["query"]["function_score"]["query"]["bool"]["filter"] if "query" in body else []
        hits = [p for p in PRODUCTS if all(self._match(p, f) for f in filters)]
        return {"took": 3, "hits": {"total": {"value": len(hits)},
                                    "hits": [{"_source": p, "_score": 1.0} for p in hits[:body["size"]]]},
                "aggregations": {"brands": {"buckets": []}, "price_stats": {}}}

    @staticmethod
    def _match(p, f):
        if "term" in f:
            (field, value), = f["term"].items()
            v = p[field]
            return value in v if isinstance(v, list) else v == value
        (field, rng), = f["range"].items()
        return p[field] <= rng.get("lte", 1e9) and p[field] >= rng.get("gte", -1e9)

    def index(self, index, document):
        self.logged.append(document)

    def info(self):
        return {"version": {"number": "9.x-fake"}}


class Understanding(unittest.TestCase):
    def test_rules_extract_diet_and_price(self):
        plan = rule_based("I need gluten free pasta under $5")
        self.assertEqual(plan.diet_tags, ["gluten-free"])
        self.assertEqual(plan.max_price, 5)
        self.assertEqual(plan.search_text, "pasta")

    def test_rules_brand_and_synonym(self):
        plan = rule_based("plant-based Green Valley snacks")
        self.assertEqual(plan.brand, "Green Valley")
        self.assertIn("vegan", plan.diet_tags)

    def test_clean_drops_invented_values(self):
        plan = clean(QueryPlan(intent="find_product", search_text="x", diet_tags=["gluten-free", "paleo"],
                               category="Toys", brand="Acme"))
        self.assertEqual((plan.diet_tags, plan.category, plan.brand), (["gluten-free"], None, None))


class Search(unittest.TestCase):
    def test_filters_are_in_filter_context(self):
        plan = QueryPlan(intent="find_product", search_text="pasta", diet_tags=["gluten-free"], max_price=5)
        body = build_request(plan, "store-1001", "lexical")
        f = body["query"]["function_score"]["query"]["bool"]["filter"]
        self.assertIn({"term": {"diet_tags": "gluten-free"}}, f)
        self.assertIn({"range": {"price": {"lte": 5}}}, f)
        self.assertIn({"term": {"in_stock_stores": "store-1001"}}, f)

    def test_hybrid_applies_filters_to_both_retrievers(self):
        plan = QueryPlan(intent="find_product", search_text="pasta", diet_tags=["gluten-free"])
        body = build_request(plan, "store-1001", "hybrid")
        a, b = body["retriever"]["rrf"]["retrievers"]
        self.assertTrue(a["standard"]["query"]["function_score"]["query"]["bool"]["filter"])
        self.assertTrue(b["standard"]["query"]["bool"]["filter"])

    def test_falls_back_to_lexical_without_semantic_index(self):
        plan = QueryPlan(intent="find_product", search_text="pasta")
        self.assertEqual(run_search(FakeES(semantic=False), plan, "store-1001")["mode"], "lexical")

    def test_falls_back_when_rrf_fails(self):
        plan = QueryPlan(intent="find_product", search_text="pasta")
        self.assertEqual(run_search(FakeES(semantic=True, fail_rrf=True), plan, "store-1001")["mode"], "lexical")


class Api(unittest.TestCase):
    def setUp(self):
        self.fake = FakeES()
        main._es = self.fake
        self.client = main.app.test_client()

    def test_chat_end_to_end(self):
        r = self.client.post("/api/chat", json={"message": "gluten-free pasta under $5", "store": "store-1001"})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertGreater(data["total"], 0)
        for p in data["products"]:
            self.assertIn("gluten-free", p["diet_tags"])
            self.assertLessEqual(p["price"], 5)
            self.assertIn("store-1001", p["in_stock_stores"])
        self.assertEqual(self.fake.logged[-1]["understanding"], "rules")

    def test_pipeline_explains_each_step(self):
        data = self.client.post("/api/chat", json={"message": "gluten free pasta under $5"}).get_json()
        titles = [s["title"] for s in data["pipeline"]]
        self.assertEqual(titles[0], "Your phrase")
        self.assertIn("built-in rules", titles[1])
        text = " ".join(" ".join(s.get("lines", [])) for s in data["pipeline"])
        self.assertIn('Synonym "gluten free"', text)
        self.assertIn("max_price 5", text)
        self.assertIn("term  diet_tags = 'gluten-free'", text)

    def test_empty_message_rejected(self):
        self.assertEqual(self.client.post("/api/chat", json={"message": "  "}).status_code, 400)

    def test_zero_results_logged(self):
        self.client.post("/api/chat", json={"message": "Ocean Bay vegan under $1"})
        self.assertTrue(self.fake.logged[-1]["zero_results"])


if __name__ == "__main__":
    unittest.main()
