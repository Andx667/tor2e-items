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
| `src/rules.toml` | Item types, categories, weapon groups, craftsmanships and the qualities from the rule book |
| `tools/check.py` | Checks the database against the rules |
| `tools/build.py` | PDF build |
| `tools/logo.py` | Draws the logo into `assets/` (needs Pillow) |
| `tools/site.py` | Writes `site/data.js` for the item wizard |
| `tools/test_site.py` | Checks that the wizard and the checker agree |
| `site/` | The item wizard (static website, published on GitHub Pages) |
| `latex/` | Layout |

## Adding an item

Add a table to `src/cards.toml`. The fields are listed at the top of that file.

```toml
[items.narcrist]
name = "Narcrist, das Schwert des Hauptmanns"
type = "weapon"                    # a type from src/rules.toml
proficiency = "swords"             # weapons only: the category in the PDF
base = "Long sword"                # the Core Rules item; shown on the card as its type
craft = "elbische Arbeit"          # printed on the card
craftsmanship = "Elven"            # Dwarven, Elven or Númenórean: what the qualities below depend on
damage = 4                         # the base stats of a Long sword
injury = 14
injury_two_handed = 16
load = 3
text = "In Gondolin geschmiedet …" # name and origin only
qualities = ["Superior Fell"]      # from src/rules.toml, which also holds their rules text
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

An item may leave out all its stats and its qualities: the card then shows only the name, the kind line and the
text. Weapons, armour, helms and shields always need a `base`. Partial stats are an error.

The PDF follows the `[categories]` of `src/rules.toml`: the Combat Proficiencies for weapons, then armour, helms,
shields and useful items (ordered by the skill they bless). Each category starts a new page of cards; one without
items yet gets an empty page.

## Stats and qualities

The stats are the base values of the item's `base`, and that is what the cards and the overview show, like the
war gear cards of the game. A quality changes them where the rule book says so (*Fell* +2 Injury, *Superior
Grievous* of Dwarven craftsmanship +2 Damage, *Mithril Armour* sets the Load, …); that bonus is printed small
below the base value on the card and in brackets in the overview, not added to it. A Load never goes below 0.

`src/rules.toml` holds the qualities as the rule book gives them: the basic rewards (*Keen*, *Fell*, *Grievous*,
*Close-fitting*, *Cunning Make*, *Reinforced*), the superior and ancient ones, and the weapon qualities
(*Cleaving*, *Hammering*, *Luminescence*, *Straight Flight*, …). For each quality it says

- which item types, weapon groups (close combat, ranged), Combat Proficiencies or bases may carry it,
- which craftsmanships may carry it, and what it does for each (`effects`),
- the German text printed on the card, and the English rule book text for reference.

Bonuses that become the bearer's Valour rating against a Bane creature are printed as text on the card; they do
not change the stats.

**Famous items.** Everything that is not a basic reward makes an item famous: a superior or ancient reward, any
other special quality (*Luminescence*, *Mithril Armour*, …), a blessing or a free effect. Famous weapons and
armour start their kind line with *Famous Weapon* or *Famous Armour*. Items with only basic rewards (`basic = true`
in `src/rules.toml`), or none, are just well made and get no such label. A *Bane* comes with a superior reward
and is only allowed on an item that has one. It does not count towards the number of rewards.

## Useful items

Special items that are not weapons or armour are either **wondrous items** or **marvellous artefacts**. Wondrous
items are the very important ones, so powerful that they seem like magic to people; every other special item is
a marvellous artefact. A wondrous item blesses two skills (`blessings`), a marvellous artefact one. The skills
are listed in `src/rules.toml`, the count per type is `blessings` there, and the checker enforces both. The
cards of this category are ordered by the first skill they bless.

## Item wizard

`site/` is a small website that walks through the steps of the rule book (item type, craftsmanship, Banes,
qualities, name), checks the new item against the rules, and ends with the TOML table to paste into
`src/cards.toml`. Qualities that do not fit the item are greyed out with the reason, and a live card shows the
result. The workflow `.github/workflows/pages.yml` publishes it on GitHub Pages (once: Settings > Pages >
Source: GitHub Actions); it is then at `https://<user>.github.io/<repository>/`.

To run it locally:

```sh
python3 tools/site.py      # writes site/data.js from src/rules.toml and the existing ids
# then open site/index.html in a browser
```

The page needs no server and no libraries. Its rules come from `src/rules.toml`, so a new quality or base shows
up without touching the page. The checks are `site/verify.js`, a copy of what `tools/check.py` does;
`python3 tools/test_site.py` runs both on every item and on hundreds of broken variants and fails if they
disagree, and the TOML the wizard writes must read back as the same item. It needs Node or `pip install
quickjs`. A new `@rule` in `tools/check.py` has to be added to `site/verify.js` too, which this test notices.

## The checker

`python3 tools/check.py` prints one line per problem and fails if there is any. The build and the CI run it first.

1. **Schema** (built in): known fields, required fields, whole numbers, the stats each type needs (all or none),
   a `base` on weapons, armour, helms and shields, known craftsmanships, hoards that only hold existing items.
   The rules file is checked too, including a German text on every quality.
2. **Rules** from `src/rules.toml`: `applies_to`, `weapon_group`, `proficiency`, `bases`, `craftsmanship`,
   `excludes` and `requires` per quality, and `[limits.<type>]` for the highest number of rewards and blessings
   (a Bane is not counted).
3. **Custom rules**: whatever the tables cannot express is a Python function with `@rule` at the end of
   `tools/check.py`: a Bane only with a superior reward and with the kinds and number of Banes that the
   craftsmanship allows, stats that follow the base, a base on all gear, and the number of blessings of a type.

There are no limits on the number of rewards yet.

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

## Printing

Print at 100 % (actual size), not "fit to page". The dashed line is the cut line: the cell is 63.5 × 88.9 mm
(2.5 × 3.5 in) and the parchment fills it right up to the line, with the gold frame 1.6 mm inside.

## Licence

MIT, see [LICENSE](LICENSE).
