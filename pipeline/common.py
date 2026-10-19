"""Shared helpers: name keys, casing, name matching, cuisine rules and money benchmarks.

Adapted from ny-eats/pipeline/common.py (from ct-eats, wi-eats and chi-eats): same rules, with Pennsylvania words, places and cuisines.
"""
import os, re
from rapidfuzz import fuzz

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
PA = os.path.join(DATA, "pa")

STOP = {"THE", "INC", "LLC", "CO", "CORP", "RESTAURANT", "RESTAURANTS", "AND", "OF", "LTD", "CAFE", "#"}


def norm_name(s):
    s = (s or "").upper().replace("&", " AND ").replace("'S", "S").replace("’S", "S")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\b\d{2,}\b", " ", s)  # store numbers like "#1234"
    return " ".join(w for w in s.split() if w not in STOP)


SMALL = {"of", "and", "the", "on", "at", "in", "de", "la", "el", "y", "du"}
NOT_ACRONYM = {"mr", "mrs", "ms", "st", "dr", "jr", "sr", "pl", "ct", "rd", "ln", "blvd", "pkwy", "hwy", "sq", "cr", "th", "nd", "mc",
               "cty", "hwy", "trl", "cir", "ste", "fl", "wy", "pkwy", "rr", "rt", "ne", "nw", "se", "sw"}
UNIT_TAIL = re.compile(r"(\s+(BLDG|BLD|STE|SUITE|FL|FLR|FLOOR|UNIT|RM|LOWER LEVEL|LL|APT|SPACE)\b.*$)|(\s+\d+\s*$)", re.I)


def _case(w, first, addr):
    lw = w.lower()
    if not lw:
        return w
    if first is False and lw in SMALL and not addr:
        return lw
    if lw == "bj's":
        return "BJ's"
    core = re.sub(r"[^a-z']", "", lw)
    if re.fullmatch(r"(bbq|ii|iii|iv|usa|jj|kfc|ihop|tgi|atm|llc|bp|dj|pb|vfw|amvets|ymca|uw|[a-z])", core):
        return w.upper()
    if addr and re.fullmatch(r"(ne|nw|se|sw|us|ct|rt|rte)", core):
        return w.upper()
    if re.fullmatch(r"(dj|bj|jj)'s", core):
        return core[:2].upper() + core[2:] + w[len(core):]
    if not addr and core not in NOT_ACRONYM and re.fullmatch(r"[b-df-hj-np-tv-xz]{2,4}", core) and not re.search(r"(.)\1\1", core):
        return w.upper()
    if re.match(r"^mc[a-z]{3}", lw):
        return "Mc" + lw[2].upper() + lw[3:]
    if re.match(r"^o'[a-z]{2}", lw):
        return "O'" + lw[2].upper() + lw[3:]
    t = lw[:1].upper() + lw[1:]
    return re.sub(r"([-(.&])([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)


def nice(s, addr=False):
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = re.sub(r"(?i)\b(\w+)IES'S\b", r"\1IE'S", s)
    s = re.sub(r"(?i)'S\s+'S\b", "'S", s)
    s = re.sub(r"(?i)\bMC\s+([A-Z]{2,})", r"MC\1", s)
    if addr:   # "55 E MAIN ST STE 4" -> drop the dangling unit / stray number
        m = re.match(r"^(\d+[A-Z]?(?:\s*-\s*\d+)?\s+.+?\b(?:ST|AVE|BLVD|DR|RD|PL|CT|PKWY|TER|WAY|LN|HWY|PLZ|SQ|CIR|TRL|MARKET)\b)", s, re.I)
        if m and UNIT_TAIL.search(s[m.end():]):
            s = m.group(1)
    if not s:
        return s
    out = []
    words = s.split(" ")
    for i, w in enumerate(words):
        parts = re.split(r"([/@&])", w)
        cased = "".join(p if p in "/@&" else _case(p, None if i == 0 and j == 0 else False, addr) for j, p in enumerate(parts))
        if i and re.fullmatch(r"\(?ct\)?[\d,]*", w.lower()) and (i == len(words) - 1 or "(" in w):   # the state code
            cased = w.upper()
        out.append(cased)
    return " ".join(out).replace("Chick-Fil-A", "Chick-fil-A")


def canon_city(c):
    """One spelling per city, borough, township or village: "City of X" -> X, "Bensalem Twp" -> Bensalem, case fixes."""
    if not isinstance(c, str) or not c.strip():
        return None
    c = re.sub(r"(?:,\s*|\s+)(?:PA|Pa\.?|P\.A\.|Penna\.?|Pennsylvania)$", "", c.strip(), flags=re.I)
    c = re.sub(r"^(?:City|Town|Borough|Township|Twp\.?|Boro)\s+of\s+", "", c, flags=re.I)
    c = re.sub(r"\s+(?:Twp|Township|Boro|Borough)\.?$", "", c, flags=re.I)
    c = nice(c) if c.isupper() or c.islower() else c
    c = re.sub(r"\b(?:Saint|St)\b\.?\s*", "St. ", c)
    c = re.sub(r"\bMt\b\.?\s*", "Mount ", c)
    c = re.sub(r"\bHts\b\.?", "Heights", c)
    c = re.sub(r"\bFt\b\.?\s*", "Fort ", c)
    c = re.sub(r"\bN\.?\s+(?=[A-Z])", "North ", c); c = re.sub(r"\bS\.?\s+(?=[A-Z])", "South ", c)
    c = re.sub(r"\bE\.?\s+(?=[A-Z])", "East ", c); c = re.sub(r"\bW\.?\s+(?=[A-Z])", "West ", c)
    c = re.sub(r"\s+", " ", c).strip()
    key = re.sub(r"[^a-z]", "", c.lower())
    return {"philadelphia": "Philadelphia", "phila": "Philadelphia", "philly": "Philadelphia", "phl": "Philadelphia",
            "pittsburgh": "Pittsburgh", "pgh": "Pittsburgh", "pitt": "Pittsburgh", "wilkesbarre": "Wilkes-Barre",
            "kingofprussia": "King of Prussia", "mckeesrocks": "McKees Rocks", "mckeesport": "McKeesport", "mcmurray": "McMurray",
            "mcdonald": "McDonald", "mcconnellsburg": "McConnellsburg", "mckean": "McKean", "mcsherrystown": "McSherrystown",
            "mcadoo": "McAdoo", "mcclure": "McClure", "mcveytown": "McVeytown", "mckeesrock": "McKees Rocks",
            "stroudsburg": "Stroudsburg", "eaststroudsburg": "East Stroudsburg", "statecollege": "State College",
            "newhope": "New Hope", "conshohocken": "Conshohocken", "westconshohocken": "West Conshohocken",
            "bryanmawr": "Bryn Mawr", "brynmawr": "Bryn Mawr", "bala cynwyd": "Bala Cynwyd", "balacynwyd": "Bala Cynwyd",
            "feastervilletrevose": "Feasterville-Trevose", "feasterville": "Feasterville-Trevose", "trevose": "Feasterville-Trevose",
            "lansdale": "Lansdale", "plymouthmeeting": "Plymouth Meeting", "fortwashington": "Fort Washington",
            "huntingdonvalley": "Huntingdon Valley", "glenmills": "Glen Mills", "newtownsquare": "Newtown Square",
            "westchester": "West Chester", "kennettsquare": "Kennett Square", "chaddsford": "Chadds Ford",
            "camphill": "Camp Hill", "mechanicsburg": "Mechanicsburg", "newcumberland": "New Cumberland", "jimthorpe": "Jim Thorpe",
            "scranton": "Scranton", "dunmore": "Dunmore", "clarkssummit": "Clarks Summit", "oldforge": "Old Forge",
            "laceyville": "Laceyville", "bethelpark": "Bethel Park", "mtlebanon": "Mount Lebanon", "mountlebanon": "Mount Lebanon",
            "upperstclair": "Upper St. Clair", "uppersaintclair": "Upper St. Clair", "cranberrytownship": "Cranberry Township",
            "cranberrytwp": "Cranberry Township", "warrendale": "Warrendale", "wexford": "Wexford", "gibsonia": "Gibsonia",
            "monroeville": "Monroeville", "northhuntingdon": "North Huntingdon", "irwin": "Irwin", "greensburg": "Greensburg",
            "newkensington": "New Kensington", "lowerburrell": "Lower Burrell", "erie": "Erie", "harrisburg": "Harrisburg",
            "lancaster": "Lancaster", "york": "York", "reading": "Reading", "allentown": "Allentown", "bethlehem": "Bethlehem",
            "easton": "Easton", "altoona": "Altoona", "johnstown": "Johnstown", "williamsport": "Williamsport",
            "hershey": "Hershey", "gettysburg": "Gettysburg", "intercourse": "Intercourse", "birdinhand": "Bird-in-Hand",
            "lititz": "Lititz", "ephrata": "Ephrata", "strasburg": "Strasburg", "levittown": "Levittown", "doylestown": "Doylestown",
            "newtown": "Newtown", "yardley": "Yardley", "langhorne": "Langhorne", "bensalem": "Bensalem", "bristol": "Bristol",
            "morrisville": "Morrisville", "norristown": "Norristown", "kingofprussi": "King of Prussia", "wayne": "Wayne",
            "media": "Media", "springfield": "Springfield", "havertown": "Havertown", "drexelhill": "Drexel Hill",
            "upperdarby": "Upper Darby", "lansdowne": "Lansdowne", "ardmore": "Ardmore", "narberth": "Narberth",
            "wynnewood": "Wynnewood", "jenkintown": "Jenkintown", "abington": "Abington", "willowgrove": "Willow Grove",
            "horsham": "Horsham", "hatboro": "Hatboro", "ambler": "Ambler", "blue bell": "Blue Bell", "bluebell": "Blue Bell",
            "collegeville": "Collegeville", "pottstown": "Pottstown", "phoenixville": "Phoenixville", "exton": "Exton",
            "downingtown": "Downingtown", "coatesville": "Coatesville", "malvern": "Malvern", "berwyn": "Berwyn", "paoli": "Paoli"}.get(key, c)


def town_key(c):
    k = c.lower().replace(".", " ")
    k = re.sub(r"^(e|n|s|w)\s+", lambda m: {"e": "east ", "n": "north ", "s": "south ", "w": "west "}[m.group(1)], k)
    k = re.sub(r"\bmt\b", "mount", k); k = re.sub(r"\bhts\b", "heights", k); k = re.sub(r"\bft\b", "fort", k)
    return re.sub(r"[^a-z]", "", k)


# words that don't identify a business on their own: a name match needs a shared word outside this list
GENERIC = set("""PIZZA PIZZERIA PHO TACO TACOS TAQUERIA GRILL GRILLE KITCHEN EXPRESS HOUSE COFFEE BAR PUB TAVERN FOOD FOODS STORE SHOP MARKET
DELI BAKERY CHICKEN FISH BBQ SUSHI THAI CHINESE MEXICAN INDIAN ITALIAN GYROS BURGER BURGERS WINGS DONUTS DONUT BEEF TEA JUICE
NORTH SOUTH EAST WEST PARK SQUARE STATION UNION TOWN VILLAGE STREET AVE AVENUE CENTER PLAZA LAKE LAKES RIVER BAY
NEW OLD BEST GOLDEN LITTLE BIG KING STAR ORIGINAL FAMOUS FRESH HOT GRAND LA EL LOS LAS DE DEL ON THE Y AT OF LOUNGE SNACK SNACKS
NOODLE NOODLES ASIAN SHRIMP PATIO CLUB SUPPER INN LODGE SALOON RESORT BREWING BREWERY COMPANY BREW HALL CUSTARD FROZEN CHEESE CURDS
FRY BRATS BRAT WISCONSIN BAKE CAFETERIA CORNER SPOT STOP PLACE ROOM SPORTS FAMILY STEAKHOUSE STEAK DINER CREAMERY ICE CREAM
MKE MILW HUT WOK MEAL FUSION BUFFET CUISINE EATS EATERY APIZZA LOBSTER LOBSTERS CLAM CLAMS SHACK DOCK DOCKS HARBOR HARBOUR SHORE
SHORELINE PENNSYLVANIA PENN PENNA PA PHILLY PHILADELPHIA PITTSBURGH PGH KEYSTONE ALLEGHENY SUSQUEHANNA LEHIGH POCONO POCONOS
DUTCH AMISH STEAK STEAKS CHEESESTEAK CHEESESTEAKS HOAGIE HOAGIES PRETZEL PRETZELS PIEROGI PIEROGIES WATER ICE ITALIAN SLICE SLICES
BAGEL BAGELS HOTS GRINDER GRINDERS DRIVE IN DRIVEIN POUND WHARF MARINA SEAFOOD COVE POINT LANDING ROUTE RT HILL HILLS VALLEY
TOWNSHIP TWP BORO BOROUGH COLONIAL TAVERNA TRATTORIA OSTERIA BRICK OVEN COAL FIRED WOOD""".split())


def _stems(s):
    return {w if w in GENERIC else (w[:-1] if len(w) > 3 and w.endswith("S") else w) for w in s.split()} - GENERIC


def name_sim(a, b):
    ours, theirs = set(a.split()), set(b.split())
    distinct = (_stems(a) - GENERIC) & (_stems(b) - GENERIC)
    joined = a.replace(" ", "") == b.replace(" ", "") or fuzz.ratio(a.replace(" ", ""), b.replace(" ", "")) >= 92
    if joined:
        return 96
    if not distinct and fuzz.ratio(a, b) < 95:   # nothing but generic words in common: not the same business
        return 60
    s_set = fuzz.token_set_ratio(a, b)
    # token_set_ratio is 100 whenever one name's words are a subset of the other's: cap it unless the overlap is a real share of both
    if len(ours & theirs) < 0.5 * min(len(ours), len(theirs)) + 0.5 or len(ours & theirs) < 0.4 * max(len(ours), len(theirs)):
        s_set = min(s_set, 72)
    return max(s_set, fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b))


FOODCAT = re.compile(r"\b(restaurant|cafe|coffee|bakery|pizza|bar|pub|diner|deli|taco|ice cream|donut|dessert|sandwich|food court|caterer|tea house|bistro|brewpub|brewery|juice|grill|takeout|buffet|bagel|chicken|seafood|steak|hot dog|tavern|lounge|gastropub|snack|yogurt|creperie|patisserie|chocolate|confectionery|bubble tea|night club|beer|wine|bbq|barbecue|pie|pastry|popcorn|tamale|churro|takeaway|tortilleria|supper club|custard|fish & chips|cheesesteak)\b", re.I)
NOTFOOD = re.compile(r"^(?:Tower|Museum|Stadium|Convention|Hotel|Performing|Theater|Hospital|University|Corporate|Observation|Tourist|Airport|Casino|Gas station|Grocery|Supermarket|Convenience|Liquor store|Event|Banquet|Park|Arena)\b")

# Name keywords -> cuisine. Whole words only, so HOSPITAL isn't "PITA", BREWING isn't "WING", BOWLING isn't "BOWL".
# Order matters: specific before general.
_W = lambda words: re.compile(r"\b(?:" + words + r")\b")
CUISINE_RULES = [
    ("Hot Dogs", _W(r"HOT ?DOGS?|DOGS|WIENERS?|WEENIES?|FRANKS|FRANKFURTERS?|SAUSAGES?|RED HOTS?|BLACKIES|RAWLEYS|SUPER DUPER")),
    ("Pizza", _W(r"PIZZA|PIZZAS|PIZZERIA|PIZZERIAS|APIZZA|APIZZERIA|DOMINOS|PAPA JOHNS|LITTLE CAESARS?|COLONY GRILL|BAR PIE|FRANK PEPE|PEPES PIZZERIA|SALLYS APIZZA")),
    ("Korean", _W(r"KOREAN?|KOREA|KIMCHI|BIBIMBAP|SEOUL|GOGI|BULGOGI|KBBQ|CUPBOP")),
    ("Thai", _W(r"THAI|SIAM|BANGKOK|ISAAN|ISAN")),
    ("Vietnamese", _W(r"PHO|VIETNAMESE|VIETNAM|SAIGON|BANH MI|BANH|HANOI")),
    ("Coffee & Café", _W(r"COFFEE|ESPRESSO|STARBUCKS|DUNKIN|CAFFE|TEA|TEAS|TEAHOUSE|BOBA|COLECTIVO|STONE CREEK|ANODYNE|STEEP AND BREW|BRADBURYS|LATTE|ROASTERS?|ROASTING|KAFFE|KAFFEE")),
    ("Bakery & Sweets", _W(r"BAKERY|BAKERIES|BAKESHOP|BAKE SHOP|BAKEHOUSE|PASTRY|PASTRIES|PATISSERIE|DONUTS?|DOUGHNUTS?|PANADERIA|CAKES?|CUPCAKES?|COOKIES?|DESSERTS?|ICE CREAM|GELATO|GELATERIA|PALETERIA|PALETAS|YOGURT|FROYO|CREPES?|CREPERIE|SWEETS|CHOCOLATE|CHOCOLATIER|CINNABON|BAGELS?|CREAMERY|CHURROS?|PIES|KRINGLE|CONFECTIONS?|MICHOACANA|DAIRY QUEEN|BASKIN")),
    ("Mexican", _W(r"TAQUERIA|TAQUERIAS|TACOS?|MEXICAN[AO]?|MEXICO|BURRITOS?|BIRRIA|BIRRIERIA|CARNITAS|TAMALES?|TORTAS?|ELOTES?|MARISCOS|CHIPOTLE|QDOBA|AZTECA|JALISCO|MICHOACAN|GUADALAJARA|OAXACA|GUERRERO|PUEBLA|CANTINA|TORTILLERIA|ANTOJITOS?|QUESADILLAS?|NACHOS?|HUARACHES?|FONDA|EL TORO|TAQUERIA")),
    ("Latin & Caribbean", _W(r"CUBAN[AO]?|CUBA|PUERTO RICAN|BORINQUEN|CARIBBEAN|JAMAICAN?|JERK|HAITIAN?|PERUVIAN|PERU|COLOMBIAN[AO]?|COLOMBIA|SALVADOREN[AO]|PUPUSAS?|PUPUSERIA|ARGENTIN[AE]|ARGENTINIAN|VENEZUELAN?|AREPAS?|BRAZILIAN?|EMPANADAS?|DOMINICAN|GUATEMALTEC[AO]|HONDUREN[AO]|ECUADORIAN|LATIN[AO]?|CEVICHE")),
    ("Japanese & Sushi", _W(r"SUSHI|RAMEN|JAPANESE|JAPAN|IZAKAYA|TERIYAKI|HIBACHI|OMAKASE|TOKYO|BENTO|UDON|YAKITORI|KATSU|SAKE|TEMPURA|SASHIMI|TEPPANYAKI|KYOTO|OSAKA|BENIHANA")),
    ("European", _W(r"PELMENI|PIEROGI|PIEROGIES|HOLLANDER|BENELUX|CENTRAAL|BELGIAN|DUTCH|MELTING POT|FONDUE|SCHNITZEL|BIERGARTEN|BIERHALLE|RATSKELLER|RATHSKELLER|SERBIAN|POLISH|POLSKI|POLSKA|STAROPOLSKA|PODLASIE|CRACOVIA|KIELBASA|GERMAN|BAVARIAN|PORTUGUESE|ALBANIAN")),
    ("Chinese", _W(r"CHINA|CHINESE|EGG ROLLS?|WOK|DUMPLINGS?|DIM SUM|PANDA EXPRESS|HUNAN|SZECHUAN|SICHUAN|MANDARIN|CANTONESE|KUNG PAO|HONG KONG|BEIJING|SHANGHAI|HOT ?POT|CHOP SUEY|BAO|LO MEIN|WONTON|PEKING|YUNNAN")),
    ("South Asian", _W(r"INDIA|INDIAN(?! HEAD| NECK| RIVER| WELL| HILL| TRAIL| ROCK| LAKE| POINT)|TANDOOR|TANDOORI|CURRY|CURRIES|MASALA|BIRYANI|NEPAL|NEPALI|NEPALESE|HIMALAYAN?|PAKISTANI?|BOMBAY|MUMBAI|DELHI|PUNJAB|PUNJABI|KATHMANDU|MOMOS?|CHAAT|SAMOSAS?|BENGALI|SRI LANKAN?|DOSA|TIKKA")),
    ("Mediterranean & Middle Eastern", _W(r"GREEK|GYROS?|MEDITERRANEAN|MEDITERANNEAN|FALAFEL|SHAWARMA|MIDDLE EASTERN|LEBANESE|HALAL|KABOBS?|KEBABS?|KABABS?|PERSIAN|TURKISH|ISRAELI|HUMMUS|PITA|PITAS|ZAATAR|SYRIAN|AFGHAN|ARABIC|ARABIAN|ATHENS|OLYMPIA|PARTHENON|AEGEAN|NAF NAF|MEZZE|ASSYRIAN|YEMENI|ZAROB")),
    ("African", _W(r"AFRICAN?|AFRICA|ETHIOPIAN?|NIGERIAN?|ERITREAN?|GHANAIAN|SENEGALESE|SOMALI|MOROCCAN|EGYPTIAN|KENYAN|CAMEROONIAN|JOLLOF|SUYA")),
    ("Italian", _W(r"ITALIAN[AO]?|ITALIA|TRATTORIA|OSTERIA|PASTA|RISTORANTE|VINO|NONNA|CUCINA|ENOTECA|SPAGHETTI|NAPOLI|NAPOLETANA|SICILIAN|TUSCANY|TUSCAN|FORNO|MAGGIANOS|OLIVE GARDEN|BARTOLOTTA")),
    ("Burgers", _W(r"BURGERS?|HAMBURGERS?|CHEESEBURGERS?|LOUIS LUNCH|MCDONALDS|MC DONALDS|WENDYS|WHITE CASTLE|FIVE GUYS|SHAKE SHACK|SMASHBURGER|PATTY|PATTIES|STEAK N SHAKE|SONIC|ARBYS|CHECKERS|JACK IN THE BOX|BURGER KING|PLAN B")),
    ("Seafood", _W(r"SEAFOOD|FISH|FISHERIES|FISHERY|SHRIMP|OYSTERS?|CRABS?|CRAB|LOBSTERS?|CLAMS?|CLAM SHACK|CHOWDER|SCALLOPS?|CATFISH|CAJUN|BOIL|POKE|LONG JOHN SILVERS|CAPTAIN DS|LOBSTER POUND|RAW BAR")),
    ("Chicken & Wings", _W(r"CHICKEN|WINGS|POPEYES|KFC|CHURCHS|RAISING CANES?|CHICK FIL A|BROASTED|WINGSTOP|NASHVILLE HOT|KRISPY KRUNCHY")),
    ("BBQ", _W(r"BBQ|BAR B Q|BAR BQ|BAR B QUE|BAR BE CUE|BAR B CUE|BARBECUE|BARBEQUE|RIBS|SMOKEHOUSE|SMOKED|BRISKET|FAMOUS DAVES")),
    ("Sandwiches & Deli", _W(r"SANDWICH|SANDWICHES|DELI|DELICATESSEN|SUBWAY|JIMMY JOHNS|POTBELLY|JERSEY MIKES|FIREHOUSE SUBS|SUBS|HOAGIES?|GRINDERS?|PANERA|CORNER BAKERY|CHEESE ?STEAKS?|PHILLY|CAPRIOTTIS|SUB SHOP|WILD ROOTS")),
    ("Steakhouse", _W(r"STEAK|STEAKS|STEAKHOUSE|STEAK HOUSE|CHOPHOUSE|CHOP HOUSE|RUTHS CHRIS|CAPITAL GRILLE|MORTONS|TEXAS ROADHOUSE|LONGHORN|OUTBACK|PRIME RIB")),
    ("Soul & Southern", _W(r"SOUL|SOUTHERN|CREOLE|GUMBO|BISCUITS?|GRITS|CHICKEN WAFFLES")),
    ("Healthy & Vegan", _W(r"VEGAN|VEGETARIAN|SALADS?|JUICE|JUICERY|SMOOTHIES?|SWEETGREEN|PLANT BASED|ACAI|HEALTHY|ORGANIC|JAMBA|NOODLES AND COMPANY")),
    ("Breakfast & Diner", _W(r"BREAKFAST|PANCAKES?|DINER|BRUNCH|EGGS?|IHOP|DENNYS|PERKINS|YOLK|OMELETTES?|OMELETS?|SUNRISE|MORNING|WAFFLES?|GRIDDLE|SKILLETS?|MAMA DS|MY FAVORITE MUFFIN|BAGEL")),
    ("European", _W(r"POLISH|POLSKA|UKRAINIAN|GERMAN|BAVARIAN|SERBIAN|BOSNIAN|CROATIAN|RUSSIAN|FRENCH|BISTRO|BRASSERIE|IRISH|BRITISH|SWEDISH|NORWEGIAN|NORSKE|DANISH|SPANISH|TAPAS|PORTUGUESE|EUROPEAN|LITHUANIAN|CZECH|HUNGARIAN|ROMANIAN|GEORGIAN|PIEROGI|PIEROGIES|HAUS|BIERGARTEN|BEER GARDEN|BIERHALLE|RATHSKELLER|STUBE|SCHNITZEL|MADERS|KEGELS|SWISS|SLOVENIAN|FONDUE")),
    ("Bar & Pub", _W(r"PUB|TAVERN|BAR|SALOON|LOUNGE|TAP|TAPS|TAPROOM|TAPHOUSE|BREWING|BREWERY|BREWPUB|BEER|ALE HOUSE|GASTROPUB|COCKTAILS?|WINE|WINERY|DISTILLERY|DISTILLING|INN|PADDY|BARS")),
]
GCAT = [(c, re.compile(p)) for c, p in [
    ("Pizza", r"Pizza"), ("Coffee & Café", r"Coffee|Cafe|Espresso|Tea house|Bubble tea"),
    ("Bakery & Sweets", r"Bakery|Donut|Dessert|Ice cream|Pastry|Cake|Frozen yogurt|Chocolate|Bagel|Pie shop|Candy"),
    ("Mexican", r"Mexican|Taco|Burrito|Tex-Mex|Taqueria"), ("Latin & Caribbean", r"Latin|Caribbean|Cuban|Puerto Rican|Jamaican|Peruvian|Colombian|Salvadoran|Brazilian|Venezuelan|Argentin|Haitian"),
    ("Japanese & Sushi", r"Japanese|Sushi|Ramen"), ("Chinese", r"Chinese|Cantonese|Dim sum|Szechuan|Dumpling|Hot pot"),
    ("Korean", r"Korean"), ("Thai", r"Thai"), ("Vietnamese", r"Vietnamese|Pho"), ("South Asian", r"Indian|Pakistani|Nepal|Bangladeshi|Sri Lankan"),
    ("Mediterranean & Middle Eastern", r"Mediterranean|Middle Eastern|Greek|Lebanese|Falafel|Halal|Turkish|Persian|Israeli|Afghan|Shawarma"),
    ("African", r"African|Ethiopian|Nigerian|Moroccan|Eritrean|Somali"), ("Italian", r"Italian"),
    ("Hot Dogs", r"Hot dog"), ("Burgers", r"Hamburger|Burger"), ("Seafood", r"Seafood|Fish|Oyster|Poke|Cajun"),
    ("Chicken & Wings", r"Chicken"), ("BBQ", r"Barbecue"), ("Steakhouse", r"Steak"),
    ("Soul & Southern", r"Soul food|Southern"), ("Sandwiches & Deli", r"Sandwich|Deli|Cheesesteak"),
    ("Healthy & Vegan", r"Vegan|Vegetarian|Health food|Salad|Juice"), ("Breakfast & Diner", r"Breakfast|Brunch|Diner|Pancake"),
    ("European", r"French|German|Polish|Ukrainian|Spanish|Portuguese|Tapas|Irish|European|Eastern European|Serbian|Russian|Bistro|Scandinavian|Swiss|Belgian|Dutch|Fondue|Albanian"),
    ("Bar & Pub", r"Bar\b|Pub|Brewpub|Brewery|Tavern|Gastropub|Wine bar|Cocktail|Beer"),
    # a primary "American" category is an answer too, so a later "Bar" tag doesn't turn a family restaurant into a pub
    ("American & Other", r"American restaurant|Eclectic restaurant|Fine dining restaurant|Family restaurant|Southwestern"),
]]


def cuisine(name_key, gcats, raw=""):
    for c, pat in CUISINE_RULES:
        if pat.search(name_key or ""):
            return c
    cats = [x for x in (gcats or "").split("|") if x]
    for cat in cats:
        for c, pat in GCAT:
            if pat.search(cat):
                return c
    if re.search(r"\bCAF[EÉ]\b", (raw or "").upper()) and not cats:
        return "Coffee & Café"
    return "American & Other"


# Typical food-cost % by cuisine (industry rule-of-thumb ranges, midpoint)
FOOD_COST = {"Pizza": 26, "Coffee & Café": 24, "Bakery & Sweets": 25, "Mexican": 28, "Latin & Caribbean": 30,
             "Japanese & Sushi": 34, "Chinese": 30, "Korean": 32, "Thai": 30, "Vietnamese": 30, "South Asian": 28,
             "Mediterranean & Middle Eastern": 30, "African": 30, "Italian": 29, "Hot Dogs": 31, "Burgers": 31,
             "Chicken & Wings": 33, "Seafood": 36, "BBQ": 34, "Steakhouse": 38, "Soul & Southern": 32,
             "Sandwiches & Deli": 30, "Healthy & Vegan": 32, "Breakfast & Diner": 27, "European": 30, "Bar & Pub": 27,
             "American & Other": 30}
# Pre-tax net margin benchmarks by segment
MARGIN = {1: 0.075, 2: 0.05, 3: 0.055, 4: 0.045}
MARGIN_CUISINE = {"Bar & Pub": 0.10, "Steakhouse": 0.09, "Pizza": 0.07, "Coffee & Café": 0.08}
SPEND = {1: 13, 2: 28, 3: 62, 4: 165}   # typical per-person spend by price tier
