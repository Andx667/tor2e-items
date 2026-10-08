// The item wizard: five steps of the rule book (type, craftsmanship, Banes, qualities, name) and a check with the
// TOML to add to src/cards.toml. Rules and checks come from src/rules.toml (data.js) and tools/check.py (verify.js).
(function () {
  "use strict";
  const R = window.TOR_DATA.rules;
  const V = window.TorVerify;

  // ---------------------------------------------------------------- texts of the page
  const TYPES = {
    weapon: ["Weapon", "Swords, axes, bows and the like. Can have rewards, and Banes with Elven or Númenórean craftsmanship."],
    armour: ["Armour", "Leather and mail armour."],
    helm: ["Helm", "Headgear."],
    shield: ["Shield", "Shields. With Superior Reinforced an Elven or Númenórean shield can have Banes."],
    artefact: ["Marvellous artefact", "A special item that is not a weapon or armour. Blesses one skill."],
    wonder: ["Wondrous item", "A very important item that seems like magic to people. Blesses two skills."],
  };
  const CRAFTS = {
    Dwarven: ["Dwarven", "Zwergenarbeit", "Dwarves: Superior Grievous and Keen, Flame of Hope, Gleam of Terror, ancient armour."],
    Elven: ["Elven", "elbische Arbeit", "Elves: Superior Fell and Keen, Luminescence, Biting Dart, Foe-slaying; one kind of Bane."],
    "Númenórean": ["Númenórean", "númenórische Arbeit", "Númenor: Superior Fell and Grievous, Foe-slaying, Hollow Steel; two kinds of Bane."],
  };
  const BANE_EN = { Orks: "Orcs", Trolle: "Trolls", "Wölfe": "Wolves", "Böse Menschen": "Evil Men", Untote: "Undead", Spinnen: "Spiders" };
  const GROUPS = { close_combat: "close combat weapons", ranged: "ranged weapons" };
  const STATS = ["damage", "injury", "injury_two_handed", "protection", "parry", "load"];
  const STAT_NAMES = { damage: "Damage", injury: "Injury", injury_two_handed: "Injury (two-handed)", protection: "Protection (d)", parry: "Parry", load: "Load" };
  const STEPS = [
    ["type", "Item type", "Choose item type"],
    ["craft", "Craftsmanship", "Determine craftsmanship"],
    ["banes", "Banes", "Select Banes (Elven or Númenórean weapons only)"],
    ["qualities", "Qualities", "Attribute qualities"],
    ["name", "Name", "Name the item"],
    ["check", "Check & TOML", "Check the item and take its TOML"],
  ];

  // ---------------------------------------------------------------- state
  const fresh = () => ({
    step: 0, reached: 0, type: "", base: "", other: { name: "", proficiency: "swords", damage: "", injury: "", injury_two_handed: "", protection: "", parry: "", load: "" },
    craft: "", craftText: "", craftTouched: false, banes: [], qualities: [], blessings: [], effectLabel: "", effectText: "",
    name: "", id: "", idTouched: false, text: "", tags: "",
  });
  let state = fresh();
  const KEY = "tor-item-wizard-v1";
  try { const saved = JSON.parse(localStorage.getItem(KEY) || "null"); if (saved && saved.other) state = Object.assign(fresh(), saved); } catch (e) { /* no storage */ }
  const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* no storage */ } };

  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const kind = () => R.types[state.type];
  const isGear = () => !!(kind() && kind().stats && kind().stats.length);
  const craftValue = () => (state.craft && state.craft !== "none" ? state.craft : undefined);
  const baneRule = () => (kind() && kind().banes && craftValue() ? kind().banes[craftValue()] || null : null);
  const toInt = (v) => (/^\s*-?\d+\s*$/.test(String(v)) ? parseInt(v, 10) : undefined);

  function baseInfo() {
    if (!state.base) return null;
    if (state.base === "__other") {
      const o = state.other, stats = {};
      for (const k of STATS) { const n = toInt(o[k]); if (n !== undefined) stats[k] = n; }
      return { name: o.name.trim(), proficiency: state.type === "weapon" ? o.proficiency : undefined, stats };
    }
    const b = R.bases[state.base];
    if (!b) return null;
    const stats = {};
    for (const k of STATS) if (k in b) stats[k] = b[k];
    return { name: state.base, proficiency: b.proficiency, stats };
  }

  const slug = (s) => s.toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

  // The item of the state, in the field order of src/cards.toml
  function buildItem() {
    const it = {};
    it.name = state.name.trim();
    if (!state.type) return it;
    it.type = state.type;
    if (isGear()) {
      const b = baseInfo();
      if (b) {
        if (b.proficiency) it.proficiency = b.proficiency;
        if (b.name) it.base = b.name;
      }
    }
    if (state.craftText.trim()) it.craft = state.craftText.trim();
    if (craftValue()) it.craftsmanship = craftValue();
    if (isGear()) { const b = baseInfo(); if (b) for (const k of STATS) if (k in b.stats) it[k] = b.stats[k]; }
    if (state.text.trim()) it.text = state.text.trim();
    if (state.qualities.length) it.qualities = [...state.qualities];
    if (state.banes.length) it.banes = [...state.banes];
    if (state.blessings.length) it.blessings = [...state.blessings];
    if (state.effectLabel.trim() && state.effectText.trim()) it.effects = [[state.effectLabel.trim(), state.effectText.trim()]];
    const tags = state.tags.split(",").map((t) => t.trim()).filter(Boolean);
    if (tags.length) it.tags = tags;
    return it;
  }

  // ---------------------------------------------------------------- what the rules allow
  function availability(name) {
    const q = R.qualities[name];
    const ctx = buildItem();
    if (q.applies_to && !q.applies_to.includes(state.type)) return { ok: false, reason: "Only for " + q.applies_to.map((t) => TYPES[t][0].toLowerCase() + "s").join(", ") };
    if (q.craftsmanship && !q.craftsmanship.includes(ctx.craftsmanship)) return { ok: false, reason: "Needs " + q.craftsmanship.join(" or ") + " craftsmanship" };
    const allowed = V.proficienciesOf(q, R);
    if (allowed && !allowed.has(ctx.proficiency)) return { ok: false, reason: "Only for " + (q.weapon_group && !q.proficiency ? GROUPS[q.weapon_group] : [...allowed].join(", ") + " weapons") };
    if (q.bases && !q.bases.includes(ctx.base)) return { ok: false, reason: "Only for " + q.bases.join(" or ") };
    for (const other of q.excludes || []) if (state.qualities.includes(other)) return { ok: false, reason: "Excludes " + other + " (chosen)" };
    for (const s of state.qualities) if (s !== name && (R.qualities[s].excludes || []).includes(name)) return { ok: false, reason: "Excluded by " + s };
    return { ok: true };
  }
  const isSuperior = (n) => !!R.qualities[n].superior;
  const hasSuperior = () => state.qualities.some(isSuperior);

  // Drop choices that the rules no longer allow after an earlier step changed
  function prune() {
    const wanted = isGear() ? state.qualities : [], kept = [];
    for (const n of wanted) { state.qualities = kept; if (R.qualities[n] && availability(n).ok) kept.push(n); }
    state.qualities = kept;
    const rule = baneRule();
    state.banes = rule ? state.banes.filter((b) => rule.from.includes(b)).slice(0, rule.choose) : [];
    const want = kind() && kind().blessings !== undefined ? kind().blessings : 0;
    state.blessings = state.blessings.slice(0, want);
  }

  // ---------------------------------------------------------------- gates of the steps
  function gate(step) {
    const id = STEPS[step][0];
    if (id === "type") {
      if (!state.type) return "Choose an item type.";
      if (isGear()) {
        if (!state.base) return "Choose the base item.";
        if (state.base === "__other") {
          const o = state.other, b = baseInfo(), want = kind().stats;
          if (!o.name.trim()) return "Name the base item.";
          if (R.bases[o.name.trim()]) return `'${o.name.trim()}' is in the list: choose it there.`;
          for (const k of want) if (b.stats[k] === undefined) return "Enter the whole number for " + STAT_NAMES[k] + ".";
          if (o.injury_two_handed.trim() && toInt(o.injury_two_handed) === undefined) return "Injury (two-handed) must be a whole number.";
        }
      }
    }
    if (id === "craft" && !state.craft) return "Choose a craftsmanship, or none.";
    if (id === "banes") {
      const rule = baneRule();
      if (rule && state.banes.length && state.banes.length !== rule.choose) return `Choose ${rule.choose} kind${rule.choose > 1 ? "s" : ""} of creature, or none at all.`;
    }
    if (id === "qualities") {
      if (!isGear()) {
        const n = kind().blessings || 0;
        if (state.blessings.length !== n) return `Choose ${n} skill${n > 1 ? "s" : ""} to bless.`;
      } else if (state.banes.length && !hasSuperior()) return "A Bane comes with a superior reward: choose one, or remove the Bane in step 3.";
      if ((state.effectLabel.trim() === "") !== (state.effectText.trim() === "")) return "A special effect needs a label and a text.";
    }
    if (id === "name") {
      if (!state.name.trim()) return "Give the item a name.";
      if (!/^[A-Za-z0-9_-]+$/.test(state.id)) return "The id may only have letters, digits, - and _.";
      if (window.TOR_DATA.existing.some((e) => e.id === state.id)) return `The id '${state.id}' exists already: ${window.TOR_DATA.existing.find((e) => e.id === state.id).name}.`;
    }
    return "";
  }
  const banesApply = () => !!baneRule();

  // ---------------------------------------------------------------- screens
  function stepType() {
    let h = `<fieldset><legend class="sr-only">Item type</legend><div class="choices">`;
    for (const t of Object.keys(R.types)) {
      h += `<label class="choice"><input type="radio" name="type" value="${t}"${state.type === t ? " checked" : ""}><span class="t">${TYPES[t][0]}</span><span class="d">${TYPES[t][1]}</span></label>`;
    }
    h += `</div></fieldset>`;
    if (isGear()) {
      const own = Object.entries(R.bases).filter(([, b]) => b.type === state.type);
      const stats = (b) => STATS.filter((k) => k in b).map((k) => `${STAT_NAMES[k].replace(" (d)", "")} ${k === "protection" ? b[k] + "d" : k === "parry" ? "+" + b[k] : b[k]}`)
        .join(" · ").replace(/Injury (\d+) · Injury \(two-handed\) (\d+)/, "Injury $1/$2");
      const baseChoice = ([name, b]) => `<label class="choice"><input type="radio" name="base" value="${esc(name)}"${state.base === name ? " checked" : ""}><span class="t">${esc(name)}</span><span class="d">${esc(stats(b))}</span>${b.note ? `<span class="r">${esc(b.note)}</span>` : ""}</label>`;
      h += `<h3>Base item</h3><p class="rulebook">The Core Rules item the new item is based on. Its stats are the base stats; qualities change them.</p><fieldset><legend class="sr-only">Base item</legend>`;
      if (state.type === "weapon") {
        // weapons by Combat Proficiency, in the order of the categories
        for (const prof of Object.values(R.categories).filter((c) => c.proficiency).map((c) => c.proficiency)) {
          const list = own.filter(([, b]) => b.proficiency === prof);
          if (list.length) h += `<h4 class="prof">${prof[0].toUpperCase() + prof.slice(1)}</h4><div class="choices">${list.map(baseChoice).join("")}</div>`;
        }
        h += `<h4 class="prof">Other</h4><div class="choices">`;
      } else h += `<div class="choices">`;
      h += `<label class="choice"><input type="radio" name="base" value="__other"${state.base === "__other" ? " checked" : ""}><span class="t">Other base…</span><span class="d">Another Core Rules item: enter its stats yourself.</span></label></div></fieldset>`;
      if (state.type !== "weapon") h = h.replace(`<div class="choices"><label class="choice"><input type="radio" name="base" value="__other"`, `<div class="choices">${own.map(baseChoice).join("")}<label class="choice"><input type="radio" name="base" value="__other"`);
      if (state.base === "__other") {
        const o = state.other;
        const num = (k) => `<div class="field"><label for="o-${k}">${STAT_NAMES[k]}</label><input id="o-${k}" data-other="${k}" inputmode="numeric" type="text" value="${esc(o[k])}"></div>`;
        h += `<div class="inline-other"><div class="field"><label for="o-name">Name of the base item</label><input id="o-name" data-other="name" type="text" value="${esc(o.name)}" placeholder="Axe"></div>`;
        if (state.type === "weapon") {
          const profs = Object.values(R.categories).filter((c) => c.proficiency).map((c) => c.proficiency);
          h += `<div class="field"><label for="o-proficiency">Combat Proficiency</label><select id="o-proficiency" data-other="proficiency">${profs.map((p) => `<option${o.proficiency === p ? " selected" : ""}>${p}</option>`).join("")}</select></div>`;
        }
        h += `<div class="grid2">${kind().stats.map(num).join("")}${kind().stats.includes("injury") ? num("injury_two_handed") : ""}</div><p class="help">Whole numbers. Injury (two-handed) only for versatile weapons.</p></div>`;
      }
    }
    return h;
  }

  function stepCraft() {
    let h = `<fieldset><legend class="sr-only">Craftsmanship</legend><div class="choices one">`;
    for (const c of R.craftsmanships) {
      h += `<label class="choice"><input type="radio" name="craft" value="${c}"${state.craft === c ? " checked" : ""}><span class="t">${CRAFTS[c][0]}</span><span class="d">${CRAFTS[c][2]}</span></label>`;
    }
    h += `<label class="choice"><input type="radio" name="craft" value="none"${state.craft === "none" ? " checked" : ""}><span class="t">Ordinary or other</span><span class="d">No special craftsmanship: no superior or ancient qualities, no Banes.</span></label></div></fieldset>`;
    const dflt = CRAFTS[craftValue()] ? CRAFTS[craftValue()][1] : "";
    h += `<div class="field"><label for="craftText">Craft line on the card (German)</label><input id="craftText" type="text" value="${esc(state.craftText)}" placeholder="${esc(dflt || "Arbeit der Dúnedain")}"><span class="help">Printed after the base, for example “Famous Weapon · Long sword · elbische Arbeit”. Optional.</span></div>`;
    return h;
  }

  function stepBanes() {
    const rule = baneRule();
    if (!rule) {
      let why = "Banes are only for weapons and shields of Elven or Númenórean craftsmanship.";
      if (kind() && !(kind().banes)) why = `A ${TYPES[state.type][0].toLowerCase()} cannot have a Bane. Banes are for Elven or Númenórean weapons (and shields with Superior Reinforced).`;
      else if (kind() && !craftValue()) why = "This item has no special craftsmanship. Go back if it should be Elven or Númenórean.";
      else if (kind()) why = `${CRAFTS[craftValue()][0]} ${TYPES[state.type][0].toLowerCase()}s cannot have a Bane.`;
      return `<div class="note">${esc(why)} Nothing to choose here: continue.</div>`;
    }
    let h = `<p class="rulebook">${CRAFTS[craftValue()][0]} ${TYPES[state.type][0].toLowerCase()}s choose <b>${rule.choose}</b> kind${rule.choose > 1 ? "s" : ""} of creature. A Bane is optional, but it needs a superior reward in the next step.</p>`;
    h += `<fieldset><legend>Bane against (${state.banes.length} of ${rule.choose})</legend><div class="skills">`;
    for (const b of rule.from) {
      const on = state.banes.includes(b), full = !on && state.banes.length >= rule.choose;
      h += `<label class="choice"><input type="checkbox" name="bane" value="${esc(b)}"${on ? " checked" : ""}${full ? " disabled" : ""}><span class="t">${esc(b)}</span><span class="d">${esc(BANE_EN[b] || "")}</span></label>`;
    }
    return h + `</div></fieldset>`;
  }

  function qualityCard(name) {
    const q = R.qualities[name], av = availability(name), on = state.qualities.includes(name);
    const item = buildItem();
    // what it does for this item, or for every craftsmanship if it does nothing for this one
    let text = V.qualityText(name, item, R);
    if (!text || !av.ok) text = q.effects ? q.effects.map((e) => (e.crafts ? e.crafts.join("/") + ": " : "") + e.text).join(" · ") : q.text || "";
    const sup = isSuperior(name) ? `<span class="chip">superior</span>` : "";
    return `<label class="choice"><input type="checkbox" name="quality" value="${esc(name)}"${on ? " checked" : ""}${!av.ok && !on ? " disabled" : ""}>`
      + `<span class="t">${esc(name)}${sup}</span><span class="d">${esc(text)}</span>`
      + (av.ok ? "" : `<span class="r">${esc(av.reason)}</span>`) + `</label>`;
  }

  function stepQualities() {
    let h = "";
    if (isGear()) {
      const names = Object.keys(R.qualities);
      const basic = names.filter((n) => R.qualities[n].basic);
      const sup = names.filter(isSuperior);
      const rest = names.filter((n) => !basic.includes(n) && !sup.includes(n));
      const fits = (n) => R.qualities[n].applies_to.includes(state.type);
      const section = (title, list, note) => {
        const shown = list.filter(fits);
        return shown.length ? `<h3>${title}</h3>${note ? `<p class="rulebook">${note}</p>` : ""}<fieldset><legend class="sr-only">${title}</legend><div class="choices">${shown.map(qualityCard).join("")}</div></fieldset>` : "";
      };
      h += `<p class="rulebook">Greyed qualities do not fit this item; the reason is under each. Every quality that is not a basic reward makes the item famous.</p>`;
      if (state.banes.length) h += `<div class="note ${hasSuperior() ? "ok" : "bad"}">Bane: ${esc(state.banes.join(", "))}. ${hasSuperior() ? "A superior reward is chosen." : "Choose a superior reward for it."}</div>`;
      h += section("Basic rewards", basic) + section("Superior rewards", sup, "The stronger rewards of Elven, Dwarven and Númenórean items; a Bane needs one.") + section("Ancient and special qualities", rest);
    } else {
      const n = kind().blessings || 0;
      h += `<p class="rulebook">A ${TYPES[state.type][0].toLowerCase()} blesses <b>${n}</b> skill${n > 1 ? "s" : ""}: a hero using it gets a bonus on rolls of those skills.</p><fieldset><legend>Blessed skills (${state.blessings.length} of ${n})</legend><div class="skills">`;
      for (const s of R.skills) {
        const on = state.blessings.includes(s), full = !on && state.blessings.length >= n;
        h += `<label class="choice"><input type="checkbox" name="skill" value="${s}"${on ? " checked" : ""}${full ? " disabled" : ""}><span class="t">${s}</span></label>`;
      }
      h += `</div></fieldset>`;
    }
    h += `<h3>Special effect <span class="chip plain">optional</span></h3><p class="rulebook">A free effect that is not a rule-book quality, like “Ruf der Wacht”.</p><div class="grid2"><div class="field"><label for="effectLabel">Label</label><input id="effectLabel" type="text" value="${esc(state.effectLabel)}"></div></div><div class="field"><label for="effectText">Text (German)</label><input id="effectText" type="text" value="${esc(state.effectText)}"></div>`;
    return h;
  }

  function stepName() {
    return `<div class="field"><label for="name">Name of the item</label><input id="name" type="text" value="${esc(state.name)}" autocomplete="off" placeholder="Die Klinge der Wacht"><span class="help">As it is printed on the card.</span></div>`
      + `<div class="field"><label for="id">Id</label><input id="id" type="text" value="${esc(state.id)}" autocomplete="off"><span class="help">The key in <code>src/cards.toml</code>: letters, digits and “-”. It must not exist yet.</span></div>`
      + `<div class="field"><label for="text">Lore text (German, optional)</label><textarea id="text">${esc(state.text)}</textarea><span class="help">Only the name or origin of the item, in the past tense, without the names of characters.</span></div>`
      + `<div class="field"><label for="tags">Tags (optional)</label><input id="tags" type="text" value="${esc(state.tags)}" placeholder="finsterwacht, film"><span class="help">Comma separated. Not printed.</span></div>`;
  }

  // ---------------------------------------------------------------- check and TOML
  const toToml = V.toToml;

  function verification() {
    const item = buildItem();
    const groups = V.groups(item, R);
    const idProblems = [];
    if (!/^[A-Za-z0-9_-]+$/.test(state.id)) idProblems.push("the id may only have letters, digits, - and _");
    else if (window.TOR_DATA.existing.some((e) => e.id === state.id)) idProblems.push(`the id '${state.id}' exists already`);
    groups.push({ label: "The id is free and a valid key", problems: idProblems });
    return { item, groups, ok: groups.every((g) => !g.problems.length) };
  }

  function stepCheck() {
    const v = verification();
    let h = `<p class="status ${v.ok ? "ok" : "bad"}" role="status">${v.ok ? "✓ The item follows all the rules." : "✗ The item breaks some rules. Go back and fix them."}</p>`;
    h += `<ul class="report">` + v.groups.map((g) => `<li class="${g.problems.length ? "fail" : "pass"}"><span class="mark" aria-hidden="true">${g.problems.length ? "✗" : "✓"}</span><span>${esc(g.label)}</span>${g.problems.map((p) => `<span class="msg">${esc(p)}</span>`).join("")}</li>`).join("") + `</ul>`;
    const summary = [
      ["Type", TYPES[state.type] ? TYPES[state.type][0] + (v.item.base ? " · " + v.item.base : "") : "–", 0],
      ["Craftsmanship", craftValue() || "none", 1],
      ["Banes", state.banes.join(", ") || "none", 2],
      [isGear() ? "Qualities" : "Skills", (isGear() ? state.qualities : state.blessings).join(", ") || "none", 3],
      ["Name", state.name || "–", 4],
    ];
    h += `<h3>Your choices</h3><dl class="summary">${summary.map(([k, val, s]) => `<dt>${k}</dt><dd>${esc(val)}</dd><dd><button class="link" data-goto="${s}">edit</button></dd>`).join("")}</dl>`;
    if (v.ok) {
      const toml = toToml(v.item, state.id);
      h += `<h3>TOML for <code>src/cards.toml</code></h3><pre class="toml" id="toml" tabindex="0">${esc(toml)}</pre>`
        + `<div class="actions" style="margin-top:.4rem"><div class="right"><button class="btn primary" data-act="copy">Copy TOML</button><button class="btn" data-act="download">Download</button></div></div>`
        + `<p class="help" id="copied" role="status"></p>`
        + `<h3>Add it to the project</h3><ol><li>Paste the table into <code>src/cards.toml</code>, for example under the weapons.</li><li>If the item belongs to a hoard, add it to <code>items</code> of that <code>[hoards.…]</code> table.</li><li>Run <code>python3 tools/check.py</code>: it must report no problems.</li></ol>`;
    }
    return h;
  }

  // ---------------------------------------------------------------- preview
  function preview() {
    const item = buildItem();
    if (!state.type) return `<div class="card"><p class="empty">Choose an item type to see the card.</p></div>`;
    const stats = V.cardStats(item, R);
    let h = `<div class="card"><div class="name">${esc(item.name || "Unnamed item")}</div><div class="kind">${esc(V.kindLine(item, R))}</div>`;
    if (stats.length) h += `<div class="stats">${stats.map(([k, v, b]) => `<div><small>${k}</small><b>${esc(v)}</b>${stats.some((s) => s[2]) ? `<i>${esc(b) || "&nbsp;"}</i>` : ""}</div>`).join("")}</div>`;
    if (item.text) h += `<p>${esc(item.text)}</p>`;
    const li = [];
    for (const q of item.qualities || []) li.push(`<li><b>${esc(q)}:</b> ${esc(V.qualityText(q, item, R))}</li>`);
    if ((item.banes || []).length) li.push(`<li><b>Bane:</b> ${esc(item.banes.join(", "))}</li>`);
    if ((item.blessings || []).length) li.push(`<li><b>Blessing${item.blessings.length > 1 ? "s" : ""}:</b> ${esc(item.blessings.join(", "))}</li>`);
    for (const e of item.effects || []) li.push(`<li><b>${esc(e[0])}:</b> ${esc(e[1])}</li>`);
    if (li.length) h += `<ul>${li.join("")}</ul>`;
    else if (!stats.length && !item.text) h += `<p class="empty">Nothing special yet.</p>`;
    return h + `</div>`;
  }

  // ---------------------------------------------------------------- rendering
  const naSteps = () => ({ 2: state.type && state.craft && !banesApply() });
  function renderSteps() {
    $("#steps").innerHTML = STEPS.map(([id, title], i) => {
      const cls = [i === state.step ? "current" : "", i < state.step ? "done" : "", naSteps()[i] ? "skipped" : ""].join(" ").trim();
      return `<li class="${cls}"><button type="button" data-goto="${i}"${i > state.reached ? " disabled" : ""}${i === state.step ? ' aria-current="step"' : ""}><span class="n">${i + 1}</span>${title}${naSteps()[i] ? " (n/a)" : ""}</button></li>`;
    }).join("");
  }
  function renderStep(focusTitle) {
    const [id, title, rule] = STEPS[state.step];
    const body = { type: stepType, craft: stepCraft, banes: stepBanes, qualities: stepQualities, name: stepName, check: stepCheck }[id]();
    const why = gate(state.step);
    const last = state.step === STEPS.length - 1;
    $("#wizard").innerHTML = `<h2 id="step-title" tabindex="-1">${state.step + 1} · ${title}</h2><p class="rulebook">Rule book: “${rule}”</p>${body}`
      + `<div class="actions"><button class="btn" type="button" data-act="back"${state.step === 0 ? " disabled" : ""}>Back</button><div class="right">`
      + (last ? `<button class="btn" type="button" data-act="reset">Start over</button>` : `<button class="btn primary" type="button" data-act="next"${why ? " disabled" : ""}>Next</button>`)
      + `</div></div>` + (why && !last ? `<p class="why" id="why">${esc(why)}</p>` : `<p class="why" id="why"></p>`);
    if (focusTitle) $("#step-title").focus({ preventScroll: false });
  }
  function renderPreview() { $("#preview").innerHTML = preview(); }
  function render(focusTitle) {
    // keep the focus on the same control when the step is drawn again
    const a = document.activeElement;
    let sel = null;
    if (a && a.closest && a.closest("#wizard")) sel = a.id ? "#" + CSS.escape(a.id) : a.name ? `[name="${a.name}"][value="${CSS.escape(a.value)}"]` : null;
    renderSteps(); renderStep(focusTitle); renderPreview(); save();
    if (sel && !focusTitle) { const el = $(sel); if (el) el.focus(); }
  }
  // after typing: update only what does not hold the focus
  function refreshLight() {
    renderPreview(); renderSteps(); save();
    const why = gate(state.step), next = document.querySelector('[data-act="next"]');
    if (next) next.disabled = !!why;
    const w = $("#why"); if (w) w.textContent = why && state.step < STEPS.length - 1 ? why : "";
  }

  // ---------------------------------------------------------------- navigation
  function go(n) { state.step = Math.max(0, Math.min(STEPS.length - 1, n)); state.reached = Math.max(state.reached, state.step); render(true); window.scrollTo({ top: 0 }); }
  function next() { if (!gate(state.step)) go(state.step + 1); }

  // ---------------------------------------------------------------- events
  const toggle = (list, v, on) => { const i = list.indexOf(v); if (on && i < 0) list.push(v); if (!on && i >= 0) list.splice(i, 1); };
  document.addEventListener("change", (e) => {
    const t = e.target, n = t.name;
    if (!t.closest("#wizard")) return;
    if (n === "type") { state.type = t.value; state.base = ""; state.reached = state.step; prune(); }
    else if (n === "base") { state.base = t.value; prune(); }
    else if (n === "craft") {
      state.craft = t.value;
      const old = CRAFTS[Object.keys(CRAFTS).find((k) => CRAFTS[k][1] === state.craftText)];
      if (!state.craftTouched || old || !state.craftText) { state.craftText = CRAFTS[t.value] ? CRAFTS[t.value][1] : ""; state.craftTouched = false; }
      prune();
    }
    else if (n === "bane") toggle(state.banes, t.value, t.checked);
    else if (n === "quality") { toggle(state.qualities, t.value, t.checked); prune(); }
    else if (n === "skill") toggle(state.blessings, t.value, t.checked);
    else if (t.dataset.other === "proficiency") { state.other.proficiency = t.value; prune(); return refreshLight(); }
    else return;
    render(false);
  });
  document.addEventListener("input", (e) => {
    const t = e.target;
    if (!t.closest("#wizard")) return;
    if (t.dataset.other) { state.other[t.dataset.other] = t.value; return refreshLight(); }
    const f = { craftText: () => { state.craftText = t.value; state.craftTouched = true; }, effectLabel: () => (state.effectLabel = t.value), effectText: () => (state.effectText = t.value),
      name: () => { state.name = t.value; if (!state.idTouched) { state.id = slug(state.name); const idEl = $("#id"); if (idEl) idEl.value = state.id; } },
      id: () => { state.id = t.value; state.idTouched = true; }, text: () => (state.text = t.value), tags: () => (state.tags = t.value) }[t.id];
    if (f) { f(); refreshLight(); }
  });
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-act],[data-goto]");
    if (!b) return;
    if (b.dataset.goto !== undefined) { if (!b.disabled) go(parseInt(b.dataset.goto, 10)); return; }
    const act = b.dataset.act;
    if (act === "next") next();
    else if (act === "back") go(state.step - 1);
    else if (act === "reset") { state = fresh(); render(true); }
    else if (act === "copy" || act === "download") {
      const v = verification(); if (!v.ok) return;
      const toml = toToml(v.item, state.id);
      if (act === "download") {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([toml], { type: "text/plain;charset=utf-8" })); a.download = state.id + ".toml"; a.click(); URL.revokeObjectURL(a.href);
      } else {
        const done = () => { const c = $("#copied"); if (c) c.textContent = "Copied."; };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(toml).then(done, () => selectToml());
        else selectToml();
      }
    }
  });
  function selectToml() { const el = $("#toml"); if (!el) return; const r = document.createRange(); r.selectNodeContents(el); const s = getSelection(); s.removeAllRanges(); s.addRange(r); const c = $("#copied"); if (c) c.textContent = "Press Ctrl+C to copy."; }

  // ---------------------------------------------------------------- start
  $("#generated").textContent = "Rules from " + window.TOR_DATA.generated + ".";
  if (state.step > state.reached) state.reached = state.step;
  prune();
  render(false);
  // for tests: set the state and show a step
  window.__wizard = { reset() { state = fresh(); render(true); }, set(o) { Object.assign(state, o); prune(); render(false); }, go, state: () => state, item: buildItem, verification, toToml };
})();
