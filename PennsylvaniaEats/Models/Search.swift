import Foundation

/// Search that matches the start of words, the way the web leaderboard does:
/// "dalessandro" finds Dalessandro's Steaks, "south 9th" finds S 9th St, "erie" or a mailing name like "feasterville" narrows to that
/// place, and "cheesesteaks", "tomato pie", "pierogies", "pa dutch" or "pretzels" mean those Pennsylvania guides (or a place named that way).
struct Search {
    static let typeSynonyms = ["avenue": "ave", "av": "ave", "street": "st", "boulevard": "blvd", "road": "rd", "drive": "dr", "place": "pl",
                               "court": "ct", "parkway": "pkwy", "highway": "hwy", "lane": "ln", "trail": "trl", "circle": "cir", "terrace": "ter",
                               "turnpike": "tpke", "route": "rt", "rte": "rt"]
    static let synonyms: [String: String] = typeSynonyms.merging(["north": "n", "south": "s", "east": "e", "west": "w", "saint": "st", "mount": "mt"]) { a, _ in a }
    static let abbreviations = Set(synonyms.values)
    static let typeAbbreviations = Set(typeSynonyms.values)
    static let tagPhrases: [(String, PlaceTags)] = [("cheesesteaks", .steak), ("cheesesteak", .steak), ("cheese steaks", .steak),
                                                   ("cheese steak", .steak), ("roast pork", .steak), ("hoagies", .steak), ("hoagie", .steak),
                                                   ("tomato pie", .pie), ("old forge", .pie), ("pierogies", .pierogi), ("pierogi", .pierogi),
                                                   ("perogies", .pierogi), ("pennsylvania dutch", .dutch), ("pa dutch", .dutch),
                                                   ("smorgasbord", .dutch), ("soft pretzels", .pretzel), ("soft pretzel", .pretzel),
                                                   ("pretzels", .pretzel), ("pretzel", .pretzel), ("diners", .diner), ("diner", .diner)]

    private static let enUS = Locale(identifier: "en_US")

    /// Lowercase, no accents or apostrophes, "&" as "and" ("B&B" stays "bb"), everything else a single space.
    /// Runs for every place at launch (64,000 x 3), so it's one pass over the characters instead of four regex passes; the output
    /// matched the regex version on all 192,000 launch strings when it was written.
    static func normalize(_ s: String) -> String {
        var t = s.utf8.allSatisfy({ $0 < 0x80 }) ? s.lowercased()
            : s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: enUS).lowercased()
        if t.contains("&") {
            t = t.replacingOccurrences(of: #"\b([a-z0-9])\s*&\s*([a-z0-9])\b"#, with: "$1$2", options: .regularExpression)
            t = t.replacingOccurrences(of: "&", with: " and ")
        }
        var out = String.UnicodeScalarView()
        var gap = false
        for u in t.unicodeScalars {
            if u == "'" || u == "\u{2019}" || u == "`" { continue }
            switch u.properties.generalCategory {
            case .uppercaseLetter, .lowercaseLetter, .titlecaseLetter, .modifierLetter, .otherLetter, .decimalNumber, .letterNumber, .otherNumber:
                if gap && !out.isEmpty { out.append(" ") }
                gap = false
                out.append(u)
            default:
                gap = true
            }
        }
        return String(out)
    }

    /// A route number: "PA-30", "US 22", "SR 309", "Rte 611" and "route 611" all read "rt <number>" (a letter suffix stays).
    static let routeWords: Set<String> = ["pa", "us", "sr", "rte", "route", "rt"]
    static func routes(_ words: [String]) -> [String] {
        words.enumerated().map { i, w in
            routeWords.contains(w) && i + 1 < words.count && words[i + 1].range(of: #"^\d+[a-z]?$"#, options: .regularExpression) != nil ? "rt" : w
        }
    }

    /// Addresses (only) get their street words abbreviated so "north main street" finds "N Main St".
    static func normalizeAddress(_ s: String) -> String {
        routes(normalize(s).split(separator: " ").map(String.init)).map { synonyms[$0] ?? $0 }.joined(separator: " ")
    }

    struct Query {
        var tokens: [[String]] = []     // each token: needles, any of which may match
        var town: String?
        var village: String?
        var placePhrase: String?
        var tag: PlaceTags?
        var tagPhrase: String?
        var isEmpty: Bool { tokens.isEmpty && town == nil && village == nil && tag == nil }
    }

    /// `towns` maps a normalized city name ("erie", "state college", "philadelphia") to its display name; `villages` the same for
    /// neighborhoods and mailing names ("flushing", "williamsburg", "levittown"), which narrow to places with that name.
    static func parse(_ text: String, towns: [String: String], villages: [String: String] = [:]) -> Query {
        var q = Query()
        var raw = normalize(text).split(separator: " ").map(String.init)
        var i0 = 0
        while i0 + 1 < raw.count { if raw[i0] == "near" && raw[i0 + 1] == "me" { raw.removeSubrange(i0...(i0 + 1)) } else { i0 += 1 } }   // "near me" asks for nothing
        guard !raw.isEmpty else { return q }
        var mapped = routes(raw).map { synonyms[$0] ?? $0 }
        func find(_ phrase: String) -> Range<Int>? {
            let p = phrase.split(separator: " ").map(String.init)
            guard p.count <= mapped.count else { return nil }
            for i in 0...(mapped.count - p.count) where Array(mapped[i..<i + p.count]) == p { return i..<i + p.count }
            return nil
        }
        func cut(_ r: Range<Int>) -> String {
            let words = raw[r].joined(separator: " ")
            raw.removeSubrange(r); mapped.removeSubrange(r)
            return words
        }
        for (phrase, tag) in tagPhrases {
            if let r = find(normalize(phrase)) { q.tag = tag; q.tagPhrase = cut(r); break }
        }
        // the longest town (then neighborhood) named in the query wins, unless a street type follows it ("flushing ave" is a street)
        func place(_ dict: [String: String]) -> (String, String)? {
            for key in dict.keys.sorted(by: { $0.count > $1.count }) {
                if let r = find(key), !(r.upperBound < mapped.count && typeAbbreviations.contains(mapped[r.upperBound])) {
                    return (dict[key]!, cut(r))
                }
            }
            return nil
        }
        if let (t, phrase) = place(towns) { q.town = t; q.placePhrase = phrase }
        else if let (v, phrase) = place(villages) { q.village = v; q.placePhrase = phrase }
        let stop: Set<String> = ["the", "and", "of", "a", "in", "near"]
        var idx = Array(raw.indices)
        // stop words go once a town, neighborhood or guide is set, or when any other word is left ("dim sum in flushing")
        if q.town != nil || q.village != nil || q.tag != nil || idx.contains(where: { !stop.contains(mapped[$0]) }) { idx = idx.filter { !stop.contains(mapped[$0]) } }
        let routed = routes(raw)
        for (n, i) in idx.enumerated() {
            let token = raw[i], isLast = n == idx.count - 1
            if routed[i] == "rt" && routeWords.contains(token) && token != "rt" { q.tokens.append([" rt "]); continue }   // "US 9W" = "Route 9W"
            if let abbr = synonyms[token] { q.tokens.append([" \(abbr) ", " \(token)"]); continue }
            let whole = (abbreviations.contains(token) && (!isLast || token.count > 1)) || (token.count <= 2 && !isLast)
            var needles = [" " + token + (whole ? " " : "")]
            // what people call a place ("katzs", "lucalis") may be a possessive the name doesn't have
            if token.count >= 4 && token.hasSuffix("s") && !whole { needles.append(" " + token.dropLast()) }
            if isLast && token.count >= 3 {
                for (word, abbr) in typeSynonyms where word != token && word.hasPrefix(token) { needles.append(" \(abbr) ") }
            }
            q.tokens.append(needles)
        }
        // "bleecker st": a finished street type sticks to the word before it
        if q.tokens.count >= 2, let last = idx.last, typeAbbreviations.contains(mapped[last]) {
            let prev = idx[idx.count - 2]
            q.tokens.removeLast(2)
            q.tokens.append([" \(mapped[prev]) \(mapped[last]) ", " \(raw[prev]) \(raw[last])"])
        }
        return q
    }

    static func matches(_ p: Place, _ q: Query) -> Bool {
        if let tag = q.tag, !p.tags.contains(tag) {
            let stem = normalize(q.tagPhrase ?? "").replacingOccurrences(of: #"s$"#, with: "", options: .regularExpression)
            if stem.isEmpty || !p.nameText.contains(" " + stem) { return false }
        }
        if let town = q.town, p.city != town {
            if !p.nameText.contains(" " + normalize(q.placePhrase ?? "")) { return false }
        }
        if let village = q.village, p.neighborhood != village && p.mailingName != village && p.municipality != village {
            if !p.nameText.contains(" " + normalize(q.placePhrase ?? "")) { return false }
        }
        for needles in q.tokens where !needles.contains(where: { p.searchText.contains($0) }) { return false }
        return true
    }

    /// Name matches first ("erie" puts Erie Brewing ahead of everything else in Erie).
    static func nameMatches(_ p: Place, _ q: Query) -> Bool {
        !q.tokens.isEmpty && q.tokens.allSatisfy { needles in needles.contains { p.nameText.contains($0) } }
    }
}
