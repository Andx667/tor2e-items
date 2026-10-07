#!/usr/bin/env python3
"""Builds the printable PDF of the item database.

    python3 tools/build.py                      # everything: all items, then all hoards
    python3 tools/build.py kammer-der-wacht     # a selection: ids of items and hoards

A hoard in a selection brings its own card and one card per copy of every item it holds.
Without a selection the PDF follows the categories of src/rules.toml; each one starts a new
page of cards, and one without items yet gets an empty page.

Everything collection-specific lives in collection.toml (title, language, credit), src/cards.toml
(items and hoards) and src/rules.toml (types, categories, qualities, rules). Steps:

  1. check the database (tools/check.py); problems stop the build
  2. version and date from git (latest tag v*, commit date)  -> build/version.tex
  3. collection.toml                                          -> build/meta.tex
  4. src/cards.toml -> build/index.tex (overview) and build/cards.tex (nine cards per A4 page)
  5. LuaLaTeX (latexmk) -> build/<file_name>.pdf
  6. copy with the exact version in the name (published by CI)

Needs: LuaLaTeX with latexmk (TeX Live or MiKTeX), Python 3.11+.
Without luaotfload XeLaTeX is used instead (FW_ENGINE=... forces an engine).
"""
import datetime
import os
import re
import shutil
import subprocess
import sys
import tomllib

import check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
PER_PAGE = 9

STRINGS = {
    "english": {"Contents": "Contents", "Version": "Version", "Date": "Date", "Cards": "Cards",
                "Hoards": "Hoards", "Hoard": "Hoard", "Name": "Name", "Kind": "Kind",
                "Stats": "Stats", "Holds": "Holds", "Page": "Page",
                "Selection": "Selection", "NoItems": "No items yet",
                "ModifiersNote": "All stats in the overview and on the cards already include the "
                                 "modifiers of the listed qualities; do not apply them again."},
    "ngerman": {"Contents": "Inhalt", "Version": "Version", "Date": "Stand", "Cards": "Karten",
                "Hoards": "Horte", "Hoard": "Hort", "Name": "Name", "Kind": "Art",
                "Stats": "Werte", "Holds": "Inhalt", "Page": "Seite",
                "Selection": "Auswahl", "NoItems": "Noch keine Gegenstände",
                "ModifiersNote": "Alle Werte in der Übersicht und auf den Karten enthalten bereits die "
                                 "Modifikatoren der aufgeführten Eigenschaften; sie werden nicht noch "
                                 "einmal angerechnet."},
}


def run(cmd, **kw):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True, **kw)


def git(*args):
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else ""
    except FileNotFoundError:
        return ""


def tex_escape(s):
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                 ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}")):
        s = s.replace(a, b)
    return s


def load_config():
    with open(os.path.join(ROOT, "collection.toml"), "rb") as f:
        cfg = tomllib.load(f)
    cfg.setdefault("short_title", cfg["title"])
    cfg.setdefault("subtitle", "")
    cfg.setdefault("author", "")
    cfg.setdefault("license", "")
    cfg.setdefault("language", "english")
    cfg.setdefault("file_name", re.sub(r"[^A-Za-z0-9]+", "-", cfg["title"]).strip("-") + "-TOR2e")
    cfg["language"] = "ngerman" if cfg["language"].lower() in ("german", "ngerman", "de") else "english"
    return cfg


# ------------------------------------------------------------------ 2. version
def version():
    """The version in the PDF is the number of the latest tag: v2.1.1 -> "2.1.1".

    The third value is the exact version for the file name: "v2.1.1" on the tagged commit,
    three commits later "v2.1.1+3-abc1234".
    """
    desc = git("describe", "--tags", "--long", "--match", "v*")
    m = re.match(r"v(.+)-(\d+)-g([0-9a-f]+)$", desc)
    if m:
        ver = m[1]
        slug = "v" + (m[1] if m[2] == "0" else f"{m[1]}+{m[2]}-{m[3]}")
    else:
        commit = git("rev-parse", "--short", "HEAD")
        ver = "0.0"
        slug = "v0.0" + ("-" + commit if commit else "")
    if git("status", "--porcelain", "--untracked-files=no"):
        slug += "-local"
    stand = git("log", "-1", "--format=%cd", "--date=format:%d.%m.%Y") or datetime.date.today().strftime("%d.%m.%Y")
    return ver, stand, slug


# ------------------------------------------------------------------ 3. meta
def write_meta(cfg):
    s = STRINGS[cfg["language"]]
    by = ("by " if cfg["language"] == "english" else "von ") + cfg["author"] if cfg["author"] else ""
    credit = " – ".join(x for x in (by, cfg["license"]) if x)
    lines = [r"\def\advLang{%s}" % cfg["language"],
             r"\def\advTitle{%s}" % tex_escape(cfg["title"]),
             r"\def\advTitleShort{%s}" % tex_escape(cfg["short_title"]),
             r"\def\advSubtitle{%s}" % tex_escape(cfg["subtitle"]),
             r"\def\advAuthor{%s}" % tex_escape(cfg["author"]),
             r"\def\advCredit{%s}" % tex_escape(credit)]
    lines += [r"\def\advStr%s{%s}" % (k, tex_escape(v)) for k, v in s.items()]
    with open(os.path.join(BUILD, "meta.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ------------------------------------------------------------------ 4. overview and cards
def select(db, rules, wanted, s):
    """The cards to print, in order, as groups: (heading, [(table, id), ...]).

    Everything: one group per category, also the empty ones, then the hoards. A selection is a
    single group without a heading, in the order it was asked for.
    """
    if not wanted:
        groups = []
        for cat, c in rules["categories"].items():
            def order(k):
                item = db["items"][k]
                skill = (item.get("blessings") or ["\uffff"])[0] if c.get("sort") == "blessings" else ""
                return skill, item["name"]
            keys = sorted((k for k, item in db["items"].items() if check.category_of(item, rules) == cat), key=order)
            groups.append((c["label"], [("items", k) for k in keys]))
        if db["hoards"]:
            groups.append((s["Hoards"], [("hoards", k) for k in db["hoards"]]))
        return groups
    cards = []
    for key in wanted:
        if key in db["items"]:
            cards.append(("items", key))
        elif key in db["hoards"]:
            cards.append(("hoards", key))
            for item, count in db["hoards"][key].get("items", {}).items():
                cards += [("items", item)] * count
        else:
            sys.exit(f"Unknown id '{key}' - neither an item nor a hoard")
    return [("", cards)]


def kind_line(item, rules):
    """The kind line of a card. A superior reward makes an item famous. One without a superior
    reward (and without blessings or free effects) is not, and gets the type's `plain_label` (if
    it has one) instead of its `label`."""
    kind = rules["types"][item["type"]]
    famous = (any(rules["qualities"][q].get("superior") for q in item.get("qualities", []))
              or item.get("blessings") or item.get("effects"))
    label = kind["plain_label"] if not famous and "plain_label" in kind else kind["label"]
    return " · ".join(x for x in (label, item.get("base"), item.get("craft")) if x)


def quality_text(name, item, rules):
    """What the card says after a quality's name: the texts of the parts that count for the
    item's craftsmanship."""
    effects = check.quality_effects(rules["qualities"][name], item)
    return "; ".join(e["text"] for e in effects if e.get("text"))


def stats_entries(item, rules):
    """The stats as (label, value) pairs, with the `modifies` of the item's qualities applied;
    the injury of a versatile weapon is "18/20"."""
    item = dict(item)
    for q in item.get("qualities", []):
        for effect in check.quality_effects(rules["qualities"][q], item):
            for stat, value in effect.get("sets", {}).items():
                if stat in item:
                    item[stat] = value
            for stat, change in effect.get("modifies", {}).items():
                for key in (stat, "injury_two_handed") if stat == "injury" else (stat,):
                    if key in item:
                        item[key] += change
    if "load" in item:
        item["load"] = max(0, item["load"])
    entries = []
    if "damage" in item:
        entries.append(("Damage", str(item["damage"])))
    if "injury" in item:
        injury = str(item["injury"])
        if "injury_two_handed" in item:
            injury += f"/{item['injury_two_handed']}"
        entries.append(("Injury", injury))
    if "protection" in item:
        entries.append(("Protection", f"{item['protection']}d"))
    if "parry" in item:
        entries.append(("Parry", f"{item['parry']:+d}"))
    if "load" in item:
        entries.append(("Load", str(item["load"])))
    return entries


def stats_line(item, rules):
    return " · ".join(f"{label} {value}" for label, value in stats_entries(item, rules))


def wealth_line(hoard):
    return f"Treasure {hoard['wealth']}" if hoard.get("wealth") else ""


def holds(hoard, db):
    return [f"{count}× {db['items'][key]['name']}" for key, count in hoard.get("items", {}).items()]


def cards_tex(db, rules, groups, s):
    terms = set(db["terms"]) | set(rules["qualities"]) | {t["label"] for t in rules["types"].values()}
    terms = sorted(terms, key=len, reverse=True)
    term_re = re.compile(r"(?<![\w])(" + "|".join(re.escape(t) for t in terms) + r")(?![\w])") if terms else None
    labelled = set()

    def it(text):
        text = tex_escape(text)
        return term_re.sub(lambda m: r"\textit{" + m[1] + "}", text) if term_re else text

    def card(table, key):
        c = db[table][key]
        if table == "items":
            kind, stats, note = kind_line(c, rules), stats_entries(c, rules), c.get("stats_note", "")
            lines = [(q, quality_text(q, c, rules)) for q in c.get("qualities", [])]
            if c.get("banes"):
                lines.append(("Bane", ", ".join(c["banes"])))
            if c.get("blessings"):
                lines.append(("Blessings" if len(c["blessings"]) > 1 else "Blessing", ", ".join(c["blessings"])))
            lines += [tuple(e) for e in c.get("effects", [])]
            bullets = [r"\item \textbf{" + tex_escape(a) + (":} " + it(b) if b else "}") for a, b in lines]
        else:
            kind, stats, note = s["Hoard"], wealth_line(c), c.get("wealth_note", "")
            bullets = [r"\item " + tex_escape(line) for line in holds(c, db)]
        up = []
        if (table, key) not in labelled:  # the overview points at the first copy
            labelled.add((table, key))
            up.append(r"\fwcardanchor{card-%s}{%s}" % (key, tex_escape(c["name"])))
        up += [r"\fwcardname{" + tex_escape(c["name"]) + "}", r"\fwcardkind{" + it(kind) + "}"]
        if stats:
            if table == "items":  # labels like table headers, the values below them
                heads = " & ".join(r"\fwstathead{" + tex_escape(label) + "}" for label, _ in stats)
                values = " & ".join(tex_escape(value) for _, value in stats)
                up.append(r"\fwcardstats{%d}{%s}{%s}{%s}" % (len(stats), heads, values, it(note)))
            else:
                up.append(r"\fwcardline{" + it(stats) + "}{" + it(note) + "}")
        if c.get("text"):
            up.append(r"\fwcardtext{" + it(c["text"]) + "}")
        if bullets:
            up += [r"\begin{fwcardeffects}", *bullets, r"\end{fwcardeffects}"]
        return r"\fwcard{" + "\n".join(up) + "}{" + tex_escape(db["footer"]) + "}"

    # nine cards per page; \fwcard breaks the rows itself (3 x 3). Every group starts a new
    # page, and an empty group still gets one.
    out = []
    for title, cards in groups:
        for i in range(0, max(len(cards), 1), PER_PAGE):
            bookmark = "[%s]" % tex_escape(title or s["Cards"]) if i == 0 else ""
            out.append(r"\fwcardspage%s{%s}{%s}{%%" % (bookmark, tex_escape(title), tex_escape(db["hint"])) + "\n"
                       + "\n".join(card(*c) for c in cards[i:i + PER_PAGE]) + "}")
    return "\n\n".join(out) + "\n"


def index_tex(db, rules, groups, s):
    """The overview on the first pages: one table per group of cards."""
    def table(title, widths, heads, rows):
        if not rows:
            return r"\subsection{%s}" % tex_escape(title) + "\n" + r"\fwnone{%s}" % tex_escape(s["NoItems"]) + "\n"
        cols = "".join("%s{%s}" % wc for wc in zip("BPPR", widths))
        head = " & ".join(r"\fwth{%s}" % tex_escape(h) for h in heads)
        body = "".join(" & ".join(r) + "\\\\\\fwrowrule\n" for r in rows)
        return (r"\subsection{%s}" % tex_escape(title or s["Selection"]) + "\n" + r"\begin{fwtable}{small}" + "\n"
                + r"\begin{longtable}{@{}%s@{}}" % cols + "\n" + head + "\\\\\\fwheadrule\\endhead\n" + body
                + r"\end{longtable}" + "\n" + r"\end{fwtable}" + "\n")

    def link(key, name):
        return r"\hyperref[card-%s]{%s}" % (key, tex_escape(name))

    def page(key):
        return r"\textcolor{fwred}{\pageref*{card-%s}}" % key

    out = []
    for title, cards in groups:
        unique = list(dict.fromkeys(cards))
        keys = [k for table_, k in unique if table_ == "items"]
        if keys or not unique:
            rows = []
            for k in keys:
                c = db["items"][k]
                extras = c.get("qualities", []) + [f"Bane: {b}" for b in c.get("banes", [])] + c.get("blessings", [])
                rows.append([link(k, c["name"]), tex_escape(" · ".join(x for x in (c.get("base"), c.get("craft")) if x)),
                             tex_escape(" · ".join(x for x in (stats_line(c, rules), ", ".join(extras)) if x)), page(k)])
            out.append(table(title, ("0.30", "0.27", "0.36", "0.07"),
                             (s["Name"], s["Kind"], s["Stats"], s["Page"]), rows))
        keys = [k for table_, k in unique if table_ == "hoards"]
        if keys:
            rows = []
            for k in keys:
                c = db["hoards"][k]
                rows.append([link(k, c["name"]), str(c.get("wealth", "")), tex_escape(", ".join(holds(c, db))), page(k)])
            out.append(table(s["Hoards"], ("0.30", "0.14", "0.49", "0.07"),
                             (s["Name"], "Treasure", s["Holds"], s["Page"]), rows))
    return "\n".join(out)


# ------------------------------------------------------------------ flow
def main():
    wanted = sys.argv[1:]
    cfg = load_config()
    s = STRINGS[cfg["language"]]
    rules = check.load_rules()
    db, duplicates = check.load_db()
    problems = check.check(db, rules, duplicates)
    if problems:
        sys.exit("\n".join("error: " + p for p in problems) + "\nThe database has problems - nothing built.")
    groups = select(db, rules, wanted, s)
    count = sum(len(cards) for _, cards in groups)
    if not count:
        sys.exit("The database is empty - nothing to build.")

    os.makedirs(BUILD, exist_ok=True)
    ver, stand, slug = version()
    with open(os.path.join(BUILD, "version.tex"), "w", encoding="utf-8") as f:
        f.write("\\def\\fwversion{%s}\n\\def\\fwstand{%s}\n" % (tex_escape(ver), stand))
    print(f"{cfg['title']} - version {ver} - date {stand} - {count} cards")

    write_meta(cfg)
    with open(os.path.join(BUILD, "index.tex"), "w", encoding="utf-8") as f:
        f.write(index_tex(db, rules, groups, s))
    with open(os.path.join(BUILD, "cards.tex"), "w", encoding="utf-8") as f:
        f.write(cards_tex(db, rules, groups, s))

    env = dict(os.environ)
    env["TEXINPUTS"] = os.path.join(ROOT, "latex") + "//" + os.pathsep + env.get("TEXINPUTS", "")
    tex = ["-interaction=nonstopmode", "-halt-on-error", "-file-line-error"]
    engine = os.environ.get("FW_ENGINE") or (
        "lualatex" if subprocess.run(["kpsewhich", "luaotfload-main.lua"], capture_output=True, text=True).stdout.strip()
        else "xelatex")
    print("TeX engine:", engine)
    job = cfg["file_name"] + ("-" + s["Selection"] if wanted else "")
    if shutil.which("latexmk"):
        run(["latexmk", "-" + engine, "-outdir=build", "-jobname=" + job, *tex, "latex/tor2e.tex"], env=env)
    else:  # without latexmk three runs settle page references and bookmarks
        for _ in range(3):
            run([engine, *tex, "-output-directory=build", "-jobname=" + job, "latex/tor2e.tex"], env=env)
    pdf = os.path.join("build", f"{job}-{slug}.pdf")
    shutil.copyfile(os.path.join(BUILD, job + ".pdf"), os.path.join(ROOT, pdf))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("pdf=" + pdf.replace(os.sep, "/") + "\n")
    print("done:", pdf)


if __name__ == "__main__":
    sys.exit(main())
