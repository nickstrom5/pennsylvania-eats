import SwiftUI

/// Penn's Woods palette (Nick, 2026-10-19), light only: hemlock #2E4E3F (9.2:1 on white) for type and fills, barn red #A23B2A (6.6:1)
/// for small accents, cream #F6F1E7 surfaces, gold #E8A33D only ever as a fill under near-black text (2.2:1 as text; hemlock on gold is
/// 4.3:1, failing AA). Token names are the family's (navy = the main dark colour). No team marks, no PA.gov keystone.
enum Theme {
    static let navy = Color(hex: 0x2E4E3F)
    static let navy2 = Color(hex: 0x3E6553)
    static let barn = Color(hex: 0xA23B2A)
    /// gold: a fill with `onAccent` (near-black) text on it, never text itself
    static let accent = Color(hex: 0xE8A33D)
    static let onAccent = Color(hex: 0x1B1F1C)
    static let accentSoft = Color(hex: 0xF8E3BD)
    static let onAccentSoft = Color(hex: 0x5A3A00)
    /// map pins for hand-checked places: a darker gold that holds up on Apple's map tiles
    static let markerAccent = Color(hex: 0xB98226)
    static let gray = Color(hex: 0x7C857F)
    static let ink = Color(hex: 0x1B1F1C)
    static let ink2 = Color(hex: 0x34403A)
    static let muted = Color(hex: 0x525C55)
    static let surface = Color.white
    static let surface2 = Color(hex: 0xF6F1E7)
    static let surface3 = Color(hex: 0xECE4D3)
    static let rule = Color(hex: 0xE3DCCD)
    static let rule2 = Color(hex: 0xC4BBA7)

    /// ACHD placards as posted: green Inspected & Permitted, yellow Consumer Alert, red closure; anything else gray.
    static func placardColor(_ c: ACHDPlacard.Color) -> (fill: Color, text: Color, edge: Color) {
        switch c {
        case .green: (Color(hex: 0xE6F2EA), Color(hex: 0x1D5B37), Color(hex: 0x2F7A4C))
        case .yellow: (Color(hex: 0xFFF3C4), Color(hex: 0x5A4300), Color(hex: 0xC9A200))
        case .red: (Color(hex: 0xFBE3DF), Color(hex: 0x8A1F12), Color(hex: 0xA23B2A))
        case .other: (Color(hex: 0xF1F1F1), Color(hex: 0x444444), Color(hex: 0x999999))
        }
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255, blue: Double(hex & 0xFF) / 255)
    }
}

/// A small uppercase label: "CHEESESTEAKS", "SEASONAL".
struct Chip: View {
    enum Style { case accent, navy, plain, dashed }
    let text: String
    var style: Style = .plain

    var body: some View {
        Text(text.uppercased())
            .font(.caption2.weight(.bold))
            .tracking(0.4)
            .padding(.horizontal, 7).padding(.vertical, 3)
            .foregroundStyle(style == .navy ? Color.white : style == .accent ? Theme.onAccentSoft : style == .dashed ? Theme.muted : Theme.navy)
            .background {
                RoundedRectangle(cornerRadius: 5).fill(style == .accent ? Theme.accentSoft : style == .navy ? Theme.navy : style == .dashed ? .clear : Theme.surface2)
            }
            .overlay {
                if style == .dashed { RoundedRectangle(cornerRadius: 5).strokeBorder(Theme.rule2, style: StrokeStyle(lineWidth: 1, dash: [3, 2])) }
            }
            .accessibilityLabel(text)
    }
}

/// An official Allegheny County placard (ACHD) as a chip: the placard's own words in its colour, and the inspection month.
struct PlacardChip: View {
    let placard: ACHDPlacard
    var date: String?

    var body: some View {
        let c = Theme.placardColor(placard.color)
        HStack(spacing: 5) {
            Text(placard.p.uppercased()).font(.caption2.weight(.bold)).tracking(0.4).foregroundStyle(c.text)
            if let date { Text(date.uppercased()).font(.caption2.weight(.semibold)).tracking(0.4).foregroundStyle(c.text.opacity(0.85)) }
        }
        .padding(.horizontal, 7).padding(.vertical, 3)
        .background(RoundedRectangle(cornerRadius: 5).fill(c.fill))
        .overlay(RoundedRectangle(cornerRadius: 5).strokeBorder(c.edge, lineWidth: 1.5))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Allegheny County placard: \(placard.p)" + (date.map { ", \($0)" } ?? ""))
    }
}

/// The state's outline: the one Pennsylvania element in the header, with a barn-red rule under it (no keystone, no team marks).
struct StateBand: View {
    /// the outline's color: hemlock on cream, white on the hemlock masthead
    var fill: Color = Theme.navy

    var body: some View {
        StateShape().fill(fill)
            .aspectRatio(StateOutline.aspect, contentMode: .fit)
            .accessibilityHidden(true)
    }
}

/// Condensed, heavy display type for titles and big numbers (the system font's compressed width). It scales with the
/// reader's text size, capped at 1.6× so a big number can't swallow its row.
struct DisplayFont: ViewModifier {
    let size: CGFloat
    var weight: Font.Weight = .black
    @ScaledMetric(relativeTo: .body) private var scale: CGFloat = 1

    func body(content: Content) -> some View {
        content.font(.system(size: size * min(scale, 1.6), weight: weight).width(.compressed))
    }
}

extension View {
    func displayFont(_ size: CGFloat, weight: Font.Weight = .black) -> some View {
        modifier(DisplayFont(size: size, weight: weight))
    }
}
