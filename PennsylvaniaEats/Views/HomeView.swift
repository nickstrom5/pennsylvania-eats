import SwiftUI

struct HomeView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dynamicTypeSize) private var typeSize
    @State private var lastRandom: String?
    /// two cards a row; one at the accessibility text sizes, where two would be too narrow for the titles
    private var columns: [GridItem] {
        typeSize.isAccessibilitySize ? [GridItem(.flexible())] : [GridItem(.adaptive(minimum: 158), spacing: 12)]
    }

    /// Classics with too few hand-checked places to be worth a card stay in the iPad sidebar only.
    private var classics: [Guide] { [Guide.cheesesteaks, .tomatoPie, .pierogies, .dutch, .pretzels, .diners].filter(model.hasEnough) }
    private let more: [Guide] = [.icons, .oldest, .nearMe, .all]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                VStack(spacing: 14) {
                    hero
                    searchButton
                }
                VStack(alignment: .leading, spacing: 12) {
                    sectionHeader("Pennsylvania classics", "Hand-checked, each open per a 2025 or 2026 source")
                    LazyVGrid(columns: columns, spacing: 12) {
                        ForEach(classics) { g in
                            Button { model.openGuide(g) } label: { ClassicCard(guide: g, count: model.count(g)) }
                                .buttonStyle(.plain)
                        }
                    }
                    surpriseButton
                }
                VStack(alignment: .leading, spacing: 12) {
                    sectionHeader("More ways in", nil)
                    VStack(spacing: 0) {
                        ForEach(Array(more.enumerated()), id: \.element) { i, g in
                            Button { model.openGuide(g) } label: { GuideRow(guide: g, count: model.count(g)) }
                                .buttonStyle(.plain)
                            if i < more.count - 1 { Divider().padding(.leading, 62) }
                        }
                    }
                    .background(RoundedRectangle(cornerRadius: 16).fill(Theme.surface))
                    .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Theme.rule))
                }
                Text("Ratings, hours and photos come live from Apple Maps on each place. Lists are built from open map data, the City of Philadelphia's food licenses\(model.recordsThrough?.achd == nil ? "" : ", Allegheny County's inspection placards") and hand-checked research. See About for sources.")
                    .font(.footnote).foregroundStyle(Theme.muted)
            }
            .padding(16)
        }
        .background(Theme.surface2)
        .navigationTitle("")
        .toolbar(.hidden, for: .navigationBar)
    }

    /// The masthead: the wordmark and the state outline in white on hemlock, a barn-red rule under it.
    private var hero: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 12) {
                VStack(alignment: .leading, spacing: -12) {   // set tight, like a sign; shrinks rather than breaking "PENNSYLVANIA"
                    Text("PENNSYLVANIA").lineLimit(1).minimumScaleFactor(0.45)
                    Text("EATS").lineLimit(1).minimumScaleFactor(0.5)
                }
                .displayFont(56)
                .foregroundStyle(.white)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(Links.appName)
                .accessibilityAddTraits(.isHeader)
                Spacer(minLength: 0)
                StateBand(fill: .white).frame(maxWidth: 96, maxHeight: 60).padding(.top, 10)
            }
            Rectangle().fill(Theme.barn).frame(width: 64, height: 5)
            Text("Restaurants statewide, from Philadelphia to Pittsburgh and Erie")
                .font(.headline).foregroundStyle(.white)
            // three tiles of one height in a row; stacked at the accessibility text sizes
            let tiles = typeSize.isAccessibilitySize ? AnyLayout(VStackLayout(spacing: 8)) : AnyLayout(HStackLayout(alignment: .top, spacing: 8))
            tiles {
                stat(model.restaurantCount.formatted(), "restaurants")
                stat(model.towns.count.formatted(), "towns")
                stat("67", "counties")
            }
            .fixedSize(horizontal: false, vertical: true)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 22).fill(Theme.navy))
        .padding(.top, 4)
    }

    private func stat(_ big: String, _ small: String) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(big).displayFont(22).foregroundStyle(.white).monospacedDigit().lineLimit(1).minimumScaleFactor(0.7)
            Text(small).font(.caption2.weight(.semibold)).foregroundStyle(.white.opacity(0.85)).fixedSize(horizontal: false, vertical: true)
        }
        .padding(.horizontal, 10).padding(.vertical, 8)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(RoundedRectangle(cornerRadius: 12).fill(Theme.navy2))
        .accessibilityElement(children: .combine)
    }

    private var searchButton: some View {
        Button { model.openGuide(.all) } label: {
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass").font(.body.weight(.semibold)).foregroundStyle(Theme.navy)
                Text("Search by name, town or street").foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
            }
            .font(.subheadline)
            .padding(.horizontal, 16).padding(.vertical, 14)
            .background(RoundedRectangle(cornerRadius: 24, style: .continuous).fill(Theme.surface))   // a capsule on one line
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).strokeBorder(Theme.navy, lineWidth: 1.5))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Search every restaurant")
    }

    private func sectionHeader(_ title: String, _ note: String?) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title.uppercased()).displayFont(22).foregroundStyle(Theme.navy).accessibilityAddTraits(.isHeader)
            if let note { Text(note).font(.caption).foregroundStyle(Theme.muted) }
        }
    }

    private var surpriseButton: some View {
        Button {
            if let p = model.randomPick(from: [.cheesesteaks, .tomatoPie, .pierogies, .dutch, .pretzels, .diners], excluding: lastRandom) {
                lastRandom = p.id
                model.guidesPath.append(.place(p))
                model.selectedPlace = p
            }
        } label: {
            Label("Surprise me with a Pennsylvania classic", systemImage: "dice.fill")
                .font(.subheadline.weight(.bold))
                .foregroundStyle(Theme.onAccent)
                .frame(maxWidth: .infinity).padding(.vertical, 14)
                .background(Capsule().fill(Theme.accent))
        }
        .buttonStyle(.plain)
    }
}

/// A Pennsylvania classic on Home: its food glyph, how many hand-checked places, the guide's name and what's in it, on soft gold.
struct ClassicCard: View {
    let guide: Guide
    let count: Int

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top) {
                GuideGlyph(guide: guide, size: 34)
                Spacer()
                Text(count.formatted()).displayFont(26).foregroundStyle(Theme.navy).monospacedDigit()
            }
            .padding(.bottom, 4)
            Text(guide.shortTitle).displayFont(24, weight: .heavy).foregroundStyle(Theme.navy)
                .lineLimit(2).minimumScaleFactor(0.85).fixedSize(horizontal: false, vertical: true)
            Text(guide.subtitle).font(.caption).foregroundStyle(Theme.onAccentSoft)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(14)
        .frame(maxWidth: .infinity, minHeight: 168, alignment: .topLeading)
        .background {
            RoundedRectangle(cornerRadius: 18).fill(Theme.accentSoft)
                .overlay(alignment: .bottomTrailing) {   // the glyph again, large and faint, as the card's texture
                    GuideGlyph(guide: guide, size: 92, color: Theme.navy.opacity(0.06)).offset(x: 18, y: 18)
                }
                .clipShape(RoundedRectangle(cornerRadius: 18))
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(guide.title), \(count) places")
        .accessibilityHint(guide.subtitle)
    }
}

/// The other ways in (icons, oldest, near me, everything) as rows in one grouped card.
struct GuideRow: View {
    let guide: Guide
    let count: Int

    var body: some View {
        HStack(spacing: 14) {
            GuideGlyph(guide: guide, size: 22)
                .frame(width: 36, height: 36)
                .background(Circle().fill(Theme.surface2))
            VStack(alignment: .leading, spacing: 2) {
                Text(guide.title).font(.body.weight(.semibold)).foregroundStyle(Theme.ink)
                Text(guide.subtitle).font(.caption).foregroundStyle(Theme.muted).lineLimit(2)
            }
            Spacer(minLength: 8)
            if guide != .nearMe && guide != .all {
                Text(count.formatted()).font(.subheadline.weight(.semibold)).foregroundStyle(Theme.navy).monospacedDigit()
            }
            Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(Theme.rule2)
        }
        .padding(.horizontal, 12).padding(.vertical, 12)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityHint(guide == .nearMe || guide == .all ? "" : "\(count) places")
    }
}
