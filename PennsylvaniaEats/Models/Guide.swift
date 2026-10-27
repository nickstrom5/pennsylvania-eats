import Foundation
import CoreLocation

/// The lists the app is built around. Each is a filter plus an order; none uses ratings (the app only publishes data it may).
enum Guide: String, CaseIterable, Identifiable, Hashable {
    case cheesesteaks, tomatoPie, pierogies, dutch, pretzels, diners, icons, oldest, nearMe, all

    var id: String { rawValue }

    var title: String {
        switch self {
        case .cheesesteaks: "Cheesesteaks, Roast Pork & Hoagies"
        case .tomatoPie: "Tomato Pie & Old Forge Pizza"
        case .pierogies: "Pierogies & Pittsburgh Classics"
        case .dutch: "Pennsylvania Dutch"
        case .pretzels: "Soft Pretzel Bakeries"
        case .diners: "Diners"
        case .icons: "Pennsylvania Icons"
        case .oldest: "Oldest Taverns & Places"
        case .nearMe: "Near Me"
        case .all: "All Restaurants"
        }
    }

    /// The Home card's title: short enough to sit on two lines of display type on the narrowest iPhone.
    var shortTitle: String {
        switch self {
        case .cheesesteaks: "Cheesesteaks"
        case .tomatoPie: "Tomato Pie"
        case .pierogies: "Pierogies"
        case .dutch: "PA Dutch"
        case .pretzels: "Pretzels"
        case .diners: "Diners"
        case .oldest: "Oldest Places"
        default: title
        }
    }

    var subtitle: String {
        switch self {
        case .cheesesteaks: "Philadelphia's steak shops, roast pork and hoagie counters"
        case .tomatoPie: "Square tomato pie and Old Forge-style trays"
        case .pierogies: "Pierogi kitchens and Pittsburgh's sandwich classics"
        case .dutch: "Family-style dining rooms and smorgasbords"
        case .pretzels: "Hand-twisted soft pretzels, baked daily"
        case .diners: "Counters, booths and breakfast all day"
        case .icons: "MICHELIN, James Beard honorees and institutions"
        case .oldest: "Years at the same address, oldest first"
        case .nearMe: "Everything around you, closest first"
        case .all: "Restaurants, cafés, bars and bakeries statewide"
        }
    }

    var systemImage: String {
        switch self {
        case .cheesesteaks: "takeoutbag.and.cup.and.straw"
        case .tomatoPie: "square.grid.2x2"
        case .pierogies: "fork.knife.circle"
        case .dutch: "house"
        case .pretzels: "infinity"
        case .diners: "cup.and.saucer"
        case .icons: "star.circle"
        case .oldest: "clock.arrow.circlepath"
        case .nearMe: "location"
        case .all: "fork.knife"
        }
    }

    /// The Pennsylvania classics: hand-checked lists, highlighted on Home.
    var isClassic: Bool { [.cheesesteaks, .tomatoPie, .pierogies, .dutch, .pretzels, .diners].contains(self) }

    /// Guides whose order is a ranking worth numbering.
    var isRanked: Bool { [.icons, .oldest].contains(self) }

    var sortOptions: [SortOrder] {
        switch self {
        case .cheesesteaks, .tomatoPie, .pierogies, .dutch, .pretzels, .diners: [.featured, .nearest, .oldest, .name]
        case .icons: [.iconic, .oldest, .nearest]
        case .oldest: [.oldest]
        case .nearMe: [.nearest]
        case .all: [.name, .nearest]
        }
    }

    var defaultSort: SortOrder { sortOptions[0] }

    func includes(_ p: Place) -> Bool {
        switch self {
        // the classics promise "hand-checked", so only places our research confirmed open; a listing merely named "… Steaks" isn't enough
        case .cheesesteaks: p.handChecked && !p.kinds.isDisjoint(with: [.cheesesteak, .roastPork, .hoagie])
        case .tomatoPie: p.handChecked && !p.kinds.isDisjoint(with: [.tomatoPie, .oldForge])
        case .pierogies: p.handChecked && !p.kinds.isDisjoint(with: [.pierogi, .pittsburghSandwich])
        case .dutch: p.handChecked && p.kinds.contains(.paDutch)
        case .pretzels: p.handChecked && p.kinds.contains(.pretzel)
        case .diners: p.handChecked && p.kinds.contains(.diner)
        case .icons: p.iconicPoints != nil
        case .oldest: p.founded != nil && p.handChecked
        case .nearMe, .all: true
        }
    }
}

enum SortOrder: String, CaseIterable, Identifiable {
    case featured, nearest, oldest, name, iconic
    var id: String { rawValue }
    var label: String {
        switch self {
        case .featured: "Featured first"
        case .nearest: "Nearest"
        case .oldest: "Oldest first"
        case .name: "A to Z"
        case .iconic: "Most iconic"
        }
    }
}

/// Filters shared by every list. Search text lives with each list.
struct Filters: Equatable, Codable {
    var region: String?
    var town: String?
    var cuisine: String?
    var hideChains = false
    var confirmedOnly = false
    var includeNonRestaurants = false
    var bibGourmand = false          // MICHELIN Bib Gourmand only: a fact from the Guide, not a rating

    var activeCount: Int {
        [region != nil, town != nil, cuisine != nil, hideChains, confirmedOnly, includeNonRestaurants, bibGourmand].filter { $0 }.count
    }

    func allows(_ p: Place) -> Bool {
        if !includeNonRestaurants && p.isVenue { return false }
        if let region, p.region != region { return false }
        if let town, p.city != town { return false }
        if let cuisine, p.cuisine != cuisine { return false }
        if hideChains && p.isChain { return false }
        if confirmedOnly && p.tier == .listing { return false }
        if bibGourmand && p.michelin != .bib { return false }
        return true
    }
}

extension Filters {
    /// Filters saved by an older build have no bibGourmand key: read what's there instead of dropping them all.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        self.init(region: try c.decodeIfPresent(String.self, forKey: .region),
                  town: try c.decodeIfPresent(String.self, forKey: .town),
                  cuisine: try c.decodeIfPresent(String.self, forKey: .cuisine),
                  hideChains: try c.decodeIfPresent(Bool.self, forKey: .hideChains) ?? false,
                  confirmedOnly: try c.decodeIfPresent(Bool.self, forKey: .confirmedOnly) ?? false,
                  includeNonRestaurants: try c.decodeIfPresent(Bool.self, forKey: .includeNonRestaurants) ?? false,
                  bibGourmand: try c.decodeIfPresent(Bool.self, forKey: .bibGourmand) ?? false)
    }
}

enum Ranking {
    /// `nameRank` (place id -> position in A-to-Z order, computed once at load) makes name order a number comparison.
    static func sort(_ places: [Place], by order: SortOrder, from here: CLLocation?, nameRank: [String: Int] = [:]) -> [Place] {
        func name(_ a: Place, _ b: Place) -> Bool {
            if let ra = nameRank[a.id], let rb = nameRank[b.id] { return ra < rb }
            return a.name.localizedCaseInsensitiveCompare(b.name) == .orderedAscending
        }
        switch order {
        case .nearest where here != nil:
            // distance computed once per place (a statewide list can hold 50,000 places)
            let d = Dictionary(places.map { ($0.id, $0.location?.distance(from: here!) ?? .greatestFiniteMagnitude) }, uniquingKeysWith: { a, _ in a })
            return places.sorted { d[$0.id]! != d[$1.id]! ? d[$0.id]! < d[$1.id]! : name($0, $1) }
        case .featured, .nearest:
            // honored places first, then the verified year at this address, then name
            return places.sorted {
                let a = $0.iconicPoints ?? -1, b = $1.iconicPoints ?? -1
                if a != b { return a > b }
                let fa = $0.founded ?? 9999, fb = $1.founded ?? 9999
                return fa != fb ? fa < fb : name($0, $1)
            }
        case .oldest:
            return places.sorted { ($0.founded ?? 9999, $0.name) < ($1.founded ?? 9999, $1.name) }
        case .name:
            return places.sorted(by: name)
        case .iconic:
            return places.sorted { ($0.iconicPoints ?? -1) != ($1.iconicPoints ?? -1) ? ($0.iconicPoints ?? -1) > ($1.iconicPoints ?? -1) : name($0, $1) }
        }
    }
}
