import SwiftUI
import CoreLocation

struct GuideListView: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    let guide: Guide
    /// iPad passes a selection; iPhone pushes the place onto the stack
    var selection: Binding<Place?>? = nil

    @State private var sort: SortOrder?
    @State private var search = ""
    @State private var showFilters = false
    @State private var shown = 100

    private var order: SortOrder { sort ?? (guide.isClassic ? (here != nil ? .nearest : .featured) : guide.defaultSort) }
    private var here: CLLocation? { model.screenshotLocation ?? location.location }

    var body: some View {
        let places = model.list(guide, sort: order, search: search, here: here)
        List {
            Section {
                Text(guide.subtitle + (guide.isClassic ? ". Each one checked open with a 2025 or 2026 source." : ""))
                    .font(.subheadline).foregroundStyle(Theme.muted)
                    .listRowSeparator(.hidden)
                if guide == .dutch {
                    Text("Many Pennsylvania Dutch dining rooms close on Sundays, and some close for part of the winter. Check before you drive.")
                        .font(.caption).foregroundStyle(Theme.ink2).listRowSeparator(.hidden)
                }
                if (order == .nearest || guide == .nearMe) && here == nil { locationPrompt }
                if order == .nearest && model.screenshotLocation == nil && location.isOutsidePennsylvania {
                    Text("You're outside Pennsylvania. Every place here is in Pennsylvania, so distances are from where you are now.")
                        .font(.subheadline).foregroundStyle(Theme.ink2).listRowSeparator(.hidden)
                }
                if model.filters.activeCount > 0 { activeFilters }
            }
            Section {
                if places.isEmpty && !(guide == .nearMe && here == nil) {
                    ContentUnavailableView {
                        Label(search.isEmpty ? "Nothing here" : "No matches", systemImage: "magnifyingglass")
                    } description: {
                        Text(search.isEmpty ? "No places match your filters." : "No places match “\(search)” with your filters.")
                    } actions: {
                        if model.filters.activeCount > 0 { Button("Clear filters") { model.filters = Filters() } }
                        if !search.isEmpty { Button("Clear search") { search = "" } }
                    }
                }
                ForEach(Array(places.prefix(shown).enumerated()), id: \.element.id) { i, p in
                    row(p, rank: guide.isRanked ? i + 1 : nil)
                }
                if places.count > shown {
                    Button("Show more (\((places.count - shown).formatted()) left)") { shown += 200 }
                        .frame(maxWidth: .infinity).foregroundStyle(Theme.navy)
                }
            } header: {
                Text("\(places.count.formatted()) \(places.count == 1 ? "place" : "places") · \(order.label)").textCase(nil).foregroundStyle(Theme.ink2)
            }
        }
        .listStyle(.plain)
        .navigationTitle(guide.title)
        .navigationBarTitleDisplayMode(.large)
        .searchable(text: $search, placement: .navigationBarDrawer(displayMode: guide == .all ? .always : .automatic), prompt: "Name, town, street or zip")
        .onChange(of: search) { shown = 100 }
        .onChange(of: sort) { shown = 100 }
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                if guide.sortOptions.count > 1 {
                    Menu {
                        Picker("Sort", selection: Binding(get: { order }, set: { sort = $0; if $0 == .nearest { location.request() } })) {
                            ForEach(guide.sortOptions) { Text($0.label).tag($0) }
                        }
                    } label: { Label("Sort", systemImage: "arrow.up.arrow.down") }
                }
                Button { showFilters = true } label: {
                    Label("Filters", systemImage: model.filters.activeCount > 0 ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
                }
            }
        }
        .sheet(isPresented: $showFilters) { FiltersSheet() }
        .task { if !ScreenshotMode.isActive && (guide == .nearMe || order == .nearest) { location.request() } }
    }

    @ViewBuilder
    private func row(_ p: Place, rank: Int?) -> some View {
        let metric = metricText(p)
        if let selection {
            Button { selection.wrappedValue = p } label: { PlaceRow(place: p, rank: rank, metric: metric) }
                .listRowBackground(selection.wrappedValue?.id == p.id ? Theme.surface2 : Theme.surface)
        } else {
            NavigationLink(value: AppModel.Route.place(p)) { PlaceRow(place: p, rank: rank, metric: metric) }
        }
    }

    private func metricText(_ p: Place) -> PlaceRow.Metric? {
        switch order {
        case .nearest: if let here, let l = p.location { return .text(here.milesText(to: l), "away") }
        case .oldest: if let f = p.founded { return .text("\(f)", "since") }
        case .iconic: if let pts = p.iconicPoints { return .text("\(Int(pts.rounded()))", "iconic pts") }
        default: break
        }
        if let f = p.founded, guide != .all { return .text("\(f)", "since") }
        return nil
    }

    private var locationPrompt: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(location.isDenied ? "Location is off for this app. Turn it on in Settings to sort by distance."
                 : location.failed ? "Couldn't find your location. Check that Location Services is on, then try again."
                 : "Sort by distance from where you are. Your location stays on this device.")
                .font(.subheadline).foregroundStyle(Theme.ink2)
            if location.isDenied {
                Button("Open Settings") { LocationService.openSettings() }.buttonStyle(.bordered).tint(Theme.navy)
            } else {
                Button(location.failed ? "Try again" : "Use my location") { location.request() }.buttonStyle(.borderedProminent).tint(Theme.navy)
            }
        }
        .padding(.vertical, 4)
        .listRowSeparator(.hidden)
    }

    private var activeFilters: some View {
        HStack {
            Text("\(model.filters.activeCount) filter\(model.filters.activeCount == 1 ? "" : "s") on").font(.subheadline).foregroundStyle(Theme.ink2)
            Spacer()
            Button("Clear") { model.filters = Filters() }.font(.subheadline.weight(.semibold))
        }
        .listRowSeparator(.hidden)
    }
}

struct PlaceRow: View {
    enum Metric { case text(String, String) }
    let place: Place
    var rank: Int?
    var metric: Metric?

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            if let rank {
                Text("\(rank)")
                    .displayFont(rank < 100 ? 26 : 20).monospacedDigit()
                    .foregroundStyle(rank <= 3 ? Theme.onAccent : Theme.navy)
                    .frame(minWidth: 38, minHeight: 38)
                    .background(RoundedRectangle(cornerRadius: 8).fill(rank <= 3 ? Theme.accent : .clear))
                    .accessibilityLabel("Rank \(rank)")
            }
            VStack(alignment: .leading, spacing: 4) {
                Text(place.name).font(.body.weight(.semibold)).foregroundStyle(Theme.ink).multilineTextAlignment(.leading)
                Text(place.townLine).font(.subheadline).foregroundStyle(Theme.muted)
                PlaceChips(place: place, compact: true)
            }
            Spacer(minLength: 8)
            if case .text(let big, let small) = metric {
                VStack(alignment: .trailing, spacing: 0) {
                    Text(big).displayFont(22).foregroundStyle(Theme.navy).monospacedDigit()
                    Text(small).font(.caption2).foregroundStyle(Theme.muted)
                }
            }
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }
}

/// The small labels on a place: Pennsylvania classics, honors, the official Allegheny County placard, chain size, how sure we are it's real.
struct PlaceChips: View {
    let place: Place
    var compact = false

    var body: some View {
        let (lead, tail) = items
        let placard = place.placard
        if !lead.isEmpty || !tail.isEmpty || placard != nil {
            FlowLayout(spacing: 5) {
                ForEach(lead, id: \.0) { Chip(text: $0.0, style: $0.1) }
                // the official placard always travels with its inspection date
                if let placard { PlacardChip(placard: placard, date: placard.d.map(Self.monthYear)) }
                ForEach(tail, id: \.0) { Chip(text: $0.0, style: $0.1) }
            }
        }
    }

    /// Chips before the placard (honors, what it is) and after it (seasonal, chain, how sure we are).
    private var items: (lead: [(String, Chip.Style)], tail: [(String, Chip.Style)]) {
        var lead: [(String, Chip.Style)] = [], tail: [(String, Chip.Style)] = []
        if let m = place.michelin { lead.append((m.label, .navy)) }
        if let jb = place.jamesBeardLabel { lead.append((jb, .navy)) }
        for k in place.kinds.names where k != "Historic" { lead.append((k, .accent)) }
        if place.kinds.isEmpty {   // places outside the research still carry tags from their names (a "… Pierogies", a "… Diner")
            if place.tags.contains(.pierogi) { lead.append(("Pierogies", .accent)) }
            if place.tags.contains(.pretzel) { lead.append(("Pretzels", .accent)) }
        }
        if place.isSeasonal { tail.append(("Seasonal", .plain)) }
        if place.isChain { tail.append(("Chain · \(place.chainCount)", .plain)) }
        if place.tier == .listing && !place.handChecked && place.tags.isEmpty { tail.append(("Listing only", .dashed)) }
        guard compact else { return (lead, tail) }
        let room = place.placard != nil ? 3 : 4
        let l = Array(lead.prefix(room))
        return (l, Array(tail.prefix(room - l.count)))
    }

    /// "2025-02-25" -> "Feb 2025"
    static func monthYear(_ iso: String) -> String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.locale = Locale(identifier: "en_US_POSIX"); f.timeZone = .gmt   // a day, not an instant
        guard let d = f.date(from: iso) else { return iso }
        let o = DateFormatter(); o.dateFormat = "MMM yyyy"; o.locale = Locale(identifier: "en_US_POSIX"); o.timeZone = .gmt
        return o.string(from: d)
    }
}

/// Wraps chips onto new lines.
struct FlowLayout: Layout {
    var spacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxW = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowH: CGFloat = 0, widest: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > 0 && x + s.width > maxW { y += rowH + spacing; x = 0; rowH = 0 }
            x += s.width + spacing; rowH = max(rowH, s.height); widest = max(widest, x - spacing)
        }
        return CGSize(width: min(widest, maxW), height: y + rowH)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowH: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x > bounds.minX && x + s.width > bounds.maxX { y += rowH + spacing; x = bounds.minX; rowH = 0 }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing; rowH = max(rowH, s.height)
        }
    }
}
