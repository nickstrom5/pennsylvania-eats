import SwiftUI

/// Flat, one-color food glyphs for the Pennsylvania classics (the app icon's soft pretzel is the model): a cheesesteak in its roll,
/// a tray of square-cut tomato pie, a crimped pierogi, a whoopie pie (Pennsylvania Dutch), a soft pretzel. Diners keep the SF Symbol cup.
/// Drawn in a unit square and filled even-odd, so holes (the pretzel's loops, the pie's cuts) read at any size.
enum FoodGlyph {
    case cheesesteak, tomatoPie, pierogi, whoopiePie, pretzel

    static func of(_ guide: Guide) -> FoodGlyph? {
        switch guide {
        case .cheesesteaks: .cheesesteak
        case .tomatoPie: .tomatoPie
        case .pierogies: .pierogi
        case .dutch: .whoopiePie
        case .pretzels: .pretzel
        default: nil
        }
    }

    func path(in r: CGRect) -> Path {
        let s = min(r.width, r.height)
        let o = CGPoint(x: r.midX - s / 2, y: r.midY - s / 2)
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: o.x + x * s, y: o.y + y * s) }
        func circle(_ x: CGFloat, _ y: CGFloat, _ rad: CGFloat) -> CGRect { CGRect(x: o.x + (x - rad) * s, y: o.y + (y - rad) * s, width: 2 * rad * s, height: 2 * rad * s) }
        func rect(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> CGRect { CGRect(x: o.x + x * s, y: o.y + y * s, width: w * s, height: h * s) }
        var path = Path()
        switch self {
        case .cheesesteak:   // side on: the chopped steak heaped in a split roll, a gap between them
            var heap = Path()
            heap.move(to: p(0.12, 0.50))
            heap.addCurve(to: p(0.50, 0.24), control1: p(0.14, 0.30), control2: p(0.32, 0.22))
            heap.addCurve(to: p(0.88, 0.50), control1: p(0.68, 0.22), control2: p(0.86, 0.30))
            heap.closeSubpath()
            let roll = Path(roundedRect: rect(0.04, 0.55, 0.92, 0.30), cornerRadius: 0.15 * s)
            path = heap.union(roll)
        case .tomatoPie:   // a tray of square-cut pie: four squares with cuts between them
            for (x, y) in [(0.10, 0.14), (0.52, 0.14), (0.10, 0.52), (0.52, 0.52)] as [(CGFloat, CGFloat)] {
                path.addRoundedRect(in: rect(x, y, 0.38, 0.34), cornerSize: CGSize(width: 0.05 * s, height: 0.05 * s))
            }
        case .pierogi:   // a half-moon with fork crimps notched into its curved edge
            var moon = Path()
            moon.move(to: p(0.06, 0.74))
            moon.addArc(center: p(0.5, 0.74), radius: 0.44 * s, startAngle: .degrees(180), endAngle: .degrees(0), clockwise: false)
            moon.closeSubpath()
            var notches = Path()
            for i in 0..<7 {
                let t = Double.pi * (1.10 + 0.80 * Double(i) / 6)
                notches.addEllipse(in: circle(0.5 + 0.44 * CGFloat(cos(t)), 0.74 + 0.44 * CGFloat(sin(t)), 0.045))
            }
            path = moon.subtracting(notches)
        case .whoopiePie:   // two domed cakes with the cream filling between them as a gap
            var top = Path()
            top.move(to: p(0.08, 0.50))
            top.addCurve(to: p(0.92, 0.50), control1: p(0.10, 0.12), control2: p(0.90, 0.12))
            top.closeSubpath()
            path.addPath(top)
            path.addRoundedRect(in: rect(0.08, 0.60, 0.84, 0.22), cornerSize: CGSize(width: 0.11 * s, height: 0.11 * s))
        case .pretzel:   // the icon's pretzel as one rope
            var rope = Path()
            rope.move(to: p(0.36, 0.78))
            rope.addCurve(to: p(0.57, 0.48), control1: p(0.42, 0.66), control2: p(0.50, 0.55))
            rope.addCurve(to: p(0.82, 0.26), control1: p(0.66, 0.38), control2: p(0.74, 0.24))
            rope.addCurve(to: p(0.78, 0.68), control1: p(0.94, 0.30), control2: p(0.93, 0.58))
            rope.addCurve(to: p(0.50, 0.82), control1: p(0.70, 0.76), control2: p(0.60, 0.82))
            rope.addCurve(to: p(0.22, 0.68), control1: p(0.40, 0.82), control2: p(0.30, 0.76))
            rope.addCurve(to: p(0.18, 0.26), control1: p(0.07, 0.58), control2: p(0.06, 0.30))
            rope.addCurve(to: p(0.43, 0.48), control1: p(0.26, 0.24), control2: p(0.34, 0.38))
            rope.addCurve(to: p(0.64, 0.78), control1: p(0.50, 0.55), control2: p(0.58, 0.66))
            path = rope.strokedPath(StrokeStyle(lineWidth: 0.13 * s, lineCap: .round, lineJoin: .round)).union(Path())
        }
        return path
    }
}

struct FoodGlyphShape: Shape {
    let glyph: FoodGlyph
    func path(in rect: CGRect) -> Path { glyph.path(in: rect) }
}

/// A guide's mark: its food glyph for the classics, its SF Symbol for the rest.
struct GuideGlyph: View {
    let guide: Guide
    var size: CGFloat = 22
    var color: Color = Theme.navy

    var body: some View {
        Group {
            if let g = FoodGlyph.of(guide) {
                FoodGlyphShape(glyph: g).fill(color, style: FillStyle(eoFill: true)).frame(width: size, height: size)
            } else {
                Image(systemName: guide.systemImage).font(.system(size: size * 0.8, weight: .semibold)).foregroundStyle(color)
                    .frame(width: size, height: size)
            }
        }
        .accessibilityHidden(true)
    }
}

#Preview {
    HStack(spacing: 18) {
        ForEach([Guide.cheesesteaks, .tomatoPie, .pierogies, .dutch, .pretzels, .diners]) { GuideGlyph(guide: $0, size: 44) }
    }
    .padding()
}
