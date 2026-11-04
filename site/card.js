// The card image of the item wizard: draws an item the way the PDFs print it (\fwcard in latex/tor2e.sty, the
// card text of tools/build.py) on a canvas at print resolution, to look at and to save as PNG.
// The text comes from site/verify.js (kind line, stats, quality texts), so it is the same as on the cards.
// The spacing is measured on the PDF; the line breaks are the browser's (no hyphenation).
(function (root) {
  "use strict";

  const PT = 25.4 / 72.27;                 // mm per TeX point
  const W = 63.5, H = 88.9;                // poker size: the cut size of a card
  const FRAME = 1.6 + 0.9 * PT;            // the invisible frame of the card, 1.6 mm in, 0.9 pt wide
  const LEFT = FRAME + 2.8, TOP = FRAME + 2.68, BOTTOM = H - FRAME - 1.8;
  const WIDTH = W - 2 * LEFT;
  const C = {
    ink: "#2B2420", strong: "#1D1714", red: "#7A2A1F", grey: "#6F665C",
    parch: "#F7F1E6", parchDark: "#EFE3C6", line: "#D8CBB2",
  };
  // TeX Gyre Pagella, the font of the PDFs (site/fonts, copied there by tools/site.py); Palatino-like
  // fonts stand in when it cannot be loaded (a page opened as a file)
  const FAMILY = '"TorPagella", "TeX Gyre Pagella", "Palatino Linotype", "Book Antiqua", Palatino, Georgia, serif';
  const DPI = 300;

  // ---------------------------------------------------------------- fonts and icons
  let fonts = null;
  function loadFonts(base = "fonts/") {
    if (fonts) return fonts;
    if (typeof FontFace === "undefined" || !document.fonts) return (fonts = Promise.resolve(false));
    const faces = [["regular", "normal", "normal"], ["bold", "normal", "bold"], ["italic", "italic", "normal"]]
      .map(([file, style, weight]) => new FontFace("TorPagella", `url(${base}texgyrepagella-${file}.otf)`, { style, weight }));
    fonts = Promise.all(faces.map((f) => f.load().then((face) => { document.fonts.add(face); return true; }, () => false)))
      .then((ok) => ok.every(Boolean));
    return fonts;
  }

  // the source icons come inline (data URIs in site/data.js), so the canvas can always be saved
  const images = {};
  function icon(uri, onload) {
    if (!uri) return null;
    if (!images[uri]) {
      const img = new Image();
      img.onload = () => onload && onload();
      img.src = uri;
      images[uri] = img;
    }
    const img = images[uri];
    return img.complete && img.naturalWidth ? img : null;
  }

  // ---------------------------------------------------------------- rules terms in italics (as tools/build.py)
  let termCache = null;
  function termRegex(rules, terms) {
    if (termCache && termCache.rules === rules && termCache.terms === terms) return termCache.re;
    const all = new Set([...(terms || []), ...Object.keys(rules.qualities || {}), ...(rules.skills || []),
      ...Object.values(rules.types || {}).map((t) => t.label)]);
    const list = [...all].filter(Boolean).sort((a, b) => b.length - a.length);
    const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const re = list.length ? new RegExp("(?<![\\p{L}\\p{N}_])(" + list.map(esc).join("|") + ")(?![\\p{L}\\p{N}_])", "gu") : null;
    termCache = { rules, terms, re };
    return re;
  }
  // text as runs of one style, the rules terms in italics
  function withTerms(text, st, re) {
    if (!re || st.i) return [{ t: text, st }];
    const out = [];
    let last = 0;
    for (const m of text.matchAll(re)) {
      if (m.index > last) out.push({ t: text.slice(last, m.index), st });
      out.push({ t: m[0], st: Object.assign({}, st, { i: true }) });
      last = m.index + m[0].length;
    }
    if (last < text.length) out.push({ t: text.slice(last), st });
    return out;
  }

  // ---------------------------------------------------------------- text setting
  // a style: { size (pt), b (bold), i (italic), color }
  function setFont(ctx, st, k) { ctx.font = `${st.i ? "italic " : ""}${st.b ? "bold " : ""}${(st.size * PT * k).toFixed(3)}px ${FAMILY}`; }

  // Breaks the runs into lines of at most `width` mm: at spaces and after hyphens, ragged right as \RaggedRight.
  // A line is a list of pieces { t, st, x } with x in mm from the left edge; asc and desc are the ink above
  // and below the baseline (mm).
  function lines(ctx, k, runs, width) {
    const words = []; // { segs: [{t, st}], glue: style of the space after it, or null for a break without space }
    let segs = [];
    const end = (glue) => { if (segs.length) { words.push({ segs, glue }); segs = []; } else if (glue && words.length && !words[words.length - 1].glue) words[words.length - 1].glue = glue; };
    for (const r of runs) {
      for (const part of String(r.t).replace(/\s+/g, " ").split(/( )/)) {
        if (!part) continue;
        if (part === " ") { end(r.st); continue; }
        const bits = part.split(/(?<=-)(?=.)/); // a break is allowed after a hyphen
        bits.forEach((bit, n) => { segs.push({ t: bit, st: r.st }); if (n < bits.length - 1) end(null); });
      }
    }
    end(null);
    const measure = (t, st) => { setFont(ctx, st, k); return ctx.measureText(t).width / k; };
    // a line: its words with the space before each; a space may shrink by 2/5 as in TeX (Pagella: 0.25 em, shrink 0.1 em)
    const rows = [];
    let row = [], natural = 0, shrink = 0, pendingGlue = null;
    for (const w of words) {
      const ww = w.segs.reduce((s, g) => s + measure(g.t, g.st), 0);
      const gap = pendingGlue ? measure(" ", pendingGlue) : 0;
      if (row.length && natural + gap + ww - (shrink + gap * 0.4) > width + 1e-6) {
        rows.push({ row, natural, shrink }); row = []; natural = 0; shrink = 0;
        row.push({ w, gap: 0, ww }); natural = ww;
      } else {
        row.push({ w, gap, ww }); natural += gap + ww; shrink += gap * 0.4;
      }
      pendingGlue = w.glue;
    }
    if (row.length) rows.push({ row, natural, shrink });
    const out = rows.map(({ row, natural, shrink }) => {
      const squeeze = natural > width && shrink ? Math.min(1, (natural - width) / shrink) * 0.4 : 0; // part of each space
      const pieces = [];
      let x = 0;
      for (const { w, gap } of row) {
        x += gap * (1 - squeeze);
        for (const g of w.segs) { pieces.push({ t: g.t, st: g.st, x }); x += measure(g.t, g.st); }
      }
      return pieces;
    });
    return out.map((pieces) => {
      let asc = 0, desc = 0;
      for (const p of pieces) {
        setFont(ctx, p.st, k);
        const m = ctx.measureText(p.t);
        asc = Math.max(asc, (m.actualBoundingBoxAscent || p.st.size * PT * k * 0.7) / k);
        desc = Math.max(desc, (m.actualBoundingBoxDescent || 0) / k);
      }
      return { pieces, asc, desc };
    });
  }

  function drawLine(ctx, k, line, x, y) {
    for (const p of line.pieces) {
      setFont(ctx, p.st, k);
      ctx.fillStyle = p.st.color;
      ctx.fillText(p.t, (x + p.x) * k, y * k);
    }
  }

  // ---------------------------------------------------------------- the card
  // Draws the item on the canvas; returns { overflow } (true if the text does not fit on the card,
  // which stops the PDF build). opts: terms (the rules terms of src/cards.toml), icons ({name: data URI}),
  // onload (called when an icon has loaded, to draw again), dpi
  function draw(canvas, item, rules, V, opts = {}) {
    const dpi = opts.dpi || DPI, k = dpi / 25.4;
    canvas.width = Math.round(W * k);
    canvas.height = Math.round(H * k);
    const ctx = canvas.getContext("2d");
    ctx.textBaseline = "alphabetic";
    ctx.textAlign = "left";
    ctx.fillStyle = C.parch;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const re = termRegex(rules, opts.terms);
    const body = { size: 8, color: C.ink };
    const lead = 10.2 * PT;
    let overflow = false;
    const mark = (y) => { if (y > BOTTOM + 0.3) overflow = true; };

    // name, 12 pt bold, and the kind line under it
    const nameLines = lines(ctx, k, [{ t: item.name || "Unnamed item", st: { size: 12, b: true, color: C.red } }], WIDTH);
    let base = TOP + nameLines[0].asc;
    nameLines.forEach((l, n) => { if (n) base += 13.8 * PT; drawLine(ctx, k, l, LEFT, base); });
    const kind = V.kindLine(item, rules);
    let ruleTop = base + nameLines[nameLines.length - 1].desc + 0.6 + 1.4;
    if (kind) {
      const kindLines = lines(ctx, k, [{ t: kind, st: { size: 8, i: true, color: C.grey } }], WIDTH);
      kindLines.forEach((l) => { base += lead + (l === kindLines[0] ? 0.6 : 0); drawLine(ctx, k, l, LEFT, base); });
      ruleTop = base + kindLines[kindLines.length - 1].desc + 1.4;
    }
    ctx.fillStyle = C.line;
    ctx.fillRect(LEFT * k, ruleTop * k, WIDTH * k, 0.5 * PT * k);
    let top = ruleTop + 0.5 * PT + 1.8; // where the next block starts
    let prev = null;                     // or the baseline of the last line of text above, and its gap

    // the stats box: labels, base values and the bonuses of the qualities, and the stats note
    const stats = V.cardStats(item, rules);
    if (stats.length) {
      const T = top, inner = WIDTH - 4, col = inner / stats.length;
      const bonuses = stats.some((s) => s[2]);
      const note = item.stats_note ? lines(ctx, k, [{ t: `(${item.stats_note})`, st: { size: 7.2, i: true, color: C.grey } }], inner) : [];
      let bottom = bonuses ? T + 13.63 : T + 9.31;
      if (note.length) bottom = T + (bonuses ? 16.3 : 11.98) + (note.length - 1) * 9 * PT + 1.4;
      ctx.fillStyle = C.parchDark;
      roundRect(ctx, LEFT * k, T * k, WIDTH * k, (bottom - T) * k, 1 * k);
      ctx.fill();
      ctx.textAlign = "center";
      stats.forEach(([label, value, bonus], n) => {
        const cx = (LEFT + 2 + col * (n + 0.5)) * k;
        setFont(ctx, { size: 6.2, b: true }, k); ctx.fillStyle = C.grey; ctx.fillText(label, cx, (T + 3.61) * k);
        setFont(ctx, { size: 8.8, b: true }, k); ctx.fillStyle = C.ink; ctx.fillText(value, cx, (T + 7.27) * k);
        if (bonus) { setFont(ctx, { size: 7 }, k); ctx.fillStyle = C.grey; ctx.fillText(bonus, cx, (T + 11.7) * k); }
      });
      ctx.textAlign = "left";
      note.forEach((l, n) => drawLine(ctx, k, l, LEFT + 2, T + (bonuses ? 16.3 : 11.98) + n * 9 * PT));
      top = bottom + 1.88;
      mark(bottom);
    }

    // the first baseline of a block: under the last text (with the gap between), or at the top
    const first = (l, gap) => (prev ? prev.base + lead + gap : top + l.asc);
    const block = (ls, x, gap) => {
      let b = 0;
      ls.forEach((l, n) => { b = n ? b + lead : first(l, gap); drawLine(ctx, k, l, x, b); });
      const last = ls[ls.length - 1];
      prev = { base: b };
      mark(b + last.desc);
    };

    if (item.text) block(lines(ctx, k, withTerms(item.text, body, re), WIDTH), LEFT, 1.8);
    const afterText = !!item.text;

    // the effects as a list: qualities, Banes, the blessing, free effects and the curse
    const items = [];
    for (const q of item.qualities || []) items.push([q, V.qualityText(q, item, rules), true]);
    if ((item.banes || []).length) items.push(["Bane", item.banes.join(", "), true]);
    const blessing = V.blessingLine(item, rules);
    if (blessing) items.push([blessing[0], blessing[1], true]);
    for (const e of item.effects || []) items.push([e[0], e[1], true]);
    if (item.curse) items.push(["Curse", item.curse, false]); // free text: no terms in italics
    const indent = 3.6;
    items.forEach(([label, text, terms], n) => {
      const strong = { size: 8, b: true, color: C.strong };
      const runs = [{ t: label + (text ? ":" : ""), st: strong }];
      if (text) runs.push({ t: " ", st: body }, ...(terms ? withTerms(text, body, re) : [{ t: text, st: body }]));
      const ls = lines(ctx, k, runs, WIDTH - indent);
      const gap = n === 0 ? (afterText ? 1.8 : 0) : 0.9;
      const b = first(ls[0], gap);
      setFont(ctx, body, k); ctx.fillStyle = C.ink; ctx.textAlign = "right";
      ctx.fillText("•", (LEFT + indent - 1.4) * k, b * k);
      ctx.textAlign = "left";
      block(ls, LEFT + indent, gap);
    });

    // the source icon in the lower right corner
    const src = item.source && rules.sources && rules.sources[item.source];
    const img = src && icon((opts.icons || {})[src.icon], opts.onload);
    if (img) {
      const h = 4.4, w = h * img.naturalWidth / img.naturalHeight;
      ctx.globalAlpha = 0.75;
      ctx.drawImage(img, (W - FRAME - 2 - w) * k, (H - FRAME - 1.66 - h) * k, w * k, h * k);
      ctx.globalAlpha = 1;
    }
    return { overflow };
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // ---------------------------------------------------------------- saving
  // The canvas as PNG, with its resolution in the file (a pHYs chunk), so that it prints at card size
  const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let j = 0; j < 8; j++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  function crc32(bytes) { let c = 0xffffffff; for (const b of bytes) c = CRC[(c ^ b) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; }
  function withDpi(buffer, dpi) {
    const src = new Uint8Array(buffer), ppm = Math.round(dpi / 0.0254);
    const chunk = new Uint8Array(21), view = new DataView(chunk.buffer);
    view.setUint32(0, 9);
    chunk.set([0x70, 0x48, 0x59, 0x73], 4); // "pHYs"
    view.setUint32(8, ppm); view.setUint32(12, ppm); chunk[16] = 1; // pixels per metre
    view.setUint32(17, crc32(chunk.subarray(4, 17)));
    const at = 8 + 25; // after the signature and IHDR
    const out = new Uint8Array(src.length + chunk.length);
    out.set(src.subarray(0, at)); out.set(chunk, at); out.set(src.subarray(at), at + chunk.length);
    return out;
  }
  function save(canvas, filename, dpi = DPI) {
    canvas.toBlob((blob) => {
      if (!blob) return;
      blob.arrayBuffer().then((buf) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([withDpi(buf, dpi)], { type: "image/png" }));
        a.download = filename;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      });
    }, "image/png");
  }

  root.TorCard = { draw, save, loadFonts, W, H, DPI };
})(typeof window !== "undefined" ? window : globalThis);
