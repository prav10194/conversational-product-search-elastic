"""Creates the indices and loads the catalog. Optionally creates Kibana data views.

    python -m app.setup_index                 # products index with semantic search (needs ELSER: trial or Elastic Cloud)
    python -m app.setup_index --no-semantic   # keyword search only (works on any license)
    python -m app.setup_index --kibana        # also create Kibana data views
"""
from __future__ import annotations

import argparse
import json
import time

import requests
from elasticsearch import ApiError, helpers

from app import config
from app.es_client import get_es

PRODUCT_MAPPINGS = {
    "properties": {
        "sku": {"type": "keyword"},
        # text for searching inside the name + keyword sub-field for exact match and A-Z sorting
        "name": {"type": "text", "analyzer": "english", "fields": {"keyword": {"type": "keyword"}},
                 "copy_to": config.SEMANTIC_FIELD},
        "brand": {"type": "keyword"},
        "category": {"type": "keyword", "copy_to": config.SEMANTIC_FIELD},
        "aisle": {"type": "keyword"},
        "description": {"type": "text", "analyzer": "english", "copy_to": config.SEMANTIC_FIELD},
        "diet_tags": {"type": "keyword"},
        "price": {"type": "float"},
        "size": {"type": "keyword", "index": False},
        "rating": {"type": "float"},
        "popularity": {"type": "integer"},
        "in_stock_stores": {"type": "keyword"},
        # ELSER embeds this field automatically; with no inference_id the deployment's default model is used
        config.SEMANTIC_FIELD: {"type": "semantic_text"},
    }
}

LOG_MAPPINGS = {
    "properties": {
        "@timestamp": {"type": "date"},
        "message": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
        "intent": {"type": "keyword"},
        "search_text": {"type": "keyword"},
        "diet_tags": {"type": "keyword"},
        "category": {"type": "keyword"},
        "brand": {"type": "keyword"},
        "max_price": {"type": "float"},
        "store": {"type": "keyword"},
        "mode": {"type": "keyword"},
        "understanding": {"type": "keyword"},
        "hits": {"type": "integer"},
        "zero_results": {"type": "boolean"},
        "took_ms": {"type": "integer"},
        "top_sku": {"type": "keyword"},
    }
}


def create_products(es, semantic: bool, reset: bool):
    if reset:
        es.indices.delete(index=config.PRODUCTS_INDEX, ignore_unavailable=True)
    if es.indices.exists(index=config.PRODUCTS_INDEX):
        print(f"{config.PRODUCTS_INDEX} already exists (use --reset to rebuild)")
        return
    mappings = json.loads(json.dumps(PRODUCT_MAPPINGS))
    if not semantic:
        mappings["properties"].pop(config.SEMANTIC_FIELD)
        for f in ("name", "category", "description"):
            mappings["properties"][f].pop("copy_to")
    mappings["_meta"] = {"semantic": semantic}
    es.indices.create(index=config.PRODUCTS_INDEX, settings={"number_of_replicas": 0} if "localhost" in config.ES_URL else {},
                      mappings=mappings)
    print(f"Created {config.PRODUCTS_INDEX} (semantic search: {'on' if semantic else 'off'})")


def load_products(es, semantic: bool):
    products = json.loads((config.ROOT / "data" / "products.json").read_text())
    actions = ({"_index": config.PRODUCTS_INDEX, "_id": p["sku"], "_source": p} for p in products)
    # Semantic search embeds each product at index time: small batches, long timeout, retry while ELSER starts.
    for attempt in range(1, 6):
        try:
            ok, _ = helpers.bulk(es.options(request_timeout=300), actions, chunk_size=50 if semantic else 500)
            es.indices.refresh(index=config.PRODUCTS_INDEX)
            print(f"Loaded {ok} products")
            return
        except ApiError as exc:
            print(f"  attempt {attempt}: {exc.message if hasattr(exc, 'message') else exc}; the model may still be starting, waiting 30s")
            time.sleep(30)
            actions = ({"_index": config.PRODUCTS_INDEX, "_id": p["sku"], "_source": p} for p in products)
    raise SystemExit("Loading failed. Try --no-semantic, or check Kibana > Machine Learning > Trained Models.")


def create_logs(es):
    if not es.indices.exists(index=config.LOGS_INDEX):
        es.indices.create(index=config.LOGS_INDEX, mappings=LOG_MAPPINGS)
        print(f"Created {config.LOGS_INDEX}")


def create_data_views():
    auth = (config.ES_USERNAME, config.ES_PASSWORD or "")
    headers = {"kbn-xsrf": "true", "Content-Type": "application/json"}
    if config.ES_API_KEY:
        headers["Authorization"] = f"ApiKey {config.ES_API_KEY}"
        auth = None
    for title, name, time_field in [(config.PRODUCTS_INDEX, "Grocery products", None),
                                    (config.LOGS_INDEX, "Search logs", "@timestamp")]:
        view = {"title": title, "name": name}
        if time_field:
            view["timeFieldName"] = time_field
        r = requests.post(f"{config.KIBANA_URL}/api/data_views/data_view", json={"data_view": view},
                          auth=auth, headers=headers, timeout=30)
        print(f"Kibana data view '{name}': {'created' if r.ok else r.text[:200]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-semantic", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--kibana", action="store_true")
    args = ap.parse_args()
    es = get_es()
    print(f"Connected to Elasticsearch {es.info()['version']['number']} at {config.ES_URL}")
    semantic = not args.no_semantic
    create_products(es, semantic, args.reset)
    load_products(es, semantic)
    create_logs(es)
    if args.kibana:
        create_data_views()


if __name__ == "__main__":
    main()
