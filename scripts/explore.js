// Pennsylvania Eats web app: the iPhone app's guides, search, filters, map and place details, in the browser.
// The same data as the app, split by scripts/make-site.py into a small index, the guides' places statewide, and one core + one
// detail file per region: the region picker loads a region; "All of Pennsylvania" loads them all.
// No cookies, no trackers, no third-party scripts or map tiles; saved places live in this browser's localStorage only.
// Ported from PennsylvaniaEats/Models/{Guide,Search,Place,AppModel}.swift and Views/PlaceDetailView.swift: keep them in step.
(() => {
  "use strict";
  const BASE = document.documentElement.dataset.base || "";
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k, d) { try { const v = localStorage.getItem("pae-" + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem("pae-" + k, JSON.stringify(v)); } catch { /* private mode */ } },
  };
  // lookups keyed by what people type or what a URL says have no prototype, so "constructor" or "__proto__" is just a word
  const dict = (...objs) => Object.assign(Object.create(null), ...objs);
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const niceDate = (iso) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || ""); return m ? `${MONTHS[+m[2] - 1]} ${+m[3]}, ${m[1]}` : String(iso || ""); };
  const fmt = (n) => Number(n).toLocaleString("en-US");

  // ---------------------------------------------------------------- search (a port of PennsylvaniaEats/Models/Search.swift)
  const typeSyn = dict({ avenue: "ave", av: "ave", street: "st", boulevard: "blvd", road: "rd", drive: "dr", place: "pl", court: "ct",
    parkway: "pkwy", highway: "hwy", lane: "ln", trail: "trl", circle: "cir", terrace: "ter", turnpike: "tpke", route: "rt", rte: "rt" });
  const syn = dict(typeSyn, { north: "n", south: "s", east: "e", west: "w", saint: "st", mount: "mt" });
  const abbrs = new Set(Object.values(syn)), typeAbbrs = new Set(Object.values(typeSyn));
  // a route number: "PA-30", "US 22", "SR 309", "Rte 611" and "route 611" all read "rt <number>"
  const ROUTE_WORDS = new Set(["pa", "us", "sr", "rte", "route", "rt"]);
  const routes = (words) => words.map((w, i) => (ROUTE_WORDS.has(w) && /^\d+[a-z]?$/.test(words[i + 1] || "") ? "rt" : w));   // 9W, 25A, 17M
  let T = {};   // tag bits, from the data's "tags" order
  // Search.tagPhrases: the first phrase found wins. A dish with a kind of its own matches that kind, not the whole tag: "roast pork"
  // lists the roast pork counters, not every steak shop on the Cheesesteaks guide.
  const TAG_PHRASES = [["cheesesteaks", "steak", ["cheesesteak"]], ["cheesesteak", "steak", ["cheesesteak"]], ["cheese steaks", "steak", ["cheesesteak"]],
    ["cheese steak", "steak", ["cheesesteak"]], ["roast pork", "steak", ["roast pork"]], ["hoagies", "steak", ["hoagie"]], ["hoagie", "steak", ["hoagie"]],
    ["tomato pie", "pie", ["tomato pie"]], ["old forge", "pie", ["old forge"]], ["pierogies", "pierogi"], ["pierogi", "pierogi"], ["perogies", "pierogi"],
    ["pennsylvania dutch", "dutch"], ["pa dutch", "dutch"], ["smorgasbord", "dutch"], ["soft pretzels", "pretzel"], ["soft pretzel", "pretzel"],
    ["pretzels", "pretzel"], ["pretzel", "pretzel"], ["diners", "diner"], ["diner", "diner"]];
  const STOP = new Set(["the", "and", "of", "a", "in", "near"]);
  function normalize(s) {
    let t = String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    t = t.replace(/\b([a-z0-9])\s*&\s*([a-z0-9])\b/g, "$1$2").replace(/&/g, " and ").replace(/['’`]/g, "");
    return t.replace(/[^\p{L}\p{N}]+/gu, " ").trim();
  }
  const normAddr = (s) => routes(normalize(s).split(" ")).map((w) => syn[w] || w).join(" ");
  // towns (the mailing towns) statewide from the index; mailing names and municipalities (Millvale, Bensalem) from the regions
  // loaded. Each list longest first; a town is tried before a neighborhood (Search.parse).
  let TOWN_KEYS = [], VILLAGE_KEYS = [], TOWN_REGION = dict();

  function parse(text) {
    const q = { tokens: [], town: null, village: null, placePhrase: null, tag: 0, kind: 0, narrow: false, tagPhrase: null, unsearchable: false };
    const raw = normalize(text).split(" ").filter(Boolean);
    q.unsearchable = !raw.length && String(text || "").trim() !== "";   // "🍕", "!!!": nothing to look for
    for (let i = 0; i + 1 < raw.length;) { if (raw[i] === "near" && raw[i + 1] === "me") raw.splice(i, 2); else i++; }   // "near me" asks for nothing
    if (!raw.length) return q;
    const mapped = routes(raw).map((w) => syn[w] || w);
    const find = (phrase) => {
      const p = phrase.split(" ");
      for (let i = 0; i + p.length <= mapped.length; i++) if (p.every((w, k) => mapped[i + k] === w)) return [i, i + p.length];
      return null;
    };
    const cut = ([a, b]) => { const words = raw.slice(a, b).join(" "); raw.splice(a, b - a); mapped.splice(a, b - a); return words; };
    for (const [phrase, tag, ks] of TAG_PHRASES) {
      const r = find(normalize(phrase));
      if (r) { q.tag = T[tag]; q.kind = ks ? kinds(...ks) : 0; q.narrow = ks === false; q.tagPhrase = cut(r); break; }
    }
    // the longest town named in the query wins, then the longest neighborhood, unless a street type follows ("lancaster ave" is a street)
    const place = (keys) => {
      for (const [key, name] of keys) {
        const r = find(key);
        if (r && !(r[1] < mapped.length && typeAbbrs.has(mapped[r[1]]))) return [name, cut(r)];
      }
      return null;
    };
    const t = place(TOWN_KEYS);
    if (t) { q.town = t[0]; q.placePhrase = t[1]; }
    else { const v = place(VILLAGE_KEYS); if (v) { q.village = v[0]; q.placePhrase = v[1]; } }
    // stop words go once a town, neighborhood or tag is set, or when any other word is left ("pierogies in millvale")
    let idx = raw.map((_, i) => i);
    if (q.town || q.village || q.tag || idx.some((i) => !STOP.has(mapped[i]))) idx = idx.filter((i) => !STOP.has(mapped[i]));
    const routed = routes(raw);
    idx.forEach((i, n) => {
      const token = raw[i], isLast = n === idx.length - 1;
      if (routed[i] === "rt" && ROUTE_WORDS.has(token) && token !== "rt") { q.tokens.push([" rt "]); return; }   // "US 9W" = "Route 9W"
      if (mapped[i] !== token) { q.tokens.push([` ${mapped[i]} `, ` ${token}`]); return; }
      const whole = (abbrs.has(token) && (!isLast || token.length > 1)) || (token.length <= 2 && !isLast);
      const needles = [" " + token + (whole ? " " : "")];
      // what people call a place ("katzs", "lucalis") may be a possessive the name doesn't have
      if (token.length >= 4 && token.endsWith("s") && !whole) needles.push(" " + token.slice(0, -1));
      if (isLast && token.length >= 3) for (const [word, abbr] of Object.entries(typeSyn)) if (word !== token && word.startsWith(token)) needles.push(` ${abbr} `);
      q.tokens.push(needles);
    });
    // "bleecker st": a finished street type sticks to the word before it
    if (q.tokens.length >= 2 && idx.length >= 2 && typeAbbrs.has(mapped[idx[idx.length - 1]])) {
      const last = idx[idx.length - 1], prev = idx[idx.length - 2];
      q.tokens.splice(-2, 2, [` ${mapped[prev]} ${mapped[last]} `, ` ${raw[prev]} ${raw[last]}`]);
    }
    return q;
  }
  const qEmpty = (q) => !q.tokens.length && !q.town && !q.village && !q.tag;
  function matches(p, q) {
    if (q.tag && !(q.kind ? p.k & q.kind : p.g & q.tag)) {
      const stem = normalize(q.tagPhrase || "").replace(/s$/, "");
      if (!stem || !p.nameText.includes(" " + stem)) return false;
    }
    if (q.town && p.c !== q.town && !p.nameText.includes(" " + normalize(q.placePhrase || ""))) return false;
    if (q.village && p.hd !== q.village && p.pl !== q.village && !p.nameText.includes(" " + normalize(q.placePhrase || ""))) return false;
    return q.tokens.every((needles) => needles.some((n) => p.search.includes(n)));
  }
  // name matches first ("erie" puts Erie Brewing ahead of everything else in Erie)
  const nameMatches = (p, q) => q.tokens.length && q.tokens.every((needles) => needles.some((n) => p.nameText.includes(n)));

  // Place.searchText: name, town, mailing name, municipality, zip, cuisine, brand, dishes, then the address with
  // street words abbreviated. Built on the first search, or bit by bit when the browser is idle.
  function indexPlace(p) {
    if (p.search) return;
    p.search = " " + normalize([p.n, p.c, p.pl, p.hd, p.mu, p.z, p.cu, p.brand, p.dish].filter(Boolean).join(" ")) + " " + normAddr(p.a || "") + " ";
    p.nameText = " " + normalize([p.n, p.brand].filter(Boolean).join(" ")) + " ";
  }
  let toIndex = [];
  function ensureIndex() { for (const p of toIndex) indexPlace(p); toIndex = []; }
  function indexWhenIdle() {
    const idle = window.requestIdleCallback || ((f) => setTimeout(f, 50));
    const step = () => {
      const batch = toIndex.splice(0, 2000);
      batch.forEach(indexPlace);
      if (toIndex.length) idle(step);
    };
    idle(step);
  }

  // ---------------------------------------------------------------- guides (PennsylvaniaEats/Models/Guide.swift)
  // The classics list only hand-checked places (hc 1: our research checked it open), by the research's kind bits: a listing
  // merely named "… Steaks" isn't enough. hc 2 marks a MICHELIN or James Beard honoree we haven't open-checked.
  let K = {};
  const CLASSIC_SORTS = ["featured", "nearest", "oldest", "name"];
  const RANKING = new Set(["iconic", "oldest"]);   // the sorts that rank; only these show rank numbers
  const kinds = (...ks) => ks.reduce((m, k) => m | (K[k] || 0), 0);
  const GUIDES = {
    steak: { title: "Cheesesteaks, Roast Pork & Hoagies", sub: "Philadelphia's steak shops, roast pork and hoagie counters, hand-checked", inc: (p) => p.hc === 1 && p.k & kinds("cheesesteak", "roast pork", "hoagie"), sorts: CLASSIC_SORTS, classic: true },
    pie: { title: "Tomato Pie & Old Forge Pizza", sub: "Square tomato pie and Old Forge-style trays, hand-checked", inc: (p) => p.hc === 1 && p.k & kinds("tomato pie", "old forge"), sorts: CLASSIC_SORTS, classic: true },
    pierogi: { title: "Pierogies & Pittsburgh Classics", sub: "Pierogi kitchens and Pittsburgh's sandwich classics, hand-checked", inc: (p) => p.hc === 1 && p.k & kinds("pierogi", "pittsburgh sandwich"), sorts: CLASSIC_SORTS, classic: true },
    dutch: { title: "Pennsylvania Dutch", sub: "Family-style dining rooms and smorgasbords, hand-checked", inc: (p) => p.hc === 1 && p.k & kinds("pa dutch"), sorts: CLASSIC_SORTS, classic: true },
    pretzel: { title: "Soft Pretzel Bakeries", sub: "Hand-twisted soft pretzels, hand-checked", inc: (p) => p.hc === 1 && p.k & kinds("pretzel"), sorts: CLASSIC_SORTS, classic: true },
    diner: { title: "Diners", sub: "Counters, booths and breakfast all day, hand-checked", inc: (p) => p.hc === 1 && p.k & kinds("diner"), sorts: CLASSIC_SORTS, classic: true },
    icons: { title: "Pennsylvania Icons", sub: "MICHELIN, James Beard honorees and institutions", note: "Points come from honors and years at the address; not a rating.", inc: (p) => p.ip != null, sorts: ["iconic", "oldest", "nearest"], ranked: true, guideData: true },
    oldest: { title: "Oldest Places", sub: "Years at the same address, oldest first", inc: (p) => p.f != null && p.hc === 1, sorts: ["oldest"], ranked: true, guideData: true },
    near: { title: "Near Me", sub: "Everything around you, closest first", inc: () => true, sorts: ["nearest"], needsHere: true, directory: true },
    all: { title: "All Restaurants", sub: "Restaurants, cafés, bars and bakeries", inc: () => true, sorts: ["name", "nearest"], directory: true },
    saved: { title: "Saved", sub: "Places you saved in this browser", inc: (p) => p.id != null && saved.has(p.id), sorts: ["name", "nearest"] },
  };
  const isGuide = (g) => typeof g === "string" && Object.hasOwn(GUIDES, g);
  const SORT_LABEL = { featured: "Featured first", nearest: "Nearest", oldest: "Oldest first", name: "A to Z", iconic: "Most iconic" };

  // ---------------------------------------------------------------- state
  let IX = null, REGIONS = [], SLUGS = [], COUNTIES = [], CAL = {}, SOURCES = [], RT = {}, HAS_ACHD = false;
  // a place is keyed by region and row ("0:1234") from the start; its stable id (saved places, #p= links) comes with the region's
  // detail file, which also holds the panel's facts: the ids are a quarter of the data, so the list doesn't wait for them
  const P = [], byKey = new Map(), byId = new Map();
  const loaded = new Set(), loading = new Map(), details = new Map();
  let here = null, locDenied = false, shown = 100, current = [], view = "list";
  // nickstrom5.github.io is shared by every Eats Ranked site, so a stored value can be anything: keep only what has the right shape
  const saved = new Set([].concat(store.get("saved", [])).filter((x) => typeof x === "string"));
  const savedRegion = dict(Object.fromEntries(Object.entries(Object(store.get("savedr", {}))).filter(([k, v]) => saved.has(k) && typeof v === "string")));
  const st = { g: "steak", r: "philadelphia", q: "", sort: "", town: "", cuisine: "", chains: false, conf: false, bib: false, p: "" };
  const NY_BOX = { s: 39.71, n: 42.27, w: -80.53, e: -74.68 };   // Pennsylvania's box (the name is the family's)
  const regionIdx = (slug) => SLUGS.indexOf(slug);
  const regionName = (slug) => (slug === "all" ? "Pennsylvania" : REGIONS[regionIdx(slug)] || "");

  const miles = (a, b) => {
    const r = Math.PI / 180, dLa = (b.la - a.la) * r, dLo = (b.lo - a.lo) * r;
    const h = Math.sin(dLa / 2) ** 2 + Math.cos(a.la * r) * Math.cos(b.la * r) * Math.sin(dLo / 2) ** 2;
    return 3958.8 * 2 * Math.asin(Math.sqrt(h));
  };
  const milesText = (m) => (m < 10 ? m.toFixed(1) : Math.round(m)) + " mi";

  // which county (and so which region) a point is in: ray casting over the Census county outlines
  function countyAt(pt) {
    if (!SHAPES || !pt) return null;
    for (const c of SHAPES.counties || []) {
      let inside = false;
      for (const ring of c.c) {
        for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
          const [xi, yi] = ring[i], [xj, yj] = ring[j];
          if ((yi > pt.la) !== (yj > pt.la) && pt.lo < ((xj - xi) * (pt.la - yi)) / (yj - yi) + xi) inside = !inside;
        }
      }
      if (inside) return c;
    }
    return null;
  }
  const inNY = (pt) => pt && pt.la >= NY_BOX.s && pt.la <= NY_BOX.n && pt.lo >= NY_BOX.w && pt.lo <= NY_BOX.e && (!SHAPES || countyAt(pt));

  function order() {
    const g = GUIDES[st.g];
    if (st.sort && g.sorts.includes(st.sort)) return st.sort;
    return g.classic && here && inNY(here) ? "nearest" : g.sorts[0];   // from outside Pennsylvania, distance isn't the point
  }

  function allows(p, anyRegion = false) {   // Guide.swift Filters.allows (anyRegion: the same filters, wherever the place is)
    if (p.v && st.g !== "saved") return false;            // convenience counters, members' clubs, airport stands and the like
    if (!anyRegion && st.r !== "all" && st.g !== "saved" && p.ri !== regionIdx(st.r)) return false;
    if (!anyRegion && st.town && p.c !== st.town) return false;
    if (st.cuisine && p.cu !== st.cuisine) return false;
    if (st.chains && p.ch >= 5 && !(p.hc === 1 && !p.br)) return false;   // a hand-checked original stays; its branches can go
    if (st.conf && p.t === 0 && !p.hc) return false;      // hand-checked counts as confirmed
    if (st.bib && p.mi !== 2) return false;               // MICHELIN Bib Gourmand only, as the app's Filters switch
    return true;
  }

  // the region files the current view needs: the directory guides need the region's whole list; the guides have theirs already
  function need() {
    const g = GUIDES[st.g];
    if (g.directory) return st.r === "all" ? SLUGS.slice() : [st.r];
    if (st.g === "saved") return [...new Set([...saved].map((id) => savedRegion[id]).filter((s) => SLUGS.includes(s)))];
    return [];
  }

  function list() {
    const g = GUIDES[st.g], q = parse(st.q), o = order();
    if (q.unsearchable) return [];
    if (g.needsHere && !here) return [];
    if (!qEmpty(q)) ensureIndex();
    let out = P.filter((p) => g.inc(p) && allows(p) && (qEmpty(q) || matches(p, q)));
    const byName = (a, b) => a.n.localeCompare(b.n, "en", { sensitivity: "base" }) || (b.ip ?? -1) - (a.ip ?? -1) || (a.c || "").localeCompare(b.c || "");
    if (o === "nearest" && here) {
      const d = new Map(out.map((p) => [p, miles(here, p)]));
      out.sort((a, b) => d.get(a) - d.get(b) || byName(a, b));
    } else if (o === "featured" || o === "nearest") out.sort((a, b) => (b.ip ?? -1) - (a.ip ?? -1) || (a.f ?? 9999) - (b.f ?? 9999) || byName(a, b));
    else if (o === "oldest") out.sort((a, b) => (a.f ?? 9999) - (b.f ?? 9999) || byName(a, b));
    else if (o === "iconic") out.sort((a, b) => (b.ip ?? -1) - (a.ip ?? -1) || byName(a, b));
    else out.sort(byName);
    if (q.tokens.length && !g.ranked) {       // name matches first when searching
      const named = out.filter((p) => nameMatches(p, q));
      if (named.length && named.length < out.length) { const ids = new Set(named); out = named.concat(out.filter((p) => !ids.has(p))); }
    }
    return out;
  }

  // ---------------------------------------------------------------- rendering
  let KIND_LABELS = [];
  const kindNames = (p) => KIND_LABELS.filter(([bit]) => p.k & bit).map(([, l]) => l);
  const jbLabel = (p) => (p.h & 1 ? "America's Classic" : p.h & 2 ? "James Beard winner" : p.h & 4 ? "James Beard nominee" : p.h & 8 ? "James Beard semifinalist" : null);
  const MI_LABEL = { 1: "MICHELIN Guide", 2: "Bib Gourmand", 3: "1 MICHELIN Star", 4: "2 MICHELIN Stars", 5: "3 MICHELIN Stars" };
  // "Pittsburgh" or "Feasterville-Trevose, Bensalem" (Place.placeName)
  const placeName = (p) => { if (!p.c) return p.pl || ""; const n = p.pl; return n && n !== p.c ? `${n}, ${p.c}` : p.c; };
  const plClass = (t) => (t === "Inspected & Permitted" ? "green" : /consumer alert/i.test(t) ? "yellow" : /clos/i.test(t) ? "red" : "other");

  function chips(p, max) {   // GuideListView.swift PlaceChips (the ACHD placard goes on its own line, with its date)
    const c = [];
    if (MI_LABEL[p.mi]) c.push(`<span class="tag tag-hon">${p.mi === 1 && p.gs ? "MICHELIN Green Star" : MI_LABEL[p.mi]}</span>`);
    const jb = jbLabel(p);
    if (jb) c.push(`<span class="tag tag-hon">${jb}</span>`);
    if (p.hc === 1) for (const k of kindNames(p)) if (k !== "Historic") c.push(`<span class="tag">${k}</span>`);
    if (p.seas) c.push('<span class="tag tag-plain">Seasonal</span>');
    if (p.ch >= 5) c.push(`<span class="tag tag-plain">Chain · ${p.ch}</span>`);
    if (p.t === 0 && !p.hc && !p.g) c.push('<span class="tag tag-dash">Listing only</span>');
    return (max ? c.slice(0, max) : c).join("");
  }

  // the official Allegheny County placard is always shown with its date (ACHD's own; we compute no grade)
  function gradeLine(p) {
    if (!p.ap) return "";
    return `<span class="ex-gline"><span class="pl pl-${plClass(p.ap)}">${esc(p.ap)}</span>${p.ad ? " · inspected " + niceDate(p.ad) : ""} · ACHD</span>`;
  }

  function metric(p, o) {
    if (o === "nearest" && here && p.la != null) return [milesText(miles(here, p)), "away"];
    if (o === "oldest" && p.f) return [String(p.f), "since"];
    if (o === "iconic") return p.f ? [String(p.f), "since"] : null;   // what earns the place, never points
    if (p.f && st.g !== "all") return [String(p.f), "since"];
    return null;
  }

  function render() {
    const g = GUIDES[st.g], o = order();
    const missing = need().filter((s) => !loaded.has(s));
    const missingDetail = st.g === "saved" ? need().filter((s) => !details.has(regionIdx(s))) : [];
    hideChooser();
    document.querySelectorAll(".ex-guides button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.g === st.g)));
    $("#ex-region").value = st.r;
    $("#ex-sub").textContent = (g.directory ? `${g.sub} in ${regionName(st.r)}` : g.sub) + (g.note ? `. ${g.note}` : "");
    const sortSel = $("#ex-sort");
    sortSel.innerHTML = g.sorts.map((s) => `<option value="${s}"${s === o ? " selected" : ""}>${SORT_LABEL[s]}</option>`).join("");
    sortSel.disabled = g.sorts.length < 2;
    if (missing.length) {
      current = [];
      $("#ex-count").textContent = `Loading ${missing.length > 1 ? "every region" : regionName(missing[0])}…`;
      $("#ex-list").innerHTML = `<li class="ex-empty">Loading ${esc(missing.length > 1 ? "all of Pennsylvania" : regionName(missing[0]))}…</li>`;
      $("#ex-more").hidden = true;
      loadRegions(missing).then(() => render(), () => { $("#ex-list").innerHTML = '<li class="ex-empty">That region couldn\'t load. Refresh to try again.</li>'; });
      saveHash();
      return;
    }
    if (missingDetail.length) {
      $("#ex-list").innerHTML = '<li class="ex-empty">Loading your saved places…</li>';
      Promise.all(missingDetail.map((s) => loadDetail(regionIdx(s)))).then(() => render());
      return;
    }
    current = list();
    if (!current.length && followTown()) return;   // nothing here, and the search names a town elsewhere: go there
    const filters = [st.town && `in ${st.town}`, st.cuisine && st.cuisine, st.chains && "no chains", st.conf && "high-confidence only", st.bib && "Bib Gourmand"].filter(Boolean);
    const where = st.g === "saved" ? "" : ` · ${st.r === "all" ? "all of Pennsylvania" : regionName(st.r)}`;
    // "Nearest" before there's a fix (asking, denied, timed out) is the Featured order: the label says so, not "Nearest"
    const label = o === "nearest" && !here ? (g.needsHere ? "no location yet" : "Featured first (no location yet)") : SORT_LABEL[o];
    $("#ex-count").textContent = `${fmt(current.length)} ${current.length === 1 ? "place" : "places"} · ${label}${where}` + (filters.length ? ` · ${filters.join(", ")}` : "");
    $("#ex-clear").hidden = !filters.length;
    if (view === "list") renderList(o); else drawMap();
    saveHash();
  }

  // A search inside a guide that the guide can't answer, or answers with only a few: the same words in "All restaurants". First the
  // region in view, counted once its file is in (it starts loading here, and the list redraws when it lands). Then, when no name there
  // matches, the region whose loaded places do ("primanti" from Philadelphia: every guide's places are loaded statewide, plus any
  // region opened), or failing that any place that matches at all. A count is named only when the files it covers are all in, so a
  // button never promises a number the list then doesn't show.
  const FEW = 3;
  let wideWait = null;
  function wideOffers(min) {
    const q = parse(st.q);
    if (q.unsearchable || qEmpty(q)) return [];
    ensureIndex();
    if (st.r === "all") {
      if (!SLUGS.every((s) => loaded.has(s))) return min ? [] : [{ r: "all", n: null }];   // the whole state loads only when asked for
      const n = P.filter((p) => allows(p) && matches(p, q)).length;
      return n > min ? [{ r: "all", n }] : [];
    }
    if (!loaded.has(st.r)) {
      if (!wideWait) wideWait = loadRegions([st.r]).then(() => { wideWait = null; render(); }, () => { wideWait = null; });
      return min ? [] : [{ r: st.r, n: null }];
    }
    const ri = regionIdx(st.r), here_ = P.filter((p) => allows(p) && matches(p, q));
    const out = here_.length > min ? [{ r: st.r, n: here_.length }] : [];
    if (min || here_.some((p) => nameMatches(p, q))) return out;
    const best = (test) => {
      const per = new Map();
      for (const p of P) if (p.ri !== ri && allows(p, true) && matches(p, q) && test(p)) per.set(p.ri, (per.get(p.ri) || 0) + 1);
      const top = [...per.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0])[0];
      return top && SLUGS[top[0]];
    };
    const sl = best((p) => nameMatches(p, q)) || (here_.length ? null : best(() => true));
    if (sl) out.push({ r: sl, n: loaded.has(sl) ? P.filter((p) => p.ri === regionIdx(sl) && allows(p, true) && matches(p, q)).length : null });
    return out;
  }
  const wideButton = (w) => `<button type="button" class="ex-small ex-wide" data-r="${esc(w.r)}">Search all restaurants in ${esc(regionName(w.r))}`
    + `${w.n == null ? "" : ` <span>(${fmt(w.n)} ${w.n === 1 ? "match" : "matches"})</span>`}</button>`;
  function wireWide() {
    for (const b of document.querySelectorAll("#ex-list .ex-wide")) {
      b.onclick = () => {
        st.g = "all"; st.sort = ""; shown = 100;
        if (b.dataset.r !== st.r) setRegion(b.dataset.r); else render();
        // the button is gone with the old list: focus goes to the first result once the region's list is in
        loadRegions(need()).then(() => requestAnimationFrame(() => $("#ex-list .ex-row")?.focus()), () => null);
      };
    }
  }

  function renderList(o) {
    const ol = $("#ex-list");
    const g = GUIDES[st.g];
    if (!current.length) {
      let msg = "No places match. Try fewer words or clear the filters.", btn = "", wide = [];
      if (st.g === "saved") msg = "Nothing saved yet. Open a place and tap Save to keep it here, in this browser.";
      else if (g.needsHere && !here) msg = locDenied
        ? "Location is blocked for this site, so Near me has nothing to sort. Allow location for this site in your browser's settings, then tap “Use my location”."
        : "Tap “Use my location” to see the places around you. Your location stays in this browser.";
      else if (st.r !== "all" && !st.q && !st.town && !st.cuisine) {
        const total = P.filter((p) => g.inc(p) && !p.v).length;
        if (total) { msg = `None of the ${GUIDES[st.g].title} places is in ${regionName(st.r)}.`; btn = `<br><button type="button" class="ex-small" id="ex-allny">See all ${fmt(total)} in Pennsylvania</button>`; }
      } else if (!g.directory && st.g !== "saved" && st.q && (wide = wideOffers(0)).length) {
        // a search inside a guide that the guide can't answer ("kalaya" in Cheesesteaks): offer every restaurant, not a dead end
        msg = `Nothing on the ${g.title} list${st.r === "all" ? "" : ` in ${regionName(st.r)}`} matches that.`;
        btn = wide.map((w) => `<br>${wideButton(w)}`).join("");
      } else if (st.r !== "all" && st.q && !st.town && !st.cuisine && g.directory) {
        // a dish with a home elsewhere ("pierogies" from Philadelphia): offer the region with the most hand-checked places for it (the
        // guides' places are loaded statewide from the start; the rest of that region isn't, so the button names no count)
        const q = parse(st.q);
        if (q.tag && !q.narrow) {
          const n = new Map();
          for (const p of P) if (!p.v && p.hc === 1 && matches(p, q)) n.set(p.ri, (n.get(p.ri) || 0) + 1);
          const best = [...n.entries()].sort((a, b) => b[1] - a[1])[0];
          if (best) {
            msg = `No places match “${st.q.replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, "")}” in ${regionName(st.r)}.`;   // no bidi controls echoed
            btn = `<br><button type="button" class="ex-small" id="ex-allny" data-r="${esc(SLUGS[best[0]])}">Search ${esc(REGIONS[best[0]])}</button>`;
          }
        }
      }
      ol.innerHTML = `<li class="ex-empty">${esc(msg)}${btn}</li>`;
      const b = $("#ex-allny");
      if (b) b.onclick = () => setRegion(b.dataset.r || "all");
      wireWide();
      $("#ex-more").hidden = true;
      return;
    }
    const ranked = RANKING.has(o);
    // a guide search that finds only a few: the whole directory may hold the one they meant ("pats" in Tomato Pie)
    const few = !g.directory && st.g !== "saved" && st.q && current.length <= FEW ? wideOffers(current.length)[0] : null;
    ol.innerHTML = current.slice(0, shown).map((p, i) => {
      const m = metric(p, o);
      const rank = ranked ? `<span class="ex-rank${i < 3 ? " top" : ""}"><span class="sr">Rank </span>${i + 1}</span>` : "";
      return `<li><button class="ex-row" data-key="${p.key}">${rank}<span class="ex-main"><b class="ex-name">${esc(p.n)}</b><span class="ex-town">${esc([placeName(p), p.cu].filter(Boolean).join(" · "))}</span>${gradeLine(p)}<span class="ex-chips">${chips(p, 4)}</span></span>${m ? `<span class="ex-metric"><b>${esc(m[0])}</b><small>${m[1]}</small></span>` : ""}</button></li>`;
    }).join("") + (few && few.n != null ? `<li class="ex-wider">${wideButton(few)}</li>` : "");
    wireWide();
    const left = current.length - shown;
    $("#ex-more").hidden = left <= 0;
    $("#ex-more").textContent = `Show more (${fmt(left)} left)`;
  }

  // ---------------------------------------------------------------- place panel (PlaceDetailView.swift)
  const JUR_LIST = { 1: "City of Philadelphia food licenses (L&I)", 2: "Allegheny County Health Department food facility permits",
    3: "Pennsylvania Liquor Control Board licenses" };
  const TIER = { 2: "On an official list", 1: "High-confidence listing", 0: "Listing only" };   // the family wording (Nick, 2026-10-13)
  const CHECKED = "checked in October 2026 against a 2025 or 2026 source";
  // the PA Department of Agriculture's own disclosure on its inspection search, quoted verbatim wherever we link it; the City's for its licenses
  const PDA_DISCLOSURE = "Please remember that any inspection is a 'snapshot' of the day and time of the inspection. An inspection conducted on any given day may not be representative of the overall, long-term cleanliness of an establishment. Also, at the time of the inspection, violations are recorded but are often corrected on site prior to the inspector leaving the establishment.";
  const PHILLY_DISCLAIMER = "The City of Philadelphia makes no representation about the accuracy of any specific information in this data and is provided “as is” and without Warranty of any kind.";
  const PDA_SEARCH = "https://www.pafoodsafety.pa.gov/Web/Inspection/PublicInspectionSearch.aspx";
  const PHILLY_SEARCH = "https://philadelphia-pa.healthinspections.us/philadelphia/";
  const COUNTY_SEARCH = { Bucks: "https://bucks-pa.healthinspections.us/", Montgomery: "https://pa.healthinspections.us/montgomery/" };
  const ACHD_PAGE = "https://www.alleghenycounty.us/Services/Health-Department/Food-Safety";
  const usPhone = (ph) => (/^\+1[2-9]\d{9}$/.test(ph || "") ? ph : null);
  const phoneText = (ph) => `(${ph.slice(2, 5)}) ${ph.slice(5, 8)}-${ph.slice(8)}`;
  const webLink = (w) => { try { const u = new URL(w); return u.protocol === "http:" || u.protocol === "https:" ? u.href : null; } catch { return null; } };

  function rate(p) {   // AppModel.matchRate: how often a listing like this matched a permitted food business on the official list
    const src = SOURCES[p.s] || "meta";
    let group;
    if (src === "meta") group = p.t === 1 ? "Meta, confidence 0.95+" : "Meta, 0.90-0.95";
    else if (src === "AllThePlaces" || src === "DAC") group = "brand feed";
    else return null;
    const g = (CAL.philly_restaurant_licenses || {})[group];
    if (!g || g.n < 20) return null;
    return `${Math.round(g.matched * 100)}%`;
  }

  function howWeKnow(p) {   // PlaceDetailView.listingNote
    const src = SOURCES[p.s] || "meta";
    if (src === "research") return `On our hand-checked list (${CHECKED}). The open map data didn't list it as a place to eat, so it's placed at its street address.`;
    if (p.t === 2) return src === "official"
      ? `From the ${JUR_LIST[p.j] || "official list"}. The open map data didn't have it, so it's placed at its street address.`
      : `Matched to an active entry in the ${JUR_LIST[p.j] || "official list"}.`;
    if (p.hc === 1) return `On our hand-checked list: ${CHECKED} (such as its own site or menu, local news, or an official listing). It's in Overture's open map data too.`;
    const r = rate(p);
    return (p.t === 1 ? "A high-confidence listing in Overture's open map data." : "A single listing in Overture's open map data, so it may be closed or misfiled.")
      + (r ? ` Checked against Philadelphia's restaurant licenses, listings like this matched a licensed food business ${r} of the time (the license list also holds schools and corner stores, so that's a floor).` : "");
  }

  const kv = (k, v) => (v == null || v === "" ? "" : `<div class="ex-kv"><span>${esc(k)}</span><b>${esc(v)}</b></div>`);
  const fact = (k, v) => (v ? `<p><b>${esc(k)}</b><br>${esc(v)}</p>` : "");
  const section = (t, body, cls = "") => `<section class="ex-sec${cls}"><h3>${esc(t)}</h3>${body}</section>`;

  function inspections(p, d) {   // PlaceDetailView.inspections: each jurisdiction's own record, never blended
    const county = COUNTIES[p.co] || "";
    if (county === "Allegheny") {
      const head = p.ap
        ? `<div class="ex-grade"><span class="pl pl-${plClass(p.ap)}">${esc(p.ap)}</span><span><b>Official placard</b>${p.ad ? `<span class="ex-graded">Inspected ${esc(niceDate(p.ad))}</span>` : ""}</span></div>`
          + `<p class="ex-fine">The placard is the Allegheny County Health Department's own: green “Inspected &amp; Permitted”, yellow “Consumer Alert” (up to 10 days to correct), red for a closure. We compute no grade. Source: Western Pennsylvania Regional Data Center${RT.achd ? `, records through ${esc(niceDate(RT.achd))}` : ""}.</p>`
        : `<p class="ex-fine ex-noinsp">${HAS_ACHD ? "No ACHD placard matched this listing." : "Allegheny County's placards aren't in this version yet."}</p>`;
      return section("Health inspections · Allegheny County Health Department", head
        + `<p class="ex-fine"><a href="${ACHD_PAGE}" rel="noopener" target="_blank">ACHD food safety and inspection reports</a></p>`, " ex-ac");
    }
    if (county === "Philadelphia") {
      return section("Licenses & inspections · City of Philadelphia", kv("L&I food license", p.phl ? "Active" : "— (none matched)")
        + `<p class="ex-fine">The Department of Public Health posts inspection reports one search at a time, with no grade or score, so we link to them rather than copy them. Licenses: OpenDataPhilly. “${esc(PHILLY_DISCLAIMER)}”</p>`
        + `<p class="ex-fine"><a href="${PHILLY_SEARCH}" rel="noopener" target="_blank">Philadelphia inspection reports</a></p>`, " ex-phl");
    }
    if (COUNTY_SEARCH[county]) {
      return section("Health inspections", `<p class="ex-fine">${esc(county)} County inspects its own restaurants and posts reports one search at a time, so we link to them rather than copy them.</p>`
        + `<p class="ex-fine"><a href="${COUNTY_SEARCH[county]}" rel="noopener" target="_blank">${esc(county)} County inspection reports</a></p>`, " ex-county");
    }
    return section("Health inspections", '<p class="ex-fine">The Pennsylvania Department of Agriculture and local health departments post inspection results one search at a time, so we link to them rather than copy them. There is no statewide grade, and we don\'t make one.</p>'
      + `<p class="ex-fine">PDA: “${esc(PDA_DISCLOSURE)}”</p>`
      + `<p class="ex-fine"><a href="${PDA_SEARCH}" rel="noopener" target="_blank">PA Food Safety Inspection Search</a></p>`, " ex-pda");
  }

  // On a phone the panel is a modal sheet: a dialog, with everything behind it inert so Tab can't reach what it covers.
  const PHONE = window.matchMedia("(max-width: 600px)");
  let inerted = [];
  function setModal() {
    const panel = $("#ex-panel"), modal = PHONE.matches && !panel.hidden;
    panel.setAttribute("role", PHONE.matches ? "dialog" : "complementary");
    if (PHONE.matches) panel.setAttribute("aria-modal", "true"); else panel.removeAttribute("aria-modal");
    inerted.forEach((el) => { el.inert = false; });
    inerted = [];
    if (!modal) return;
    for (let el = panel; el.parentElement && el !== document.body; el = el.parentElement) {
      for (const sib of el.parentElement.children) if (sib !== el && !sib.inert && sib.tagName !== "SCRIPT") { sib.inert = true; inerted.push(sib); }
    }
  }
  PHONE.addEventListener("change", setModal);

  // Back closes a place: opening one adds a history entry (beforePush is the entry under it), and closing it goes back over it
  let pushed = false, closingBack = false, beforePush = "";

  function fullAddress(p) {   // Place.fullAddress
    const town = p.pl || p.c;
    return [p.a, [town && `${town}, PA`, p.z].filter(Boolean).join(" ")].filter(Boolean).join(", ");
  }

  let pendingOpen = null, lastKey = "";
  function openPlace(p, push = true) {
    const panel = $("#ex-panel");
    const det = details.get(p.ri);
    if (!det) {   // the facts (and the place's id) come with the region's detail file: show the name, then the rest
      pendingOpen = p;
      panel.innerHTML = `<button class="ex-close" id="ex-close" aria-label="Close">×</button><p class="ex-kicker">${esc((placeName(p) || "Pennsylvania").toUpperCase())}</p><h2 id="ex-pname">${esc(p.n)}</h2><p class="ex-fine">Loading…</p>`;
      panel.hidden = false; panel.dataset.ready = "0";
      document.body.classList.add("ex-open"); setModal();
      $("#ex-close").onclick = () => { pendingOpen = null; panel.hidden = true; document.body.classList.remove("ex-open"); setModal(); };
      loadDetail(p.ri).then(() => { if (pendingOpen === p) { pendingOpen = null; openPlace(p, push); } });
      return;
    }
    st.p = p.id; lastKey = p.key;
    const d = det.d[p.rr] || {};
    const addr = fullAddress(p);
    const apple = `https://maps.apple.com/?q=${encodeURIComponent(p.n)}&ll=${p.la},${p.lo}`;
    const dirs = `https://maps.apple.com/?daddr=${p.la},${p.lo}&dirflg=d`;
    const site = d.w ? webLink(d.w) : null;
    const ph = usPhone(d.ph);
    let html = `<button class="ex-close" id="ex-close" aria-label="Close">×</button>
      <p class="ex-kicker">${esc((placeName(p) || "Pennsylvania").toUpperCase())}</p>
      <h2 id="ex-pname">${esc(p.n)}</h2>
      <p class="ex-addr">${esc([addr, p.cu].filter(Boolean).join(" · "))}</p>
      ${ph ? `<p class="ex-addr">${esc(phoneText(ph))}</p>` : ""}
      ${here && p.la != null ? `<p class="ex-dist">${milesText(miles(here, p))} away</p>` : ""}
      <p class="ex-chips">${chips(p)}</p>
      <div class="ex-actions">
        <a class="btn ex-apple" href="${esc(apple)}" rel="noopener" target="_blank">Hours, photos &amp; more · Apple Maps</a>
        <div class="ex-act-row">
          <a href="${esc(dirs)}" rel="noopener" target="_blank">Directions</a>
          ${ph ? `<a href="tel:${esc(ph)}" aria-label="Call ${esc(phoneText(ph))}">Call</a>` : ""}
          ${site ? `<a href="${esc(site)}" rel="noopener nofollow" target="_blank">Website</a>` : ""}
          <button id="ex-save" type="button" aria-pressed="${saved.has(p.id)}">${saved.has(p.id) ? "Saved" : "Save"}</button>
        </div>
      </div>`;
    if (p.hc === 1) {
      const src = d.src ? webLink(d.src) : null;
      html += section("Hand-checked", (d.note ? `<p>${esc(d.note)}</p>` : "")
        + fact("On our lists", kindNames(p).join(", ")) + fact("Known for", (p.dish || "").replace(/; /g, ", "))
        + (d.sea ? fact("Season", d.sea) : p.seas ? fact("Season", "Seasonal; check before you go.") : "")
        + (p.f ? fact("At this address since", String(p.f) + (d.fn ? `. ${d.fn}` : "")) : d.fn ? fact("History", d.fn) : "") + fact("A branch of", p.br)
        + `<p class="ex-fine">Checked open in October 2026 against a 2025 or 2026 source, such as the place's own site or menu, local news, or an official listing.${src ? ` <a href="${esc(src)}" rel="noopener nofollow" target="_blank">Our source</a>.` : ""} Hours and menus change, so check before you go.</p>`);
    }
    if (p.mi || d.jbf) {
      const lines = [...(MI_LABEL[p.mi] ? [`${p.mi === 1 && p.gs ? "MICHELIN Green Star" : MI_LABEL[p.mi]} · MICHELIN Guide, Philadelphia, 2025 selection`] : []), ...(d.jbf ? d.jbf.split("; ").map((x) => "James Beard: " + x) : [])];
      html += section("Honors", `<ul>${lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>` + (d.chef ? kv("Chef", d.chef) : "")
        + '<p class="ex-fine">Honors are facts, not ratings. MICHELIN and the MICHELIN Guide are trademarks of Michelin. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation.</p>');
    }
    html += inspections(p, d);
    html += section("How we know it's here", kv("Listed as", p.hc === 1 && p.t !== 2 ? "Hand-checked" : TIER[p.t])
      + (p.t === 2 ? kv("Official list", JUR_LIST[p.j] || "") : "") + kv("Liquor license", d.lq || "— (none matched)")
      + kv("County", (COUNTIES[p.co] || "") + (REGIONS[p.ri] ? ` · ${REGIONS[p.ri]}` : "")) + kv("Municipality", p.mu)
      + (p.ch >= 2 ? kv("Locations in Pennsylvania", fmt(p.ch)) : "") + `<p class="ex-fine">${esc(howWeKnow(p))}</p>`);
    const appUrl = webLink(window.APP_STORE_URL || "");
    html += appUrl
      ? `<p class="ex-app">Save it on your phone: <a href="${esc(appUrl)}" rel="noopener">Get the free iPhone app</a></p>`
      : `<p class="ex-app"><a href="${BASE}/#download">The free iPhone app is coming soon</a></p>`;
    panel.innerHTML = html;
    panel.hidden = false;
    panel.dataset.ready = "1";
    document.body.classList.add("ex-open");
    setModal();
    $("#ex-close").onclick = () => closePlace();
    $("#ex-save").onclick = (ev) => {
      if (saved.has(p.id)) { saved.delete(p.id); delete savedRegion[p.id]; } else { saved.add(p.id); savedRegion[p.id] = SLUGS[p.ri]; }
      store.set("saved", [...saved]);
      store.set("savedr", savedRegion);
      ev.target.textContent = saved.has(p.id) ? "Saved" : "Save";
      ev.target.setAttribute("aria-pressed", String(saved.has(p.id)));
      if (st.g === "saved") render();
    };
    panel.scrollTop = 0;
    $("#ex-close").focus();
    if (push) {
      if (!pushed) beforePush = location.hash;
      saveHash(!pushed); pushed = true;
    }
  }

  function closePlace(fromHistory = false) {
    const was = lastKey;
    st.p = ""; pendingOpen = null;
    $("#ex-panel").hidden = true;
    document.body.classList.remove("ex-open");
    setModal();
    if (!fromHistory && pushed) { pushed = false; closingBack = true; history.back(); }
    else { pushed = false; saveHash(); }
    const row = was && document.querySelector(`.ex-row[data-key="${was}"]`);
    if (row) row.focus();
  }

  // ---------------------------------------------------------------- map (canvas: the state, its 67 county lines, a dot per place)
  let SHAPES = null, cam = null;
  const LAT0 = 41.0, KX = Math.cos(LAT0 * Math.PI / 180);
  const proj = (lo, la) => [(lo + 77.6) * KX, -(la - LAT0)];
  function regionBox() {
    if (st.r === "all" || st.g === "saved" || !SHAPES) return NY_BOX;
    const name = regionName(st.r), b = { s: 90, n: -90, w: 180, e: -180 };
    for (const c of SHAPES.counties || []) {
      if (c.region !== name) continue;
      for (const ring of c.c) for (const [lo, la] of ring) { b.s = Math.min(b.s, la); b.n = Math.max(b.n, la); b.w = Math.min(b.w, lo); b.e = Math.max(b.e, lo); }
    }
    return b.s < b.n ? b : NY_BOX;
  }
  function fitCam(w, h) {
    const box = regionBox();
    const [x0, y0] = proj(box.w, box.n), [x1, y1] = proj(box.e, box.s);
    const k = Math.min(w / (x1 - x0), h / (y1 - y0)) * 0.92;
    return { k, x: (w - (x1 - x0) * k) / 2 - x0 * k, y: (h - (y1 - y0) * k) / 2 - y0 * k };
  }
  const toScreen = (la, lo) => { const [x, y] = proj(lo, la); return [x * cam.k + cam.x, y * cam.k + cam.y]; };

  async function drawMap() {
    const cv = $("#ex-map"), wrap = $("#ex-mapwrap");
    const w = wrap.clientWidth, h = wrap.clientHeight, dpr = window.devicePixelRatio || 1;
    if (!w || !h) return;
    if (!SHAPES) SHAPES = await fetchJSON(`${BASE}/data/pa_shapes.json`).catch(() => ({ state: [], counties: [] }));
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    if (!cam) cam = fitCam(w, h);
    const c = cv.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const ring = (r) => { r.forEach(([lo, la], i) => { const [x, y] = toScreen(la, lo); i ? c.lineTo(x, y) : c.moveTo(x, y); }); c.closePath(); };
    c.fillStyle = "#ffffff";
    c.beginPath(); (SHAPES.state || []).forEach((poly) => poly.forEach(ring)); c.fill("evenodd");
    const name = st.r === "all" || st.g === "saved" ? null : regionName(st.r);
    if (name) {   // the other regions' counties a shade darker, so the region in view stands out
      c.fillStyle = "#f1ede3";
      for (const ct of SHAPES.counties || []) if (ct.region !== name) { c.beginPath(); ct.c.forEach(ring); c.fill("evenodd"); }
    }
    c.strokeStyle = "rgba(124,135,142,.6)"; c.lineWidth = 0.7;
    for (const ct of SHAPES.counties || []) { c.beginPath(); ct.c.forEach(ring); c.stroke(); }
    c.strokeStyle = "#7c878e"; c.lineWidth = 1.2;
    c.beginPath(); (SHAPES.state || []).forEach((poly) => poly.forEach(ring)); c.stroke();
    const pts = current.filter((p) => p.la != null);
    const r = Math.max(1.6, Math.min(5, 1.2 + cam.k / 220));
    for (const classic of [false, true]) {
      c.fillStyle = classic ? "#e8a33d" : "#2e4e3f";
      c.strokeStyle = "#2e4e3f"; c.lineWidth = 1;
      for (const p of pts) {
        if ((p.hc === 1) !== classic) continue;
        const [x, y] = toScreen(p.la, p.lo);
        if (x < -5 || y < -5 || x > w + 5 || y > h + 5) continue;
        c.beginPath(); c.arc(x, y, classic ? r + 1.5 : r, 0, 6.2832); c.fill(); if (classic) c.stroke();
      }
    }
    if (here && inNY(here)) {
      const [x, y] = toScreen(here.la, here.lo);
      c.fillStyle = "#24497f"; c.strokeStyle = "#ffffff"; c.lineWidth = 2.5;
      c.beginPath(); c.arc(x, y, 6, 0, 6.2832); c.fill(); c.stroke();
    }
    $("#ex-maphint").textContent = pts.length ? `${fmt(pts.length)} ${pts.length === 1 ? "place" : "places"} · tap a dot` : "No places to show";
  }

  function nearestDot(px, py) {
    let best = null, bd = 14 * 14;
    for (const p of current) {
      if (p.la == null) continue;
      const [x, y] = toScreen(p.la, p.lo);
      const d = (x - px) ** 2 + (y - py) ** 2;
      if (d < bd) { bd = d; best = p; }
    }
    return best;
  }

  // several places on the very same spot (one address, a food hall) can't be told apart by tapping: list them
  function showChooser(stack, x, y) {
    const box = $("#ex-chooser"), wrap = $("#ex-mapwrap");
    stack.sort((a, b) => a.n.localeCompare(b.n, "en", { sensitivity: "base" }));
    box.innerHTML = `<p id="ex-chooser-h">${stack.length} places at this spot</p><ul>${stack.slice(0, 40).map((p) => `<li><button type="button" data-key="${p.key}">${esc(p.n)}</button></li>`).join("")}</ul>`;
    box.hidden = false;
    box.style.left = Math.max(10, Math.min(x + 8, wrap.clientWidth - box.offsetWidth - 10)) + "px";
    box.style.top = Math.max(10, Math.min(y + 8, wrap.clientHeight - box.offsetHeight - 10)) + "px";
    box.querySelector("button").focus();
  }
  function hideChooser() { const box = $("#ex-chooser"); if (box && !box.hidden) { box.hidden = true; box.innerHTML = ""; } }

  function zoomAt(f, px, py) {
    const k = Math.min(Math.max(cam.k * f, 40), 400000);
    const s = k / cam.k;
    cam = { k, x: px - (px - cam.x) * s, y: py - (py - cam.y) * s };
    hideChooser();
    drawMap();
  }

  function mapEvents() {
    const cv = $("#ex-map");
    const ptrs = new Map();
    let moved = false, pinch0 = null, start = null;
    cv.addEventListener("wheel", (e) => { e.preventDefault(); const b = cv.getBoundingClientRect(); zoomAt(e.deltaY < 0 ? 1.25 : 0.8, e.clientX - b.left, e.clientY - b.top); }, { passive: false });
    cv.addEventListener("pointerdown", (e) => {
      cv.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]);
      moved = false; pinch0 = null; start = [e.clientX, e.clientY];
      hideChooser();
    });
    cv.addEventListener("pointermove", (e) => {
      if (!ptrs.has(e.pointerId)) return;
      const prev = ptrs.get(e.pointerId);
      ptrs.set(e.pointerId, [e.clientX, e.clientY]);
      if (ptrs.size === 2) {
        const [a, b] = [...ptrs.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        const r = cv.getBoundingClientRect();
        if (pinch0) zoomAt(d / pinch0, (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top);
        pinch0 = d; moved = true; return;
      }
      // a drag, however slow, is a drag: measured from where the finger went down, not move by move
      if (start && Math.hypot(e.clientX - start[0], e.clientY - start[1]) > 6) moved = true;
      cam.x += e.clientX - prev[0]; cam.y += e.clientY - prev[1]; drawMap();
    });
    const up = (e) => {
      ptrs.delete(e.pointerId);
      if (!moved && ptrs.size === 0) {
        const b = cv.getBoundingClientRect(), x = e.clientX - b.left, y = e.clientY - b.top, p = nearestDot(x, y);
        if (p) {
          const stack = current.filter((o) => o.la === p.la && o.lo === p.lo);
          if (stack.length > 1) showChooser(stack, x, y); else openPlace(p);
        }
      }
      if (ptrs.size < 2) pinch0 = null;
    };
    cv.addEventListener("pointerup", up);
    cv.addEventListener("pointercancel", (e) => ptrs.delete(e.pointerId));
    $("#ex-chooser").addEventListener("click", (e) => { const b = e.target.closest("button[data-key]"); if (b) { hideChooser(); const p = byKey.get(b.dataset.key); if (p) openPlace(p); } });
    $("#ex-zin").onclick = () => zoomAt(1.6, cv.clientWidth / 2, cv.clientHeight / 2);
    $("#ex-zout").onclick = () => zoomAt(0.625, cv.clientWidth / 2, cv.clientHeight / 2);
    let rt = null;
    window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if (view === "map") { cam = null; drawMap(); } }, 150); });
    if ("ResizeObserver" in window) new ResizeObserver(() => { if (view === "map") drawMap(); }).observe($("#ex-mapwrap"));
  }

  // read-only: where a place is drawn on screen (scripts/qa-site.py taps dots with it)
  window.NYE_MAP = { at: (la, lo) => (cam ? toScreen(la, lo) : null) };

  function centerOn(pt) {
    const cv = $("#ex-map"), w = cv.clientWidth, h = cv.clientHeight;
    const k = 4000, [x, y] = proj(pt.lo, pt.la);
    cam = { k, x: w / 2 - x * k, y: h / 2 - y * k };
  }

  // ---------------------------------------------------------------- data: index + guides at once, a region's core when needed, its detail lazily
  async function fetchJSON(url) { const r = await fetch(url); if (!r.ok) throw new Error(r.status + " " + url); return r.json(); }

  // one file's columns -> place objects (strings from the file's own lookup tables); ri/rr say where each lives
  const isoDay = (days) => (days == null ? null : new Date(Date.UTC(2000, 0, 1) + days * 864e5).toISOString().slice(0, 10));
  function readCols(d, ri) {
    const n = d.count, C = {};
    for (const [k, v] of Object.entries(d.cols)) {   // dense arrays, or sparse {i: row gaps, v: values}
      if (Array.isArray(v)) { C[k] = v; continue; }
      const a = new Array(n).fill(null);
      let r = 0;
      v.i.forEach((gap, j) => { r += gap; a[r] = v.v[j]; });
      C[k] = a;
    }
    const col = (k, i) => (C[k] ? C[k][i] : null);
    const lk = (t, v) => (v == null ? null : d[t][v]);
    const deg = (v, base) => (v == null ? null : (v + base) / 1e5);
    const out = [];
    for (let i = 0; i < n; i++) {
      const pri = ri == null ? col("ri", i) : ri, prr = ri == null ? col("rr", i) : i;
      out.push({ key: `${pri}:${prr}`, id: col("id", i), n: col("n", i), c: lk("cities", col("c", i)), co: col("co", i),
        cu: lk("cuisines", col("cu", i)) || "American & Other", t: col("t", i) ?? 0, s: col("s", i), pl: lk("mailing", col("pl", i)),
        hd: lk("hoods", col("hd", i)), mu: lk("munis", col("mu", i)), a: col("a", i), z: col("z", i), la: deg(col("la", i), d.la0),
        lo: deg(col("lo", i), d.lo0), brand: lk("brands", col("b", i)), ch: col("ch", i) || 1, j: col("j", i), v: col("v", i) === 1,
        g: col("g", i) || 0, hc: col("hc", i) || 0, k: col("k", i) || 0, h: col("h", i) || 0, mi: col("mi", i), ip: col("ip", i),
        f: col("f", i), seas: col("seas", i) === 1, br: col("br", i), dish: col("dish", i), ap: lk("placards", col("ap", i)), ad: isoDay(col("ad", i)),
        phl: col("phl", i) === 1, gs: col("gs", i) === 1,
        ri: pri, rr: prr, search: null, nameText: null });
    }
    return out;
  }

  function addPlaces(list) {
    const fresh = [];
    for (const p of list) {
      if (byKey.has(p.key)) continue;
      const det = details.get(p.ri);
      if (p.id == null && det) p.id = det.ids[p.rr];
      byKey.set(p.key, p); P.push(p); fresh.push(p);
      if (p.id != null) byId.set(p.id, p);
    }
    toIndex.push(...fresh);
    return fresh;
  }

  function loadRegions(slugs) {
    return Promise.all(slugs.map((sl) => {
      if (loaded.has(sl)) return null;
      if (!loading.has(sl)) {
        const f = IX.files.find((x) => x.slug === sl);
        loading.set(sl, fetchJSON(`${BASE}/data/${f.core}`).then((d) => {
          addPlaces(readCols(d, regionIdx(sl)));
          loaded.add(sl); loading.delete(sl);
          refreshLookups();
          indexWhenIdle();
        }, (err) => { loading.delete(sl); throw err; }));
      }
      return loading.get(sl);
    }));
  }

  const detailLoads = new Map();
  function loadDetail(ri) {
    if (!detailLoads.has(ri)) {
      detailLoads.set(ri, fetchJSON(`${BASE}/data/${IX.files[ri].detail}`).then((d) => {
        details.set(ri, d);
        d.ids.forEach((id, i) => { const p = byKey.get(`${ri}:${i}`); if (p) { p.id = id; byId.set(id, p); } });
      }, () => { details.set(ri, { ids: [], d: [] }); }));
    }
    return detailLoads.get(ri);
  }

  // the town and kind menus follow the region in view; the neighborhood keys follow what's loaded
  function refreshLookups() {
    const towns = new Map(), cuis = new Map(), vills = new Set();
    let bibs = 0;   // Bib Gourmand places in view, counted like the kinds: the box shows only when there are some
    for (const p of P) {
      if (p.hd) vills.add(p.hd);
      if (p.pl) vills.add(p.pl);
      if (p.mu) vills.add(p.mu);
      if (p.v || (st.r !== "all" && p.ri !== regionIdx(st.r))) continue;
      if (p.c) towns.set(p.c, (towns.get(p.c) || 0) + 1);
      cuis.set(p.cu, (cuis.get(p.cu) || 0) + 1);
      if (p.mi === 2) bibs += 1;
    }
    const tk = new Set(TOWN_KEYS.map(([k]) => k));
    const vk = dict();
    for (const v of vills) { const k = normAddr(v); if (k && !tk.has(k) && !(k in vk)) vk[k] = v; }
    VILLAGE_KEYS = Object.keys(vk).sort((a, b) => b.length - a.length).map((k) => [k, vk[k]]);
    if (st.town && !towns.has(st.town)) towns.set(st.town, 0);   // a town from a link stays selectable while its region loads
    $("#ex-town").innerHTML = '<option value="">All towns</option>' + [...towns.keys()].sort((a, b) => a.localeCompare(b)).map((t) => `<option>${esc(t)}</option>`).join("");
    if (st.cuisine && !cuis.has(st.cuisine)) cuis.set(st.cuisine, 0);
    $("#ex-cuisine").innerHTML = '<option value="">All kinds</option>' + [...cuis.entries()].sort((a, b) => b[1] - a[1]).map(([c, k]) => `<option value="${esc(c)}">${esc(c)} (${fmt(k)})</option>`).join("");
    $("#ex-town").value = st.town; $("#ex-cuisine").value = st.cuisine;
    $("#ex-bibwrap").hidden = !bibs && !st.bib;          // a box from a link stays while its region loads
    $("#ex-bibn").textContent = `(${fmt(bibs)})`;
  }

  async function load() {
    const [ix, gd] = await Promise.all([fetchJSON(`${BASE}/data/index.json`), fetchJSON(`${BASE}/data/guides.json`)]);
    IX = ix; REGIONS = ix.regions; SLUGS = ix.slugs; COUNTIES = ix.counties; CAL = ix.calibration || {}; SOURCES = ix.srcs || [];
    RT = ix.records_through || {}; HAS_ACHD = !!ix.has_achd;
    T = Object.fromEntries(ix.tags.map((t, i) => [t, 1 << i]));
    K = Object.fromEntries(ix.kinds.map((k, i) => [k, 1 << i]));
    const LABEL = { cheesesteak: "Cheesesteaks", "roast pork": "Roast pork", hoagie: "Hoagies", "tomato pie": "Tomato pie", "old forge": "Old Forge pizza",
      pierogi: "Pierogies", "pittsburgh sandwich": "Pittsburgh sandwich", "pa dutch": "PA Dutch", pretzel: "Soft pretzels", diner: "Diner", oldest: "Historic" };
    KIND_LABELS = ix.kinds.map((k, i) => [1 << i, LABEL[k] || k]);
    // AppModel.apply: the biggest place wins a shared spelling.
    const tk = dict();
    for (const [name, ri] of ix.towns) {
      const k = normAddr(name);
      if (k && !(k in tk)) { tk[k] = name; TOWN_REGION[name] = ri; }
    }
    TOWN_KEYS = Object.keys(tk).sort((a, b) => b.length - a.length).map((k) => [k, tk[k]]);
    addPlaces(readCols(gd, null));
  }

  function readHash() {
    const h = new URLSearchParams(location.hash.slice(1));
    const remembered = store.get("guide", "steak");
    st.g = isGuide(h.get("g")) ? h.get("g") : isGuide(remembered) ? remembered : "steak";
    const r = h.get("r");
    st.r = r === "all" || SLUGS.includes(r) ? r : "philadelphia";
    st.q = h.get("q") || ""; st.town = h.get("town") || ""; st.cuisine = h.get("kind") || "";
    st.chains = h.get("chains") === "1"; st.conf = h.get("conf") === "1"; st.bib = h.get("bib") === "1";
    st.sort = h.get("sort") || ""; st.p = h.get("p") || "";
    view = h.get("view") === "map" ? "map" : "list";
  }
  let lastHash = "";
  function saveHash(push = false) {
    const h = new URLSearchParams();
    h.set("g", st.g); h.set("r", st.r);
    if (st.q) h.set("q", st.q); if (st.town) h.set("town", st.town); if (st.cuisine) h.set("kind", st.cuisine);
    if (st.chains) h.set("chains", "1"); if (st.conf) h.set("conf", "1"); if (st.bib) h.set("bib", "1"); if (st.sort) h.set("sort", st.sort);
    if (view === "map") h.set("view", "map"); if (st.p) h.set("p", st.p);
    if (push) history.pushState({ place: true }, "", "#" + h.toString());
    else history.replaceState(history.state, "", "#" + h.toString());
    lastHash = location.hash;
    store.set("guide", st.g);
  }

  function setRegion(slug, note = "") {
    if (slug !== st.r) { st.r = slug; cam = null; }
    if (st.town && TOWN_REGION[st.town] != null && SLUGS[TOWN_REGION[st.town]] !== slug && slug !== "all") st.town = "";
    $("#ex-locmsg").textContent = note;
    shown = 100;
    refreshLookups();
    render();
  }

  // a search with nothing in this region that names a town in another one moves there ("erie" from Philadelphia shows the
  // Northwest). Only when nothing here matches.
  function followTown() {
    if (st.g === "saved" || st.r === "all" || !st.q) return false;
    const q = parse(st.q);
    const ri = q.town != null ? TOWN_REGION[q.town] : null;
    if (ri == null || SLUGS[ri] === st.r) return false;
    setRegion(SLUGS[ri], `Showing ${REGIONS[ri]}, where ${q.town} is.`);
    return true;
  }

  function locate() {
    if (!navigator.geolocation) { $("#ex-locmsg").textContent = "This browser can't share its location."; return; }
    $("#ex-locmsg").textContent = "Finding you…";
    // a fresh fix on every tap (a fix from launch jumps back home after a drive)
    navigator.geolocation.getCurrentPosition(async (pos) => {
      here = { la: pos.coords.latitude, lo: pos.coords.longitude };
      locDenied = false;
      if (!SHAPES) SHAPES = await fetchJSON(`${BASE}/data/pa_shapes.json`).catch(() => null);
      const county = inNY(here) ? countyAt(here) : null;
      let msg = county ? "Sorted by distance from you. Your location stays in this browser."
        : "You're outside Pennsylvania, so distances are long. The map stays on the state. Your location stays in this browser.";
      if (county && st.r !== "all" && st.g !== "saved" && county.region !== regionName(st.r)) {   // you're in another region: go there
        st.r = SLUGS[REGIONS.indexOf(county.region)]; cam = null; st.town = "";
        msg = `You're in ${county.region}, so that's the region shown. ` + msg;
        refreshLookups();
      }
      $("#ex-locmsg").textContent = msg;
      st.sort = county && GUIDES[st.g].sorts.includes("nearest") ? "nearest" : st.sort;
      if (view === "map" && county) { drawMap().then(() => { centerOn(here); drawMap(); }); }
      shown = 100; render();
    }, (err) => {
      locDenied = err.code === 1;
      $("#ex-locmsg").textContent = locDenied
        ? "Location is blocked for this site. Allow it in your browser's settings to sort by distance."
        : "Couldn't get a fix on your location. Try again.";
      if (GUIDES[st.g].needsHere) render();
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 });
  }

  function setView(v) {
    view = v;
    document.querySelectorAll(".ex-view button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
    $("#ex-listwrap").hidden = v !== "list";
    $("#ex-mapwrap").hidden = v !== "map";
    render();
  }

  async function findPlace(id) {   // a shared #p= link: the guides, then the hash's region, then everywhere
    if (byId.has(id)) return byId.get(id);
    const first = st.r === "all" ? -1 : regionIdx(st.r);
    const tries = [first, ...SLUGS.map((_, i) => i).filter((i) => i !== first)].filter((i) => i >= 0);
    for (const ri of tries) {
      await loadDetail(ri);
      const rr = details.get(ri).ids.indexOf(id);
      if (rr < 0) continue;
      await loadRegions([SLUGS[ri]]).catch(() => null);
      return byId.get(id) || null;
    }
    return null;
  }

  function onHistory() {
    if (closingBack) { closingBack = false; saveHash(); return; }
    if (location.hash === lastHash) return;
    if (!location.hash.includes("=")) return;                       // "#main" from the skip link isn't app state
    if (pushed && location.hash === beforePush) { closePlace(true); return; }
    pushed = false;
    const was = st.r;
    readHash(); if (st.r !== was) cam = null;
    refreshLookups(); syncInputs(); shown = 100; setView(view);
    if (st.p) findPlace(st.p).then((p) => { if (p && st.p === p.id) openPlace(p, false); });
    else if (!$("#ex-panel").hidden) closePlace(true);
  }

  function controls() {
    document.querySelectorAll(".ex-guides button").forEach((b) => b.onclick = () => {
      st.g = b.dataset.g; st.sort = ""; shown = 100;
      if (st.g === "near") locate();   // a fresh fix on every tap: a fix from earlier can be miles off after a drive
      render();
    });
    let t = null;
    $("#ex-q").addEventListener("input", (e) => { clearTimeout(t); t = setTimeout(() => { st.q = e.target.value; shown = 100; render(); }, 120); });
    $("#ex-region").onchange = (e) => setRegion(e.target.value);
    $("#ex-sort").onchange = (e) => { st.sort = e.target.value; if (st.sort === "nearest" && !here) locate(); shown = 100; render(); };
    $("#ex-town").onchange = (e) => { st.town = e.target.value; shown = 100; render(); };
    $("#ex-cuisine").onchange = (e) => { st.cuisine = e.target.value; shown = 100; render(); };
    $("#ex-chains").onchange = (e) => { st.chains = e.target.checked; shown = 100; render(); };
    $("#ex-conf").onchange = (e) => { st.conf = e.target.checked; shown = 100; render(); };
    $("#ex-bib").onchange = (e) => { st.bib = e.target.checked; shown = 100; render(); };
    $("#ex-clear").onclick = () => { st.town = st.cuisine = ""; st.chains = st.conf = st.bib = false; syncInputs(); shown = 100; render(); };
    $("#ex-locate").onclick = locate;
    $("#ex-more").onclick = () => { shown += 200; renderList(order()); };
    document.querySelectorAll(".ex-view button").forEach((b) => b.onclick = () => setView(b.dataset.v));
    $("#ex-list").addEventListener("click", (e) => { const b = e.target.closest(".ex-row"); if (b) { const p = byKey.get(b.dataset.key); if (p) openPlace(p); } });
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (!$("#ex-chooser").hidden) hideChooser(); else if (st.p) closePlace();
    });
    window.addEventListener("popstate", onHistory);
    window.addEventListener("hashchange", onHistory);
    mapEvents();
  }
  function syncInputs() {
    $("#ex-q").value = st.q; $("#ex-region").value = st.r; $("#ex-town").value = st.town; $("#ex-cuisine").value = st.cuisine;
    $("#ex-chains").checked = st.chains; $("#ex-conf").checked = st.conf; $("#ex-bib").checked = st.bib;
  }

  // the guide pills scroll sideways on a phone: fade the edge while more are off to the right
  const pills = $(".ex-guides");
  const pillHint = () => pills.classList.toggle("more", pills.scrollLeft + pills.clientWidth < pills.scrollWidth - 4);
  pills.addEventListener("scroll", pillHint, { passive: true });
  window.addEventListener("resize", pillHint);
  pillHint();

  (async () => {
    try { await load(); } catch (e) { $("#ex-loading").textContent = "The restaurant list couldn't load. Refresh to try again."; return; }
    readHash();
    refreshLookups();
    $("#ex-app").querySelectorAll(":disabled").forEach((el) => { el.disabled = false; });
    $("#ex-app").setAttribute("aria-busy", "false");
    syncInputs(); controls();
    setView(view);
    if (st.p) { const want = st.p; const p = await findPlace(want); if (p && st.p === want) { await loadDetail(p.ri); openPlace(p, false); } }
    const idle = window.requestIdleCallback || ((f) => setTimeout(f, 200));
    // the region in view loads in the background, so "All restaurants" and the search are ready when asked for
    idle(() => { if (st.r !== "all") { loadRegions([st.r]).catch(() => null); loadDetail(regionIdx(st.r)); } indexWhenIdle(); });
  })();
})();
