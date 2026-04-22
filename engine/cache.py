"""
Data cache in MongoDB (hiccup-tools.DataCache).
Split across multiple documents to stay under 16MB BSON limit.
"""

from datetime import datetime, timezone
import zlib

import pandas as pd
import streamlit as st
from pymongo import MongoClient

WRITE_URI = (
    "mongodb+srv://claude-hiccup-tools:LU6nLczES8GXzd5W"
    "@hiccup-prod.clqls.mongodb.net/hiccup-tools"
)

_write_client = None

CACHE_KEYS = ["df_sku", "df_sku_size", "df_supplier", "df_category", "df_recent_size"]


def _get_db():
    global _write_client
    if _write_client is None:
        uri = st.secrets.get("MONGO_WRITE_URI", WRITE_URI)
        _write_client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    return _write_client["hiccup-tools"]


def _coll():
    return _get_db()["DataCache"]


def save_cache(data: dict):
    """Save each DataFrame as a separate compressed document."""
    coll = _coll()
    now = datetime.now(timezone.utc)

    for key in CACHE_KEYS:
        df = data.get(key)
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            continue

        if isinstance(df, pd.DataFrame):
            df_copy = df.copy()
            for col in df_copy.columns:
                if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                    df_copy[col] = df_copy[col].astype(str)

            json_str = df_copy.to_json(orient="records", default_handler=str)
            compressed = zlib.compress(json_str.encode(), level=6)

            coll.replace_one(
                {"_id": key},
                {"_id": key, "data": compressed, "rows": len(df), "updatedOn": now},
                upsert=True,
            )

    coll.replace_one(
        {"_id": "meta"},
        {"_id": "meta", "updatedOn": now},
        upsert=True,
    )


def load_cache() -> dict:
    """Load cached DataFrames from MongoDB."""
    coll = _coll()
    meta = coll.find_one({"_id": "meta"})
    if not meta:
        return None

    result = {"updatedOn": meta.get("updatedOn")}

    # Known datetime columns per cache key
    datetime_columns = {
        "df_sku": ["first_order"],
    }

    for key in CACHE_KEYS:
        doc = coll.find_one({"_id": key})
        if doc and "data" in doc:
            json_str = zlib.decompress(doc["data"]).decode()
            df = pd.read_json(json_str, orient="records")
            # Convert known datetime columns back from strings
            for col in datetime_columns.get(key, []):
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
            result[key] = df
        else:
            result[key] = pd.DataFrame()

    return result


def get_cache_age() -> str:
    """Return human-readable age of cache."""
    try:
        coll = _coll()
        meta = coll.find_one({"_id": "meta"}, {"updatedOn": 1})
        if not meta or "updatedOn" not in meta:
            return "never"
        updated = meta["updatedOn"]
        if not isinstance(updated, datetime):
            return "unknown"
        now = datetime.now(tz=None)
        if updated.tzinfo is not None:
            updated = updated.replace(tzinfo=None)
        delta = now - updated
    except Exception:
        return "unknown"
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{int(delta.total_seconds() / 60)} min ago"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours / 24)}d ago"
