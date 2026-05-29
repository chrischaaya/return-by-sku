"""
MongoDB connection singleton.
Uses the read-only claude-code-read-all user against hiccup-prod.
"""

from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database

import config

_client: Optional[MongoClient] = None
_ff_client: Optional[MongoClient] = None


def get_db() -> Database:
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=30_000)
    return _client[config.MONGO_DB]


def get_ff_db() -> Database:
    """Singleton connection to hiccup-ff (POs). Reused across reruns to avoid
    paying the Atlas TLS/SRV handshake (~0.3-0.8s) on every interaction."""
    global _ff_client
    if _ff_client is None:
        import streamlit as st
        uri = st.secrets.get("MONGO_FF_URI", st.secrets.get("MONGO_URI"))
        _ff_client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
    return _ff_client["hiccup-ff"]


def close():
    global _client, _ff_client
    if _client is not None:
        _client.close()
        _client = None
    if _ff_client is not None:
        _ff_client.close()
        _ff_client = None
