// The random famous item of the item wizard: rolls the dice of an item (type, base, craftsmanship, Banes, qualities,
// skills, name) and keeps only what verify.js allows, so the result follows the rules. It does not touch the page;
// tools/test_site.py runs it on many seeds and has tools/check.py check every item.
(function (root) {
  "use strict";

  // d12 for the type. Only famous items: a useful item is never rolled
  const TYPE_TABLE = ["weapon", "weapon", "weapon", "weapon", "weapon", "weapon", "armour", "armour", "helm", "shield", "artefact", "wonder"];
  // d6 for the craftsmanship of weapons and armour, in the order of rules.craftsmanships; the rest is ordinary
  const CRAFT_TABLE = [0, 0, 1, 1, 2, -1];

  // German nouns for the Core Rules bases, and for the items that are not gear
  const BASE_NOUN = {
    Dagger: "Dolch", Cudgel: "Knüppel", Club: "Keule", "Short sword": "Kurzschwert", Sword: "Schwert", "Long sword": "Langschwert",
    "Short spear": "Kurzspeer", Spear: "Speer", "Great spear": "Langspeer", Axe: "Axt", "Long-hafted axe": "Langstielaxt",
    "Great axe": "Streitaxt", Mattock: "Hacke", Bow: "Bogen", "Great bow": "Langbogen", "Leather shirt": "Lederhemd",
    "Leather corslet": "Lederkoller", "Mail-shirt": "Kettenhemd", "Coat of mail": "Panzerhemd", Helm: "Helm", Buckler: "Faustschild",
    Shield: "Schild", "Great shield": "Großschild",
  };
  const OTHER_NOUN = {
    artefact: ["Ring", "Amulett", "Stein", "Horn", "Phiole", "Fibel", "Stab", "Becher", "Laterne", "Flöte", "Siegel", "Spange"],
    wonder: ["Mantel", "Krone", "Palantír", "Kristall", "Buch", "Banner", "Kelch", "Zepter", "Spiegel", "Harfe", "Schlüssel", "Stundenglas"],
  };
  // where an item comes from and whose it was, by craftsmanship (null: ordinary)
  const PLACES = {
    Dwarven: ["Erebor", "Khazad-dûm", "Nogrod", "Belegost", "Thal"],
    Elven: ["Eregion", "Gondolin", "Lothlórien", "Bruchtal", "Ossiriand", "Lindon"],
    "Númenórean": ["Arnor", "Fornost", "Annúminas", "Minas Tirith", "Dol Amroth", "Númenor"],
    none: ["Bree", "Archet", "Esgaroth", "Edoras", "Dale", "Dunland", "Rhudaur", "Cardolan"],
  };
  const GROUPS = {
    Dwarven: ["Zwerge", "Eisenfäuste", "Langbärte", "Steinhauer", "Durinssöhne"],
    Elven: ["Galadhrim", "Noldor", "Waldelben", "Sindar", "Elbenfürsten"],
    "Númenórean": ["Dúnedain", "Waldläufer", "Könige von Arnor", "Nordmänner", "Hauptmänner"],
    none: ["Beorninger", "Wacht", "Grenzer", "Jäger", "Wanderer", "Bauern", "Händler"],
  };

  function roll(rules, V, rng, isTaken) {
    const log = [];
    // a die with `n` sides; the result is logged with what it meant
    const die = (n) => 1 + Math.floor(rng() * n);
    const pick = (list, what) => {
      const r = die(list.length);
      log.push({ die: "d" + list.length, roll: r, text: what ? what(list[r - 1]) : String(list[r - 1]) });
      return list[r - 1];
    };

    for (let attempt = 0; attempt < 50; attempt++) {
      log.length = 0;
      const item = { name: "?" };
      const table = TYPE_TABLE.filter((t) => rules.types[t]);
      const r = die(table.length);
      const type = table[r - 1];
      const kind = rules.types[type];
      item.type = type;
      log.push({ die: "d" + table.length, roll: r, text: kind.label });
      const gear = !!(kind.stats && kind.stats.length);

      if (gear) {
        const bases = Object.entries(rules.bases).filter(([, b]) => b.type === type);
        if (!bases.length) continue;
        const [name, b] = pick(bases, ([n]) => n);
        item.base = name;
        if (b.proficiency) item.proficiency = b.proficiency;
        for (const k of ["damage", "injury", "injury_two_handed", "protection", "parry", "load"]) if (k in b && (kind.stats.includes(k) || k === "injury_two_handed")) item[k] = b[k];
        const rr = die(6);
        const crafts = rules.craftsmanships;
        const craft = CRAFT_TABLE[rr - 1] >= 0 ? crafts[CRAFT_TABLE[rr - 1]] : undefined;
        log.push({ die: "d6", roll: rr, text: craft || "ordinary make" });
        if (craft) item.craftsmanship = craft;
      }

      const craftKey = item.craftsmanship || "none";
      const places = PLACES[craftKey] || PLACES.none, groups = GROUPS[craftKey] || GROUPS.none;
      const noun = gear ? BASE_NOUN[item.base] || item.base : pick(OTHER_NOUN[type] || ["Ding"]);
      let named = false;
      for (let i = 0; i < 12 && !named; i++) {
        const byPlace = pick(["place", "group"], (x) => (x === "place" ? "named after a place" : "named after its owners")) === "place";
        const where = byPlace ? pick(places) : pick(groups);
        item.name = byPlace ? `${noun} von ${where}` : `${noun} der ${where}`;
        item.text = byPlace ? `In ${where} entstanden.` : `Einst im Besitz der ${where}.`;
        named = !isTaken(item.name);
        if (!named) log.length -= 2;
      }
      if (!named) continue;

      const banes = ((kind.banes || {})[item.craftsmanship]) || null;
      if (banes) {
        const left = [...banes.from];
        item.banes = [];
        for (let i = 0; i < banes.choose; i++) {
          const b = pick(left, (x) => "Bane: " + x);
          item.banes.push(b);
          left.splice(left.indexOf(b), 1);
        }
      }

      if (gear) {
        // 1 to 3 qualities; the first is not a basic reward, so the item is famous
        const count = die(3);
        log.push({ die: "d3", roll: count, text: count + (count > 1 ? " qualities" : " quality") });
        item.qualities = [];
        for (let i = 0; i < count; i++) {
          const fits = (n) => !item.qualities.includes(n) && !V.verify(Object.assign({}, item, { qualities: [...item.qualities, n] }), rules).length;
          let list = Object.keys(rules.qualities).filter(fits);
          if (i === 0) list = list.filter((n) => !rules.qualities[n].basic);
          if (!list.length) break;
          item.qualities.push(pick(list));
        }
        if (!item.qualities.length) continue; // nothing but basic rewards fits this make: roll again
      } else {
        const left = [...rules.skills];
        item.blessings = [];
        for (let i = 0; i < (kind.blessings || 0); i++) {
          const s = pick(left, (x) => "Skill: " + x);
          item.blessings.push(s);
          left.splice(left.indexOf(s), 1);
        }
      }
      if (V.verify(item, rules).length) continue;
      // the order of src/cards.toml
      const out = {};
      for (const k of ["name", "type", "proficiency", "base", "craftsmanship", "damage", "injury", "injury_two_handed", "protection", "parry", "load", "text", "qualities", "banes", "blessings"]) if (k in item) out[k] = item[k];
      return { item: out, log: log.slice() };
    }
    return null;
  }

  const api = { roll };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.TorRoll = api;
})(typeof window !== "undefined" ? window : globalThis);
