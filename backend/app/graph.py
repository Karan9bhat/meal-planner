"""Food knowledge graph in MongoDB Atlas.

Nodes (kg_nodes, _id = "<type>:<key>") and edges (kg_edges: from -rel-> to):

  place ─IN→ country ─USES→ currency          place ─EATS→ cuisine
  cuisine ─HAS_DISH→ dish ─CONTAINS→ tag      cuisine ─STAPLE→ ingredient     cuisine ─PRICED_IN→ currency
  diet / restriction ─EXCLUDES→ tag           allergy ─IS→ tag                tag ─INCLUDES→ tag (animal_product → meat → red_meat → beef)
  style (keto, high protein…) and equipment are nodes the planner reads.

Only reference knowledge lives here: user answers and plans stay in the browser.
Everything degrades to the JSON knowledge base when MONGODB_URI is unset or Atlas is unreachable: every query
returns None and callers fall back.
"""

import hashlib
import json
import logging
import os
import threading
import time
from functools import lru_cache

from pymongo import ASCENDING, MongoClient, UpdateOne
from pymongo.errors import PyMongoError

from . import kb
from .config import BACKEND_DIR

log = logging.getLogger("mealplanner.graph")

URI = os.getenv("MONGODB_URI", "")
DB_NAME = os.getenv("MONGODB_DB", "meal_planner")
# X.509 auth: Atlas's downloaded PEM (certificate + private key). On Render it's a Secret File under /etc/secrets.
CERT_PATH = os.getenv("MONGODB_CERT_PATH") or str(BACKEND_DIR / "certs" / "mongodb-x509.pem")
RETRY_AFTER_S = 60


def _client_options() -> dict | None:
    opts: dict = {"serverSelectionTimeoutMS": 4000, "connectTimeoutMS": 4000, "appname": "meal-planner"}
    if "MONGODB-X509" in URI.upper():
        if not os.path.isfile(CERT_PATH):
            log.warning("MONGODB_URI uses certificate (X.509) auth but no certificate was found at %s; "
                        "download it from Atlas (Database Access) or set MONGODB_CERT_PATH", CERT_PATH)
            return None
        opts["tlsCertificateKeyFile"] = CERT_PATH
    return opts

_lock = threading.Lock()
_db = None
_down_until = 0.0


def _database():
    """Lazily connected database, or None while Atlas is unconfigured/unreachable (retried after a minute)."""
    global _db, _down_until
    if not URI:
        return None
    if _db is not None:
        return _db
    if time.monotonic() < _down_until:
        return None
    with _lock:
        if _db is None:
            opts = _client_options()
            if opts is None:
                _down_until = time.monotonic() + RETRY_AFTER_S
                return None
            try:
                client = MongoClient(URI, **opts)
                client.admin.command("ping")
                _db = client[DB_NAME]
                log.info("connected to MongoDB knowledge graph (%s)", DB_NAME)
            except PyMongoError as e:
                log.warning("MongoDB unavailable, using the JSON knowledge base: %s", e)
                _down_until = time.monotonic() + RETRY_AFTER_S
    return _db


def available() -> bool:
    return _database() is not None


def _nid(kind: str, key: str) -> str:
    return f"{kind}:{kb.normalize(key).replace(' ', '_')}"


def _node(kind: str, key: str, name: str, **props) -> UpdateOne:
    return UpdateOne({"_id": _nid(kind, key)}, {"$set": {"type": kind, "key": key, "name": name, **props}}, upsert=True)


def _edge(frm: str, rel: str, to: str, **props) -> UpdateOne:
    # $setOnInsert keeps the update non-empty for property-less edges (an empty $set is rejected).
    update: dict = {"$setOnInsert": {"created": time.time()}}
    if props:
        update["$set"] = props
    return UpdateOne({"from": frm, "rel": rel, "to": to}, update, upsert=True)


# ---------- writes ----------

def _cuisine_ops(p: kb.CuisineProfile) -> tuple[list[UpdateOne], list[UpdateOne]]:
    c = _nid("cuisine", p.key)
    nodes = [
        _node(
            "cuisine", p.key, p.name,
            region=p.region,
            aliases=[kb.normalize(a) for a in [p.name, p.region, *p.aliases]],
            meal_pattern=p.meal_pattern,
            meal_times=p.meal_times,
            daily_budget=p.daily_budget.model_dump(),
            pantry_basics=p.pantry_basics,
            source=p.source,
            # Full profile for exact reloads; the edges below are what queries traverse.
            profile=p.model_dump(),
        ),
        _node("currency", p.currency.code, p.currency.code, symbol=p.currency.symbol),
    ]
    edges = [_edge(c, "PRICED_IN", _nid("currency", p.currency.code))]
    for s in p.staples:
        nodes.append(_node("ingredient", s, s))
        edges.append(_edge(c, "STAPLE", _nid("ingredient", s)))
    for d in p.dishes:
        dish = f"dish:{p.key}:{kb.normalize(d.name).replace(' ', '_')}"
        nodes.append(UpdateOne({"_id": dish}, {"$set": {"type": "dish", "key": dish, "name": d.name, "portion": d.portion,
                                                        "kcal": d.kcal, "protein_g": d.protein_g, "cuisine": p.key}}, upsert=True))
        edges.append(_edge(c, "HAS_DISH", dish))
        for t in d.contains:
            edges.append(_edge(dish, "CONTAINS", _nid("tag", t)))
    return nodes, edges


def _rules_ops() -> tuple[list[UpdateOne], list[UpdateOne]]:
    nodes, edges = [], []
    tags = set(kb.TAG_HIERARCHY) | {t for kids in kb.TAG_HIERARCHY.values() for t in kids}
    tags |= {t for p in kb.CUISINES.values() for d in p.dishes for t in d.contains} | set(kb.ALLERGIES)
    for t in tags:
        nodes.append(_node("tag", t, t.replace("_", " ")))
    for parent, kids in kb.TAG_HIERARCHY.items():
        for k in kids:
            edges.append(_edge(_nid("tag", parent), "INCLUDES", _nid("tag", k)))
    for key, d in kb.DIET_TYPES.items():
        nodes.append(_node("diet", key, d["label"], desc=d["desc"]))
        edges += [_edge(_nid("diet", key), "EXCLUDES", _nid("tag", t)) for t in d["excludes"]]
    for key, r in kb.RESTRICTIONS.items():
        nodes.append(_node("restriction", key, r["label"]))
        edges += [_edge(_nid("restriction", key), "EXCLUDES", _nid("tag", t)) for t in r["excludes"]]
    for key, label in kb.ALLERGIES.items():
        nodes.append(_node("allergy", key, label))
        edges.append(_edge(_nid("allergy", key), "IS", _nid("tag", key)))
    nodes += [_node("style", k, v) for k, v in kb.DIET_STYLES.items()]
    nodes += [_node("equipment", k, v) for k, v in kb.EQUIPMENT.items()]
    return nodes, edges


def _write(nodes: list[UpdateOne], edges: list[UpdateOne]) -> None:
    db = _database()
    if db is None:
        return
    if nodes:
        db.kg_nodes.bulk_write(nodes, ordered=False)
    if edges:
        db.kg_edges.bulk_write(edges, ordered=False)


def _seed_hash() -> str:
    raw = (kb.KB_DIR / "cuisines.json").read_bytes() + json.dumps(
        [kb.TAG_HIERARCHY, kb.DIET_TYPES, kb.RESTRICTIONS, kb.ALLERGIES, kb.DIET_STYLES, kb.EQUIPMENT], sort_keys=True
    ).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def seed() -> bool:
    """Write curated knowledge + rules into the graph; skipped when nothing changed since the last seed."""
    db = _database()
    if db is None:
        return False
    try:
        db.kg_nodes.create_index([("type", ASCENDING)])
        db.kg_nodes.create_index([("aliases", ASCENDING)])
        db.kg_edges.create_index([("from", ASCENDING), ("rel", ASCENDING), ("to", ASCENDING)], unique=True)
        db.kg_edges.create_index([("to", ASCENDING), ("rel", ASCENDING)])
        digest = _seed_hash()
        if (db.kg_meta.find_one({"_id": "seed"}) or {}).get("hash") == digest:
            return True
        nodes, edges = _rules_ops()
        for p in kb.CUISINES.values():
            if p.source == "curated":
                n, e = _cuisine_ops(p)
                nodes += n
                edges += e
        _write(nodes, edges)
        db.kg_meta.update_one({"_id": "seed"}, {"$set": {"hash": digest, "at": time.time()}}, upsert=True)
        excluded_tags.cache_clear()
        log.info("seeded knowledge graph: %d node and %d edge upserts", len(nodes), len(edges))
        return True
    except PyMongoError as e:
        log.warning("graph seed failed: %s", e)
        return False


def save_cuisine(p: kb.CuisineProfile) -> None:
    try:
        _write(*_cuisine_ops(p))
    except PyMongoError as e:
        log.warning("couldn't save cuisine %s to the graph: %s", p.key, e)


def save_place(text: str, ref: dict) -> None:
    """A place someone typed, linked to its country, currency and cuisine (no user data, just geography)."""
    db = _database()
    if db is None:
        return
    try:
        place = _nid("place", ref["place"])
        country = _nid("country", ref.get("country") or "unknown")
        currency = _nid("currency", ref["currency_code"])
        nodes = [
            UpdateOne({"_id": place}, {"$set": {"type": "place", "key": ref["place"], "name": ref["place"], "ref": ref},
                                       "$addToSet": {"aliases": kb.normalize(text)}}, upsert=True),
            _node("country", ref.get("country") or "unknown", ref.get("country") or "Unknown"),
            _node("currency", ref["currency_code"], ref["currency_code"], symbol=ref["currency_symbol"]),
        ]
        edges = [
            _edge(place, "IN", country),
            _edge(country, "USES", currency),
            _edge(place, "EATS", _nid("cuisine", ref["key"])),
        ]
        _write(nodes, edges)
    except PyMongoError as e:
        log.warning("couldn't save place %s: %s", text, e)


# ---------- reads ----------

def find_place(text: str) -> dict | None:
    db = _database()
    if db is None:
        return None
    try:
        hit = db.kg_nodes.find_one({"type": "place", "aliases": kb.normalize(text)}, {"ref": 1})
        return hit["ref"] if hit else None
    except PyMongoError:
        return None


def generated_cuisines() -> list[kb.CuisineProfile]:
    """Model-written cuisine profiles saved in Atlas, so they survive redeploys (Render's free disk doesn't)."""
    db = _database()
    if db is None:
        return []
    try:
        docs = db.kg_nodes.find({"type": "cuisine", "source": {"$regex": "^generated"}}, {"profile": 1})
        return [kb.CuisineProfile.model_validate(d["profile"]) for d in docs if d.get("profile")]
    except (PyMongoError, ValueError) as e:
        log.warning("couldn't load generated cuisines: %s", e)
        return []


def _start_nodes(diet_type: str, restrictions: tuple[str, ...], allergies: tuple[str, ...]) -> list[str]:
    return (
        [_nid("diet", diet_type)]
        + [_nid("restriction", r) for r in restrictions if r in kb.RESTRICTIONS]
        + [_nid("allergy", a) for a in allergies if a in kb.ALLERGIES]
    )


@lru_cache(maxsize=512)
def _excluded(diet_type: str, restrictions: tuple[str, ...], allergies: tuple[str, ...]) -> frozenset[str] | None:
    db = _database()
    if db is None:
        return None
    try:
        rows = db.kg_edges.aggregate([
            {"$match": {"from": {"$in": _start_nodes(diet_type, restrictions, allergies)}, "rel": {"$in": ["EXCLUDES", "IS"]}}},
            # Walk the tag hierarchy: excluding "animal_product" also excludes meat → red_meat → beef …
            {"$graphLookup": {"from": "kg_edges", "startWith": "$to", "connectFromField": "to", "connectToField": "from",
                              "as": "below", "restrictSearchWithMatch": {"rel": "INCLUDES"}}},
            {"$project": {"tags": {"$concatArrays": [["$to"], "$below.to"]}}},
        ])
        tags = {t.split(":", 1)[1] for row in rows for t in row["tags"]}
        # Free-text allergies ("kiwi") aren't graph nodes; they still count as banned words.
        return frozenset(tags | {a for a in allergies if a not in kb.ALLERGIES})
    except PyMongoError as e:
        log.warning("graph rule lookup failed: %s", e)
        return None


def excluded_tags(diet_type: str, restrictions: list[str], allergies: list[str]) -> set[str] | None:
    found = _excluded(diet_type, tuple(sorted(restrictions)), tuple(sorted(allergies)))
    return set(found) if found is not None else None


excluded_tags.cache_clear = _excluded.cache_clear  # type: ignore[attr-defined]


def allowed_dishes(cuisine_keys: list[str], banned: set[str], limit: int = 40) -> list[kb.Dish] | None:
    """cuisine ─HAS_DISH→ dish ─CONTAINS→ tag, keeping dishes that touch no banned tag."""
    db = _database()
    if db is None or not cuisine_keys:
        return None
    try:
        rows = db.kg_nodes.aggregate([
            {"$match": {"_id": {"$in": [_nid("cuisine", k) for k in cuisine_keys]}}},
            {"$graphLookup": {"from": "kg_edges", "startWith": "$_id", "connectFromField": "to", "connectToField": "from",
                              "as": "path", "maxDepth": 1, "restrictSearchWithMatch": {"rel": {"$in": ["HAS_DISH", "CONTAINS"]}}}},
        ])
        order = {_nid("cuisine", k): i for i, k in enumerate(cuisine_keys)}
        dish_ids, tags_of = [], {}
        for row in sorted(rows, key=lambda r: order.get(r["_id"], 99)):
            for e in row["path"]:
                if e["rel"] == "HAS_DISH":
                    dish_ids.append(e["to"])
                    tags_of.setdefault(e["to"], set())
                else:
                    tags_of.setdefault(e["from"], set()).add(e["to"].split(":", 1)[1])
        ok = [d for d in dish_ids if not (tags_of.get(d, set()) & banned)]
        docs = {d["_id"]: d for d in db.kg_nodes.find({"_id": {"$in": ok}})}
        return [
            kb.Dish(name=docs[d]["name"], portion=docs[d]["portion"], kcal=docs[d]["kcal"], protein_g=docs[d]["protein_g"],
                    contains=sorted(tags_of.get(d, set())))
            for d in ok if d in docs
        ][:limit]
    except PyMongoError as e:
        log.warning("graph dish lookup failed: %s", e)
        return None


def explain(cuisine_key: str, diet_type: str, restrictions: list[str], allergies: list[str]) -> dict:
    """Why each dish of a cuisine is allowed or blocked for these preferences (for the UI and the write-up)."""
    banned = kb.excluded_tags(diet_type, restrictions, allergies)
    p = kb.CUISINES.get(cuisine_key)
    dishes = []
    for d in p.dishes if p else []:
        hit = sorted(banned & set(d.contains))
        dishes.append({"dish": d.name, "allowed": not hit, "blocked_by": hit})
    return {
        "source": "mongodb knowledge graph" if available() else "json knowledge base",
        "excluded_tags": sorted(banned),
        "allowed": sum(x["allowed"] for x in dishes),
        "blocked": sum(not x["allowed"] for x in dishes),
        "dishes": dishes,
    }


def stats() -> dict:
    db = _database()
    if db is None:
        return {"connected": False}
    try:
        nodes = {r["_id"]: r["n"] for r in db.kg_nodes.aggregate([{"$group": {"_id": "$type", "n": {"$sum": 1}}}])}
        edges = {r["_id"]: r["n"] for r in db.kg_edges.aggregate([{"$group": {"_id": "$rel", "n": {"$sum": 1}}}])}
        return {"connected": True, "database": DB_NAME, "nodes": nodes, "edges": edges}
    except PyMongoError as e:
        return {"connected": False, "error": str(e)}
