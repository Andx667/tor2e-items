#!/usr/bin/env python3
"""Checks the item database against its schema and the rules in src/rules.toml.

    python3 tools/check.py

Three layers:

  1. schema   - fields, types and references of src/cards.toml (built in, see below)
  2. rules    - which extra effects an item may carry, from src/rules.toml:
                applies_to / excludes / requires / craftsmanship per quality,
                [limits.<type>] per item type
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
VALOUR_STATS = (*STATS, "piercing_blow")  # what a `valour_bonus` may name
ITEM_KEYS = {"name", "type", "proficiency", "base", "craft", "craftsmanship", "text", "stats_note", "qualities",
             "banes", "blessings", "effects", "tags", "injury_two_handed", *STATS}
HOARD_KEYS = {"name", "text", "items", "wealth", "wealth_note", "tags"}
EFFECT_LISTS = ("qualities", "banes", "blessings")


def load_toml(*parts):
    with open(os.path.join(ROOT, *parts), "rb") as f:
        return tomllib.load(f)


def load_rules():
    rules = load_toml("src", "rules.toml")
    for key in ("types", "categories", "qualities", "limits"):
        rules.setdefault(key, {})
    rules.setdefault("craftsmanships", [])
    rules.setdefault("skills", [])
    rules.setdefault("bases", {})
    return rules


def quality_effects(quality, item):
    """The parts of a quality that count for this item: the `effects` entries whose `crafts` and
    `bases` name its craftsmanship and base (or name none), or the quality itself if it has no
    `effects`."""
    if "effects" not in quality:
        return [quality]
    return [e for e in quality["effects"]
            if ("crafts" not in e or item.get("craftsmanship") in e["crafts"])
            and ("bases" not in e or item.get("base") in e["bases"])]


def proficiencies_of(quality, rules):
    """The Combat Proficiencies a quality is limited to, or None for any weapon."""
    allowed = None
    if "weapon_group" in quality:
        allowed = set(rules.get("weapon_groups", {}).get(quality["weapon_group"], []))
    if "proficiency" in quality:
        allowed = (allowed & set(quality["proficiency"])) if allowed is not None else set(quality["proficiency"])
    return allowed


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
        if "plain_label" in t and not isinstance(t["plain_label"], str):
            yield f"rules: types.{name}: 'plain_label' must be text"
        for s in t.get("stats", []):
            if s not in STATS:
                yield f"rules: types.{name}: unknown stat '{s}'"
        if "blessings" in t and not is_int(t["blessings"]):
            yield f"rules: types.{name}: 'blessings' must be a whole number"
        banes = t.get("banes", {})
        if not isinstance(banes, dict):
            yield f"rules: types.{name}: banes must be tables: [types.{name}.banes.<craftsmanship>]"
            banes = {}
        for craft, b in banes.items():
            if craft not in rules["craftsmanships"]:
                yield f"rules: types.{name}.banes: unknown craftsmanship '{craft}'"
            if not is_int(b.get("choose")) or b["choose"] < 1:
                yield f"rules: types.{name}.banes.{craft}: 'choose' must be a whole number, 1 or more"
            if not is_strings(b.get("from")) or not b["from"]:
                yield f"rules: types.{name}.banes.{craft}: 'from' must be a list of texts"
    for name, b in rules["bases"].items():
        if b.get("type") not in rules["types"]:
            yield f"rules: bases.{name}: unknown type '{b.get('type')}'"
        for s in (*STATS, "injury_two_handed"):
            if s in b and not is_int(b[s]):
                yield f"rules: bases.{name}: '{s}' must be a whole number"
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
        for c in q.get("craftsmanship", []):
            if c not in rules["craftsmanships"]:
                yield f"rules: qualities.{name}: craftsmanship names the unknown craftsmanship '{c}'"
        if "weapon_group" in q and q["weapon_group"] not in rules.get("weapon_groups", {}):
            yield f"rules: qualities.{name}: unknown weapon_group '{q['weapon_group']}'"
        known = {c["proficiency"] for c in rules["categories"].values() if "proficiency" in c}
        for group, members in rules.get("weapon_groups", {}).items():
            for p in members:
                if p not in known:
                    yield f"rules: weapon_groups.{group}: unknown proficiency '{p}'"
        for p in q.get("proficiency", []):
            if p not in known:
                yield f"rules: qualities.{name}: proficiency names the unknown proficiency '{p}'"
        if not is_strings(q.get("bases", [])):
            yield f"rules: qualities.{name}: bases must be a list of texts"
        effects = q.get("effects", [])
        if not isinstance(effects, list) or not all(isinstance(e, dict) for e in effects):
            yield f"rules: qualities.{name}: effects must be a list of [[qualities.<name>.effects]] tables"
            continue
        if q.get("basic") and q.get("superior"):
            yield f"rules: qualities.{name}: a quality is either basic or superior"
        explained = [(f"qualities.{name}.effects #{n}", e) for n, e in enumerate(effects, 1)] or [(f"qualities.{name}", q)]
        for where, part in explained:
            if not isinstance(part.get("text"), str) or not part["text"].strip():
                yield f"rules: {where}: 'text' is missing (the card explains every quality)"
        for i, part in enumerate([q, *effects]):
            where = f"qualities.{name}" if i == 0 else f"qualities.{name}.effects #{i}"
            for c in part.get("crafts", []):
                if c not in rules["craftsmanships"]:
                    yield f"rules: {where}: crafts names the unknown craftsmanship '{c}'"
            for s in part.get("valour_bonus", []):
                if s not in VALOUR_STATS:
                    yield f"rules: {where}: valour_bonus names the unknown stat '{s}'"
            if "piercing_blow" in part and not is_int(part["piercing_blow"]):
                yield f"rules: {where}: piercing_blow must be a whole number"
            if "protection_roll" in part and not is_int(part["protection_roll"]):
                yield f"rules: {where}: protection_roll must be a whole number"
            if i and not is_strings(part.get("bases", [])):
                yield f"rules: {where}: bases must be a list of texts"
            for field in ("modifies", "sets"):
                table = part.get(field, {})
                if not isinstance(table, dict):
                    yield f"rules: {where}: {field} must be a table: {{ <stat> = <number> }}"
                    continue
                for s, change in table.items():
                    if s not in STATS:
                        yield f"rules: {where}: {field} names the unknown stat '{s}'"
                    if not is_int(change):
                        yield f"rules: {where}: the value of '{s}' in {field} must be a whole number"
    for name in rules["limits"]:
        if name not in rules["types"]:
            yield f"rules: limits.{name}: unknown type"


def check_item(item, rules):
    for key in sorted(set(item) - ITEM_KEYS):
        yield f"unknown field '{key}'"
    for key in ("name", "type"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            yield f"'{key}' is missing"
    for key in ("proficiency", "base", "craft", "craftsmanship", "text", "stats_note"):
        if key in item and not isinstance(item[key], str):
            yield f"'{key}' must be text"
    if isinstance(item.get("craftsmanship"), str) and item["craftsmanship"] not in rules["craftsmanships"]:
        yield f"unknown craftsmanship '{item['craftsmanship']}' (known: {', '.join(rules['craftsmanships'])})"
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
        if any(s in item for s in (*STATS, "injury_two_handed")):  # no stats at all: name and story only
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
        if "craftsmanship" in q and item.get("craftsmanship") not in q["craftsmanship"]:
            yield f"'{name}' needs a 'craftsmanship' of {', '.join(q['craftsmanship'])}"
        allowed = proficiencies_of(q, rules)
        if allowed is not None and item.get("proficiency") not in allowed:
            yield f"'{name}' is only for weapons of: {', '.join(sorted(allowed))}"
        if "bases" in q and item.get("base") not in q["bases"]:
            yield f"'{name}' needs a 'base' of {', '.join(q['bases'])}"
        for other in q.get("excludes", []):
            if other in qualities:
                yield f"'{name}' and '{other}' exclude each other"
        for other in q.get("requires", []):
            if other not in qualities:
                yield f"'{name}' requires '{other}'"
    for skill in effect_list(item, "blessings"):
        if skill not in rules["skills"]:
            yield f"blessings: unknown skill '{skill}' (known: {', '.join(rules['skills'])})"
    limits = rules["limits"].get(kind, {})
    counts = {key: len(effect_list(item, key)) for key in EFFECT_LISTS}
    counts["total"] = counts["qualities"] + counts["blessings"]  # a Bane is free with a superior reward
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


def superior_qualities(item, rules):
    return [q for q in effect_list(item, "qualities") if rules["qualities"].get(q, {}).get("superior")]


@rule
def gear_needs_a_base(key, item, db, rules):
    """Weapons, armour, helms and shields name the Core Rules item they are based on: the card
    shows it as their type (Sword, Axe, Coat of mail, ...)."""
    if rules["types"].get(item.get("type"), {}).get("stats") and not item.get("base"):
        yield f"a {item['type']} needs a 'base' (Sword, Axe, Bow, ...)"


@rule
def stats_follow_the_base(key, item, db, rules):
    """An item with a base from src/rules.toml has the type, the proficiency and the base stats of
    that base (before its qualities change them)."""
    base = rules["bases"].get(item.get("base"))
    if base is None:
        return
    if base["type"] != item.get("type"):
        yield f"'{item['base']}' is a {base['type']} base, not a {item.get('type')}"
        return
    if "proficiency" in base and item.get("proficiency") != base["proficiency"]:
        yield f"a {item['base']} has the proficiency '{base['proficiency']}'"
    if any(s in item for s in (*STATS, "injury_two_handed")):  # name and story only: no stats to compare
        for s in (*STATS, "injury_two_handed"):
            if base.get(s) != item.get(s):
                yield f"a {item['base']} has {s} {base.get(s, 'none')}, this one {item.get(s, 'none')}"


@rule
def banes_follow_the_craftsmanship(key, item, db, rules):
    """The Banes an item may have come from `banes` in src/rules.toml: a type and craftsmanship that
    has them (Elven and Númenórean weapons and shields), the number of kinds of creature to choose and
    the kinds to choose from."""
    banes = effect_list(item, "banes")
    if not banes:
        return
    allowed = rules["types"].get(item.get("type"), {}).get("banes")
    if allowed is None:
        yield f"a {item.get('type')} has no 'banes'"
        return
    craft = item.get("craftsmanship")
    if craft not in allowed:
        yield f"a {item['type']} may only have a Bane with {' or '.join(allowed)} craftsmanship"
        return
    choose = allowed[craft]["choose"]
    if len(banes) != choose:
        yield f"a {craft} {item['type']} has {choose} kind{'s' if choose != 1 else ''} of Bane, this one has {len(banes)}"
    for b in banes:
        if b not in allowed[craft]["from"]:
            yield f"Bane '{b}' is not one of: {', '.join(allowed[craft]['from'])}"


@rule
def blessings_by_type(key, item, db, rules):
    """A type with a `blessings` count in src/rules.toml has exactly that many blessed skills."""
    wanted = rules["types"].get(item.get("type"), {}).get("blessings")
    have = len(effect_list(item, "blessings"))
    if wanted is not None and have != wanted:
        yield f"a {item['type']} blesses {wanted} skill{'s' if wanted != 1 else ''}, this one {have}"


@rule
def bane_needs_a_superior_reward(key, item, db, rules):
    """A Bane comes with a superior reward, so it is only allowed on an item that has one. The
    other way round it is optional."""
    if effect_list(item, "banes") and not superior_qualities(item, rules):
        yield "a Bane is only allowed on an item with a superior quality (Superior Fell, Superior Grievous, ...)"


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
