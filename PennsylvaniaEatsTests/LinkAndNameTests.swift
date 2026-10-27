import XCTest
import Foundation

// Link and name guards for the bundled data (QA 2026-10-26, PA-1, PA-2, PA-5 and PA-3). Each is proven on the 2026-10-21 bundle,
// which carried 481 tracking-tagged links, 57 blocklisted ones and 21 legal-entity names.

/// QA 2026-10-26, PA-1 (the same rules as the 2026-10-19 fix in the other states): outbound links ship without tracking tags (ref=google, referrer=google_food_ordering, cn_channel, utm_* …).
/// pipeline/tracking_params.py strips them in the export; these are the same rules.
final class TrackingParamTests: XCTestCase {
    func testNoTrackingParametersInBundledLinks() throws {
        let files = TrackingParams.bundledJSON()
        XCTAssertFalse(files.isEmpty, "no bundled JSON found")
        var hits: [String] = []
        for url in files {
            let text = try String(contentsOf: url, encoding: .utf8)
            hits += TrackingParams.tracked(in: text).map { "\(url.lastPathComponent): \($0)" }
            hits += TrackingParams.trackedFragments(in: text).map { "\(url.lastPathComponent): \($0)" }
        }
        XCTAssertEqual(hits, [], "links with tracking parameters in the app's bundled data")
    }

    /// The guard fires on a broken copy (four kinds of tracking tag, one in escaped JSON) and leaves a store's own parameters alone.
    func testTrackingGuardCatchesABrokenCopy() {
        let broken = #"[{"w":"https:\/\/places.example.com\/menu?ref=google"},{"w":"https://a.example/?utm_source=gmb&store=4"},"#
            + #"{"w":"https://b.example/x?referrer=google_food_ordering"},{"w":"https://c.example/order/1?cn_channel=cn_google"}]"#
        XCTAssertEqual(TrackingParams.tracked(in: broken).count, 4)
        XCTAssertEqual(TrackingParams.trackedFragments(in: #"{"w":"https://cafe.example.com/philadelphia/#utm_source=x&utm_medium=Yext"}"#).count, 1)
        XCTAssertEqual(TrackingParams.trackedFragments(in: #"{"w":"https://cafe.example.com/#menu"}"#), [])
        let clean = #"[{"w":"https://order.example.com/menu?restaurantId=51&location=7"},{"w":"https://shop.example.com/?cid=12&ref=gs"}]"#
        XCTAssertEqual(TrackingParams.tracked(in: clean), [])
    }
}

enum TrackingParams {
    /// tracking by name, whatever the value
    static let keys = try! NSRegularExpression(pattern: #"^(?:utm[_-].*|gclid|gbraid|wbraid|dclid|fbclid|msclkid|mc_cid|mc_eid|_ga|_gl|igsh|"#
        + #"igshid|mibextid|srsltid|cn_channel|y_source|rwg_token|olonwp|ost_redirect_attribution|cmpid|yext_?.*)$"#, options: [.caseInsensitive])
    /// tracking only with these values
    static let values: [String: String] = ["ref": #"^(?:google|gmb|gbp|yext|bookmarks)\b"#, "referrer": "^google",
                                           "source": #"^(?:google|gmb|gbp|yext)\b"#, "cid": "^RF:YXT", "cmp": "^OKC-"]

    /// every .json file in the app bundle, subfolders included
    static func bundledJSON() -> [URL] {
        let all = FileManager.default.enumerator(at: Bundle.main.bundleURL, includingPropertiesForKeys: nil)?.allObjects as? [URL] ?? []
        return all.filter { $0.pathExtension == "json" && !$0.path.contains("/PlugIns/") }
    }

    static func isTracking(_ key: String, _ value: String) -> Bool {
        let k = key.trimmingCharacters(in: .whitespaces)
        if keys.firstMatch(in: k, range: NSRange(k.startIndex..., in: k)) != nil { return true }
        guard let pattern = values[k.lowercased()] else { return false }
        return value.trimmingCharacters(in: .whitespaces).range(of: pattern, options: [.regularExpression, .caseInsensitive]) != nil
    }

    /// links whose fragment carries the tags instead ("https://cafe.hardrock.com/philadelphia/#utm_source=…&utm_medium=Yext")
    static func trackedFragments(in text: String) -> [String] {
        let t = text.replacingOccurrences(of: "\\/", with: "/")
        let rx = try! NSRegularExpression(pattern: ##"https?://[^\s"'<>\\#]+#(?:[^\s"'<>\\]*&)?utm_[^\s"'<>\\]*"##)
        return rx.matches(in: t, range: NSRange(t.startIndex..., in: t)).map { String(t[Range($0.range, in: t)!]) }
    }

    /// links in a JSON text whose query carries a tracking parameter
    static func tracked(in text: String) -> [String] {
        let t = text.replacingOccurrences(of: "\\/", with: "/")
        let rx = try! NSRegularExpression(pattern: #"https?://[^\s"'<>\\]+"#)
        return rx.matches(in: t, range: NSRange(t.startIndex..., in: t)).compactMap { m -> String? in
            let s = String(t[Range(m.range, in: t)!])
            guard let q = s.split(separator: "?", maxSplits: 1).dropFirst().first else { return nil }
            let query = q.split(separator: "#", maxSplits: 1, omittingEmptySubsequences: false).first ?? ""
            for part in query.split(separator: "&") {
                let kv = part.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false)
                let k = String(kv[0]).replacingOccurrences(of: "+", with: " ").removingPercentEncoding ?? String(kv[0])
                let v = kv.count > 1 ? (String(kv[1]).replacingOccurrences(of: "+", with: " ").removingPercentEncoding ?? String(kv[1])) : ""
                if isTracking(k, v) { return s }
            }
            return nil
        }
    }
}

/// pipeline/website_blocklist.json (hacked, taken-over, expired or another business's sites, confirmed by hand in the link sweeps):
/// no link on it may ship in any field of any JSON file the app bundles. The 2026-10-19 QA found the export had only filtered the
/// website field, or nothing, so hijacked links were still in the bundle. Read from the repo, so a new entry needs no code change.
final class LinkBlocklistTests: XCTestCase {
    func testNoBlocklistedLinkInBundledData() throws {
        let entries = try LinkBlocklist.entries()
        XCTAssertFalse(entries.isEmpty, "the blocklist is missing or empty")
        let files = LinkBlocklist.bundledJSON()
        XCTAssertFalse(files.isEmpty, "no bundled JSON found")
        var hits: [String] = []
        for url in files {
            let text = try String(contentsOf: url, encoding: .utf8)
            hits += LinkBlocklist.hits(in: text, entries).map { "\(url.lastPathComponent): \($0)" }
        }
        XCTAssertEqual(hits, [], "blocklisted links in the app's bundled data")
    }

    /// The guard fires on a copy of the bundled data broken three ways: a blocklisted domain, its subdomain, and a "url" entry.
    func testBlocklistGuardCatchesABrokenCopy() throws {
        let entries = try LinkBlocklist.entries()
        let file = try XCTUnwrap(LinkBlocklist.bundledJSON().max { (try? $0.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0) ?? 0 < (try? $1.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0) ?? 0 })
        let text = try String(contentsOf: file, encoding: .utf8)
        let domain = try XCTUnwrap(entries.first { ($0["match"] as? String ?? "domain") == "domain" }?["domain"] as? String)
        let fake: [[String: Any]] = entries + [["match": "url", "url": "https://example.org/hacked-page"]]
        let before = LinkBlocklist.hits(in: text, fake).count
        let broken = text + "{\"w\":\"https://www.\(domain)/menu\"}{\"src\":\"http://shop.\(domain)/\"}{\"w\":\"https://example.org/hacked-page/\"}"
        XCTAssertEqual(LinkBlocklist.hits(in: broken, fake).count, before + 3, "a domain, a subdomain and a url entry are all caught")
        XCTAssertEqual(LinkBlocklist.hits(in: "{\"w\":\"https://not\(domain)/\"}", entries), [], "a host that only ends with the domain's letters isn't it")
    }
}

enum LinkBlocklist {
    static func entries() throws -> [[String: Any]] {
        let url = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("pipeline/website_blocklist.json")
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [[String: Any]])
    }

    /// every .json file in the app bundle, subfolders included
    static func bundledJSON() -> [URL] {
        let root = Bundle.main.bundleURL
        let all = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil)?.allObjects as? [URL] ?? []
        return all.filter { $0.pathExtension == "json" && !$0.path.contains("/PlugIns/") }
    }

    private static func host(_ u: URLComponents) -> String {
        var h = (u.host ?? "").lowercased()
        if h.hasSuffix(".") { h.removeLast() }
        return h.hasPrefix("www.") ? String(h.dropFirst(4)) : h
    }

    private static func trimmedPath(_ p: String) -> String { p.hasSuffix("/") ? String(p.dropLast()) : p }

    /// the links in a JSON text that an entry covers: a "domain" entry its domain and subdomains, a "url" entry that page only
    static func hits(in text: String, _ entries: [[String: Any]]) -> [String] {
        let t = text.replacingOccurrences(of: "\\/", with: "/")
        let rx = try! NSRegularExpression(pattern: #"https?://[^"\s\\]+"#, options: [.caseInsensitive])
        return rx.matches(in: t, range: NSRange(t.startIndex..., in: t)).compactMap { m -> String? in
            let s = String(t[Range(m.range, in: t)!])
            guard let u = URLComponents(string: s) else { return nil }
            let h = host(u)
            for e in entries {
                if (e["match"] as? String ?? "domain") == "url" {
                    guard let v = URLComponents(string: e["url"] as? String ?? "") else { continue }
                    if !h.isEmpty && h == host(v) && trimmedPath(u.path) == trimmedPath(v.path) { return s }
                } else {
                    var d = (e["domain"] as? String ?? "").lowercased()
                    if let r = d.range(of: "://") { d = String(d[r.upperBound...]) }
                    d = String(d.split(separator: "/").first ?? "")
                    if d.hasPrefix("www.") { d = String(d.dropFirst(4)) }
                    if !d.isEmpty && (h == d || h.hasSuffix("." + d)) { return s }
                }
            }
            return nil
        }
    }
}

/// QA 2026-10-26, PA-3: no place is shown under its license holder's legal name ("Bierfish Restaurant Partners, Lp", "1231 Barrage
/// Incorporated", "Dba Chick-fil-A"). pipeline/private_dining.py's entity_fix() gives the trade name or drops a bare holder in the export;
/// these are its patterns. Hand-checked and honored places are exempt (their names are researched). Venues count too: they're shown
/// with "Include non-restaurants".
final class EntityNameTests: XCTestCase {
    func testNoLegalEntityNameInBundledData() throws {
        var places: [[String: Any]] = []
        for url in LinkBlocklist.bundledJSON() {
            places += EntityNames.places(in: try Data(contentsOf: url))
        }
        XCTAssertGreaterThan(places.count, 1000, "the bundled places weren't found")
        XCTAssertEqual(EntityNames.hits(places), [], "legal-entity names in the app's bundled data")
    }

    /// The guard fires on a broken copy (a tail, a holder, a "dba", a house-number holder) and spares hand-checked and look-alike names.
    func testEntityGuardCatchesABrokenCopy() throws {
        let json = #"{"places":[{"n":"Bierfish Restaurant Partners, Lp"},{"n":"1231 Barrage Incorporated"},{"n":"Dba Chick-fil-A"},"#
            + #"{"n":"Spruce Restaurants L P","v":1},{"n":"Chestnut Restaurant Ventures"},{"n":"Starr Restaurant Group Lp","hc":1},"#
            + #"{"n":"Partners Deli and Arcade"},{"n":"Pizza Co"},{"n":"A&W"},{"n":"Lucky Corp Cafe"}]}"#
        XCTAssertEqual(EntityNames.hits(EntityNames.places(in: Data(json.utf8))),
                       ["Bierfish Restaurant Partners, Lp", "1231 Barrage Incorporated", "Dba Chick-fil-A", "Spruce Restaurants L P", "Chestnut Restaurant Ventures"])
    }
}

enum EntityNames {
    static let entityTail = try! NSRegularExpression(pattern: #"(?:[,\s]+(?:L\.?\s?P\.?|LTD\.?|LLC\.?|L\.L\.C\.?|LLP\.?|L\.L\.P\.?|INC\.?|INCORPOR\w*|CORP\.?|CORPORATION))+\s*$"#, options: [.caseInsensitive])
    static let holder = try! NSRegularExpression(pattern: #"(?:^|\s)(?:PARTNERS|PARTNERSHIP|HOLDINGS?|ENTERPRISES?|VENTURES|OWNER|INVESTMENTS|PROPERTIES)\s*$"#, options: [.caseInsensitive])
    static let dba = try! NSRegularExpression(pattern: #"(?:^|[,\s])(?:D\s?/?\s?B\s?/?\s?A|DOING BUSINESS AS)\.?:?\s"#, options: [.caseInsensitive])

    static func matches(_ rx: NSRegularExpression, _ s: String) -> Bool { rx.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil }

    static func hits(_ places: [[String: Any]]) -> [String] {
        places.compactMap { p in
            guard let n = p["n"] as? String else { return nil }
            return matches(entityTail, n) || matches(holder, n) || matches(dba, n) ? n : nil
        }
    }

    /// every place in a region file except the hand-checked and honored ones
    static func places(in data: Data) -> [[String: Any]] {
        guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let places = obj["places"] as? [[String: Any]] else { return [] }
        return places.filter { $0["hc"] == nil && $0["mi"] == nil && $0["jbf"] == nil }
    }
}
