"""
One-time migration script: rename collections and backfill schema.

Run BEFORE deploying code changes.
Safe to run multiple times — uses upsert/idempotent operations.

Steps:
1. Copy SkuActions → returns.SkuActions
2. Copy Settings → returns.Settings
3. Copy DataCache → returns.DataCache
4. Backfill statusHistory on returns.SkuActions
5. Create indexes on returns.SkuActions
6. Verify document counts
7. Old collections are NOT dropped (manual cleanup later)

Usage:
    python migrate.py
"""

import sys
from datetime import datetime, timezone

from pymongo import MongoClient

# Connection — same write URI used by the app
URI = (
    "mongodb+srv://claude-hiccup-tools:LU6nLczES8GXzd5W"
    "@hiccup-prod.clqls.mongodb.net/hiccup-tools"
)

OLD_COLLECTIONS = {
    "SkuActions": "returns.SkuActions",
    "Settings": "returns.Settings",
    "DataCache": "returns.DataCache",
}


def migrate():
    client = MongoClient(URI, serverSelectionTimeoutMS=15000)
    db = client["hiccup-tools"]

    print("=" * 60)
    print("Migration: hiccup-tools collection rename + schema backfill")
    print("=" * 60)

    # --- Step 1-3: Copy collections ---
    for old_name, new_name in OLD_COLLECTIONS.items():
        old_coll = db[old_name]
        new_coll = db[new_name]

        old_count = old_coll.count_documents({})
        new_count = new_coll.count_documents({})

        if old_count == 0:
            print(f"\n[SKIP] {old_name} — empty, nothing to copy")
            continue

        if new_count > 0:
            print(f"\n[SKIP] {old_name} → {new_name} — target already has {new_count} docs (already migrated?)")
            continue

        print(f"\n[COPY] {old_name} ({old_count} docs) → {new_name}")
        docs = list(old_coll.find())
        if docs:
            # Remove _id to let MongoDB assign new ones (except Settings/DataCache which use fixed _ids)
            if old_name == "SkuActions":
                for doc in docs:
                    del doc["_id"]
            new_coll.insert_many(docs)
            new_count = new_coll.count_documents({})
            print(f"  Copied: {new_count} docs")
            if new_count != old_count:
                print(f"  WARNING: count mismatch! old={old_count}, new={new_count}")
            else:
                print(f"  OK — counts match")

    # --- Step 4: Backfill statusHistory on returns.SkuActions ---
    print(f"\n[BACKFILL] statusHistory on returns.SkuActions")
    sku_coll = db["returns.SkuActions"]
    backfilled = 0
    skipped = 0

    for doc in sku_coll.find():
        # Skip docs that already have statusHistory
        if doc.get("statusHistory") and len(doc["statusHistory"]) > 0:
            skipped += 1
            continue

        status = doc.get("status", "tracking")
        created_on = doc.get("createdOn", datetime.now(timezone.utc))

        # Build initial statusHistory from what we know
        history = [{
            "from": None,
            "to": status,
            "date": created_on,
            "actor": "system-migration",
            "reason": "Backfilled from existing document state",
        }]

        sku_coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {"statusHistory": history}},
        )
        backfilled += 1

    print(f"  Backfilled: {backfilled}, Already had history: {skipped}")

    # --- Step 5: Create indexes ---
    print(f"\n[INDEX] Creating indexes on returns.SkuActions")

    existing_indexes = [idx["name"] for idx in sku_coll.list_indexes()]

    if any("skuPrefix" in str(idx) for idx in existing_indexes):
        print("  skuPrefix index already exists")
    else:
        sku_coll.create_index("skuPrefix", unique=True, name="skuPrefix_unique")
        print("  Created unique index: skuPrefix_unique")

    if any("status" in str(idx) for idx in existing_indexes):
        print("  status index already exists")
    else:
        sku_coll.create_index("status", name="status_1")
        print("  Created index: status_1")

    # --- Step 6: Final verification ---
    print(f"\n[VERIFY] Final document counts:")
    for old_name, new_name in OLD_COLLECTIONS.items():
        old_count = db[old_name].count_documents({})
        new_count = db[new_name].count_documents({})
        status = "OK" if new_count >= old_count else "MISMATCH"
        print(f"  {old_name}: {old_count} → {new_name}: {new_count} [{status}]")

    # Show indexes
    print(f"\n[VERIFY] Indexes on returns.SkuActions:")
    for idx in sku_coll.list_indexes():
        print(f"  {idx['name']}: {dict(idx['key'])}")

    print(f"\n{'=' * 60}")
    print("Migration complete. Old collections NOT dropped.")
    print("Verify everything works, then manually drop old collections.")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    migrate()
