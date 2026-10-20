"""Builds site/index.html (the private web leaderboard) from ny-eats/site/index.html (read-only reference; itself generated from
wi-eats/site/index.html), with Pennsylvania's regions, boards, sources and a provisional palette (Penn's Woods: hemlock, barn red,
cream). Every replacement is asserted, so a change in the New York page fails loudly instead of leaving New York text behind. The data
comes split by region (site/pa_index.json + pa-<region>.json), loaded in parallel.
Usage: .venv/bin/python scripts/make-leaderboard.py"""
import os, re, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
s = open(os.path.join(ROOT, "..", "ny-eats", "site", "index.html")).read()


def R(a, b, n=1):
    global s
    c = s.count(a)
    if c != n:
        sys.exit(f"expected {n} of {a[:90]!r}, found {c}")
    s = s.replace(a, b)


def block(start, end, new):
    """Replace s[start marker : end marker) with new (the end marker stays)."""
    global s
    a = s.index(start)
    b = s.index(end, a + len(start))
    s = s[:a] + new + s[b:]


PDA_DISCLAIMER = ("Please remember that any inspection is a &#39;snapshot&#39; of the day and time of the inspection. An inspection conducted on "
                  "any given day may not be representative of the overall, long-term cleanliness of an establishment. Also, at the time of the "
                  "inspection, violations are recorded but are often corrected on site prior to the inspector leaving the establishment.")

# ---------------- head, palette, type
R('<title>New York Restaurant Leaderboard</title>', '<title>Pennsylvania Restaurant Leaderboard</title>')
R('<meta name="description" content="Every restaurant in New York State, ranked on ratings, popularity, honors, slices, bagels, wings, value, estimated sales and official inspection results.">',
  '<meta name="description" content="Every restaurant in Pennsylvania, ranked on ratings, popularity, honors, cheesesteaks, tomato pie, pierogies, PA Dutch, pretzels, diners, value, estimated sales and Allegheny County placards.">')
R('family=Barlow+Condensed:wght@600;700;800&family=Barlow:ital,wght@0,400;0,500;0,600;0,700;1,400',
  'family=Archivo+Narrow:wght@500;600;700&family=Archivo:ital,wght@0,400;0,500;0,600;0,700;1,400')
block('  /* Layout: sticky leaderboard tabs', '}\n', '''  /* Layout: sticky leaderboard tabs over a filter rail + ranked list; one Pennsylvania element, a hemlock band with a barn-red rule.
     Provisional Penn's Woods palette (the app palette is Nick's call): hemlock #2E4E3F (9.2:1 on white), barn red #A23B2A (6.6:1),
     cream #F6F1E7, gold #E8A33D only ever a fill under near-black text (2.2:1 as text; hemlock on gold is 4.3:1, failing AA). Light-only. */
  color-scheme:light;
  --bg:#FFFFFF; --surface:#FFFFFF; --surface-2:#F6F1E7; --surface-3:#ECE4D3;
  --ink:#1B1F1C; --ink-2:#34403A; --muted:#5C655F; --rule:#E3DCCD; --rule-2:#C4BBA7;
  --green:#2E4E3F; --green-2:#3E6553; --gold:#E8A33D; --gold-soft:#F8E3BD; --on-gold:#1B1F1C; --red:#A23B2A;
  --map-fill:#F6F1E7; --map-line:#CFC6B2; --dot-edge:rgba(27,31,28,.35);
  --seq1:#D5E2DA; --seq2:#A3C1AF; --seq3:#6A947C; --seq4:#41685A; --seq5:#2E4E3F;
  --scrim:rgba(27,31,28,.38);
  --shadow:0 1px 2px rgba(27,31,28,.06),0 8px 28px rgba(27,31,28,.10);
  --display:"Archivo Narrow","Arial Narrow","Roboto Condensed",sans-serif;
  --body:"Archivo",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
''')
R('.hmid{padding:22px 16px 18px;border-bottom:6px solid var(--gold);box-shadow:0 4px 0 var(--green)}',
  '.hmid{padding:22px 16px 18px;border-bottom:6px solid var(--green);box-shadow:0 4px 0 var(--red)}')
R('.tab.wi{border-color:#C98F12;background:#FDF5E2}', '.tab.wi{border-color:#B98226;background:#FBF3E3}')
R('.chips.wi .chip[aria-pressed="false"]{background:#FDF5E2;border-color:#C98F12}', '.chips.wi .chip[aria-pressed="false"]{background:#FBF3E3;border-color:#B98226}')
block('.ng{display:inline-grid', '.cnt{display:inline-block', '''.pl{display:inline-block;padding:2px 8px;border-radius:5px;font:700 12.5px/1.5 var(--body);border:2px solid}
.pl.green{background:#E6F2EA;color:#1D5B37;border-color:#2F7A4C} .pl.yellow{background:#FFF3C4;color:#5A4300;border-color:#C9A200}
.pl.red{background:#FBE3DF;color:#8A1F12;border-color:#A23B2A} .pl.other{background:#F1F1F1;color:#444;border-color:#999}
''')
R('.fhint{font-size:12.5px;color:#8A1A2E;margin:0}', '.fhint{font-size:12.5px;color:#8A2A1C;margin:0}')
R('max(260px,calc((100dvh - var(--stickyH) - 120px) * 1.3)));margin:0 auto;aspect-ratio:1.3;', 'max(260px,calc((100dvh - var(--stickyH) - 120px) * 1.7)));margin:0 auto;aspect-ratio:1.7;')
R('@media (max-height:500px){#map{max-width:max(160px,calc((100dvh - var(--stickyH) - 70px) * 1.3))}}', '@media (max-height:500px){#map{max-width:max(160px,calc((100dvh - var(--stickyH) - 70px) * 1.7))}}')

# ---------------- header and filters
R('New York State · map listings as of Sep 2026', 'Pennsylvania · map listings as of Sep 2026')
R('<h1 id="h1">Every New York restaurant, <span class="count">ranked</span></h1>', '<h1 id="h1">Every Pennsylvania restaurant, <span class="count">ranked</span></h1>')
block('<p class="lede" id="lede">Slice joints', '</p>', '<p class="lede" id="lede">Cheesesteak counters, tomato pie bakeries, pierogi kitchens, '
      'Pennsylvania Dutch dining rooms, diners, pretzel bakers, MICHELIN stars and the places in between, from Philadelphia to Pittsburgh and Erie. '
      'Each one is ranked on ratings, popularity, value and estimated sales, with Pennsylvania boards for its food traditions and Allegheny County\'s '
      'official placards, kept to their own county. Flip any leaderboard to see the bottom.')
R('<option value="">All of New York</option>', '<option value="">All of Pennsylvania</option>', 3)
R('for="city">Borough, city or town</label>', 'for="city">City, borough or township</label>')
R('<span class="flabel" id="l-tags">New York guides</span>', '<span class="flabel" id="l-tags">Pennsylvania guides</span>')
R('Only confirmed places (on an official list: a DOHMH or NYSDOH permit, a Buffalo or liquor license, a Suffolk inspection; or in two sources)',
  'Only confirmed places (on an official list: a Philadelphia food license, an Allegheny County permit or a liquor license; or in two sources)')
R('Each ingredient is a 0–100 percentile across New York State.', 'Each ingredient is a 0–100 percentile across Pennsylvania.')
R('NY Score', 'PA Score', s.count('NY Score'))
R('“bagels”…', '“pierogies”…', 2)

# ---------------- constants and state
block('const TAGS = [', '\n', 'const TAGS = [["steak","Cheesesteaks & hoagies",1],["pie","Tomato pie & Old Forge",2],["pierogi","Pierogies & Pittsburgh",4],'
      '["dutch","Pennsylvania Dutch",8],["pretzel","Soft pretzels",16],["diner","Diners",32],["oldest","Oldest taverns & places",64]];')
block('const JUR = [', 'const GR_TXT', 'const JUR = ["", "Philadelphia L&I food license", "Allegheny County Health Department permit", "PLCB liquor license"];\n')
block('const GR_TXT', '\n', 'const PL_COLOR = p => /^Inspected & Permitted$/.test(p) ? "green" : /Consumer Alert/.test(p) ? "yellow" : /Clos/.test(p) ? "red" : "other";')
R('localStorage.getItem("ny-eats")', 'localStorage.getItem("pa-eats")')
R('localStorage.setItem("ny-eats"', 'localStorage.setItem("pa-eats"')

# ---------------- boards
block('const ngPill = ', 'const guide = ', 'const plPill = p => `<span class="pl ${PL_COLOR(p)}" title="Official ACHD placard">${esc(p)}</span>`;\n')
block('  guide("slice", "Slices"', '  {id:"iconic", tab:"Iconic"', '''  guide("steak", "Cheesesteaks", 1, "Cheesesteaks, roast pork and hoagies: places we hand-checked (each with a 2025–26 source), plus places named for them. Who invented the cheesesteak is a legend, not a fact we rank."),
  guide("pie", "Tomato pie", 2, "Philadelphia-style tomato pie and Old Forge-style pizza: hand-checked places plus places named for them."),
  guide("pierogi", "Pierogies", 4, "Pierogies and Pittsburgh's sandwich-and-pierogi classics: hand-checked places plus places named for pierogies."),
  guide("dutch", "PA Dutch", 8, "Pennsylvania Dutch dining rooms and smorgasbords (many close Sundays, which isn't closed): hand-checked places plus places with Dutch or Amish in the name."),
  guide("pretzel", "Pretzels", 16, "Soft pretzel bakeries: hand-checked places plus places named for pretzels."),
  guide("diner", "Diners", 32, "Diners: hand-checked places plus places with diner in the name or listed as a diner."),
''')
R("the MICHELIN Guide New York selection (stars, Bib Gourmand), James Beard awards and nominations 2023–26, America's Classics, and places we verified open at the same address since before 1920.",
  "the MICHELIN Guide's Philadelphia selection (stars, Bib Gourmand; Pittsburgh's first comes in 2027), James Beard awards 2025–26, America's Classics, and places we verified open at the same address for a century.")
block('  {id:"nycgrade", tab:"NYC grades"', '];\n', '''  {id:"achd", tab:"Allegheny placards", top:"Allegheny County: latest placards", bottom:"Allegheny County: Consumer Alert and closure placards", metric:"placard date",
   val:r=>r.ap == null ? null : ({green:3, other:2, yellow:1, red:0})[PL_COLOR(r.ap)] * 1e5 + Number(String(r.ad || "").replace(/-/g, "")) / 1e3, need:r=>r.ap!=null,
   sub:d=>`Allegheny County only, by the Health Department's (ACHD) own placards: green “Inspected & Permitted”, yellow “Consumer Alert” (up to 10 days to correct), red for a closure. Each row shows the placard and the date of that inspection. Placards are ACHD's; we compute no grade. Records through ${esc(META.records_through?.achd || "")}.`,
   show:r=>[plPill(r.ap), `inspected ${esc(r.ad || "")} · ${esc(r.addr || "")}`], dup:"grade"},
''')

# ---------------- rows, badges, stats
R('''  if (r.hc && r.tags) h += `<span class="badge sc">Hand-checked</span>`;''', '''  if (r.hc && r.tags) h += `<span class="badge sc">Hand-checked</span>`;
  if (r.flag & 1) h += `<span class="badge">Convenience counter</span>`;
  if (r.flag & 2) h += `<span class="badge">Members' club</span>`;''')
block('  if (r.gl) bits.push(', '  if (S.board !== "overall"',
      '  if (r.ap) bits.push(`<span class="${dup("grade")}" title="Official Allegheny County placard (ACHD)">${plPill(r.ap)} <i>ACHD ${esc(r.ad || "")}</i></span>`);\n')
block('const TAG_PH = [', '.map(([p, t]) => [norm(p), t]);', '''const TAG_PH = [["cheesesteaks","steak"],["cheesesteak","steak"],["cheese steaks","steak"],["cheese steak","steak"],["roast pork","steak"],["hoagies","steak"],["hoagie","steak"],
  ["tomato pie","pie"],["old forge","pie"],["pierogies","pierogi"],["pierogi","pierogi"],["perogies","pierogi"],["pa dutch","dutch"],["pennsylvania dutch","dutch"],
  ["smorgasbord","dutch"],["soft pretzels","pretzel"],["soft pretzel","pretzel"],["pretzels","pretzel"],["diners","diner"],["oldest","oldest"]]''')
R('''  // "dim sum", "beef on weck", "riggies" mean the New York guides, not words in a name''', '''  // "cheesesteak", "tomato pie", "pierogies" mean the Pennsylvania guides, not words in a name''')
R('''  // "buffalo wings" is the guide; "flushing dim sum" means the town; "flushing ave" or "queens blvd" is a street, not the town''',
  '''  // "scranton pierogies" means the town; "lancaster ave" or "germantown pike" is a street, not the town''')
R('''("flushing dim sum") narrows to it''', '''("scranton pierogies") narrows to it''')
R('''” in New York.''', '''” in Pennsylvania.''')
block('  if (pool.length && board().id === "nycgrade")', '\n  if (pool.length && board().id === "statecrit")', '''  if (board().id === "achd" && !(META.records_through || {}).achd) return "Allegheny County's placards aren't in this build yet: WPRDC's download path is closed to crawlers, so it waits for a hand download.";
  if (pool.length && board().id === "achd") return `${plural(pool.length, "place matches", "places match")} ${what}, but ACHD placards only exist in Allegheny County. ${f.length ? undo + " to see them." : ""}`;''')
block('\n  if (pool.length && board().id === "statecrit")', '\n', '')
R('''(S.region || "All of New York")''', '''(S.region || "All of Pennsylvania")''')
R('''No New York town matches''', '''No Pennsylvania town matches''')
R('''// "Uticaa" is no longer Utica''', '''// "Eriee" is no longer Erie''')
R('''// CITIES is biggest first: "falls" -> Niagara Falls''', '''// CITIES is biggest first: "college" -> State College''')
R('''["name","Borough, city or town"]''', '''["name","City, borough or township"]''')

# ---------------- map
R('fetchJSON("ny_shapes.json")', 'fetchJSON("pa_shapes.json")')
R("[-79.77, -71.85, 40.49, 45.02]", "[-80.52, -74.69, 39.72, 42.27]")
R("const w = c.clientWidth || 600, h = Math.round(w / 1.3);", "const w = c.clientWidth || 600, h = Math.round(w / 1.7);")
R('''${r.city || "New York"}.`;''', '''${r.city || "Pennsylvania"}.`;''')

# ---------------- drawer
block('function calibNote(r) {', '\nfunction sigCard', r'''function calibNote(r) {
  const c = (META.calibration || {}).web || {}, g = k => [c.philly_restaurant_licenses?.[k], c.allegheny_achd?.[k]].filter(Boolean);
  const range = k => { const v = g(k).map(x => x.matched); if (!v.length) return null; const lo = Math.min(...v), hi = Math.max(...v); return lo === hi ? pctTxt(lo) : `${pctTxt(lo)}–${pctTxt(hi)}`; };
  const feed = r.src === "AllThePlaces" || r.src === "DAC", checked = r.hc ? " It's also on our hand-checked list, confirmed open with a 2025–26 source." : "";
  if (r.src === "research") return "This place isn't in the map listings as a place to eat. It's on our hand-checked list, confirmed open with a 2025–26 source, and placed on its street address.";
  if (r.tier === 2) return (r.src === "official" ? `This place comes straight from the ${esc(JUR[r.jur])} list. The map listings we use didn't have it, so its location comes from the record.` : `Matched to an active ${esc(JUR[r.jur])}, so it's confirmed as a licensed or permitted business.`) + checked;
  const via = feed ? (r.tier === 1 ? "brand feed + Google 2021" : "brand feed only") : r.src === "meta" ? (r.tier === 1 ? "Meta + open in Google 2021" : "Meta only") : null;
  const rate = via ? range(via) : null, kind = feed ? "chain store-list listings" : "listings";
  if (!via) return "Kept because it's on our hand-checked list, confirmed open with a 2025–26 source, even though its only map listing comes from a source that's usually unreliable.";
  if (r.tier === 1) return `Found in two independent sources: a map listing and Google's 2021 data. Checked against Philadelphia's restaurant licenses, ${kind} like this matched a licensed business ${rate || "about half"} of the time (the license list also holds schools and corner stores, and many licenses carry a legal name, so that's a floor).` + checked;
  return `Found in one map source only. Checked against Philadelphia's restaurant licenses, single-source ${kind} like this matched a licensed business ${rate || "less than half"} of the time, so this one may be closed or misfiled.` + checked;
}
''')
R('''${r.city || ""} NY`);''', '''${r.city || ""} PA`);''')
R('(percentile vs. all New York places)', '(percentile vs. all Pennsylvania places)')
R("compared with the chain's other New York locations.", "compared with the chain's other Pennsylvania locations.")
R("relative to similar New York places", "relative to similar Pennsylvania places")
R(''' · MICHELIN Guide New York (2025 selection)"] : []),''', ''' · MICHELIN Guide Northeast Cities (Philadelphia, 2025 selection)"] : []), ...(x.green ? ["MICHELIN Green Star"] : []),''')
block('  const nyc = r.nd || r.gl ?', '  const liq = r.liq ?', '''  const PDA = `<p class="note">PDA: “''' + PDA_DISCLAIMER + '''”</p>`;
  const insp = r.county === "Allegheny" ? `<div class="dsec"><h3>Health inspections · Allegheny County Health Department (ACHD)</h3>
      ${r.ap ? `<div class="hero" style="margin:0 0 10px">${plPill(r.ap)}<span class="lbl">official placard at the inspection of ${esc(r.ad || "")}${r.acat ? " · " + esc(r.acat) : ""}</span></div>
      <p class="note">Placards are ACHD's own (green “Inspected &amp; Permitted”, yellow “Consumer Alert”, red for a closure); we compute no grade. Source: WPRDC “Allegheny County Restaurant/Food Facility Inspections”, records through ${esc(META.records_through?.achd || "")}.</p>` : `<p class="note">No ACHD placard matched to this place in this build.</p>`}
      <p class="note">Reports: <a href="https://www.alleghenycounty.us/Services/Health-Department/Food-Safety" target="_blank" rel="noopener">ACHD food safety and inspection reports</a>.</p></div>`
    : r.county === "Philadelphia" ? `<div class="dsec"><h3>Licenses &amp; inspections · City of Philadelphia</h3>
      ${kv([["L&amp;I food license", r.flag & 4 ? "Active" + (x.phl_lic ? " · " + esc(x.phl_lic) : "") + (x.phl_since ? " · first issued " + esc(x.phl_since) : "") : "— (none matched)"]])}
      <p class="note">The Department of Public Health posts inspection reports for three years, one search at a time, with no grade or score; we link to it and don't collect it: <a href="https://philadelphia-pa.healthinspections.us/philadelphia/" target="_blank" rel="noopener">Philadelphia food inspections</a>. Licenses: OpenDataPhilly “Business Licenses”.</p></div>`
    : ["Bucks", "Montgomery"].includes(r.county) ? `<div class="dsec"><h3>Health inspections</h3><p class="note">${esc(r.county)} County inspects its own restaurants and posts reports one search at a time; we link to it and don't collect it: <a href="${r.county === "Bucks" ? "https://bucks-pa.healthinspections.us/" : "https://pa.healthinspections.us/montgomery/"}" target="_blank" rel="noopener">${esc(r.county)} County inspections</a>.</p></div>`
    : `<div class="dsec"><h3>Health inspections</h3><p class="note">The PA Department of Agriculture's search covers this county (with local health departments in some towns), one search at a time; we link to it and don't collect it: <a href="https://www.pafoodsafety.pa.gov/Web/Inspection/PublicInspectionSearch.aspx" target="_blank" rel="noopener">PA Food Safety Inspection Search</a>.</p>${PDA}</div>`;
''')
R('''["Liquor license", "— (none matched)"];''', '''["Liquor license", (META.liqt || []).length > 1 ? "— (none matched)" : "— (PLCB licenses not in this build)"];''')
R('''${dhead(esc(r.city || "New York"), random)}''', '''${dhead(esc(r.city || "Pennsylvania"), random)}''')
R('''.join(", ") || "New York")}''', '''.join(", ") || "Pennsylvania")}''')
R('''    ${nyc}${stt}${sf}''', '''    ${insp}''')
R('''liq, x.buf ? ["Buffalo license", esc(x.buf)] : null,''', '''liq,''')
R('''["New York guides", esc(tagsTxt.join(", "))]''', '''["Pennsylvania guides", esc(tagsTxt.join(", "))]''')
R('esc(JUR[r.jur]) + " license list"', 'esc(JUR[r.jur])')
R('''x.muni ? ["Town or city government", esc(x.muni)] : null''', '''x.muni ? ["Municipality", esc(x.muni)] : null''')
R('''["Locations in New York",''', '''["Locations in Pennsylvania",''')

# ---------------- method cards
block('function methodCards() {', '// ---------------- boot ----------------', r'''function methodCards() {
  const m = META, c = (m.calibration || {}).web || {}, cov = (m.calibration || {}).coverage || {}, rt = m.records_through || {};
  const dv = ["Foursquare only", "BrightQuery only", "Microsoft only", "Foursquare/BrightQuery/Microsoft + Google 2021"].map(k => c.philly_restaurant_licenses?.[k]).filter(Boolean).map(g => g.matched);
  const dropRange = dv.length ? `${Math.round(Math.min(...dv) * 100)}–${Math.round(Math.max(...dv) * 100)}%` : "a small share";
  const cols = [
    ["m", "Official records", [
      ["Philadelphia licenses", `The City of Philadelphia's L&I business licenses (OpenDataPhilly; newest issue ${esc((m.feeds || {}).philly || "")}). Every place in the city that prepares and serves food holds a “Food Preparing and Serving” license, so an active one confirms the place; licensed places the map listings lacked are added from the list. Only trade names are shown, never the legal or owner names on the license. The Health Department's inspection reports are search-only, so we link to them.`],
      ["Allegheny County placards", rt.achd ? `The Allegheny County Health Department's inspections (WPRDC, CC0; records through ${esc(rt.achd)}): the official placard (green, yellow Consumer Alert, red closure) and its date, kept to Allegheny County.` : "The Allegheny County Health Department's placards (WPRDC, CC0) aren't in this build yet: the portal's download path is closed to crawlers, so the files wait for a hand download."],
      ["Rest of the state", "The PA Department of Agriculture and about 100 local agencies (Philadelphia, Chester, Delaware and Erie counties, Allentown, Bethlehem and others) post results in one search-only portal, and Bucks and Montgomery counties in their own. We link to each and never collect them: no inspection boards outside Allegheny County."],
      ["Liquor licenses", (m.liqt || []).length > 1 ? "PLCB's licenses: an active restaurant or bar license confirms a place statewide and says it serves alcohol. Only the premises (trade) name is used." : "PLCB's license export is closed to crawlers, so it's not in this build until a hand download."]]],
    ["s", "Map listings & 2021 snapshot", [
      ["Places statewide", `Overture Maps' open map listings (${esc(m.overture_release || "Sep 2026")} release, which merges Meta, Foursquare, chain store lists and other sources). We keep listings from Meta and from chains' own store lists, and drop Foursquare, BrightQuery and Microsoft listings unless an official list confirms them: checked against Philadelphia's restaurant licenses, only ${dropRange} of those matched a licensed business. Each place sits in its county, one of nine regions and its municipality (city, borough or township); the mailing town is shown and the municipality kept.`],
      ["Ratings, reviews & price level", "Google Maps ratings from the UCSD Google Local research dataset, frozen in September 2021. Each Google listing is matched to one place at most, on a shared distinctive name word nearby. Places that opened later aren't in it, and the rating boards leave them out rather than guess."],
      ["Honors & guides", "The MICHELIN Guide's Philadelphia selection (first revealed Nov 2025: stars, Bib Gourmand, Green Star) and James Beard awards 2025–26 with America's Classics. Pittsburgh enters MICHELIN's Great Lakes edition in 2027, so nothing there yet. The Pennsylvania guides (cheesesteaks, tomato pie, pierogies, PA Dutch, pretzels, diners, oldest taverns) list places named for them until the hand-checked research lands."]]],
    ["e", "Estimated", [
      ["Sales & profit", `Chains use their published U.S. average sales per store (QSR 50, Technomic, company filings and franchise disclosures; ${m.model?.n_chains ?? "50+"} brands found here), scaled by how busy the location is. Independents start from a typical figure for their price level ($600K for $ up to $3.5M for $$$$) and scale with 2021 review volume. Profit applies a typical margin for the segment. Ballparks, not financial statements.`],
      ["Price, cuisine & food cost", "Missing price levels are filled in from the chain's or cuisine's usual Pennsylvania level and marked est. Cuisine comes from the listing's category, the business name and Google categories, so a few will be off. Food cost is the typical share for that cuisine × estimated sales, a benchmark rather than a measurement."]]],
  ];
  $("#srcgrid").innerHTML = cols.map(([t, h, cards]) => `<div class="srccol"><span class="tag ${t}">${h}</span>${cards.map(([h,p]) => `<div class="src"><h3>${h}</h3><p>${p}</p></div>`).join("")}</div>`).join("");
  const G = [["Meta + open in Google 2021","Meta listing, open in Google's 2021 data","kept · two sources"],["Meta only","Meta listing only","kept · listing only"],
    ["brand feed + Google 2021","Chain store list + Google 2021","kept · two sources"],["brand feed only","Chain store list only","kept · listing only"],
    ["Foursquare/BrightQuery/Microsoft + Google 2021","Foursquare / BrightQuery / Microsoft + Google 2021","dropped unless on a list"],["Foursquare only","Foursquare only","dropped unless on a list"],
    ["BrightQuery only","BrightQuery only","dropped unless on a list"],["Microsoft only","Microsoft only","dropped unless on a list"],["Google 2021 says closed","Google showed it closed in 2021","dropped unless on a list"]];
  const cell = (j, k) => { const g = c[j]?.[k]; return g ? `${Math.round(g.matched * 100)}% <span style="color:var(--muted)">of ${fmtN(g.n)}</span>` : "—"; };
  const fc = k => cov[k] ? `${Math.round(cov[k].found * 100)}% of ${fmtN(cov[k].n)}` : "—";
  $("#calib").innerHTML = c.philly_restaurant_licenses ? `<div class="src" style="display:grid;gap:10px"><h3>How the map listings were checked</h3>
    <p>In Philadelphia, where every food business holds an L&I license, each map listing was checked against the active restaurant licenses: same business name nearby, or the same street address with a distinctive name word in common (or the only listing at the address of a license filed under a legal or personal name). The share that matched decides what's kept. The other way round, the map listings held ${fc("philly_restaurant_licenses")} of the city's restaurant licenses; the license list also holds schools, daycares, churches and corner stores, and the licensed places the map lacked were added from the list. The 2018–20 statewide inspection list (PDA, data.pa.gov) is shown for comparison only: it says what existed in 2020, not what's open now.</p>
    <div class="calib"><table><thead><tr><th scope="col">Kind of listing</th><th scope="col" class="r">Philadelphia licenses</th><th scope="col" class="r">PDA list, 2018–20</th><th scope="col">Here</th></tr></thead><tbody>
    ${G.map(([k, l, what]) => `<tr><td>${esc(l)}</td><td class="r num">${cell("philly_restaurant_licenses", k)}</td><td class="r num">${cell("pda_2018_2020", k)}</td><td>${what}</td></tr>`).join("")}</tbody></table></div>
    <p class="note">Matched = on an active license (or the 2018–20 list). These are lower bounds: a real place under a different name on its license counts as a miss. Hand-checked places are kept whatever their source.</p></div>` : "";
}

''')

# ---------------- build: region files merged in order
block('  const GRL = m.grades || [];', '\n  pctRank(rows', '  for (const [i, p, d, cat] of sp.ac || []) if (rows[i]) Object.assign(rows[i], {ap: p, ad: d, acat: cat || null});')
R('o.liq = C.liq[i] || 0; o.hc = C.hc[i] || 0;', 'o.liq = C.liq[i] || 0; o.hc = C.hc[i] || 0; o.flag = C.flag[i] || 0;')
R('''// "st albans", "saint albans" and "St. Albans" are one place''', '''// "st marys", "saint marys" and "St. Marys" are one place''')
block('             "slice", "slices", "bagel"', ']));', '''             "cheesesteak", "cheesesteaks", "steaks", "hoagie", "hoagies", "pork", "tomato", "pie", "pierogi", "pierogies", "pretzel", "pretzels",
             "dutch", "amish", "smorgasbord", "diner", "diners", "tavern", "tap", "brewery"''')
R('''</span> New York restaurants, ranked`;''', '''</span> Pennsylvania restaurants, ranked`;''')
R('fetchJSON("ny_index.json")', 'fetchJSON("pa_index.json")')
left = []
for word in ("New York", "NYC", "NY Score", "ny_", "ny-eats", "DOHMH", "NYSDOH", "Suffolk", "Buffalo", "Wisconsin", "bagel", "Long Island", "borough"):
    hits = [m.start() for m in re.finditer(re.escape(word), s)]
    if hits:
        left.append(word)
        print(f"note: {len(hits)} '{word}' left, e.g. {s[max(0, hits[0]-70):hits[0]+40]!r}")
open(os.path.join(ROOT, "site", "index.html"), "w").write(s)
print("wrote site/index.html", len(s) // 1024, "KB")
