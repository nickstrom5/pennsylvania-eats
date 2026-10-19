"""Known chain brands in Pennsylvania: regex on normalized name -> brand label.

Adapted from ny-eats/pipeline/brands.py (from ct-eats, wi-eats and chi-eats); Pennsylvania chains added.
"""
import re

BRANDS = [
    ("Dunkin'", r"^DUNKIN"), ("Subway", r"^SUBWAY"), ("McDonald's", r"^MC ?DONALDS"), ("Starbucks", r"^STARBUCK"),
    ("Jimmy John's", r"^JIMMY JOHN"), ("Burger King", r"^BURGER KING"), ("Taco Bell", r"^TACO BELL"),
    ("Potbelly", r"^POTBELLY"), ("Wingstop", r"^WING ?STOP"), ("Chipotle", r"^CHIPOTLE"), ("Popeyes", r"^POPEYE"),
    ("Wendy's", r"^WENDYS"), ("Panda Express", r"^PANDA EXPRESS"), ("White Castle", r"^WHITE CASTLE"),
    ("Chick-fil-A", r"^CHICK FIL"), ("Domino's", r"^DOMINO"), ("Jersey Mike's", r"^JERSEY MIKE"),
    ("Panera Bread", r"^PANERA"), ("Jet's Pizza", r"^JETS PIZZA"), ("Little Caesars", r"^LITTLE CAESAR"),
    ("Papa John's", r"^PAPA JOHN"), ("KFC", r"^KFC|^KENTUCKY FRIED"), ("Tropical Smoothie Cafe", r"^TROPICAL SMOOTHIE"),
    ("Buffalo Wild Wings", r"^BUFFALO WILD"), ("Five Guys", r"^FIVE GUYS"), ("Raising Cane's", r"^RAISING CANE"),
    ("Portillo's", r"^PORTILLO"), ("Culver's", r"^CULVER"), ("Auntie Anne's", r"^AUNTIE ANNE"), ("Qdoba", r"^QDOBA"),
    ("Noodles & Company", r"^NOODLES (?:AND )?CO(?:MPANY)?\b"), ("Smoothie King", r"^SMOOTHIE KING"), ("Firehouse Subs", r"^FIREHOUSE SUB"),
    ("IHOP", r"^IHOP"), ("Denny's", r"^DENNYS"), ("Sonic", r"^SONIC DRIVE|^SONIC$"), ("Insomnia Cookies", r"^INSOMNIA COOKIE"),
    ("Crumbl", r"^CRUMBL"), ("Dairy Queen", r"^DAIRY QUEEN|^DQ GRILL|^DQ$"), ("Baskin-Robbins", r"^BASKIN"), ("Krispy Kreme", r"^KRISPY KREME"),
    ("Chuck E. Cheese", r"^CHUCK E CHEESE"), ("Rosati's", r"^ROSATI"), ("Nothing Bundt Cakes", r"^NOTHING BUNDT"),
    ("Hooters", r"^HOOTERS"), ("Cheesecake Factory", r"^CHEESECAKE FACTORY"), ("P.F. Chang's", r"^P ?F CHANG"), ("Maggiano's", r"^MAGGIANO"),
    ("Ruth's Chris", r"^RUTHS CHRIS"), ("Morton's", r"^MORTONS THE STEAK|^MORTONS STEAK"), ("Steak 'n Shake", r"^STEAK N SHAKE"),
    ("Applebee's", r"^APPLEBEE"), ("Chili's", r"^CHILIS"), ("Olive Garden", r"^OLIVE GARDEN"), ("Red Lobster", r"^RED LOBSTER"),
    ("Jamba", r"^JAMBA"), ("Cinnabon", r"^CINNABON"), ("Pizza Hut", r"^PIZZA HUT"), ("Arby's", r"^ARBYS"),
    ("Checkers", r"^CHECKERS DRIVE|^CHECKERS AND RALLY|^CHECKERS$"), ("MOD Pizza", r"^MOD PIZZA"), ("Tim Hortons", r"^TIM HORTON"),
    ("Peet's Coffee", r"^PEETS"), ("Colectivo", r"^COLECTIVO"), ("Cava", r"^CAVA$|^CAVA (?:MEDITERRANEAN|GRILL)"), ("Blaze Pizza", r"^BLAZE PIZZA"),
    # Wisconsin and Upper Midwest chains
    ("Cousins Subs", r"^COUSINS SUB"), ("Toppers Pizza", r"^TOPPERS"), ("Pizza Ranch", r"^PIZZA RANCH"), ("Hardee's", r"^HARDEES"),
    ("Taco John's", r"^TACO JOHN"), ("A&W", r"^A (?:AND )?W(?: RESTAURANTS?| ALL AMERICAN| DRIVE| ROOT| FAMILY| RESTAURANT| KITCHEN)?$|^A (?:AND )?W (?:RESTAURANT|ALL AMERICAN|DRIVE IN|ROOT BEER|FAMILY)"), ("Caribou Coffee", r"^CARIBOU COFFEE|^CARIBOU$"),
    ("Scooter's Coffee", r"^SCOOTERS COFFEE"), ("Biggby Coffee", r"^BIGGBY"), ("Perkins", r"^PERKINS (?:RESTAURANT|BAKERY|AMERICAN|FAMILY)|^PERKINS$"),
    ("Texas Roadhouse", r"^TEXAS ROADHOUSE"), ("Famous Dave's", r"^FAMOUS DAVE"), ("Red Robin", r"^RED ROBIN"),
    ("Freddy's", r"^FREDDYS FROZEN|^FREDDYS STEAKBURGER"), ("Papa Murphy's", r"^PAPA MURPH"), ("Marco's Pizza", r"^MARCOS PIZZA"),
    ("Cracker Barrel", r"^CRACKER BARREL"), ("Outback Steakhouse", r"^OUTBACK STEAK"), ("LongHorn Steakhouse", r"^LONGHORN STEAK"),
    ("Pita Pit", r"^PITA PIT"), ("Erbert & Gerbert's", r"^ERBERT"), ("Cold Stone Creamery", r"^COLD STONE"),
    ("Golden Corral", r"^GOLDEN CORRAL"), ("Old Chicago", r"^OLD CHICAGO$|^OLD CHICAGO (?:PASTA|PIZZA|TAPROOM)"), ("Granite City", r"^GRANITE CITY FOOD"),
    ("Rocky Rococo", r"^ROCKY ROCOCO"), ("Glass Nickel Pizza", r"^GLASS NICKEL"), ("George Webb", r"^GEORGE WEBB"),
    ("Milio's Sandwiches", r"^MILIOS"), ("Einstein Bros. Bagels", r"^EINSTEIN BRO"), ("Big Apple Bagels", r"^BIG APPLE BAGEL"),
    ("Quiznos", r"^QUIZNO"), ("Country Kitchen", r"^COUNTRY KITCHEN RESTAURANT|^COUNTRY KITCHEN$"), ("Fazoli's", r"^FAZOLI"),
    ("Dickey's Barbecue Pit", r"^DICKEYS"), ("HuHot Mongolian Grill", r"^HUHOT"), ("Stone Creek Coffee", r"^STONE CREEK COFFEE"),
    ("Chocolate Shoppe Ice Cream", r"^CHOCOLATE SHOPPE"), ("Blimpie", r"^BLIMPIE"), ("Dave's Hot Chicken", r"^DAVES HOT CHICKEN"),
    ("Sbarro", r"^SBARRO"), ("Orange Julius", r"^ORANGE JULIUS"),
    ("7 Brew", r"^7 BREW"), ("Great Harvest", r"^GREAT HARVEST"), ("Teriyaki Madness", r"^TERIYAKI MADNESS"), ("Forage Kitchen", r"^FORAGE KITCHEN"),
    ("JJ Fish & Chicken", r"^J ?J FISH"), ("First Watch", r"^FIRST WATCH"), ("Orange Leaf", r"^ORANGE LEAF"), ("Uno Pizzeria", r"^UNO PIZZERIA|^UNO CHICAGO"),
    ("TGI Fridays", r"^TGI FRIDAY"), ("Mooyah", r"^MOOYAH"), ("Charleys Cheesesteaks", r"^CHARLEYS"), ("Ian's Pizza", r"^IANS PIZZA"),
    ("Dunn Brothers Coffee", r"^DUNN BRO"), ("Smashburger", r"^SMASHBURGER"), ("Mission BBQ", r"^MISSION BBQ"), ("Kopp's Frozen Custard", r"^KOPPS"),
    ("Gloria Jean's Coffees", r"^GLORIA JEAN"), ("Ponderosa Steakhouse", r"^PONDEROSA STEAK"), ("Chesters Chicken", r"^CHESTERS (?:FRIED )?CHICKEN"),
    ("Hunt Brothers Pizza", r"^HUNT BROTHERS"), ("Hot Stuff Pizza", r"^HOT STUFF"), ("Krispy Krunchy Chicken", r"^KRISPY KRUNCHY"),
    ("Champs Chicken", r"^CHAMPS CHICKEN"), ("Sammy's Taste of Chicago", r"^SAMMYS TASTE"), ("Wendy's", r"^WENDYS"),
    ("Pizza Pit", r"^PIZZA PIT$"), ("Figaro's Pizza", r"^FIGAROS"), ("Parker John's", r"^PARKER JOHNS"), ("Eaton's Fresh Pizza", r"^EATONS"),
    ("Barriques", r"^BARRIQUES"), ("Moka", r"^MOKA$|^MOKA COFFEE"), ("Grace Coffee", r"^GRACE COFFEE"), ("Tom's Drive-In", r"^TOMS DRIVE"),
    ("BelAir Cantina", r"^BELAIR CANTINA"), ("Milwaukee Burger Company", r"^MILWAUKEE BURGER"), ("Mr. Brews Taphouse", r"^MR BREWS"),
    ("Pardon My Cheesesteak", r"^PARDON MY CHEESESTEAK"), ("MrBeast Burger", r"^MR ?BEAST"), ("Farmer's Fridge", r"^FARMERS FRIDGE"),
    ("Mad Chicken", r"^MAD CHICKEN"), ("It's Just Wings", r"^ITS JUST WINGS"), ("Banda Burrito", r"^BANDA BURRITO"),
    ("Tenderfix", r"^TENDERFIX"), ("Burger Den", r"^(?:THE )?BURGER DEN$"), ("The Meltdown", r"^(?:THE )?MELTDOWN$"),
    ("Cheba Hut", r"^CHEBA HUT"), ("Briq's Soft Serve", r"^BRIQS"), ("Chubby's Cheesesteaks", r"^CHUBBYS CHEESESTEAK"),
    ("Charcoal Grill & Rotisserie", r"^CHARCOAL GRILL (?:AND )?ROTISSERIE|^CHARCOAL GRILL$"), ("Wissota Chophouse", r"^WISSOTA CHOPHOUSE"),
    ("Nori Sushi & Grill", r"^NORI SUSHI"), ("7-Eleven", r"^7 ELEVEN"), ("Kwik Trip", r"^KWIK TRIP|^KWIK STAR"), ("Casey's", r"^CASEYS"),
    # Connecticut and New England chains
    ("Frank Pepe Pizzeria Napoletana", r"^(?:FRANK )?PEPES PIZZERIA|^FRANK PEPE"), ("Sally's Apizza", r"^SALLYS APIZZA"),
    ("Colony Grill", r"^COLONY GRILL"), ("Wood-n-Tap", r"^WOOD N TAP"), ("Plan B Burger Bar", r"^PLAN B BURGER|^PLAN B$"),
    ("Archie Moore's", r"^ARCHIE MOORE"), ("Duchess", r"^DUCHESS(?: RESTAURANT)?$"), ("Friendly's", r"^FRIENDLYS"),
    ("Bertucci's", r"^BERTUCCI"), ("Papa Gino's", r"^PAPA GINO"), ("D'Angelo", r"^D ?ANGELO(?: GRILLED| SANDWICH)?"),
    ("Moe's Southwest Grill", r"^MOES SOUTHWEST"), ("99 Restaurant", r"^99 RESTAURANT|^NINETY NINE"), ("Ruby Tuesday", r"^RUBY TUESDAY"),
    ("Bonefish Grill", r"^BONEFISH"), ("Carrabba's", r"^CARRABBA"), ("Max Burger", r"^MAX BURGER"), ("Rizzuto's", r"^RIZZUTOS"),
    ("J. Timothy's", r"^J TIMOTHYS"), ("Bruegger's", r"^BRUEGGER"), ("Au Bon Pain", r"^AU BON PAIN"), ("Cosi", r"^COSI$"),
    ("Shake Shack", r"^SHAKE SHACK"), ("Sweetgreen", r"^SWEETGREEN"), ("Ben & Jerry's", r"^BEN (?:AND )?JERRYS"),
    ("Carvel", r"^CARVEL"), ("Rita's", r"^RITAS(?: ITALIAN ICE)?$|^RITAS ITALIAN"), ("Cumberland Farms", r"^CUMBERLAND FARMS"),
    ("Honey Dew Donuts", r"^HONEY DEW"), ("Bess Eaton", r"^BESS EATON"), ("Nathan's Famous", r"^NATHANS"), ("Wingstop", r"^WINGSTOP"),
    ("Bareburger", r"^BAREBURGER"), ("Tony's Di Napoli", r"^TONYS DI NAPOLI"), ("Ninety Nine", r"^NINETY NINE"),
    ("City Steam Brewery", r"^CITY STEAM"), ("Little Pub", r"^LITTLE PUB"), ("Burger Joint", r"^BURGER JOINT"),
    ("Pizzeria Uno", r"^PIZZERIA UNO"), ("Joe's Crab Shack", r"^JOES CRAB"), ("Kona Grill", r"^KONA GRILL"), ("Panda Express", r"^PANDA EXPRESS"),
    ("Stop & Shop", r"^STOP (?:AND )?SHOP"), ("Big Y", r"^BIG Y\b"), ("ShopRite", r"^SHOP ?RITE"), ("Price Chopper", r"^PRICE CHOPPER"),
    ("Xtra Mart", r"^XTRA ?MART"), ("Alltown", r"^ALLTOWN"), ("Tim Hortons", r"^TIM HORTON"), ("Dave's Hot Chicken", r"^DAVES HOT CHICKEN"),
    ("Starbucks", r"^STARBUCK"), ("Grade A ShopRite", r"^GRADE A"), ("Whole Foods Market", r"^WHOLE FOODS"), ("Trader Joe's", r"^TRADER JOE"),
    ("Planet Pizza", r"^PLANET PIZZA"), ("Taste of China", r"^TASTE OF CHINA$"), ("Chuck E. Cheese", r"^CHUCK E"),
    # Pennsylvania chains (convenience-store counters are flagged as counters in stage 2, not dropped here)
    ("Wawa", r"^WAWA\b"), ("Sheetz", r"^SHEETZ\b"), ("GetGo", r"^GETGO\b|^GET GO\b"), ("Rutter's", r"^RUTTERS\b"),
    ("Turkey Hill", r"^TURKEY HILL MINIT|^TURKEY HILL MARKET|^TURKEY HILL$"), ("Royal Farms", r"^ROYAL FARMS"), ("7-Eleven", r"^7 ?ELEVEN|^SEVEN ELEVEN"),
    ("Primanti Bros.", r"^PRIMANTI"), ("Eat'n Park", r"^EAT ?N ?PARK\b"), ("Philly Pretzel Factory", r"^PHILLY PRETZEL FACTORY|^PHILLY PRETZEL$"),
    ("Rita's Italian Ice", r"^RITAS(?: ITALIAN| WATER| FROZEN)?(?: ICE)?(?: AND FROZEN CUSTARD)?$|^RITAS ITALIAN"),
    ("Saladworks", r"^SALADWORKS"), ("Chickie's & Pete's", r"^CHICKIES AND PETES|^CHICKIE AND PETES"), ("Manhattan Bagel", r"^MANHATTAN BAGEL"),
    ("Bruegger's", r"^BRUEGGERS"), ("Hoss's", r"^HOSSS|^HOSS S STEAK"), ("Isaly's", r"^ISALYS"), ("Fox's Pizza Den", r"^FOXS PIZZA"),
    ("Vocelli Pizza", r"^VOCELLI"), ("Pizza Hut", r"^PIZZA HUT"), ("Wing It On", r"^WING IT ON"), ("Federal Donuts", r"^FEDERAL DONUTS"),
    ("Dunkin'", r"^DUNKIN"), ("Bonchon", r"^BONCHON"), ("Honeygrow", r"^HONEYGROW"), ("Playa Bowls", r"^PLAYA BOWLS"),
    ("Iron Hill Brewery", r"^IRON HILL BREW"), ("Primo Hoagies", r"^PRIMO HOAGIES|^PRIMOS HOAGIES"), ("Capriotti's", r"^CAPRIOTTI"),
    ("Taco Bell", r"^TACO BELL"), ("Ruby Tuesday", r"^RUBY TUESDAY"), ("Bob Evans", r"^BOB EVANS"), ("Friendly's", r"^FRIENDLYS"),
    ("Arooga's", r"^AROOGAS"), ("Hibachi Grill", r"^HIBACHI GRILL SUPREME"), ("Duck Donuts", r"^DUCK DONUTS"), ("Bricks Pizza", r"^BRICKS PIZZA"),
    ("Mister Softee", r"^MISTER SOFTEE"), ("Wendy's", r"^WENDYS"), ("Burger King", r"^BURGER KING"),
    # New York chains
    ("Bagel Boss", r"^BAGEL BOSS"), ("Ralph's Famous Italian Ices", r"^RALPHS (?:FAMOUS )?ITALIAN ICE|^RALPHS ICES"), ("Pret A Manger", r"^PRET A MANGER|^PRET$"),
    ("Le Pain Quotidien", r"^LE PAIN QUOTIDIEN"), ("Joe & the Juice", r"^JOE (?:AND )?THE JUICE"), ("Just Salad", r"^JUST SALAD"),
    ("Dig", r"^DIG(?: INN)?$"), ("Chopt", r"^CHOPT"), ("Dos Toros", r"^DOS TOROS"), ("2 Bros. Pizza", r"^2 BROS PIZZA|^TWO BROS PIZZA"),
("Joe Coffee", r"^JOE COFFEE"), ("Blue Bottle Coffee", r"^BLUE BOTTLE"), ("Gregorys Coffee", r"^GREGORYS COFFEE"),
    ("Bluestone Lane", r"^BLUESTONE LANE"), ("Black Fox Coffee", r"^BLACK FOX COFFEE"), ("Birch Coffee", r"^BIRCH COFFEE"), ("% Arabica", r"^ARABICA$"),
    ("Mighty Quinn's", r"^MIGHTY QUINNS"), ("Los Tacos No. 1", r"^LOS TACOS NO"), ("Xi'an Famous Foods", r"^XIAN FAMOUS"),
    ("Tim Hortons", r"^TIM HORTON"), ("Spot Coffee", r"^SPOT COFFEE"), ("Wegmans", r"^WEGMANS"), ("Tops Friendly Markets", r"^TOPS (?:FRIENDLY|MARKETS?)"),
    ("Stewart's Shops", r"^STEWARTS SHOP|^STEWARTS$"), ("Nice N Easy", r"^NICE N EASY"), ("Fastrac", r"^FASTRAC"), ("Sunoco", r"^SUNOCO"),
    ("Mighty Taco", r"^MIGHTY TACO"), ("Ted's Hot Dogs", r"^TEDS HOT DOGS"), ("Anchor Bar", r"^ANCHOR BAR"), ("Duff's Famous Wings", r"^DUFFS"),
    ("Bocce Club Pizza", r"^BOCCE CLUB"), ("La Nova Pizzeria", r"^LA NOVA"), ("Just Pizza", r"^JUST PIZZA"), ("Pizza Plant", r"^PIZZA PLANT"),
    ("Abbott's Frozen Custard", r"^ABBOTTS (?:FROZEN )?CUSTARD"), ("Zweigle's", r"^ZWEIGLES"), ("Dinosaur Bar-B-Que", r"^DINOSAUR BAR"),
    ("Byrne Dairy", r"^BYRNE DAIRY"), ("Price Rite", r"^PRICE RITE"), ("Key Food", r"^KEY FOOD"), ("C-Town", r"^C ?TOWN"),
    ("Foodtown", r"^FOODTOWN"), ("Associated Supermarket", r"^ASSOCIATED SUPERMARKET"), ("King Kullen", r"^KING KULLEN"),
    ("Hale and Hearty", r"^HALE (?:AND )?HEARTY"), ("Panda Express", r"^PANDA EXPRESS"), ("Halal Guys", r"^(?:THE )?HALAL GUYS"),
    ("Popeyes", r"^POPEYE"), ("Kennedy Fried Chicken", r"^KENNEDY FRIED"), ("Crown Fried Chicken", r"^CROWN FRIED"),
    ("Golden Krust", r"^GOLDEN KRUST"), ("Applebee's", r"^APPLEBEE"), ("Friendly's", r"^FRIENDLYS"), ("Bareburger", r"^BAREBURGER"),
    ("Carvel", r"^CARVEL"), ("Nathan's Famous", r"^NATHANS"), ("Ess-a-Bagel", r"^ESS A BAGEL"),
    ("Paris Baguette", r"^PARIS BAGUETTE"), ("Tous les Jours", r"^TOUS LES JOURS"), ("Gong Cha", r"^GONG CHA"), ("Kung Fu Tea", r"^KUNG FU TEA"),
    ("Vivi Bubble Tea", r"^VIVI BUBBLE"), ("Chatime", r"^CHATIME"), ("Tiger Sugar", r"^TIGER SUGAR"), ("Morton Williams", r"^MORTON WILLIAMS"),
    ("Gristedes", r"^GRISTEDES"), ("Food Emporium", r"^FOOD EMPORIUM"), ("Westside Market", r"^WESTSIDE MARKET"), ("Duane Reade", r"^DUANE READE"),
    ("Rite Aid", r"^RITE AID"), ("Hess Express", r"^HESS EXPRESS"), ("Speedway", r"^SPEEDWAY"), ("Valero", r"^VALERO"),
]
_C = [(b, re.compile(p)) for b, p in BRANDS]

# distinctive brands also recognized mid-name ("HALE FAMILY MCDONALDS", "SAII BABA DUNKIN")
_ANYWHERE = [(b, re.compile(p)) for b, p in [("McDonald's", r"\bMC ?DONALDS\b"), ("Dunkin'", r"\bDUNKIN\b"), ("Starbucks", r"\bSTARBUCKS\b"),
             ("Wingstop", r"\bWING ?STOP\b"), ("Culver's", r"\bCULVERS\b"), ("Popeyes", r"\bPOPEYES\b"), ("Chipotle", r"\bCHIPOTLE\b"),
             ("Jimmy John's", r"\bJIMMY JOHNS\b"), ("Taco Bell", r"\bTACO BELL\b"), ("Cousins Subs", r"\bCOUSINS SUBS\b")]]


def brand_of(nkey, *more):
    """Brand from the display name, else from Overture's brand label."""
    keys = [k for k in [nkey] + [m for m in more if isinstance(m, str)] if isinstance(k, str)]
    for k in keys:
        for part in [k or ""] + [p.strip() for p in (k or "").split("/")]:
            for b, p in _C:
                if p.search(part):
                    return b
    for k in keys:
        for b, p in _ANYWHERE:
            if p.search(k or ""):
                return b
    return None
