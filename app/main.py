"""Flask web app: chat box -> Claude (understand) -> Elasticsearch (search) -> reply + log for Kibana."""
from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from app import config, telemetry
from app.es_client import get_es
from app.search import build_filters, run_search
from app.understand import understand

app = Flask(__name__, template_folder="../templates", static_folder="../static")
telemetry.setup(app)
_es = None
# Search logs are written in the background so the shopper doesn't wait for them.
# (APM showed the synchronous write adding ~680 ms to every search.)
_log_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="search-log")


def es():
    global _es
    if _es is None:
        _es = get_es()
    return _es


def reply_text(plan, result) -> str:
    if plan.intent == "store_info":
        return "Stores are open 6am to 11pm daily. Ask me about products and I'll find them in your store."
    if plan.intent == "other":
        return "I can help you find groceries. Try: \"gluten-free pasta under $5\"."
    n = result["total"]
    if n == 0:
        return "I couldn't find anything matching all of that. Try removing a filter, like the price or diet."
    bits = [", ".join(plan.diet_tags)] if plan.diet_tags else []
    if plan.brand:
        bits.append(plan.brand)
    if plan.max_price is not None:
        bits.append(f"under ${plan.max_price:g}")
    what = plan.search_text or "products"
    extra = f" ({'; '.join(bits)})" if bits else ""
    return f"Found {n} {what}{extra}. Here are the best matches."


def explain_filter(f) -> str:
    if "term" in f:
        (field, value), = f["term"].items()
        why = {"diet_tags": "diet is a fact, not relevance", "in_stock_stores": "only items on the shelf at this store",
               "brand": "the shopper named a brand", "category": "category was clearly implied"}.get(field, "")
        return f"term  {field} = {value!r}   ({why})"
    (field, rng), = f["range"].items()
    parts = [f"{'<=' if k == 'lte' else '>='} {v:g}" for k, v in rng.items()]
    return f"range {field} {' and '.join(parts)}   (price limit from the sentence)"


def build_pipeline(message, plan, source, trace, result, store):
    steps = [{"title": "Your phrase", "lines": [f'"{message}"']},
             {"title": f"Understand it ({'Claude' if source == 'claude' else 'built-in rules'})", "lines": trace},
             {"title": "Query plan", "code": plan.model_dump()}]
    if plan.intent != "find_product":
        steps.append({"title": "No product search", "lines": [f"intent = {plan.intent}, so Elasticsearch isn't called"]})
        return steps
    filters = build_filters(plan, store)
    steps.append({"title": "Filters (yes/no, not scored, cached)",
                  "lines": [explain_filter(f) for f in filters] or ["none"]})
    mode = result["mode"]
    if not plan.search_text:
        scoring = ["No search words, so match_all: every product that passes the filters"]
    else:
        scoring = [f'BM25 multi_match "{plan.search_text}" on name^3, description, category (fuzziness AUTO, first letter exact)']
        if mode in ("hybrid", "semantic"):
            scoring.append(f'ELSER semantic match "{plan.search_text}" on semantic_all (meaning, not exact words)')
        if mode == "hybrid":
            scoring.append("RRF merges the two ranked lists by position, so neither score scale dominates")
    if mode != "semantic":
        scoring.append("× log1p(popularity): bestsellers get a gentle nudge")
    steps.append({"title": f"Score what's left (mode: {mode})", "lines": scoring})
    steps.append({"title": "Elasticsearch request", "code": result["request"]})
    steps.append({"title": "Result", "lines": [f"{result['total']} matches in {result['took_ms']} ms; showing top {len(result['hits'])}"]})
    return steps


def log_search(message, plan, source, result, store):
    doc = {"@timestamp": datetime.now(timezone.utc).isoformat(), "message": message,
           "intent": plan.intent, "search_text": plan.search_text, "diet_tags": plan.diet_tags,
           "category": plan.category, "brand": plan.brand, "max_price": plan.max_price, "store": store,
           "mode": result.get("mode"), "understanding": source, "hits": result.get("total", 0),
           "zero_results": result.get("total", 0) == 0, "took_ms": result.get("took_ms", 0),
           "top_sku": result["hits"][0]["sku"] if result.get("hits") else None}
    try:
        es().index(index=config.LOGS_INDEX, document=doc)
    except Exception as exc:  # logging must never break a search
        print(f"could not log search: {exc}")


@app.get("/")
def home():
    return render_template("index.html", stores=config.STORES, default_store=config.DEFAULT_STORE,
                           kibana_url=config.KIBANA_URL)


@app.get("/api/health")
def health():
    try:
        info = es().info()
        return jsonify(ok=True, elasticsearch=info["version"]["number"],
                       claude=bool(config.ANTHROPIC_API_KEY), model=config.CLAUDE_MODEL)
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 503


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify(error="Type what you're looking for."), 400
    if len(message) > 500:
        return jsonify(error="Please keep it under 500 characters."), 400
    store = data.get("store") if data.get("store") in config.STORES else config.DEFAULT_STORE
    mode = data.get("mode") if data.get("mode") in ("hybrid", "lexical", "semantic") else "hybrid"

    with telemetry.step("understand query", **{"query.length": len(message)}) as span:
        plan, source, trace = understand(message)
        if span is not None:
            span.set_attribute("query.understanding", source)
            span.set_attribute("query.intent", plan.intent)
            span.set_attribute("query.diet_tags", ",".join(plan.diet_tags))
    result = {"mode": None, "total": 0, "hits": [], "brands": [], "request": None, "took_ms": 0}
    if plan.intent == "find_product":
        try:
            with telemetry.step("search products", **{"search.mode_requested": mode, "store": store}) as span:
                result = run_search(es(), plan, store, mode)
                if span is not None:
                    span.set_attribute("search.mode", result["mode"])
                    span.set_attribute("search.hits", result["total"])
        except Exception as exc:
            return jsonify(error=f"Search is unavailable: {exc}"), 503
    # copy_context keeps the trace context, so the log write still shows up in the same trace.
    _log_pool.submit(contextvars.copy_context().run, log_search, message, plan, source, result, store)
    telemetry.record_search(result["mode"], source, result["total"], result["took_ms"], message)
    return jsonify(reply=reply_text(plan, result), plan=plan.model_dump(), understanding=source,
                   pipeline=build_pipeline(message, plan, source, trace, result, store),
                   mode=result["mode"], total=result["total"], took_ms=result["took_ms"],
                   products=result["hits"], brands=result["brands"], es_request=result["request"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
