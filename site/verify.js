// The checks of tools/check.py for one item, in the browser. The messages are the same as the checker's;
// tools/test_site.py runs both on the same items and compares them. A rule that is only in check.py (a new
// @rule function) has to be added here too, otherwise that test fails.
(function (root) {
  "use strict";

  const STATS = ["damage", "injury", "protection", "parry", "load"];
  const ITEM_KEYS = new Set(["name", "type", "proficiency", "base", "craft", "craftsmanship", "text", "stats_note",
    "qualities", "banes", "blessings", "effects", "tags", "injury_two_handed", ...STATS]);
  const EFFECT_LISTS = ["qualities", "banes", "blessings"];

  const isInt = (v) => Number.isInteger(v);
  const isStrings = (v) => Array.isArray(v) && v.every((x) => typeof x === "string");
  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const effectList = (item, key) => (has(item, key) && isStrings(item[key]) ? item[key] : []);
  const sorted = (a) => [...a].sort();

  function categoryOf(item, rules) {
    for (const [key, c] of Object.entries(rules.categories)) {
      if ((c.types || []).includes(item.type) && (!has(c, "proficiency") || c.proficiency === item.proficiency)) return key;
    }
    return null;
  }

  // The Combat Proficiencies a quality is limited to, or null for any weapon
  function proficienciesOf(q, rules) {
    let allowed = null;
    if (has(q, "weapon_group")) allowed = new Set((rules.weapon_groups || {})[q.weapon_group] || []);
    if (has(q, "proficiency")) {
      const own = new Set(q.proficiency);
      allowed = allowed === null ? own : new Set([...allowed].filter((p) => own.has(p)));
    }
    return allowed;
  }

  // Which parts of a quality count for this item (its craftsmanship and base)
  function qualityEffects(q, item) {
    if (!has(q, "effects")) return [q];
    return q.effects.filter((e) => (!has(e, "crafts") || e.crafts.includes(item.craftsmanship))
      && (!has(e, "bases") || e.bases.includes(item.base)));
  }

  const superiorQualities = (item, rules) =>
    effectList(item, "qualities").filter((q) => rules.qualities[q] && rules.qualities[q].superior);

  // 1. schema
  function checkItem(item, rules) {
    const out = [];
    for (const key of sorted(Object.keys(item).filter((k) => !ITEM_KEYS.has(k)))) out.push(`unknown field '${key}'`);
    for (const key of ["name", "type"]) {
      if (typeof item[key] !== "string" || !item[key].trim()) out.push(`'${key}' is missing`);
    }
    for (const key of ["proficiency", "base", "craft", "craftsmanship", "text", "stats_note"]) {
      if (has(item, key) && typeof item[key] !== "string") out.push(`'${key}' must be text`);
    }
    if (typeof item.craftsmanship === "string" && !rules.craftsmanships.includes(item.craftsmanship)) {
      out.push(`unknown craftsmanship '${item.craftsmanship}' (known: ${rules.craftsmanships.join(", ")})`);
    }
    for (const key of [...EFFECT_LISTS, "tags"]) {
      if (has(item, key) && !isStrings(item[key])) out.push(`'${key}' must be a list of texts`);
    }
    const effects = has(item, "effects") ? item.effects : [];
    if (!Array.isArray(effects) || !effects.every((e) => isStrings(e) && e.length === 2)) {
      out.push("'effects' must be a list of [label, text] pairs");
    }

    const kind = rules.types[item.type];
    if (typeof item.type === "string" && kind === undefined) {
      out.push(`unknown type '${item.type}' (known: ${Object.keys(rules.types).join(", ")})`);
    }
    if (kind !== undefined) {
      const wanted = kind.stats || [];
      if ([...STATS, "injury_two_handed"].some((s) => has(item, s))) {
        for (const s of wanted) if (!has(item, s)) out.push(`a ${item.type} needs '${s}'`);
      }
      for (const s of STATS) if (has(item, s) && !wanted.includes(s)) out.push(`a ${item.type} has no '${s}'`);
      if (has(item, "injury_two_handed") && !wanted.includes("injury")) out.push(`a ${item.type} has no 'injury_two_handed'`);
      const known = Object.values(rules.categories)
        .filter((c) => (c.types || []).includes(item.type) && has(c, "proficiency")).map((c) => c.proficiency);
      if (known.length && !known.includes(item.proficiency)) {
        out.push(`a ${item.type} needs a 'proficiency' (known: ${known.join(", ")})`);
      } else if (!known.length && has(item, "proficiency")) {
        out.push(`a ${item.type} has no 'proficiency'`);
      } else if (categoryOf(item, rules) === null) {
        out.push(`a ${item.type} fits no category in src/rules.toml`);
      }
    }
    for (const s of [...STATS, "injury_two_handed"]) {
      if (has(item, s) && !isInt(item[s])) out.push(`'${s}' must be a whole number`);
    }
    return out;
  }

  // 2. rules from src/rules.toml
  function checkEffects(item, rules) {
    const out = [];
    const kind = item.type;
    const qualities = effectList(item, "qualities");
    for (const key of EFFECT_LISTS) {
      const values = effectList(item, key);
      for (const v of sorted(new Set(values))) {
        if (values.filter((x) => x === v).length > 1) out.push(`${key}: '${v}' is listed more than once`);
      }
    }
    for (const name of new Set(qualities)) {
      const q = rules.qualities[name];
      if (q === undefined) {
        out.push(`unknown quality '${name}' (known: ${Object.keys(rules.qualities).join(", ")})`);
        continue;
      }
      if (has(rules.types, kind) && has(q, "applies_to") && !q.applies_to.includes(kind)) {
        out.push(`'${name}' is not allowed on a ${kind} (only on: ${q.applies_to.join(", ")})`);
      }
      if (has(q, "craftsmanship") && !q.craftsmanship.includes(item.craftsmanship)) {
        out.push(`'${name}' needs a 'craftsmanship' of ${q.craftsmanship.join(", ")}`);
      }
      const allowed = proficienciesOf(q, rules);
      if (allowed !== null && !allowed.has(item.proficiency)) {
        out.push(`'${name}' is only for weapons of: ${sorted(allowed).join(", ")}`);
      }
      if (has(q, "bases") && !q.bases.includes(item.base)) out.push(`'${name}' needs a 'base' of ${q.bases.join(", ")}`);
      for (const other of q.excludes || []) if (qualities.includes(other)) out.push(`'${name}' and '${other}' exclude each other`);
      for (const other of q.requires || []) if (!qualities.includes(other)) out.push(`'${name}' requires '${other}'`);
    }
    for (const skill of effectList(item, "blessings")) {
      if (!rules.skills.includes(skill)) out.push(`blessings: unknown skill '${skill}' (known: ${rules.skills.join(", ")})`);
    }
    const limits = rules.limits[kind] || {};
    const counts = {};
    for (const key of EFFECT_LISTS) counts[key] = effectList(item, key).length;
    counts.total = counts.qualities + counts.blessings; // a Bane is free with a superior reward
    for (const [key, highest] of Object.entries(limits)) {
      if (has(counts, key) && counts[key] > highest) {
        out.push(`${counts[key]} ${key === "total" ? "extra effects in total" : key}, a ${kind} may have ${highest}`);
      }
    }
    return out;
  }

  // 3. custom rules: the @rule functions of check.py, in the same order
  const CUSTOM = [
    function gearNeedsABase(item, rules) {
      const kind = rules.types[item.type];
      if (kind && kind.stats && kind.stats.length && !item.base) return [`a ${item.type} needs a 'base' (Sword, Axe, Bow, ...)`];
      return [];
    },
    function statsFollowTheBase(item, rules) {
      const base = (rules.bases || {})[item.base];
      if (base === undefined) return [];
      if (base.type !== item.type) return [`'${item.base}' is a ${base.type} base, not a ${item.type}`];
      const out = [];
      if (has(base, "proficiency") && item.proficiency !== base.proficiency) out.push(`a ${item.base} has the proficiency '${base.proficiency}'`);
      if ([...STATS, "injury_two_handed"].some((s) => has(item, s))) {
        for (const s of [...STATS, "injury_two_handed"]) {
          if (base[s] !== item[s]) {
            out.push(`a ${item.base} has ${s} ${has(base, s) ? base[s] : "none"}, this one ${has(item, s) ? item[s] : "none"}`);
          }
        }
      }
      return out;
    },
    function banesFollowTheCraftsmanship(item, rules) {
      const banes = effectList(item, "banes");
      if (!banes.length) return [];
      const kind = rules.types[item.type];
      const allowed = kind ? kind.banes : undefined;
      if (allowed === undefined) return [`a ${item.type} has no 'banes'`];
      if (!has(allowed, item.craftsmanship)) return [`a ${item.type} may only have a Bane with ${Object.keys(allowed).join(" or ")} craftsmanship`];
      const rule = allowed[item.craftsmanship];
      const out = [];
      if (banes.length !== rule.choose) {
        out.push(`a ${item.craftsmanship} ${item.type} has ${rule.choose} kind${rule.choose !== 1 ? "s" : ""} of Bane, this one has ${banes.length}`);
      }
      for (const b of banes) if (!rule.from.includes(b)) out.push(`Bane '${b}' is not one of: ${rule.from.join(", ")}`);
      return out;
    },
    function blessingsByType(item, rules) {
      const kind = rules.types[item.type];
      const wanted = kind ? kind.blessings : undefined;
      const have = effectList(item, "blessings").length;
      if (wanted !== undefined && have !== wanted) return [`a ${item.type} blesses ${wanted} skill${wanted !== 1 ? "s" : ""}, this one ${have}`];
      return [];
    },
    function baneNeedsASuperiorReward(item, rules) {
      if (effectList(item, "banes").length && !superiorQualities(item, rules).length) {
        return ["a Bane is only allowed on an item with a superior quality (Superior Fell, Superior Grievous, ...)"];
      }
      return [];
    },
  ];

  const LABELS = {
    gearNeedsABase: "Weapons, armour, helms and shields name their base",
    statsFollowTheBase: "The stats follow the base",
    banesFollowTheCraftsmanship: "Banes: Elven or Númenórean, the right number and kinds",
    blessingsByType: "The number of blessed skills fits the item type",
    baneNeedsASuperiorReward: "A Bane comes with a superior reward",
  };

  // The checks one by one, in the order of check.py: [{label, problems}]
  function groups(item, rules) {
    return [
      { label: "Fields, type, stats and proficiency", problems: checkItem(item, rules) },
      { label: "Qualities fit the type, craftsmanship, base and each other; skills exist", problems: checkEffects(item, rules) },
      ...CUSTOM.map((fn) => ({ label: LABELS[fn.name] || fn.name, problems: fn(item, rules) })),
    ];
  }

  // All problems of one item, in the order of check.py
  function verify(item, rules) {
    return groups(item, rules).flatMap((g) => g.problems);
  }

  // The stats of the card: the base stats with the `sets` and `modifies` of the qualities applied (as tools/build.py)
  function cardStats(item, rules) {
    const it = JSON.parse(JSON.stringify(item));
    for (const q of effectList(item, "qualities")) {
      if (!rules.qualities[q]) continue;
      for (const e of qualityEffects(rules.qualities[q], item)) {
        for (const [stat, value] of Object.entries(e.sets || {})) if (has(it, stat)) it[stat] = value;
        for (const [stat, change] of Object.entries(e.modifies || {})) {
          for (const key of stat === "injury" ? ["injury", "injury_two_handed"] : [stat]) if (has(it, key)) it[key] += change;
        }
      }
    }
    if (has(it, "load")) it.load = Math.max(0, it.load);
    const out = [];
    if (has(it, "damage")) out.push(["Damage", String(it.damage)]);
    if (has(it, "injury")) out.push(["Injury", String(it.injury) + (has(it, "injury_two_handed") ? `/${it.injury_two_handed}` : "")]);
    if (has(it, "protection")) out.push(["Protection", `${it.protection}d`]);
    if (has(it, "parry")) out.push(["Parry", (it.parry >= 0 ? "+" : "") + it.parry]);
    if (has(it, "load")) out.push(["Load", String(it.load)]);
    return out;
  }

  // What the card says after a quality's name, for this item
  function qualityText(name, item, rules) {
    if (!rules.qualities[name]) return "";
    return qualityEffects(rules.qualities[name], item).filter((e) => e.text).map((e) => e.text).join("; ");
  }

  // The kind line of the card: a superior reward (or a blessing or free effect) makes an item famous
  function kindLine(item, rules) {
    const kind = rules.types[item.type];
    if (!kind) return "";
    const famous = superiorQualities(item, rules).length || effectList(item, "blessings").length || (item.effects || []).length;
    const label = !famous && has(kind, "plain_label") ? kind.plain_label : kind.label;
    return [label, item.base, item.craft].filter(Boolean).join(" · ");
  }

  // The TOML table of an item for src/cards.toml, in the field order of that file
  const tomlStr = (v) => '"' + String(v).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "").replace(/\t/g, "\\t")
    .replace(/[\u0000-\u001f\u007f]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0")) + '"';
  const tomlList = (a) => "[" + a.map(tomlStr).join(", ") + "]";
  function toToml(item, id) {
    const lines = [`[items.${/^[A-Za-z0-9_-]+$/.test(id) ? id : tomlStr(id)}]`];
    for (const [k, v] of Object.entries(item)) {
      if (typeof v === "number") lines.push(`${k} = ${v}`);
      else if (typeof v === "string") lines.push(`${k} = ${tomlStr(v)}`);
      else if (k === "effects") lines.push("effects = [", ...v.map((e) => `  ${tomlList(e)},`), "]");
      else lines.push(`${k} = ${tomlList(v)}`);
    }
    return lines.join("\n") + "\n";
  }

  const api = { toToml, verify, groups, checkItem, checkEffects, cardStats, qualityText, qualityEffects, kindLine, proficienciesOf, superiorQualities, effectList };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.TorVerify = api;
})(typeof window !== "undefined" ? window : globalThis);
