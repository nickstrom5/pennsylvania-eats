import XCTest
import CoreLocation
@testable import PennsylvaniaEats

@MainActor
final class PennsylvaniaEatsTests: XCTestCase {

    /// A tiny data folder with the same shape as Resources/Data (index.json + one file per region).
    private func sampleModel() async throws -> AppModel {
        let index = """
        {"v":1,"generated":"2026-10-19","overture_release":"2026-09-23.1",
         "regions":["Philadelphia","Pittsburgh Region","South Central"],"slugs":["philadelphia","pittsburgh-region","south-central"],
         "counties":["Philadelphia","Allegheny","Lancaster"],"county_region":[0,1,2],
         "cities":["Philadelphia","Pittsburgh","McKees Rocks","Lititz","East Earl"],"mailing":[],"hoods":[],"munis":["Millvale"],
         "cuisines":["Sandwiches & Deli","Seafood","Pizza","European","Breakfast & Diner","American & Other"],
         "brands":["Wawa"],"srcs":["official","meta","AllThePlaces","DAC","research"],"liqt":[null],
         "count":10,"count_restaurants":8,"records_through":{"philly":"2026-10-11","achd":"2026-07-21"},
         "calibration":{"philly_restaurant_licenses":{"Meta, confidence 0.95+":{"n":3338,"matched":0.586}}},
         "files":[{"region":"Philadelphia","file":"places-philadelphia.json","count":4,"count_restaurants":3},
                  {"region":"Pittsburgh Region","file":"places-pittsburgh-region.json","count":6,"count_restaurants":5}]}
        """
        let philly = """
        {"region":"Philadelphia","places":[
          {"id":"a","n":"Dalessandro's Steaks","c":0,"co":0,"cu":0,"t":2,"s":0,"j":1,"phl":1,"hc":1,"k":1,"g":1,"mi":2,"ip":40,"a":"600 Wendover St",
           "z":"19128","la":40.0257,"lo":-75.2167,"dish":"cheesesteak"},
          {"id":"b","n":"Oyster House","c":0,"co":0,"cu":1,"t":2,"s":0,"j":1,"phl":1,"hc":1,"h":1,"ip":80,"f":1976,"a":"1516 Sansom St","z":"19102",
           "la":39.9502,"lo":-75.1665},
          {"id":"c","n":"Iannelli's Bakery","c":0,"co":0,"cu":2,"t":1,"s":1,"hc":1,"k":8,"g":2,"a":"1155 E Passyunk Ave","la":39.9339,"lo":-75.1576},
          {"id":"d","n":"Wawa","c":0,"co":0,"cu":0,"t":1,"s":2,"b":0,"ch":400,"v":1,"cc":1,"la":39.9520,"lo":-75.1640}
        ]}
        """
        let west = """
        {"region":"Pittsburgh Region","places":[
          {"id":"f","n":"Pierogies Plus","c":2,"co":1,"cu":3,"t":2,"s":0,"j":2,"hc":1,"k":32,"g":4,"a":"342 Island Ave","la":40.4660,"lo":-80.0650,
           "ac":{"p":"Inspected & Permitted","d":"2026-07-01"}},
          {"id":"g","n":"Primanti Bros.","c":1,"co":1,"cu":0,"t":2,"s":0,"j":2,"hc":1,"k":64,"g":4,"a":"46 18th St","la":40.4508,"lo":-79.9850,
           "ac":{"p":"Consumer Alert","d":"2026-06-15"}},
          {"id":"h","n":"Millvale Pierogi Shop","c":1,"co":1,"cu":3,"t":0,"s":1,"mu":0,"g":4,"a":"100 Grant Ave","la":40.4800,"lo":-79.9790},
          {"id":"i","n":"VFW Post 1","c":1,"co":1,"cu":5,"t":1,"s":1,"v":1,"mc":1,"la":40.4400,"lo":-79.9900},
          {"id":"j","n":"Shady Maple Smorgasbord","c":4,"co":2,"cu":5,"t":1,"s":1,"hc":1,"k":128,"g":8,"a":"129 Toddy Dr","la":40.1390,"lo":-76.0330},
          {"id":"k","n":"Lititz Family Diner","c":3,"co":2,"cu":4,"t":1,"s":1,"g":32,"a":"200 E Main St","la":40.1570,"lo":-76.3010}
        ]}
        """
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("pa-test-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try index.data(using: .utf8)!.write(to: dir.appendingPathComponent("index.json"))
        try philly.data(using: .utf8)!.write(to: dir.appendingPathComponent("places-philadelphia.json"))
        try west.data(using: .utf8)!.write(to: dir.appendingPathComponent("places-pittsburgh-region.json"))
        let model = AppModel(defaults: UserDefaults(suiteName: "test-\(UUID().uuidString)")!)
        await model.load(from: dir)
        XCTAssertTrue(model.isLoaded, model.loadError ?? "")
        return model
    }

    func testDecodesRegionFilesAndHidesCountersAndClubs() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.places.count, 10)
        XCTAssertEqual(m.place(id: "f")?.region, "Pittsburgh Region")
        XCTAssertEqual(m.place(id: "j")?.region, "South Central")
        let all = Set(m.list(.all, sort: .name, search: "", here: nil).map(\.id))
        XCTAssertFalse(all.contains("d"), "a convenience-store counter is hidden unless asked for (Nick, 2026-10-19)")
        XCTAssertFalse(all.contains("i"), "a members-only club is hidden unless asked for")
        XCTAssertTrue(m.place(id: "d")!.isCounter)
        XCTAssertTrue(m.place(id: "i")!.isMembersClub)
        m.filters.includeNonRestaurants = true
        XCTAssertTrue(Set(m.list(.all, sort: .name, search: "", here: nil).map(\.id)).isSuperset(of: ["d", "i"]))
    }

    func testGuidesListOnlyHandCheckedPlaces() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.list(.cheesesteaks, sort: .name, search: "", here: nil).map(\.id), ["a"])
        XCTAssertEqual(m.list(.tomatoPie, sort: .name, search: "", here: nil).map(\.id), ["c"])
        XCTAssertEqual(Set(m.list(.pierogies, sort: .name, search: "", here: nil).map(\.id)), ["f", "g"],
                       "pierogies and Pittsburgh sandwiches share a guide; a listing merely named \u{201C}Pierogi\u{201D} stays out")
        XCTAssertEqual(m.list(.dutch, sort: .name, search: "", here: nil).map(\.id), ["j"])
        XCTAssertEqual(m.list(.diners, sort: .name, search: "", here: nil).map(\.id), [], "a name alone isn't hand-checked")
        XCTAssertEqual(m.list(.all, sort: .name, search: "lititz family diner", here: nil).map(\.id), ["k"], "but it's still in the directory")
        XCTAssertEqual(m.list(.icons, sort: .iconic, search: "", here: nil).first?.id, "b")
        XCTAssertEqual(m.list(.nearMe, sort: .nearest, search: "", here: nil), [], "near me needs a location")
    }

    func testTownsAndMunicipalities() async throws {
        let m = try await sampleModel()
        func ids(_ q: String) -> Set<String> { Set(m.list(.all, sort: .name, search: q, here: nil).map(\.id)) }
        XCTAssertEqual(ids("mckees rocks"), ["f"])
        XCTAssertEqual(ids("millvale"), ["h"], "the municipality finds a place mailed as Pittsburgh")
        XCTAssertEqual(m.place(id: "a")?.fullAddress, "600 Wendover St, Philadelphia, PA 19128")
        XCTAssertEqual(m.place(id: "f")?.placeName, "McKees Rocks")
    }

    func testSearchTagsDishesAndStreets() async throws {
        let m = try await sampleModel()
        func ids(_ q: String) -> [String] { m.list(.all, sort: .name, search: q, here: nil).map(\.id) }
        XCTAssertEqual(Set(ids("pierogies")), ["f", "g", "h"])
        XCTAssertEqual(ids("cheesesteak"), ["a"])
        XCTAssertEqual(ids("dalessandros"), ["a"], "\u{201C}Dalessandro's\u{201D} without the apostrophe")
        XCTAssertEqual(ids("alessandro"), [], "matches the start of words only")
        XCTAssertEqual(ids("sansom street"), ["b"], "street words match the abbreviated address")
        XCTAssertEqual(ids("smorgasbord"), ["j"])
        XCTAssertEqual(ids("pierogies in millvale"), ["h"], "a stop word after a guide and a place isn't a search word")
        XCTAssertEqual(Search.normalizeAddress("PA-30 Main St"), "rt 30 main st", "route spellings read the same")
        XCTAssertEqual(Search.normalizeAddress("SR 309"), "rt 309")
        XCTAssertEqual(ids("🥨"), [], "nothing searchable typed means no results, not everything")
        XCTAssertEqual(ids("!!! ?"), [])
    }

    /// Typing narrows from the previous result, but never across a change of meaning ("pierog" is a word, "pierogi" is the guide).
    func testIncrementalSearchKeepsGuideMatches() async throws {
        let m = try await sampleModel()
        _ = m.list(.all, sort: .name, search: "pierog", here: nil)
        XCTAssertEqual(Set(m.list(.all, sort: .name, search: "pierogi", here: nil).map(\.id)), ["f", "g", "h"])
        _ = m.list(.all, sort: .name, search: "oy", here: nil)
        XCTAssertEqual(m.list(.all, sort: .name, search: "oyster", here: nil).map(\.id), ["b"])
        XCTAssertTrue(m.list(.all, sort: .name, search: "o", here: nil).map(\.id).contains("b"), "a shorter search widens again")
    }

    func testNearestSort() async throws {
        let m = try await sampleModel()
        let marketSquare = CLLocation(latitude: 40.4406, longitude: -79.9959)
        XCTAssertEqual(m.list(.nearMe, sort: .nearest, search: "", here: marketSquare).first?.id, "g", "Primanti's in the Strip is closest to Market Square")
    }

    func testOfficialRecordsStayWithTheirJurisdiction() async throws {
        let m = try await sampleModel()
        XCTAssertEqual(m.place(id: "f")?.placard?.color, .green)
        XCTAssertEqual(m.place(id: "g")?.placard?.color, .yellow)
        XCTAssertEqual(m.place(id: "g")?.placard?.d, "2026-06-15", "a placard always carries its inspection date")
        XCTAssertNil(m.place(id: "b")?.placard, "no ACHD placard in Philadelphia")
        XCTAssertTrue(m.place(id: "b")!.phillyLicensed)
        XCTAssertFalse(m.place(id: "f")!.phillyLicensed)
        XCTAssertEqual(ACHDPlacard(p: "Closed - Imminent Health Hazard", d: nil).color, .red)
        XCTAssertEqual(ACHDPlacard(p: "Follow Up Required", d: nil).color, .other, "a value we don't know isn't guessed")
        XCTAssertEqual(m.recordsThrough?.achd, "2026-07-21")
        XCTAssertEqual(m.recordsThrough?.philly, "2026-10-11")
    }

    /// "Outside Pennsylvania" follows the state line, not a box: Wilmington and Binghamton sit inside the bounding box.
    func testStateOutline() {
        XCTAssertTrue(StateOutline.contains(latitude: 39.9524, longitude: -75.1636), "Philadelphia City Hall")
        XCTAssertTrue(StateOutline.contains(latitude: 40.4406, longitude: -79.9959), "Pittsburgh")
        XCTAssertTrue(StateOutline.contains(latitude: 42.1292, longitude: -80.0851), "Erie")
        XCTAssertTrue(StateOutline.contains(latitude: 40.7934, longitude: -77.8600), "State College")
        XCTAssertFalse(StateOutline.contains(latitude: 39.7447, longitude: -75.5484), "Wilmington, Delaware")
        XCTAssertFalse(StateOutline.contains(latitude: 42.0987, longitude: -75.9180), "Binghamton, New York")
        XCTAssertFalse(StateOutline.contains(latitude: 39.9526, longitude: -75.1200), "Camden, New Jersey, across the Delaware")
        XCTAssertFalse(StateOutline.contains(latitude: 37.3349, longitude: -122.0090), "Cupertino")
    }

    func testFiltersSavedPlacesAndLabels() async throws {
        let m = try await sampleModel()
        m.filters = Filters(confirmedOnly: true)
        XCTAssertFalse(m.list(.all, sort: .name, search: "", here: nil).contains { $0.id == "h" }, "single listings drop out")
        m.filters = Filters(region: "Philadelphia")
        XCTAssertEqual(Set(m.list(.all, sort: .name, search: "", here: nil).map(\.id)), ["a", "b", "c"])
        m.filters = Filters(town: "Pittsburgh")
        XCTAssertEqual(Set(m.list(.all, sort: .name, search: "", here: nil).map(\.id)), ["g", "h"])
        let p = m.place(id: "b")!
        m.toggleSaved(p)
        XCTAssertEqual(m.savedPlaces.map(\.id), ["b"])
        m.toggleSaved(p)
        XCTAssertTrue(m.savedPlaces.isEmpty)
        XCTAssertEqual(m.matchRate(for: m.place(id: "c")!), "59%", "listings cite Philadelphia's measured rate")
        XCTAssertNil(m.matchRate(for: m.place(id: "a")!), "licensed places don't cite a listing rate")
        XCTAssertFalse(PlaceDetailView.date("2026-04-29").isEmpty)
    }

    /// The real bundled data decodes and keeps the data rules.
    func testBundledData() async throws {
        let m = AppModel(defaults: UserDefaults(suiteName: "bundle-\(UUID().uuidString)")!)
        await m.load()
        XCTAssertTrue(m.isLoaded, m.loadError ?? "")
        XCTAssertGreaterThan(m.restaurantCount, 20_000)
        XCTAssertEqual(m.places.filter { !$0.isVenue }.count, m.restaurantCount, "every file in index.json loaded")
        XCTAssertGreaterThan(m.places.filter { $0.region == "Philadelphia" }.count, 4_000)
        XCTAssertEqual(m.regions.count, 9)
        XCTAssertGreaterThanOrEqual(m.count(.icons), 15)
        XCTAssertGreaterThanOrEqual(m.count(.cheesesteaks), 40, "the hand-checked cheesesteak, roast pork and hoagie list")
        XCTAssertGreaterThanOrEqual(m.count(.tomatoPie), 25)
        XCTAssertGreaterThanOrEqual(m.count(.dutch), 4)
        XCTAssertTrue(m.places.contains { $0.name == "Dalessandro's Steaks" && $0.handChecked && $0.michelin == .bib && Guide.cheesesteaks.includes($0) },
                      "one record per place: the MICHELIN Bib and the cheesesteak guide land on the same listing")
        XCTAssertEqual(m.places.filter { $0.name.hasPrefix("Del Rossi's") && $0.handChecked }.count, 1, "no duplicate of an honored place")
        XCTAssertEqual(Set(m.places.map(\.id)).count, m.places.count, "ids are unique")
        XCTAssertTrue(m.places.contains { $0.name == "Oyster House" && $0.city == "Philadelphia" && $0.handChecked })
        XCTAssertFalse(m.places.contains { $0.name.range(of: #"gentlem[ae]n'?s club|strip club|exotic dancer"#, options: [.regularExpression, .caseInsensitive]) != nil },
                       "adult clubs aren't restaurants")
        XCTAssertFalse(m.places.contains { ($0.website?.absoluteString ?? "").range(
            of: #"yelp\.com|business\.site|google\.com|groupon\.com|yellowpages\.com"#, options: .regularExpression) != nil },
                       "directory links were checked out")
        XCTAssertTrue(m.places.allSatisfy { $0.placard == nil || $0.county == "Allegheny" }, "ACHD placards only in Allegheny County")
        XCTAssertTrue(m.places.allSatisfy { $0.placard == nil || $0.placard?.d != nil }, "an official placard always shows its date")
        XCTAssertTrue(m.places.allSatisfy { !$0.phillyLicensed || $0.county == "Philadelphia" })
        XCTAssertTrue(m.places.allSatisfy { !($0.isCounter || $0.isMembersClub) || $0.isVenue }, "counters and clubs stay hidden")
        XCTAssertFalse(m.places.contains { !$0.isVenue && $0.name.range(of: #"^(?:Wawa|Sheetz)\b"#, options: .regularExpression) != nil })
        XCTAssertTrue(m.places.allSatisfy { $0.phone == nil || $0.phone!.range(of: #"^\+1\d{10}$"#, options: .regularExpression) != nil }, "phones are +1 and ten digits")
    }
}
