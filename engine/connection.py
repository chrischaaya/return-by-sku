"""
MongoDB connection singleton.
Uses the read-only claude-code-read-all user against hiccup-prod.
"""

from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database

import config

_client: Optional[MongoClient] = None


def get_db() -> Database:
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=30_000)
    return _client[config.MONGO_DB]


def close():
    global _client
    if _client is not None:
        _client.close()
        _client = None
