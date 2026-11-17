"""Step 2: turn the plan into an Elasticsearch query.

Hard constraints (diet, price, brand, store stock) go in `filter`: yes/no, no scoring, cached.
The words go to BM25 (lexical) and, when the index has it, ELSER (semantic).
Hybrid = both result lists merged with RRF. Filters are applied inside BOTH,
so semantic search can never return a non-gluten-free pasta for a gluten-free ask.
"""
from __future__ import annotations

import time

from app import config
from app.understand import QueryPlan


def build_filters(plan: QueryPlan, store: str) -> list:
    filters = [{"term": {"diet_tags": tag}} for tag in plan.diet_tags]
    if plan.category:
        filters.append({"term": {"category": plan.category}})
    if plan.brand:
        filters.append({"term": {"brand": plan.brand}})
    if plan.max_price is not None or plan.min_price is not None:
        rng = {}
        if plan.max_price is not None:
            rng["lte"] = plan.max_price
        if plan.min_price is not None:
            rng["gte"] = plan.min_price
        filters.append({"range": {"price": rng}})
    if plan.in_stock_only and store:
        filters.append({"term": {"in_stock_stores": store}})
    return filters


def lexical_query(plan: QueryPlan, filters: list) -> dict:
    must = ({"multi_match": {"query": plan.search_text,
                             "fields": ["name^3", "description", "category"],
                             "fuzziness": "AUTO",
                             # first letter must match: stops warm→farm and meal→real false matches
                             "prefix_length": 1}}
            if plan.search_text else {"match_all": {}})
    return {"function_score": {
        "query": {"bool": {"must": [must], "filter": filters}},
        # popular products get a gentle boost; log1p keeps one bestseller from dominating
        "field_value_factor": {"field": "popularity", "modifier": "log1p", "missing": 1},
        "boost_mode": "multiply"}}


def build_request(plan: QueryPlan, store: str, mode: str, size: int = 8) -> dict:
    filters = build_filters(plan, store)
    aggs = {"brands": {"terms": {"field": "brand", "size": 10}},
            "price_stats": {"stats": {"field": "price"}}}
    if mode == "lexical" or not plan.search_text:
        return {"query": lexical_query(plan, filters), "aggs": aggs, "size": size}
    semantic = {"standard": {"query": {"bool": {
        "must": [{"semantic": {"field": config.SEMANTIC_FIELD, "query": plan.search_text}}],
        "filter": filters}}}}
    if mode == "semantic":
        return {"retriever": semantic, "aggs": aggs, "size": size}
    return {"retriever": {"rrf": {"retrievers": [{"standard": {"query": lexical_query(plan, filters)}}, semantic],
                                  "rank_window_size": 50}},
            "aggs": aggs, "size": size}


# The mapping doesn't change while the app runs, so ask once per client and remember the answer.
# (APM showed this lookup costing ~420 ms on every search before it was cached.)
_semantic_cache: dict[int, bool] = {}


def index_has_semantic(es) -> bool:
    key = id(es)
    if key in _semantic_cache:
        return _semantic_cache[key]
    try:
        meta = es.indices.get_mapping(index=config.PRODUCTS_INDEX)[config.PRODUCTS_INDEX]["mappings"].get("_meta", {})
    except Exception:
        return False  # not cached: try again on the next search
    _semantic_cache[key] = bool(meta.get("semantic"))
    return _semantic_cache[key]


def run_search(es, plan: QueryPlan, store: str, mode: str = "hybrid") -> dict:
    if mode != "lexical" and (not plan.search_text or not index_has_semantic(es)):
        mode = "lexical"
    body = build_request(plan, store, mode)
    started = time.time()
    try:
        resp = es.search(index=config.PRODUCTS_INDEX, **body)
    except Exception as exc:
        if mode == "lexical":
            raise
        # RRF needs a trial/Enterprise license; ELSER may still be loading. Degrade, don't fail.
        print(f"{mode} search failed ({exc}); falling back to lexical")
        mode = "lexical"
        body = build_request(plan, store, mode)
        resp = es.search(index=config.PRODUCTS_INDEX, **body)
    took_ms = int((time.time() - started) * 1000)
    hits = [{**h["_source"], "_score": h.get("_score")} for h in resp["hits"]["hits"]]
    aggs = resp.get("aggregations", {})
    return {
        "mode": mode,
        "request": body,
        "took_ms": resp.get("took", took_ms),
        "total": resp["hits"]["total"]["value"],
        "hits": hits,
        "brands": [{"brand": b["key"], "count": b["doc_count"]} for b in aggs.get("brands", {}).get("buckets", [])],
        "price_stats": aggs.get("price_stats", {}),
    }
