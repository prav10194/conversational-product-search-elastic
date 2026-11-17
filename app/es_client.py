"""Elasticsearch connection. Works with start-local, Elastic Cloud (API key) and ECK (CA cert)."""
from __future__ import annotations

from elasticsearch import Elasticsearch

from app import config


def get_es() -> Elasticsearch:
    kwargs = {"request_timeout": 60}
    if config.ES_API_KEY:
        kwargs["api_key"] = config.ES_API_KEY
    elif config.ES_PASSWORD:
        kwargs["basic_auth"] = (config.ES_USERNAME, config.ES_PASSWORD)
    if config.ES_CA_CERT:
        kwargs["ca_certs"] = config.ES_CA_CERT
    return Elasticsearch(config.ES_URL, **kwargs)
