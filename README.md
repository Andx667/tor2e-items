# Schatzkammer

A database of items for *The One Ring, 2nd Edition*: famous weapons and armour, artefacts and treasure hoards
(collections of items plus generic wealth). The database is one TOML file; a build turns it into a printable PDF
with an overview and cards in poker size (63.5 × 88.9 mm, nine per A4 page).

The items are in [src/cards.toml](src/cards.toml) (German, rules terms in English). The PDF is built by GitHub
Actions on every commit; tagged commits (`v*`) are published as a release.

## Contents of the repository

| Path | Content |
| --- | --- |
| `collection.toml` | Title, language, credit |
| `src/cards.toml` | The database: items and hoards |
| `src/cards/*.toml` | Optional further files, merged into the database |
| `src/rules.toml` | Item types, categories, qualities and the rules for extra effects |
| `tools/check.py` | Checks the database against the rules |
| `tools/build.py` | PDF build |
| `latex/` | Layout |

## Adding an item

Add a table to `src/cards.toml`. The fields are listed at the top of that file.

```toml
[items.narcrist]
name = "Narcrist, das Schwert des Hauptmanns"
type = "weapon"                    # a type from src/rules.toml
proficiency = "swords"             # weapons only: the category in the PDF
base = "Long sword"
craft = "elbische Arbeit"
damage = 5
injury = 16
injury_two_handed = 18
load = 3
text = "Thorondirs eigene Klinge …"
qualities = ["Keen", "Fell"]       # from src/rules.toml, which also holds their rules text
banes = ["Orks"]
effects = [["Besonderheit", "Leuchtet schwach bläulich, wenn Orks nahe sind."]]
```

A hoard names the items it holds and its wealth in *Treasure* points:

```toml
[hoards.kammer-der-wacht]
name = "Die Kammer der Wacht"
items = { narcrist = 1, klinge-der-wacht = 2 }
wealth = 40
```

The stats are the base values. A quality with `modifies` in `src/rules.toml` (*Fell*, *Cunning Make* …) changes
them, and the overview and the cards show the result.

The PDF follows the `[categories]` of `src/rules.toml`: the Combat Proficiencies for weapons, then armour, helms,
shields and useful items (ordered by the skill they bless). Each category starts a new page of cards; one without
items yet gets an empty page.

## The checker

`python3 tools/check.py` prints one line per problem and fails if there is any. The build and the CI run it first.

1. **Schema** (built in): known fields, required fields, whole numbers, the stats each type needs, hoards that
   only hold existing items.
2. **Rules** from `src/rules.toml`: `applies_to`, `excludes` and `requires` per quality, and `[limits.<type>]`
   for the highest number of qualities, banes, blessings and extra effects in total.
3. **Custom rules**: whatever the tables cannot express is a Python function with `@rule` at the end of
   `tools/check.py`.

The rules in `src/rules.toml` are provisional: they only say which quality fits which item type.

## Build

Needs TeX Live or MiKTeX with LuaLaTeX and `latexmk`, and Python 3.11+.

```sh
make            # check, then build/<file_name>.pdf
make check      # only the checker
python3 tools/build.py kammer-der-wacht narcrist    # a selection: ids of items and hoards
```

A hoard in a selection brings its own card and one card per copy of every item it holds, so a selection is the
set of cards to hand out at the table.

The version in the footer comes from the latest git tag `v*`, the date from the last commit:

```sh
git tag v0.1
git push --tags      # the CI also publishes a release with the PDF
```

## Licence

MIT, see [LICENSE](LICENSE).
