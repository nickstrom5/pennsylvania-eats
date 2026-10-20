import Foundation
import CoreLocation

// MARK: - The bundled data (Resources/Data/index.json + places-<region>.json), written by pipeline/pennsylvania.py with PA_APP=1

/// index.json: shared lookup tables, the region files and the data dates.
struct DataIndex: Decodable {
    let generated: String
    let overture_release: String
    let regions: [String]
    let counties: [String]
    let county_region: [Int]
    let cities: [String]
    let mailing: [String]
    let hoods: [String]
    let munis: [String]
    let cuisines: [String]
    let brands: [String]
    let srcs: [String]
    let liqt: [String?]
    let count_restaurants: Int
    let records_through: RecordsThrough
    /// match rates measured against the official lists (calibration.json "app"): area -> listing group -> rate
    let calibration: [String: [String: CalibrationGroup]]
    let files: [RegionFile]

    /// each feed's own newest stamp minus 7 days (pipeline/official.records_through); achd only once Nick's WPRDC download is in
    struct RecordsThrough: Decodable, Hashable {
        let philly: String?
        let achd: String?
    }
    struct RegionFile: Decodable, Hashable {
        let region: String
        let file: String
        let count: Int
        let count_restaurants: Int
    }
}

struct CalibrationGroup: Decodable, Hashable {
    let n: Int
    let matched: Double
}

struct RegionData: Decodable {
    let region: String
    let places: [PlaceRecord]
}

/// Allegheny County: the placard ACHD posts after an inspection (official) and that inspection's date. We compute no grade.
struct ACHDPlacard: Decodable, Hashable {
    /// "Inspected & Permitted" (green), "Consumer Alert" (yellow), a closure (red), or another value as ACHD publishes it
    let p: String
    let d: String?

    enum Color { case green, yellow, red, other }
    var color: Color {
        if p == "Inspected & Permitted" { return .green }
        if p.localizedCaseInsensitiveContains("Consumer Alert") { return .yellow }
        if p.localizedCaseInsensitiveContains("clos") { return .red }
        return .other
    }
}

struct PlaceRecord: Decodable {
    let id: String
    let n: String
    let c: Int?
    let co: Int
    let cu: Int
    let t: Int
    let s: Int
    let pl: Int?
    let hd: Int?
    let mu: Int?
    let a: String?
    let z: String?
    let la: Double?
    let lo: Double?
    let b: Int?
    let ch: Int?
    let j: Int?
    let v: Int?
    let bar: Int?
    let g: Int?
    let lq: Int?
    let ac: ACHDPlacard?
    /// an active Philadelphia L&I food license matched (existence only)
    let phl: Int?
    /// a convenience-store counter (Wawa, Sheetz...) or a members-only club: hidden with the non-restaurants (Nick, 2026-10-19)
    let cc: Int?
    let mc: Int?
    let gs: Int?
    let hc: Int?
    let k: Int?
    let h: Int?
    let mi: Int?
    let ip: Double?
    let note: String?
    let jbf: String?
    let dish: String?
    let sea: String?
    let seas: Int?
    let br: String?
    let chef: String?
    let src: String?
    let fn: String?
    let f: Int?
    let w: String?
    let ph: String?
}

// MARK: - The model the views use

/// Pennsylvania guides, from names and the hand-checked research (never from reviews). Bit order matches pipeline/pennsylvania.py TAGS.
struct PlaceTags: OptionSet, Hashable {
    let rawValue: Int
    static let steak = PlaceTags(rawValue: 1)
    static let pie = PlaceTags(rawValue: 2)
    static let pierogi = PlaceTags(rawValue: 4)
    static let dutch = PlaceTags(rawValue: 8)
    static let pretzel = PlaceTags(rawValue: 16)
    static let diner = PlaceTags(rawValue: 32)
    static let oldest = PlaceTags(rawValue: 64)
}

/// What the hand-checked research says a place is (data/research/README.md `kinds`; bit order = pipeline/pennsylvania.py KINDS).
struct Kinds: OptionSet, Hashable {
    let rawValue: Int
    static let cheesesteak = Kinds(rawValue: 1)
    static let roastPork = Kinds(rawValue: 2)
    static let hoagie = Kinds(rawValue: 4)
    static let tomatoPie = Kinds(rawValue: 8)
    static let oldForge = Kinds(rawValue: 16)
    static let pierogi = Kinds(rawValue: 32)
    static let pittsburghSandwich = Kinds(rawValue: 64)
    static let paDutch = Kinds(rawValue: 128)
    static let pretzel = Kinds(rawValue: 256)
    static let diner = Kinds(rawValue: 512)
    static let oldest = Kinds(rawValue: 1024)

    static let labels: [(Kinds, String)] = [(.cheesesteak, "Cheesesteaks"), (.roastPork, "Roast pork"), (.hoagie, "Hoagies"),
                                            (.tomatoPie, "Tomato pie"), (.oldForge, "Old Forge pizza"), (.pierogi, "Pierogies"),
                                            (.pittsburghSandwich, "Pittsburgh sandwiches"), (.paDutch, "Pennsylvania Dutch"),
                                            (.pretzel, "Soft pretzels"), (.diner, "Diner"), (.oldest, "Historic")]
    var names: [String] { Kinds.labels.filter { contains($0.0) }.map(\.1) }
}

/// How a place got on the list. The share that matched a permitted business comes from calibration.json.
enum Tier: Int, Comparable {
    case listing = 0        // one map listing
    case confirmed = 1      // a high-confidence Meta listing, or a hand-checked place
    case licensed = 2       // on an official list: a Philadelphia food license, an Allegheny County permit or a liquor license

    static func < (a: Tier, b: Tier) -> Bool { a.rawValue < b.rawValue }

    var label: String {
        switch self {
        case .licensed: "On an official list"
        case .confirmed: "High-confidence listing"   // the family wording (Nick, 2026-10-13); these matched a permit far more often than single listings
        case .listing: "Listing only"
        }
    }
}

enum Jurisdiction: Int {
    case none = 0, philly = 1, achd = 2, plcb = 3
    var listName: String {
        switch self {
        case .philly: "City of Philadelphia food licenses (L&I)"
        case .achd: "Allegheny County Health Department food facility permits"
        case .plcb: "Pennsylvania Liquor Control Board licenses"
        case .none: ""
        }
    }
}

enum MichelinDistinction: Int {
    case recommended = 1, bib = 2, oneStar = 3, twoStars = 4, threeStars = 5
    /// Honors are facts, written out: never a row of stars that reads like a rating.
    var label: String {
        switch self {
        case .recommended: "MICHELIN Guide"
        case .bib: "Bib Gourmand"
        case .oneStar: "1 MICHELIN Star"
        case .twoStars: "2 MICHELIN Stars"
        case .threeStars: "3 MICHELIN Stars"
        }
    }
}

struct Place: Identifiable, Hashable {
    let id: String
    let name: String
    let address: String?
    /// the town in the mailing address (Philadelphia for every place in the city)
    let city: String?
    /// the mailing name when it isn't the city shown
    let mailingName: String?
    /// unused in Pennsylvania (no neighborhood layer yet)
    let neighborhood: String?
    /// the municipality (city, borough or township) when it isn't the mailing town: a Millvale bar mailed as Pittsburgh
    let municipality: String?
    let county: String
    let region: String
    let zip: String?
    let coordinate: CLLocationCoordinate2D?
    let cuisine: String
    let brand: String?
    let chainCount: Int
    let tier: Tier
    let jurisdiction: Jurisdiction
    let liquorLicense: String?
    let source: String
    let isVenue: Bool
    let isBar: Bool
    let tags: PlaceTags
    /// On our hand-checked list (data/research): confirmed open with a 2025–26 source.
    let handChecked: Bool
    let kinds: Kinds
    let honorFlags: Int
    let michelin: MichelinDistinction?
    let iconicPoints: Double?
    let note: String?
    let jamesBeard: String?
    let dishes: String?
    let season: String?
    let isSeasonal: Bool
    let branchOf: String?
    let chef: String?
    let sourceURL: URL?
    let foundedNote: String?
    let founded: Int?
    let website: URL?
    let phone: String?
    let placard: ACHDPlacard?
    let phillyLicensed: Bool
    let isCounter: Bool
    let isMembersClub: Bool
    let greenStar: Bool
    /// normalized text for search: name, places, zip, cuisine, brand, dishes, then the address with street words abbreviated
    let searchText: String
    let nameText: String

    static func == (a: Place, b: Place) -> Bool { a.id == b.id }
    func hash(into h: inout Hasher) { h.combine(id) }

    var isHonored: Bool { handChecked }
    var isChain: Bool { chainCount >= 5 }
    var jamesBeardLabel: String? {
        if honorFlags & 1 != 0 { return "America's Classic" }
        if honorFlags & 2 != 0 { return "James Beard winner" }
        if honorFlags & 4 != 0 { return "James Beard nominee" }
        if honorFlags & 8 != 0 { return "James Beard semifinalist" }
        return nil
    }
    /// "Pittsburgh", or "Feasterville-Trevose" for a mailing name that isn't the town shown
    var placeName: String? {
        guard let city else { return mailingName }
        if let n = mailingName, n != city { return "\(n), \(city)" }
        return city
    }
    var townLine: String { [placeName, cuisine].compactMap { $0 }.joined(separator: " · ") }
    var fullAddress: String {
        let town = mailingName ?? city
        return [address, [town.map { "\($0), PA" }, zip].compactMap { $0 }.joined(separator: " ")].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: ", ")
    }
    var location: CLLocation? { coordinate.map { CLLocation(latitude: $0.latitude, longitude: $0.longitude) } }

    init(_ r: PlaceRecord, index ix: DataIndex) {
        func at(_ list: [String], _ i: Int?) -> String? { i.flatMap { $0 >= 0 && $0 < list.count ? list[$0] : nil } }
        let city = at(ix.cities, r.c)
        let mailing = at(ix.mailing, r.pl)
        let hood = at(ix.hoods, r.hd)
        let muni = at(ix.munis, r.mu)
        let county = at(ix.counties, r.co) ?? ""
        let region = r.co < ix.county_region.count ? (at(ix.regions, ix.county_region[r.co]) ?? "") : ""
        let cuisine = at(ix.cuisines, r.cu) ?? "American & Other"
        let brand = at(ix.brands, r.b)
        id = r.id
        name = r.n
        address = r.a
        self.city = city
        mailingName = mailing
        neighborhood = hood
        municipality = muni
        self.county = county
        self.region = region
        zip = r.z
        if let la = r.la, let lo = r.lo { coordinate = CLLocationCoordinate2D(latitude: la, longitude: lo) } else { coordinate = nil }
        self.cuisine = cuisine
        self.brand = brand
        chainCount = r.ch ?? 1
        tier = Tier(rawValue: r.t) ?? .listing
        jurisdiction = Jurisdiction(rawValue: r.j ?? 0) ?? .none
        liquorLicense = r.lq.flatMap { $0 > 0 && $0 < ix.liqt.count ? ix.liqt[$0] : nil }
        source = r.s < ix.srcs.count ? ix.srcs[r.s] : "meta"
        isVenue = r.v == 1
        isBar = r.bar == 1
        tags = PlaceTags(rawValue: r.g ?? 0)
        handChecked = r.hc == 1
        kinds = Kinds(rawValue: r.k ?? 0)
        honorFlags = r.h ?? 0
        michelin = r.mi.flatMap(MichelinDistinction.init(rawValue:))
        iconicPoints = r.ip
        note = r.note
        jamesBeard = r.jbf
        dishes = r.dish
        season = r.sea
        isSeasonal = r.seas == 1
        branchOf = r.br
        chef = r.chef
        sourceURL = r.src.flatMap { URL(string: $0) }
        foundedNote = r.fn
        founded = r.f
        website = r.w.flatMap { URL(string: $0.hasPrefix("http") ? $0 : "https://" + $0) }
        phone = r.ph
        placard = r.ac
        phillyLicensed = r.phl == 1
        isCounter = r.cc == 1
        isMembersClub = r.mc == 1
        greenStar = r.gs == 1
        // what people search for: the name, the town, the mailing name, the municipality, dishes
        searchText = " " + Search.normalize([r.n, city, mailing, hood, muni, r.z, cuisine, brand, r.dish].compactMap { $0 }.joined(separator: " ")) + " "
            + Search.normalizeAddress(r.a ?? "") + " "
        nameText = " " + Search.normalize([r.n, brand].compactMap { $0 }.joined(separator: " ")) + " "
    }
}
