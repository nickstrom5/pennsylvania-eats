"""Places the public can't eat at, and legal-entity names (QA 2026-10-19, P1 #7).

Health permits list every kitchen: employer cafeterias on corporate campuses ("Google Cafe Nuage", "Amazon Block 21", "Boeing Co"),
contract caterers' units ("Bon Appétit at Whitman", "Guckenheimer @ Google", "Ba @ Google Hub 11D0") and school dining ("Basis
Independent Bellevue", "The Cave @ Seattle U"). private_dining() names the rule a listing matches; the pipeline hides those with the
non-restaurants (hand-checked and honored places stay shown).

Records also carry the license holder instead of the trade name ("One Market Restaurant Partners Lp", "Joban & Supreet
Enterprises", "Sars Enterprises Dba Dashpoint Chevron"). The playbook forbids showing a legal entity name (it can be a person's).
entity_fix() returns the trade name when the record has one (after "dba", before an "Lp"/"LLC" tail, or "<Name> Restaurant" before
"Partners"), or None for a bare holder name, which the pipeline drops unless the place is hand-checked or honored.

The same file is in wa-eats and ca-eats; keep the copies identical. Self-test: python3 private_dining.py
"""
import re
import unicodedata


def fold(name):
    """Upper-case ASCII words: accents folded (Bon Appétit -> BON APPETIT, which norm_name splits into "BON APP TIT"),
    apostrophes dropped (Cisco's -> CISCOS), "@" and spaced dashes kept as " @ " separators."""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().upper()
    s = re.sub(r"['’`]", "", s)
    s = re.sub(r"\s+[-–—]+\s+|\s*--\s*|@", " @ ", s)
    s = s.replace("&", " AND ")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9@ ]+", " ", s)).strip()


# Employers whose campus cafeterias hold permits in Washington and California. GOOGLE, AMAZON, MICROSOFT and BOEING: every listing that
# starts with the name is a campus site there (building names: "Amazon Doppler Cafe", "Amazon Brazil", "Google Kirkland"). The rest
# count alone ("Alaska Airlines", "Salesforce"), before a cafeteria word ("Oracle Cafes", "Apple Park Cafe"), before a dash
# ("Cisco - Paradise Cafe") or after "@" ("Cafe Mario @ Nintendo"): "Apple Jack's Bar", "Big Apple Pizza" and "Cisco's" stay.
EMPLOYERS_ANY = r"GOOGLE|AMAZON|MICROSOFT|BOEING"
EMPLOYERS = (EMPLOYERS_ANY + r"|ALASKA AIRLINES|NINTENDO|T MOBILE|EXPEDIA|F5(?: NETWORKS)?|PACCAR|KENWORTH|ZILLOW|META|FACEBOOK|SALESFORCE|"
             r"TABLEAU|WEYERHAEUSER|GATES FOUNDATION|REI CORPORATE|SNAP|APPLE|CISCO|ORACLE|NETFLIX|LINKEDIN|INTEL|NVIDIA|ADOBE|"
             r"GENENTECH|ROCKETDYNE|LOREAL|TESLA|UBER|AIRBNB|VMWARE|INTUIT|PAYPAL|EBAY|YAHOO|DROPBOX|PINTEREST|SERVICENOW|WORKDAY|"
             r"QUALCOMM|AUTODESK|ELECTRONIC ARTS")
CAFE_WORDS = (r"CAFES?|CAFETERIA|COFFEE|BARISTA|KITCHEN|MARKET|DINING|BLOCK|BLDG|BUILDING|CAMPUS|HQ|HEADQUARTERS|RETAIL|CO|COMPANY|CORP|"
              r"CORPORATION|INC|PARK CAFE|DAY 1|BOARD ROOM")
EMPLOYER = re.compile(rf"^(?:{EMPLOYERS_ANY})\b|^(?:{EMPLOYERS})$|^(?:{EMPLOYERS}) (?:{CAFE_WORDS})\b|^(?:{EMPLOYERS}) @|@ (?:{EMPLOYERS})\b|"
                      rf"\bAT (?:{EMPLOYERS_ANY}|NINTENDO|SALESFORCE|GENENTECH|NETFLIX|LINKEDIN)\b")
# contract caterers run private dining rooms ("Ba @ Google" is Bon Appetit's abbreviation there)
CATERER = re.compile(r"\bBON APPETIT\b|\bGUCKENHEIMER\b|\bSODEXO\w*|\bCULINART\b|\bFLIK\b|\bRESTAURANT ASSOCIATES\b|\bCOMPASS (?:ONE|TWO)\b|"
                     r"\bCANTEEN VENDING\b|\bEUREST\b|\bARAMARK\b|^BA @")
# school and campus dining; a school word after "@", "at" or a dash, unless it names a street or neighborhood ("College Area")
_NOT_PLACE = r"(?! (?:AVE|AVENUE|AREA|ST|STREET|BLVD|DR|DRIVE|RD|ROAD|WAY|PARK|HEIGHTS|SQUARE|VILLAGE|PLAZA|CENTER|TOWN|DISTRICT|HILL|HOUSE))"
SCHOOL = re.compile(r"\b(?:MONTESSORI|PRESCHOOL|PRE SCHOOL|BASIS INDEPENDENT|CHILDRENS ACADEMY|ADULT SCHOOL|LAW SCHOOL|HIGH SCHOOL|"
                    r"MIDDLE SCHOOL|ELEMENTARY|CAMPUS DINING|STUDENT CENTER|STUDENT UNION)\b|"
                    rf"@ (?:THE )?(?:[A-Z0-9]+ ){{0,5}}(?:UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|PREPARATORY|CAMPUS|U)\b{_NOT_PLACE}|"
                    rf"\bAT (?:THE )?(?:[A-Z0-9]+ ){{0,5}}(?:UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|PREPARATORY)\b{_NOT_PLACE}")


def private_dining(name):
    """'employer cafeteria', 'contract caterer', 'school dining' or None."""
    f = fold(name)
    if EMPLOYER.search(f):
        return "employer cafeteria"
    if CATERER.search(f):
        return "contract caterer"
    if SCHOOL.search(f):
        return "school dining"
    return None


GENERIC_ONE = {"school", "restaurant", "cafe", "bar", "kitchen", "store", "market", "deli", "grill", "bakery", "pizza", "food", "foods"}
DBA = re.compile(r"^(.+?)[,\s]+(?:D\s?/?\s?B\s?/?\s?A|DOING BUSINESS AS)\.?:?\s+(.+)$", re.I)
ENTITY_TAIL = re.compile(r"(?:[,\s]+(?:L\.?\s?P\.?|LTD\.?|LLC\.?|L\.L\.C\.?|LLP\.?|L\.L\.P\.?|INC\.?|INCORPOR\w*|CORP\.?|CORPORATION))+\s*$", re.I)
HOLDER = re.compile(r"(?:^|\s)(?:PARTNERS|PARTNERSHIP|HOLDINGS?|ENTERPRISES?|VENTURES|OWNER|INVESTMENTS|PROPERTIES)\s*$", re.I)


def entity_fix(name):
    """(trade name, rule) for a legal-entity name; (name, None) when it isn't one; (None, 'holder') when only the holder is known."""
    n, rule = (name or "").strip(), None
    m = DBA.match(n)
    if m:
        t = m.group(2).strip(" ,\"'\u201c\u201d")
        # the trade name, unless it's one generic word ("The Pearl Dba School")
        if len(t) >= 3 and not (len(t.split()) == 1 and t.lower() in GENERIC_ONE):
            n, rule = t[:1].upper() + t[1:], "dba"
        else:
            n, rule = m.group(1).strip(" ,"), "dba"
    if ENTITY_TAIL.search(n):
        n, rule = ENTITY_TAIL.sub("", n).strip(" ,&"), rule or "entity suffix"
        if not re.search(r"[A-Za-z]{2,}", n):   # "E.P & L.P.": nothing but the entity was left (a short real name like A&W never gets here)
            return None, "holder"
    if HOLDER.search(n):
        m = re.match(r"^(.*?\bRestaurant)\b\s+\S.*$", n, re.I)
        if m and len(m.group(1).split()) >= 2:
            return m.group(1), "restaurant partners"
        return None, "holder"
    if rule and n.isupper() and len(n) > 4:   # "GARA & DEAN dba THE POINT": the trade name, not shouted
        n = " ".join(w if len(w) <= 3 and w.isalpha() and w not in ("THE", "AND") else w.capitalize() for w in n.split())
    return n, rule


if __name__ == "__main__":
    want_private = {
        "Google Kirkland": "employer cafeteria", "Google Cafe Nuage": "employer cafeteria", "Amazon Block 21": "employer cafeteria",
        "Amazon Brazil": "employer cafeteria", "Boeing Co": "employer cafeteria", "Alaska Airlines": "employer cafeteria",
        "Microsoft Cafe 34": "employer cafeteria", "Union Cafe @ Amazon": "employer cafeteria", "Cafe Mario @ Nintendo": "employer cafeteria",
        "Apple Park Café": "employer cafeteria", "Apple - Mary 3 Coffee Bar": "employer cafeteria", "Cisco - Paradise Café": "employer cafeteria",
        "Oracle Cafés": "employer cafeteria", "Salesforce": "employer cafeteria", "CDS@Rocketdyne": "employer cafeteria",
        "Ba @ Google Hub 11D0": "employer cafeteria", "Guckenheimer @ Google": "employer cafeteria",
        "Bon Appétit at Whitman": "contract caterer", "Bon Appétit at Banfield Headquarters": "contract caterer",
        "Sodexomagic at KP Sacramento": "contract caterer", "Compass One Lax22 Cafe": "contract caterer",
        "Culinart - Sacred Heart Cathedral Preparatory": "contract caterer",
        "Basis Independent Bellevue": "school dining", "The Cave @ Seattle U": "school dining", "Byte/Sidebar @ Seattle U": "school dining",
        "Bellevue Children's Academy": "school dining", "Corner Cafe @ Pepperdine University": "school dining",
        "The Bistro at Oxnard College": "school dining", "Usc Law School Cafe": "school dining",
        "Campus Dining Services, Cal State Fullerton": "school dining",
        "Bleu Ribbon Kitchen - Le Cordon Bleu San Francisco Campus": "school dining",
    }
    keep = ["Amazonia Cafe", "Apple Green Bistro", "Big Apple Pizza N Grill", "Apple Jack's Bar", "Apple Fritter", "Cisco's", "CISCo Restaurant + Bar",
            "Bon Appetea Cafe", "University of Beer", "University Pizza Company", "Old School Eatery", "School House Restaurant & Tavern",
            "Living Room Coffeehouse - College Area", "Pho Ha #7 University Ave", "College Coffee and Donuts", "Partners Deli and Arcade",
            "Kaiser Grille Palm Springs", "Adobe Creek Brewing", "The Independent Pizzeria", "Tibbitts @ Fern Hill", "Compassion Cafe",
            "Broken Compass Tiki", "Thai Canteen", "Snapper Jack's", "Meta Burger", "Rio Adobe Southwest Cafe", "Paisanos @ Pechanga",
            "bb.q Chicken Apple Park", "Taproom@Bayview Corner", "Campus Drive-In"]
    want_entity = {
        "One Market Restaurant Partners Lp": ("One Market Restaurant", "restaurant partners"),
        "Smoke Eaters Mercado, Lp": ("Smoke Eaters Mercado", "entity suffix"),
        "Holdren's Terrace Ltd Lp": ("Holdren's Terrace", "entity suffix"),
        "Six Pub LP": ("Six Pub", "entity suffix"),
        "Sars Enterprises Dba Dashpoint Chevron": ("Dashpoint Chevron", "dba"),
        "Sodhi Holdings Dba 7-Eleven Store": ("7-Eleven Store", "dba"),
        "Joban & Supreet Enterprises": (None, "holder"), "Do W Chang And Bo W Kim Partners": (None, "holder"),
        "Azusa Owner LP": (None, "holder"), "Partners": (None, "holder"), "E.P & L.P.": (None, "holder"),
        "Merchants Of Venice Enterprises Incorpor": (None, "holder"),
        "Partners Deli and Arcade": ("Partners Deli and Arcade", None), "Help": ("Help", None), "Pizza Co": ("Pizza Co", None),
        "Alpine Inn": ("Alpine Inn", None), "Lucky Corp Cafe": ("Lucky Corp Cafe", None),
        # short real names the first version removed as "holders" (13 A&W restaurants in Washington)
        "A&W": ("A&W", None), "2T": ("2T", None), "4 B's": ("4 B's", None), "I-5 76": ("I-5 76", None), "U.S.K": ("U.S.K", None),
        "Orca Gas &": ("Orca Gas &", None), "GARA & DEAN dba THE POINT": ("The Point", "dba"),
        "SALT LIGHT EGG dba EGGSLUT": ("Eggslut", "dba"), "The Pearl Dba School": ("The Pearl", "dba"),
        'Music Hall Dba "great American Music Hall"': ("Great American Music Hall", "dba"), "HNR Store dba Seatac Marathon": ("Seatac Marathon", "dba"),
    }
    bad = 0
    for n, w in want_private.items():
        g = private_dining(n); bad += g != w
        print("ok  " if g == w else "FAIL", n, "->", g)
    for n in keep:
        g = private_dining(n); bad += g is not None
        print("ok  " if g is None else "FAIL", n, "->", g)
    for n, w in want_entity.items():
        g = entity_fix(n); bad += g != w
        print("ok  " if g == w else "FAIL", n, "->", g)
    print("failures:", bad)
    raise SystemExit(1 if bad else 0)
