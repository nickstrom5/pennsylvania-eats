import SwiftUI

struct AboutView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Text("PENNSYLVANIA EATS").displayFont(30).foregroundStyle(Theme.navy)
                    Text("A free guide to \(model.restaurantCount.formatted()) restaurants across Pennsylvania, with hand-checked lists of cheesesteak and hoagie shops, tomato pie, pierogies, Pennsylvania Dutch dining rooms, soft pretzel bakeries and diners, and Allegheny County's official inspection placards. No account, no ads, no tracking.")
                        .font(.subheadline).foregroundStyle(Theme.ink2)
                    Text("\(Links.appName) (\u{201C}PA Eats\u{201D}) is an independent app by Nicholas Soderstrom. It is not affiliated with, endorsed by or operated by the Commonwealth of Pennsylvania, its Department of Agriculture or Liquor Control Board, the City of Philadelphia or its Department of Public Health or Department of Licenses and Inspections, Allegheny County or its Health Department, Bucks or Montgomery County, the Western Pennsylvania Regional Data Center, Michelin, the James Beard Foundation, Apple, or any restaurant, team or chain.")
                        .font(.footnote).foregroundStyle(Theme.muted)
                }
                .padding(.vertical, 4)
            }
            Section("How the lists are built") {
                Text("Cheesesteaks, roast pork and hoagies, tomato pie and Old Forge pizza, pierogies and Pittsburgh classics, Pennsylvania Dutch, soft pretzels, diners and the oldest places are hand-checked: each was checked against a 2025 or 2026 source (the place's own website or menu, local news, or a tourism listing), with the address checked.")
                Text("The rest come from Overture Maps' open place data and official lists: the City of Philadelphia's food licenses\(model.recordsThrough?.achd == nil ? "" : " and the Allegheny County Health Department's food facility permits"). Map listings are kept only when they proved reliable: checked against Philadelphia's restaurant licenses, high-confidence listings matched a licensed food business \(rate("philly_restaurant_licenses", "Meta, confidence 0.95+")) of the time (the license list also holds schools and corner stores, so that's a floor). Members-only clubs and convenience-store counters are left out. Website links are checked, and any that no longer belong to the place are left out.")
                Text("Inspection results stay with the agency that published them. In Allegheny County the placard is the Health Department's own, shown with its date. Philadelphia, Bucks and Montgomery counties and the Pennsylvania Department of Agriculture post their reports one search at a time, so the app links to them. There is no statewide grade, and this app doesn't make one.")
                Text("Ratings, reviews, hours and photos are Apple Maps' own, shown live in Apple's place card. This app doesn't store or rank by them.")
            }
            .font(.subheadline).foregroundStyle(Theme.ink2)
            Section("Sources") {
                source("Overture Maps Foundation", "Restaurant listings and websites come from Overture Maps Foundation places data (overturemaps.org), release \(model.overtureRelease), filtered and reformatted for this app.\n• Data from Meta, Microsoft, DAC and BrightQuery. Available under CDLA Permissive 2.0.\n• Data from Foursquare. Copyright 2024 Foursquare Labs, Inc. All rights reserved. Available under Apache 2.0. Foursquare data was transformed to the Overture schema; this app further filtered and reformatted it. See the NOTICE below.\n• Data from AllThePlaces. Available under CC0 1.0.", "https://overturemaps.org")
                source("City of Philadelphia", "Licenses and Inspections Business Licenses (OpenDataPhilly, City of Philadelphia License), newest issue \(model.recordsThrough?.philly ?? "—") less a week: food licenses, used for the trade name, address and whether a license is active. Legal and owner names are never shown. \u{201C}The City of Philadelphia makes no representation about the accuracy of any specific information in this data and is provided \u{2018}as is\u{2019} and without Warranty of any kind.\u{201D}", "https://opendataphilly.org/datasets/licenses-and-inspections-business-licenses/")
                if let achd = model.recordsThrough?.achd {
                    source("Allegheny County Health Department", "Restaurant/Food Facility Inspections (Western Pennsylvania Regional Data Center, CC0), records through \(achd): the placard posted after the latest inspection and its date.", "https://data.wprdc.org/dataset/allegheny-county-restaurant-food-facility-inspection-violations")
                }
                source("Pennsylvania Department of Agriculture", "PA Food Safety Inspection Search, linked from each place outside Allegheny, Philadelphia, Bucks and Montgomery counties. \u{201C}Please remember that any inspection is a 'snapshot' of the day and time of the inspection. An inspection conducted on any given day may not be representative of the overall, long-term cleanliness of an establishment. Also, at the time of the inspection, violations are recorded but are often corrected on site prior to the inspector leaving the establishment.\u{201D}", "https://www.pafoodsafety.pa.gov/Web/Inspection/PublicInspectionSearch.aspx")
                source("Places and outlines", "U.S. Census Bureau cartographic boundary files, 2025 (public domain), for counties, municipalities and the state outline.", nil)
                source("Honors", "The MICHELIN Guide's Philadelphia selection (first revealed November 2025: stars, Bib Gourmand and Green Star) and James Beard Foundation awards and America's Classics, 2025 and 2026, are reported as facts and checked by hand against public announcements. MICHELIN and the MICHELIN Guide are trademarks of Michelin. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation. Other names belong to their owners.", nil)
                source("Maps", "Maps, place cards and directions by Apple Maps.", nil)
            }
            Section("Licenses") {
                NavigationLink("Community Data License Agreement – Permissive 2.0") { LicenseText(file: "CDLA-Permissive-2.0", title: "CDLA Permissive 2.0") }
                NavigationLink("Apache License 2.0") { LicenseText(file: "Apache-2.0", title: "Apache License 2.0") }
                NavigationLink("Foursquare OS Places NOTICE") { LicenseText(file: "Foursquare-NOTICE", title: "Foursquare NOTICE") }
            }
            Section("Privacy") {
                Text("The app collects nothing. Your location, if you allow it, only sorts lists by distance and shows where you are on the map, on this device. Saved places stay on this device.")
                    .font(.subheadline).foregroundStyle(Theme.ink2)
                Link("Privacy policy", destination: Links.privacy)
                Link("Terms of use", destination: Links.terms)
            }
            Section("Help") {
                Link("Report a missing or closed place", destination: Links.correctionEmail)
                Link("Email \(Links.supportEmail)", destination: URL(string: "mailto:\(Links.supportEmail)")!)
                Link("Website", destination: Links.site)
                Text("Data as of \(model.generated). Places open and close; check before you go. Version \(Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0")")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
        }
        .navigationTitle("About")
        .tint(Theme.navy)
    }

    private func rate(_ area: String, _ group: String) -> String {
        guard let g = model.calibration[area]?[group] else { return "most" }
        return "\(Int((g.matched * 100).rounded()))%"
    }

    @ViewBuilder
    private func source(_ name: String, _ detail: String, _ url: String?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            if let url, let u = URL(string: url) { Link(name, destination: u).font(.subheadline.weight(.semibold)) }
            else { Text(name).font(.subheadline.weight(.semibold)) }
            Text(detail).font(.caption).foregroundStyle(Theme.muted)
        }
    }
}

/// A bundled license text (Resources/Licenses), reflowed rather than shown as raw 80-column lines.
struct LicenseText: View {
    let file: String
    let title: String

    var body: some View {
        ScrollView {
            Text(text).font(.footnote).foregroundStyle(Theme.ink).textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading).padding()
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
    }

    private var text: String {
        guard let url = Bundle.main.url(forResource: file, withExtension: "txt"),
              let raw = try? String(contentsOf: url, encoding: .utf8) else { return "License text missing." }
        // join hard-wrapped lines into paragraphs; keep blank lines and list items as breaks
        var out: [String] = []
        for para in raw.components(separatedBy: "\n\n") {
            let lines = para.components(separatedBy: "\n").map { $0.trimmingCharacters(in: .whitespaces) }
            var joined = ""
            for l in lines where !l.isEmpty {
                let startsItem = l.hasPrefix("–") || l.hasPrefix("-") || l.range(of: #"^\(?[a-z0-9]{1,3}[.)]\s"#, options: .regularExpression) != nil
                joined += joined.isEmpty ? l : (startsItem ? "\n" + l : " " + l)
            }
            if !joined.isEmpty { out.append(joined) }
        }
        return out.joined(separator: "\n\n")
    }
}
