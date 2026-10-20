import Foundation
import Observation
import CoreLocation

/// The whole app's state: the bundled places, filters, saved places and what's selected.
@MainActor
@Observable
final class AppModel {
    private(set) var places: [Place] = []
    private(set) var isLoaded = false
    private(set) var loadError: String?
    private(set) var generated = ""
    private(set) var overtureRelease = ""
    private(set) var restaurantCount = 0
    private(set) var recordsThrough: DataIndex.RecordsThrough?
    private(set) var calibration: [String: [String: CalibrationGroup]] = [:]
    /// Pennsylvania's nine regions (ours, by county), in the data's order (Philadelphia first)
    private(set) var regions: [String] = []
    /// mailing towns sorted by how many restaurants they have
    private(set) var towns: [(name: String, count: Int)] = []
    private(set) var cuisines: [(name: String, count: Int)] = []
    /// city -> its region (a name shared by two regions keeps the one with more places)
    private(set) var townRegions: [String: String] = [:]
    /// normalized town name -> display name ("state college" -> "State College")
    private(set) var townKeys: [String: String] = [:]
    /// normalized mailing name or municipality -> display name ("millvale", "bensalem"), for names that aren't also a town shown
    private(set) var villageKeys: [String: String] = [:]

    var filters = Filters() { didSet { saveFilters(); listCache.removeAll(); countCache.removeAll() } }
    private(set) var saved: Set<String> = []

    // navigation (iPad sidebar / iPhone tabs)
    var selectedGuide: Guide?
    var selectedPlace: Place?
    var tab: Tab = .guides
    enum Tab: Hashable { case guides, map, saved, about }
    /// the iPhone guides stack: a guide, then a place
    var guidesPath: [Route] = []
    enum Route: Hashable { case guide(Guide), place(Place) }
    /// bumped by openGuide so the iPad sidebar follows even when the same guide is picked again
    private(set) var guideRequest = 0

    /// Open a guide from Home: pushes it on iPhone, selects it in the iPad sidebar.
    func openGuide(_ g: Guide) {
        tab = .guides
        selectedGuide = g
        guidesPath = [.guide(g)]
        guideRequest += 1
    }

    /// a fixed "you are here" for screenshots, so lists sort by distance without a permission prompt
    var screenshotLocation: CLLocation?

    private let defaults: UserDefaults
    private var byID: [String: Place] = [:]
    /// Pennsylvania has 24,000+ places: lists are memoized per guide, order, search, filters and (rounded) location, a longer search
    /// filters the previous result instead of every place, and the A-to-Z order is computed once at load.
    private var listCache: [String: [Place]] = [:]
    private var lastSearch: (key: String, query: String, scope: String, result: [Place])?
    private var countCache: [Guide: Int] = [:]
    private(set) var nameRank: [String: Int] = [:]

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        saved = Set(defaults.stringArray(forKey: "saved") ?? [])
        if let data = defaults.data(forKey: "filters"), let f = try? JSONDecoder().decode(Filters.self, from: data) { filters = f }
    }

    nonisolated static var bundledData: URL? { Bundle.main.url(forResource: "Data", withExtension: nil) }

    /// Reads index.json and every region file (in parallel, off the main thread). `directory` holds index.json and places-*.json.
    func load(from directory: URL? = AppModel.bundledData) async {
        guard !isLoaded else { return }
        guard let directory else { loadError = "The restaurant data is missing from the app."; return }
        do {
            let (ix, places, rank) = try await Task.detached(priority: .userInitiated) { () throws -> (DataIndex, [Place], [String: Int]) in
                let ix = try JSONDecoder().decode(DataIndex.self, from: Data(contentsOf: directory.appendingPathComponent("index.json")))
                let parts = try await withThrowingTaskGroup(of: (Int, [Place]).self) { group in
                    for (i, f) in ix.files.enumerated() {
                        group.addTask {
                            let data = try Data(contentsOf: directory.appendingPathComponent(f.file))
                            let region = try JSONDecoder().decode(RegionData.self, from: data)
                            return (i, region.places.map { Place($0, index: ix) })
                        }
                    }
                    var out: [(Int, [Place])] = []
                    for try await part in group { out.append(part) }
                    return out.sorted { $0.0 < $1.0 }.flatMap(\.1)
                }
                return (ix, parts, AppModel.nameRanks(parts))
            }.value
            apply(index: ix, places: places, nameRank: rank)
        } catch {
            loadError = "The restaurant data couldn't be read (\(error.localizedDescription))."
        }
    }

    /// place id -> position in A-to-Z order. Sorting 60,000 names takes a noticeable moment, so load() does it off the main thread.
    nonisolated static func nameRanks(_ places: [Place]) -> [String: Int] {
        let byName = places.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        return Dictionary(byName.enumerated().map { ($1.id, $0) }, uniquingKeysWith: { a, _ in a })
    }

    func apply(index ix: DataIndex, places: [Place], nameRank rank: [String: Int]? = nil) {
        self.places = places
        byID = Dictionary(places.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        nameRank = rank ?? AppModel.nameRanks(places)
        listCache.removeAll(); countCache.removeAll(); lastSearch = nil
        generated = ix.generated
        overtureRelease = ix.overture_release
        restaurantCount = ix.count_restaurants
        recordsThrough = ix.records_through
        calibration = ix.calibration
        regions = ix.regions
        var tc: [String: Int] = [:], cc: [String: Int] = [:], tr: [String: [String: Int]] = [:]
        for p in places where !p.isVenue {
            if let c = p.city { tc[c, default: 0] += 1; tr[c, default: [:]][p.region, default: 0] += 1 }
            cc[p.cuisine, default: 0] += 1
        }
        townRegions = tr.compactMapValues { $0.max { $0.value < $1.value }?.key }
        towns = tc.map { ($0.key, $0.value) }.sorted { $0.count != $1.count ? $0.count > $1.count : $0.name < $1.name }
        cuisines = cc.map { ($0.key, $0.value) }.sorted { $0.count != $1.count ? $0.count > $1.count : $0.name < $1.name }
        var keys: [String: String] = [:]
        for (name, _) in towns {   // the biggest place wins a shared spelling
            let k = Search.normalizeAddress(name)
            if keys[k] == nil { keys[k] = name }
        }
        townKeys = keys
        var vk: [String: String] = [:]
        for v in Set(places.compactMap(\.neighborhood) + places.compactMap(\.mailingName) + places.compactMap(\.municipality)) {
            let k = Search.normalizeAddress(v)
            if keys[k] == nil && vk[k] == nil { vk[k] = v }
        }
        villageKeys = vk
        if let t = filters.town, tc[t] == nil { filters.town = nil }
        if let c = filters.cuisine, cc[c] == nil { filters.cuisine = nil }
        if let r = filters.region, !regions.contains(r) { filters.region = nil }
        isLoaded = true
    }

    func place(id: String) -> Place? { byID[id] }

    /// Places in a guide, filtered and searched, in the chosen order.
    func list(_ guide: Guide, sort: SortOrder, search: String, here: CLLocation?) -> [Place] {
        // ~100 m of movement doesn't change the order enough to redo it
        let spot = here.map { "\(($0.coordinate.latitude * 1000).rounded()),\(($0.coordinate.longitude * 1000).rounded())" } ?? "-"
        let base = "\(guide.rawValue)|\(sort.rawValue)|\(spot)"
        let key = base + "|" + search
        if let hit = listCache[key] { return hit }
        let q = Search.parse(search, towns: townKeys, villages: villageKeys)
        // typed something, but nothing searchable ("🍕", "!!!"): show nothing rather than everything
        if q.isEmpty && !search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return [] }
        if guide == .nearMe && here == nil { return [] }
        // a longer search only narrows: start from the previous search's places instead of all 24,000
        let pool: [Place]
        let trimmed = search.trimmingCharacters(in: .whitespaces)
        // ...but only while the search means the same kind of thing: "pierog" -> "pierogi" turns into the Pierogies guide, "eri" -> "erie"
        // into the city, and those can include places the shorter word didn't match
        let scope = "\(q.tag?.rawValue ?? -1)|\(q.town ?? "")|\(q.village ?? "")"
        if let last = lastSearch, last.key == base, last.scope == scope, !last.query.isEmpty, trimmed.hasPrefix(last.query), !trimmed.hasSuffix(" "),
           trimmed.count > last.query.count, !trimmed.dropFirst(last.query.count).contains(" ") {
            pool = last.result
        } else {
            pool = places
        }
        var out = pool.filter { guide.includes($0) && filters.allows($0) && (q.isEmpty || Search.matches($0, q)) }
        out = Ranking.sort(out, by: sort, from: here, nameRank: nameRank)
        if !q.tokens.isEmpty && !(guide.isRanked) {   // name matches first when searching
            let named = out.filter { Search.nameMatches($0, q) }
            if !named.isEmpty && named.count < out.count {
                let ids = Set(named.map(\.id))
                out = named + out.filter { !ids.contains($0.id) }
            }
        }
        if listCache.count > 40 { listCache.removeAll() }
        listCache[key] = out
        lastSearch = (base, trimmed, scope, out)
        return out
    }

    func count(_ guide: Guide) -> Int {
        if let c = countCache[guide] { return c }
        let c = places.lazy.filter { guide.includes($0) && self.filters.allows($0) }.count
        countCache[guide] = c
        return c
    }

    /// Guides with too few hand-checked places to be worth a Home card (judged before filters, so a town filter can't hide a card).
    func hasEnough(_ guide: Guide) -> Bool { !guide.isClassic || places.lazy.filter { guide.includes($0) && !$0.isVenue }.count >= 4 }

    // MARK: saved places

    func isSaved(_ p: Place) -> Bool { saved.contains(p.id) }

    func toggleSaved(_ p: Place) {
        if saved.contains(p.id) { saved.remove(p.id) } else { saved.insert(p.id) }
        defaults.set(Array(saved).sorted(), forKey: "saved")
    }

    var savedPlaces: [Place] { saved.compactMap { byID[$0] }.sorted { $0.name < $1.name } }

    /// A random hand-checked classic, never the one just shown.
    func randomPick(from guides: [Guide], excluding last: String?) -> Place? {
        let pool = places.filter { p in guides.contains { $0.includes(p) } && filters.allows(p) && p.id != last }
        return pool.randomElement()
    }

    private func saveFilters() {
        if let data = try? JSONEncoder().encode(filters) { defaults.set(data, forKey: "filters") }
    }

    // MARK: honest labels

    /// "71%": how often a listing of this kind matched a permitted food business on the official list for its area
    /// (Philadelphia's restaurant licenses, the one complete list measured; the license list also holds schools and corner stores).
    func matchRate(for p: Place) -> String? {
        let group: String
        switch (p.source, p.tier) {
        case ("meta", .confirmed): group = "Meta, confidence 0.95+"
        case ("meta", _): group = "Meta, 0.90-0.95"
        case ("AllThePlaces", _), ("DAC", _): group = "brand feed"
        default: return nil
        }
        let area = "philly_restaurant_licenses"
        guard let g = calibration[area]?[group], g.n >= 20 else { return nil }
        return "\(Int((g.matched * 100).rounded()))%"
    }
}
