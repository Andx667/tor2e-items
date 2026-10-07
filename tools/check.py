#!/usr/bin/env python3
"""Checks the item database against its schema and the rules in src/rules.toml.

    python3 tools/check.py

Three layers:

  1. schema   - fields, types and references of src/cards.toml (built in, see below)
  2. rules    - which extra effects an item may carry, from src/rules.toml:
                applies_to / excludes / requires per quality, [limits.<type>] per item type
  3. custom   - anything the tables cannot express: a Python function with @rule (at the end)

Prints one line per problem and exits with 1 if there is any. tools/build.py runs the same
check before it builds.

Needs: Python 3.11+.
"""
import glob
import os
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATS = ("damage", "injury", "protection", "parry", "load")
ITEM_KEYS = {"name", "type", "proficiency", "base", "craft", "text", "stats_note", "qualities", "banes",
             "blessings", "effects", "tags", "injury_two_handed", *STATS}
HOARD_KEYS = {"name", "text", "items", "wealth", "wealth_note", "tags"}
EFFECT_LISTS = ("qualities", "banes", "blessings")


def load_toml(*parts):
    with open(os.path.join(ROOT, *parts), "rb") as f:
        return tomllib.load(f)


def load_rules():
    rules = load_toml("src", "rules.toml")
    for key in ("types", "categories", "qualities", "limits"):
        rules.setdefault(key, {})
    return rules


def load_db():
    """src/cards.toml plus every src/cards/*.toml, merged. Returns the database and the ids
    that exist more than once."""
    files = [os.path.join("src", "cards.toml")]
    files += sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "src", "cards", "*.toml")))
    db = {"items": {}, "hoards": {}, "terms": [], "hint": "", "footer": ""}
    duplicates = []
    for path in files:
        data = load_toml(path)
        for table in ("items", "hoards"):
            for key, value in data.get(table, {}).items():
                if key in db["items"] or key in db["hoards"]:
                    duplicates.append(f"{table}.{key}: id exists more than once ({path})")
                db[table][key] = value
        db["terms"] += data.get("terms", [])
        for key in ("hint", "footer"):
            db[key] = data.get(key, db[key])
    return db, duplicates


def category_of(item, rules):
    """The id of the category an item belongs to: the first one that names its type and, if
    the category asks for one, its proficiency."""
    for key, c in rules["categories"].items():
        if item.get("type") in c.get("types", []) and c.get("proficiency") in (None, item.get("proficiency")):
            return key
    return None


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def is_strings(v):
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


# ------------------------------------------------------------------ 1. schema
def check_rules_file(rules):
    for name, t in rules["types"].items():
        for s in t.get("stats", []):
            if s not in STATS:
                yield f"rules: types.{name}: unknown stat '{s}'"
    for name, c in rules["categories"].items():
        if not isinstance(c.get("label"), str) or not c["label"].strip():
            yield f"rules: categories.{name}: 'label' is missing"
        for t in c.get("types", []):
            if t not in rules["types"]:
                yield f"rules: categories.{name}: types names the unknown type '{t}'"
        if c.get("sort") not in (None, "blessings"):
            yield f"rules: categories.{name}: unknown sort '{c['sort']}' (known: blessings)"
    for name, q in rules["qualities"].items():
        for t in q.get("applies_to", []):
            if t not in rules["types"]:
                yield f"rules: qualities.{name}: applies_to names the unknown type '{t}'"
        for key in ("excludes", "requires"):
            for other in q.get(key, []):
                if other not in rules["qualities"]:
                    yield f"rules: qualities.{name}: {key} names the unknown quality '{other}'"
        modifies = q.get("modifies", {})
        if not isinstance(modifies, dict):
            yield f"rules: qualities.{name}: modifies must be a table: {{ <stat> = <change> }}"
            continue
        for s, change in modifies.items():
            if s not in STATS:
                yield f"rules: qualities.{name}: modifies names the unknown stat '{s}'"
            if not is_int(change):
                yield f"rules: qualities.{name}: the change of '{s}' must be a whole number"
    for name in rules["limits"]:
        if name not in rules["types"]:
            yield f"rules: limits.{name}: unknown type"


def check_item(item, rules):
    for key in sorted(set(item) - ITEM_KEYS):
        yield f"unknown field '{key}'"
    for key in ("name", "type"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            yield f"'{key}' is missing"
    for key in ("proficiency", "base", "craft", "text", "stats_note"):
        if key in item and not isinstance(item[key], str):
            yield f"'{key}' must be text"
    for key in (*EFFECT_LISTS, "tags"):
        if key in item and not is_strings(item[key]):
            yield f"'{key}' must be a list of texts"
    effects = item.get("effects", [])
    if not isinstance(effects, list) or not all(is_strings(e) and len(e) == 2 for e in effects):
        yield "'effects' must be a list of [label, text] pairs"

    kind = rules["types"].get(item.get("type"))
    if isinstance(item.get("type"), str) and kind is None:
        yield f"unknown type '{item['type']}' (known: {', '.join(rules['types'])})"
    if kind is not None:
        wanted = kind.get("stats", [])
        for s in wanted:
            if s not in item:
                yield f"a {item['type']} needs '{s}'"
        for s in STATS:
            if s in item and s not in wanted:
                yield f"a {item['type']} has no '{s}'"
        if "injury_two_handed" in item and "injury" not in wanted:
            yield f"a {item['type']} has no 'injury_two_handed'"
        known = [c["proficiency"] for c in rules["categories"].values()
                 if item["type"] in c.get("types", []) and "proficiency" in c]
        if known and item.get("proficiency") not in known:
            yield f"a {item['type']} needs a 'proficiency' (known: {', '.join(known)})"
        elif not known and "proficiency" in item:
            yield f"a {item['type']} has no 'proficiency'"
        elif category_of(item, rules) is None:
            yield f"a {item['type']} fits no category in src/rules.toml"
    for s in (*STATS, "injury_two_handed"):
        if s in item and not is_int(item[s]):
            yield f"'{s}' must be a whole number"


def check_hoard(hoard, db):
    for key in sorted(set(hoard) - HOARD_KEYS):
        yield f"unknown field '{key}'"
    if not isinstance(hoard.get("name"), str) or not hoard["name"].strip():
        yield "'name' is missing"
    for key in ("text", "wealth_note"):
        if key in hoard and not isinstance(hoard[key], str):
            yield f"'{key}' must be text"
    if "tags" in hoard and not is_strings(hoard["tags"]):
        yield "'tags' must be a list of texts"
    if "wealth" in hoard and (not is_int(hoard["wealth"]) or hoard["wealth"] < 0):
        yield "'wealth' must be a whole number, 0 or more"
    items = hoard.get("items", {})
    if not isinstance(items, dict):
        yield "'items' must be a table: { <item id> = <count> }"
        return
    for key, count in items.items():
        if key not in db["items"]:
            yield f"holds the unknown item '{key}'"
        if not is_int(count) or count < 1:
            yield f"the count of '{key}' must be a whole number, 1 or more"
    if not items and not hoard.get("wealth"):
        yield "holds neither items nor wealth"


# ------------------------------------------------------------------ 2. rules from src/rules.toml
def effect_list(item, key):
    v = item.get(key, [])
    return v if is_strings(v) else []


def check_effects(item, rules):
    kind = item.get("type")
    qualities = effect_list(item, "qualities")
    for key in EFFECT_LISTS:
        values = effect_list(item, key)
        for v in sorted(set(values)):
            if values.count(v) > 1:
                yield f"{key}: '{v}' is listed more than once"
    for name in dict.fromkeys(qualities):
        q = rules["qualities"].get(name)
        if q is None:
            yield f"unknown quality '{name}' (known: {', '.join(rules['qualities'])})"
            continue
        if kind in rules["types"] and kind not in q.get("applies_to", rules["types"]):
            yield f"'{name}' is not allowed on a {kind} (only on: {', '.join(q['applies_to'])})"
        for other in q.get("excludes", []):
            if other in qualities:
                yield f"'{name}' and '{other}' exclude each other"
        for other in q.get("requires", []):
            if other not in qualities:
                yield f"'{name}' requires '{other}'"
    limits = rules["limits"].get(kind, {})
    counts = {key: len(effect_list(item, key)) for key in EFFECT_LISTS}
    counts["total"] = sum(counts.values())
    for key, highest in limits.items():
        if key in counts and counts[key] > highest:
            what = "extra effects in total" if key == "total" else key
            yield f"{counts[key]} {what}, a {kind} may have {highest}"


# ------------------------------------------------------------------ 3. custom rules
# A custom rule gets the id and the table of one item, the whole database and the rules, and
# yields one message per problem:
#
#     @rule
#     def bane_needs_a_quality(key, item, db, rules):
#         if item.get("banes") and not item.get("qualities"):
#             yield "a Bane needs at least one quality"
RULES = []


def rule(fn):
    RULES.append(fn)
    return fn


# ------------------------------------------------------------------ flow
def check(db, rules, duplicates=()):
    """All problems as a list of lines; empty means the database is fine."""
    problems = list(duplicates) + list(check_rules_file(rules))
    for key, item in db["items"].items():
        found = list(check_item(item, rules)) + list(check_effects(item, rules))
        for fn in RULES:
            found += list(fn(key, item, db, rules))
        problems += [f"items.{key}: {p}" for p in found]
    for key, hoard in db["hoards"].items():
        problems += [f"hoards.{key}: {p}" for p in check_hoard(hoard, db)]
    return problems


def main():
    try:
        rules = load_rules()
        db, duplicates = load_db()
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"error: {e}")
    problems = check(db, rules, duplicates)
    for p in problems:
        print("error:", p)
    print(f"{len(db['items'])} items, {len(db['hoards'])} hoards, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
