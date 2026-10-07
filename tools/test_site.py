#!/usr/bin/env python3
"""Checks that the item wizard (site/verify.js) finds exactly the problems tools/check.py finds.

    python3 tools/test_site.py

Takes every item of src/cards.toml and a few hundred broken variants of them, runs the Python checker and the
JavaScript verifier on each, and compares the messages. Needs Node, or the quickjs package (pip install quickjs);
without either the test is skipped (exit 0) unless TEST_SITE_REQUIRED is set. The CI runs it before the site goes up.
"""
import copy
import json
import os
import random
import shutil
import subprocess
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check

ROOT = check.ROOT
VERIFY = os.path.join(ROOT, "site", "verify.js")


def python_problems(item, db, rules):
    found = list(check.check_item(item, rules)) + list(check.check_effects(item, rules))
    for fn in check.RULES:
        found += list(fn("x", item, db, rules))
    return found


def mutations(items, rules, count, rng):
    types = [*rules["types"], "bogus"]
    crafts = [*rules["craftsmanships"], "Elvish", None]
    bases = [*rules["bases"], "Axe", "Dagger", None]
    profs = ["brawling", "swords", "axes", "spears", "bows", "magic", None]
    qualities = [*rules["qualities"], "Nonsense"]
    skills = [*rules["skills"], "Cooking"]
    stats = ["damage", "injury", "injury_two_handed", "protection", "parry", "load"]
    out = []
    for _ in range(count):
        item = copy.deepcopy(rng.choice(items))
        for _ in range(rng.randint(1, 4)):
            op = rng.randrange(13)
            if op == 0:
                item["type"] = rng.choice(types)
            elif op == 1:
                c = rng.choice(crafts)
                item.pop("craftsmanship", None) if c is None else item.update(craftsmanship=c)
            elif op == 2:
                b = rng.choice(bases)
                item.pop("base", None) if b is None else item.update(base=b)
            elif op == 3:
                p = rng.choice(profs)
                item.pop("proficiency", None) if p is None else item.update(proficiency=p)
            elif op == 4:
                item["qualities"] = rng.sample(qualities, rng.randint(0, 4))
            elif op == 5:
                q = rng.choice(qualities)
                item["qualities"] = [*item.get("qualities", []), q, q] if rng.random() < 0.3 else [*item.get("qualities", []), q]
            elif op == 6:
                item["banes"] = rng.sample(["Orks", "Trolle", "Untote", "Wölfe", "Spinnen", "Böse Menschen", "Goblins"], rng.randint(0, 3))
            elif op == 7:
                item["blessings"] = rng.sample(skills, rng.randint(0, 3))
            elif op == 8:
                item.pop(rng.choice(stats), None)
            elif op == 9:
                item[rng.choice(stats)] = rng.randint(-1, 20)
            elif op == 10:
                item[rng.choice(["colour", "weight"])] = 3
            elif op == 11:
                item["effects"] = rng.choice([[["Label", "Text"]], [["Only"]], [["A", "B"], ["C", "D"]]])
            else:
                item["name"] = rng.choice(["", "Something", "  "])
        out.append(item)
    return out


JS_NODE = ("const V=require(process.argv[1]);const d=JSON.parse(require('fs').readFileSync(0,'utf8'));"
           "console.log(JSON.stringify(d.cases.map(c=>({p:V.verify(c,d.rules),t:V.toToml(c,'test-item')}))));")


def run_js(payload):
    """The JavaScript verdicts for the payload, or None if there is no JavaScript runtime."""
    node = shutil.which("node")
    if node:
        r = subprocess.run([node, "-e", JS_NODE, VERIFY], input=payload, capture_output=True, text=True, encoding="utf-8")
        if r.returncode:
            sys.exit("node failed:\n" + r.stderr)
        return json.loads(r.stdout)
    try:
        import quickjs  # pip install quickjs: an embedded JavaScript engine, for machines without Node
    except ImportError:
        return None
    ctx = quickjs.Context()
    with open(VERIFY, encoding="utf-8") as f:
        ctx.eval(f.read())
    return json.loads(ctx.eval("JSON.stringify((function(d){return d.cases.map(function(c){return {p:TorVerify.verify(c,d.rules),t:TorVerify.toToml(c,'test-item')};});})"
                               "(JSON.parse(" + json.dumps(payload) + ")))"))


def main():
    rules = check.load_rules()
    db, _ = check.load_db()
    items = list(db["items"].values())
    rng = random.Random(2)
    cases = items + mutations(items, rules, 600, rng)
    payload = json.dumps({"rules": rules, "cases": cases}, ensure_ascii=False)
    js = run_js(payload)
    if js is None:
        print("skipped: no Node and no quickjs package found")
        return 1 if os.environ.get("TEST_SITE_REQUIRED") else 0
    wrong = 0
    for i, (item, got) in enumerate(zip(cases, js)):
        want = python_problems(item, db, rules)
        if want != got["p"]:
            wrong += 1
            if wrong <= 5:
                print(f"case {i} ({item.get('name')!r}) differs\n  check.py : {want}\n  verify.js: {got['p']}")
        # the TOML the wizard writes must read back as the same item
        try:
            back = tomllib.loads(got["t"])["items"]["test-item"]
        except Exception as e:  # noqa: BLE001
            back = f"does not parse: {e}"
        if back != item:
            wrong += 1
            if wrong <= 5:
                print(f"case {i} ({item.get('name')!r}): the TOML does not read back as the item\n{got['t']}")
    clean = sum(1 for item in cases if not python_problems(item, db, rules))
    print(f"{len(cases)} items ({len(items)} real, {clean} without problems): {wrong} differences in the checks or the TOML")
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
