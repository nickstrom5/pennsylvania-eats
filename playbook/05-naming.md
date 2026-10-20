# Naming, icon and palette (Nick's calls, 2026-10-19)

## Name
**Pennsylvania Eats: Restaurants** (chosen), subtitle **Cheesesteaks to Pierogies**, Home Screen **PA Eats** (the full name
truncates). Site: pennsylvania.eatsranked.com (github.io until Nick's Cloudflare CNAME `pennsylvania` resolves).

Checked 2026-10-19:
- Apple's public search API: no app named Pennsylvania Eats, Keystone Eats or Keystone Plates.
- RDAP: pennsylvaniaeats.com and keystoneplates.com unregistered; keystoneeats.com registered 2024-03-26; paeats.com registered
  2018 (paeats.org is a PA food nonprofit, so "PA Eats" is only the Home Screen label, never the name).
- USPTO Trademark Search (tmsearch.uspto.gov, knockout search, not legal advice): "pennsylvania eats", "keystone eats" and "keystone
  plates" rank no mark with both words in the top 50; results are single-word PENNSYLVANIA, EATS and KEYSTONE marks (KEYSTONE has
  live registrations, e.g. serial 97028340 Spark Therapeutics, 90486551 Applied Materials).
- Rejected: Keystone Eats (crowded "Keystone", weaker search), Keystone Plates (breaks the "... Eats" family pattern).
- Avoid: "PA Eats" as the name, "Quaker State", "Penn", "PA Preferred", "The Great American Getaway".

## Icon
Concept **A, a salted soft pretzel** in gold #E8A33D on hemlock #2E4E3F with 6 cream salt crystals (`scripts/icon-concepts.swift`,
sheet `brand/concepts.png`). All three concepts passed `state-prompts/icon-style/check.swift`. B (pierogi) read like a gauge at 60 px;
C (cheesesteak in its roll) looked close to Chicago's hot dog (Guideline 4.3 risk). Nothing like Philly Pretzel Factory's or Auntie
Anne's marks; no team marks.

## Palette
**Penn's Woods**: hemlock #2E4E3F (9.2:1 on white), barn red #A23B2A (6.6:1), cream #F6F1E7, gold #E8A33D only as a fill under
near-black text (2.2:1 as text; hemlock on gold 4.3:1 fails AA). Neutral between Eagles and Steelers fans. Light mode only in the app.
Header element: the state outline (Erie notch, Delaware River edge). No PA.gov keystone logo.

## Data call
Members' clubs (VFW, Legion, fire company socials, ACHD "Social Club-Bar Only", PLCB Club licenses) and Wawa/Sheetz-style
convenience counters stay with the non-restaurants, hidden by default (Nick, 2026-10-19).
