import SwiftUI
import MapKit

struct PlaceDetailView: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    let place: Place

    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var mapItem: MKMapItem?
    @State private var lookingUp = false
    @State private var notOnAppleMaps = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                header
                actions
                if let c = place.coordinate { mapSnippet(c) }
                if place.handChecked { checked }
                if place.jamesBeard != nil || place.michelin != nil { honors }
                inspections
                listing
            }
            .padding(16)
        }
        .background(Theme.surface)
        .navigationTitle(place.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Button { model.toggleSaved(place) } label: {
                    Label(model.isSaved(place) ? "Saved" : "Save", systemImage: model.isSaved(place) ? "heart.fill" : "heart")
                }
                ShareLink(item: shareText) { Label("Share", systemImage: "square.and.arrow.up") }
            }
        }
        .mapItemDetailSheet(item: $mapItem)
        .alert("Not on Apple Maps", isPresented: $notOnAppleMaps) {
            Button("Open Apple Maps anyway") { AppleMaps.openInMaps(place) }
            Button("OK", role: .cancel) {}
        } message: {
            Text("Apple Maps doesn't have a listing for \(place.name) at this spot, so there are no ratings or hours to show here.")
        }
    }

    // MARK: sections

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text((place.placeName ?? "Pennsylvania").uppercased())
                .font(.caption.weight(.bold)).tracking(1.2).foregroundStyle(Theme.navy2)
            Text(place.name.uppercased())
                .displayFont(38).foregroundStyle(Theme.navy)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            Text([place.fullAddress, place.cuisine].filter { !$0.isEmpty }.joined(separator: " · "))
                .font(.subheadline).foregroundStyle(Theme.ink2)
                .textSelection(.enabled)
            if let here = model.screenshotLocation ?? location.location, let l = place.location {
                Text("\(here.milesText(to: l)) away").font(.subheadline).foregroundStyle(Theme.muted)
            }
            PlaceChips(place: place)
        }
    }

    private var actions: some View {
        VStack(spacing: 10) {
            Button {
                lookingUp = true
                Task {
                    let item = await AppleMaps.findItem(for: place)
                    lookingUp = false
                    if let item { mapItem = item } else { notOnAppleMaps = true }
                }
            } label: {
                // at the largest text sizes the caption goes under the title, so "Ratings" isn't split across lines
                let layout = typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(alignment: .leading, spacing: 4)) : AnyLayout(HStackLayout())
                layout {
                    HStack {
                        if lookingUp { ProgressView().tint(.white) } else { Image(systemName: "star.bubble") }
                        Text("Ratings, hours & photos").fontWeight(.semibold)
                    }
                    if !typeSize.isAccessibilitySize { Spacer() }
                    Text("Apple Maps").font(.caption)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(14)
                .foregroundStyle(.white)
                .background(RoundedRectangle(cornerRadius: 12).fill(Theme.navy))
            }
            .disabled(place.coordinate == nil || lookingUp)
            .accessibilityHint("Opens the Apple Maps place card with current ratings and hours")

            HStack(spacing: 10) {
                actionButton("Directions", "arrow.triangle.turn.up.right.diamond") { AppleMaps.openInMaps(place, directions: true) }
                if let phone = place.phone, let url = URL(string: "tel:\(phone.filter { $0.isNumber || $0 == "+" })") {
                    actionButton("Call", "phone") { UIApplication.shared.open(url) }
                }
                if let web = place.website {
                    actionButton("Website", "safari") { UIApplication.shared.open(web) }
                }
            }
        }
    }

    private func actionButton(_ title: String, _ icon: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 4) {
                Image(systemName: icon).font(.title3)
                Text(title).font(.caption.weight(.semibold))
            }
            .frame(maxWidth: .infinity, minHeight: 56)
            .foregroundStyle(Theme.navy)
            .background(RoundedRectangle(cornerRadius: 12).strokeBorder(Theme.rule2))
        }
    }

    private func mapSnippet(_ c: CLLocationCoordinate2D) -> some View {
        Map(initialPosition: .region(MKCoordinateRegion(center: c, latitudinalMeters: 900, longitudinalMeters: 900)), interactionModes: []) {
            Marker(place.name, systemImage: MarkerGlyph.symbol(for: place), coordinate: c).tint(place.handChecked ? Theme.markerAccent : Theme.navy)
        }
        .frame(height: 170)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .onTapGesture { AppleMaps.openInMaps(place) }
        .accessibilityLabel("Map of \(place.name). Opens Apple Maps.")
    }

    private var checked: some View {
        section("Hand-checked", icon: "checkmark.seal.fill", tint: Theme.accentSoft) {
            VStack(alignment: .leading, spacing: 8) {
                if let note = place.note { Text(note).font(.subheadline).foregroundStyle(Theme.ink2) }
                if !place.kinds.names.isEmpty { fact("On our lists", place.kinds.names.joined(separator: ", ")) }
                if let d = place.dishes { fact("Known for", d) }
                if let s = place.season { fact("Season", s) } else if place.isSeasonal { fact("Season", "Seasonal; check before you go.") }
                if let f = place.founded { fact("At this address since", "\(f)") }
                if let b = place.branchOf { fact("A branch of", b) }
                Text("Checked open in October 2026 against a 2025 or 2026 source: the place's own site or menu, local news, or a tourism listing. Hours and menus change, so check before you go.")
                    .font(.caption).foregroundStyle(Theme.ink2)
            }
        }
    }

    private var honors: some View {
        section("Honors", icon: "rosette") {
            VStack(alignment: .leading, spacing: 8) {
                if let m = place.michelin {
                    Label("\(m == .recommended && place.greenStar ? "MICHELIN Green Star" : m.label) · MICHELIN Guide, Philadelphia, 2025 selection", systemImage: "rosette").font(.subheadline).foregroundStyle(Theme.ink)
                }
                ForEach(lines(place.jamesBeard, prefix: "James Beard: "), id: \.self) { l in
                    Label(l, systemImage: "rosette").font(.subheadline).foregroundStyle(Theme.ink)
                }
                if let chef = place.chef { fact("Chef", chef) }
                Text("Honors are facts, not ratings. MICHELIN and the MICHELIN Guide are trademarks of Michelin. James Beard Foundation and James Beard Award are trademarks of the James Beard Foundation.")
                    .font(.caption).foregroundStyle(Theme.muted)
            }
        }
    }

    /// Each jurisdiction's own record, never blended. Only Allegheny County publishes results in bulk (ACHD's placard, official, with
    /// its date); Philadelphia, Bucks, Montgomery and the PA Department of Agriculture post reports one search at a time: we link them.
    @ViewBuilder
    private var inspections: some View {
        switch place.county {
        case "Allegheny":
            section("Health inspections · Allegheny County Health Department", icon: "checkmark.shield") {
                VStack(alignment: .leading, spacing: 8) {
                    if let pl = place.placard {
                        PlacardChip(placard: pl)
                        if let d = pl.d { kv("Inspection", Self.date(d)) }
                        Text("The placard is ACHD's own: green \u{201C}Inspected & Permitted\u{201D}, yellow \u{201C}Consumer Alert\u{201D} (up to 10 days to correct), red for a closure. We compute no grade. Source: Western Pennsylvania Regional Data Center, records through \(Self.date(model.recordsThrough?.achd ?? "")).")
                            .font(.caption).foregroundStyle(Theme.muted)
                    } else {
                        Text("No ACHD placard is matched to this place in the app's data.").font(.subheadline).foregroundStyle(Theme.ink2)
                    }
                    Link("ACHD food safety and inspection reports", destination: Links.achdInspections).font(.caption.weight(.semibold))
                }
            }
        case "Philadelphia":
            section("Licenses & inspections · City of Philadelphia", icon: "checkmark.shield") {
                VStack(alignment: .leading, spacing: 8) {
                    kv("L&I food license", place.phillyLicensed ? "Active" : "— (none matched)")
                    Text("The Department of Public Health posts inspection reports one search at a time, with no grade or score, so the app links to them rather than copying them. Licenses: City of Philadelphia, OpenDataPhilly.")
                        .font(.caption).foregroundStyle(Theme.muted)
                    Link("Philadelphia inspection reports", destination: Links.phillyInspections).font(.caption.weight(.semibold))
                }
            }
        case "Bucks", "Montgomery":
            section("Health inspections · \(place.county) County", icon: "checkmark.shield") {
                VStack(alignment: .leading, spacing: 8) {
                    Text("\(place.county) County's health department inspects its own restaurants and posts reports one search at a time, so the app links to them rather than copying them.")
                        .font(.caption).foregroundStyle(Theme.muted)
                    Link("\(place.county) County inspection reports", destination: place.county == "Bucks" ? Links.bucksInspections : Links.montgomeryInspections)
                        .font(.caption.weight(.semibold))
                }
            }
        default:
            section("Health inspections", icon: "checkmark.shield") {
                VStack(alignment: .leading, spacing: 8) {
                    Text("The Pennsylvania Department of Agriculture and local health departments post inspection results one search at a time, so the app links to them rather than copying them.")
                        .font(.caption).foregroundStyle(Theme.muted)
                    Text("PDA: \u{201C}Please remember that any inspection is a 'snapshot' of the day and time of the inspection. An inspection conducted on any given day may not be representative of the overall, long-term cleanliness of an establishment. Also, at the time of the inspection, violations are recorded but are often corrected on site prior to the inspector leaving the establishment.\u{201D}")
                        .font(.caption).foregroundStyle(Theme.muted)
                    Link("PA Food Safety Inspection Search", destination: Links.pdaInspections).font(.caption.weight(.semibold))
                }
            }
        }
    }

    private var listing: some View {
        section("How we know it's here", icon: "mappin.and.ellipse") {
            VStack(alignment: .leading, spacing: 8) {
                kv("Listed as", place.handChecked && place.tier != .licensed ? "Hand-checked" : place.tier.label)
                if place.tier == .licensed { kv("Official list", place.jurisdiction.listName) }
                kv("Liquor license", place.liquorLicense ?? "— (none matched)")
                kv("County", place.county + (place.region.isEmpty ? "" : " · \(place.region)"))
                if let m = place.municipality { kv("Municipality", m) }
                if place.chainCount >= 2 { kv("Locations in Pennsylvania", place.chainCount.formatted()) }
                Text(listingNote).font(.caption).foregroundStyle(Theme.muted)
            }
        }
    }

    private var listingNote: String {
        let checked = place.handChecked
        if place.source == "research" {
            return "On our hand-checked list (checked in October 2026 against a 2025 or 2026 source). The open map data didn't list it as a place to eat, so it's placed at its street address."
        }
        switch place.tier {
        case .licensed:
            return place.source == "official"
                ? "From the \(place.jurisdiction.listName). The open map data didn't have it, so it's placed at its street address."
                : "Matched to an active entry in the \(place.jurisdiction.listName)."
        case .confirmed where checked, .listing where checked:
            return "On our hand-checked list: checked open in October 2026 against a 2025 or 2026 source (its own site or menu, local news, or a tourism listing). It's in Overture's open map data too."
        case .confirmed, .listing:
            let rate = model.matchRate(for: place)
            let base = place.tier == .confirmed
                ? "A high-confidence listing in Overture's open map data."
                : "A single listing in Overture's open map data, so it may be closed or misfiled."
            let measured = rate.map { " Checked against Philadelphia's restaurant licenses, listings like this matched a licensed food business \($0) of the time (the license list also holds schools and corner stores, so that's a floor)." } ?? ""
            return base + measured + (checked ? " It's also on our hand-checked list, checked in October 2026 against a 2025 or 2026 source." : "")
        }
    }

    // MARK: helpers

    private var shareText: String {
        [place.name, place.fullAddress, "via \(Links.appName)", Links.site.absoluteString].filter { !$0.isEmpty }.joined(separator: "\n")
    }

    static func date(_ iso: String) -> String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = .gmt   // a day, not an instant: GMT has every midnight
        guard let d = f.date(from: iso) else { return iso }
        return d.formatted(Date.FormatStyle(date: .abbreviated, time: .omitted, timeZone: .gmt))
    }

    private func lines(_ s: String?, prefix: String) -> [String] {
        (s ?? "").components(separatedBy: "; ").filter { !$0.isEmpty }.map { prefix + $0 }
    }

    /// A section as a soft card: its label (with a small symbol), then its facts. Hand-checked research gets the gold card.
    private func section<Content: View>(_ title: String, icon: String, tint: Color = Theme.surface2, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Label {
                Text(title.uppercased()).font(.caption.weight(.bold)).tracking(1)
            } icon: {
                Image(systemName: icon).font(.caption.weight(.bold))
            }
            .foregroundStyle(Theme.navy2)
            .accessibilityAddTraits(.isHeader)
            content()
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 16).fill(tint))
    }

    private func fact(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink)
            Text(value).font(.subheadline).foregroundStyle(Theme.ink2)
        }
    }

    @ViewBuilder
    private func kv(_ k: String, _ v: String?) -> some View {
        if let v {
            HStack(alignment: .firstTextBaseline) {
                Text(k).font(.subheadline).foregroundStyle(Theme.ink2)
                Spacer(minLength: 12)
                Text(v).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.ink).multilineTextAlignment(.trailing)
            }
        }
    }
}

/// The glyph a place gets on the maps: steaks and hoagies, tomato pie, pierogies, PA Dutch, pretzels, diners, everything else.
enum MarkerGlyph {
    static func symbol(for p: Place) -> String {
        if !p.kinds.isDisjoint(with: [.cheesesteak, .roastPork, .hoagie]) || p.tags.contains(.steak) { return "takeoutbag.and.cup.and.straw.fill" }
        if !p.kinds.isDisjoint(with: [.tomatoPie, .oldForge]) { return "square.grid.2x2.fill" }
        if !p.kinds.isDisjoint(with: [.pierogi, .pittsburghSandwich]) { return "fork.knife.circle.fill" }
        if p.kinds.contains(.paDutch) { return "house.fill" }
        if p.kinds.contains(.pretzel) { return "infinity" }
        if p.kinds.contains(.diner) || p.tags.contains(.diner) { return "cup.and.saucer.fill" }
        if p.michelin != nil { return "rosette" }
        return "fork.knife"
    }
}

extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}
