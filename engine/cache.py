"""
Data cache in MongoDB (hiccup-tools.DataCache).
Pre-computed results are stored and read back instantly.
Only recomputed when user clicks "Update Data".
"""

from datetime import datetime, timezone
import json

import pandas as pd
import streamlit as st
from pymongo import MongoClient

WRITE_URI = (
    "mongodb+srv://claude-hiccup-tools:LU6nLczES8GXzd5W"
    "@hiccup-prod.clqls.mongodb.net/hiccup-tools"
)

_write_client = None


def _get_db():
    global _write_client
    if _write_client is None:
        uri = st.secrets.get("MONGO_WRITE_URI", WRITE_URI)
        _write_client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    return _write_client["hiccup-tools"]


def _coll():
    return _get_db()["DataCache"]


def save_cache(data: dict):
    """Save pre-computed DataFrames to MongoDB."""
    cache_doc = {"_id": "latest", "updatedOn": datetime.now(timezone.utc)}

    for key, df in data.items():
        if isinstance(df, pd.DataFrame):
            # Convert datetime columns to string for JSON serialization
            df_copy = df.copy()
            for col in df_copy.columns:
                if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                    df_copy[col] = df_copy[col].astype(str)
                elif df_copy[col].dtype == object:
                    # Handle lists and other objects
                    pass
            cache_doc[key] = json.loads(df_copy.to_json(orient="records", default_handler=str))
        else:
            cache_doc[key] = data[key]

    _coll().replace_one({"_id": "latest"}, cache_doc, upsert=True)


def load_cache() -> dict:
    """Load pre-computed DataFrames from MongoDB. Returns None if no cache."""
    doc = _coll().find_one({"_id": "latest"})
    if not doc:
        return None

    result = {}
    for key in ["df_sku", "df_sku_size", "df_supplier", "df_category", "df_recent_size"]:
        if key in doc and doc[key]:
            result[key] = pd.DataFrame(doc[key])
        else:
            result[key] = pd.DataFrame()

    result["updatedOn"] = doc.get("updatedOn")
    return result


def get_cache_age() -> str:
    """Return human-readable age of cache."""
    doc = _coll().find_one({"_id": "latest"}, {"updatedOn": 1})
    if not doc or "updatedOn" not in doc:
        return "never"
    delta = datetime.now(timezone.utc) - doc["updatedOn"]
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{int(delta.total_seconds() / 60)} min ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours / 24)}d ago"
