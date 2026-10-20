// Pennsylvania Eats: three app-icon concepts in the Eats Ranked icon style v1 (../../state-prompts/ICON-STYLE.md).
// One flat, level, centred food on flat hemlock green, in the Penn's Woods palette: hemlock #2E4E3F, barn red #A23B2A,
// cream #F6F1E7, gold #E8A33D (tones of one material are that hex mixed toward white or black, per R5).
//   A  salted soft pretzel (front view, one thick round-cap stroke; the second arm crosses over the first with a ground ring)
//   B  crimped pierogi (side view half-moon, a darker underside, gold crimp marks along the arc)
//   C  cheesesteak in its roll (side view: split roll, chopped steak, cheese)
// Usage: swift scripts/icon-concepts.swift   -> playbook/brand/concept-{a,b,c}-1024.png and concepts.png (512/180/60 sheet)
import AppKit
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

func rgb(_ h: UInt32) -> (CGFloat, CGFloat, CGFloat) { (CGFloat((h >> 16) & 255) / 255, CGFloat((h >> 8) & 255) / 255, CGFloat(h & 255) / 255) }
func hex(_ h: UInt32) -> CGColor { let (r, g, b) = rgb(h); return CGColor(srgbRed: r, green: g, blue: b, alpha: 1) }
/// A tone of one material: the hex mixed `t` toward white (t > 0) or black (t < 0).
func tone(_ h: UInt32, _ t: CGFloat) -> CGColor {
    let (r, g, b) = rgb(h)
    let m: (CGFloat) -> CGFloat = { t >= 0 ? $0 + (1 - $0) * t : $0 * (1 + t) }
    return CGColor(srgbRed: m(r), green: m(g), blue: m(b), alpha: 1)
}
let HEMLOCK: UInt32 = 0x2E4E3F, BARN: UInt32 = 0xA23B2A, CREAM: UInt32 = 0xF6F1E7, GOLD: UInt32 = 0xE8A33D

// y from the TOP, fractions of the canvas
func P(_ x: CGFloat, _ y: CGFloat, _ s: CGFloat) -> CGPoint { CGPoint(x: x * s, y: (1 - y) * s) }

// MARK: A, the pretzel. One continuous rope: left end -> crossing -> right lobe -> bottom -> left lobe -> crossing -> right end.
func pretzel(_ c: CGContext, _ s: CGFloat) {
    func P(_ x: CGFloat, _ y: CGFloat, _ s: CGFloat) -> CGPoint { CGPoint(x: (0.5 + (x - 0.5) * 0.86) * s, y: (1 - y) * s) }   // 0.86 wide
    let w = 0.105 * s                                    // rope thickness 108 px
    // first half: from the left end, up through the crossing, round the right lobe, along the bottom to the middle
    let a = CGMutablePath()
    a.move(to: P(0.385, 0.700, s))
    a.addCurve(to: P(0.560, 0.470, s), control1: P(0.430, 0.610, s), control2: P(0.500, 0.520, s))
    a.addCurve(to: P(0.800, 0.330, s), control1: P(0.640, 0.390, s), control2: P(0.730, 0.300, s))
    a.addCurve(to: P(0.770, 0.640, s), control1: P(0.880, 0.370, s), control2: P(0.880, 0.560, s))
    a.addCurve(to: P(0.500, 0.735, s), control1: P(0.690, 0.705, s), control2: P(0.590, 0.735, s))
    // second half: from the middle of the bottom round the left lobe, down through the crossing to the right end
    let b = CGMutablePath()
    b.move(to: P(0.500, 0.735, s))
    b.addCurve(to: P(0.230, 0.640, s), control1: P(0.410, 0.735, s), control2: P(0.310, 0.705, s))
    b.addCurve(to: P(0.200, 0.330, s), control1: P(0.120, 0.560, s), control2: P(0.120, 0.370, s))
    b.addCurve(to: P(0.440, 0.470, s), control1: P(0.270, 0.300, s), control2: P(0.360, 0.390, s))
    b.addCurve(to: P(0.615, 0.700, s), control1: P(0.500, 0.520, s), control2: P(0.570, 0.610, s))
    func rope(_ p: CGPath, _ col: CGColor, _ width: CGFloat) {
        c.setLineCap(.round); c.setLineJoin(.round); c.setLineWidth(width); c.setStrokeColor(col); c.addPath(p); c.strokePath()
    }
    rope(a, hex(GOLD), w)
    rope(b, hex(GOLD), w)
    // the right end's arm crosses over the left one: redraw it with a ground-colour ring along the stretch around the crossing only
    let arm = CGMutablePath()
    arm.move(to: P(0.200, 0.330, s))
    arm.addCurve(to: P(0.440, 0.470, s), control1: P(0.270, 0.300, s), control2: P(0.360, 0.390, s))
    arm.addCurve(to: P(0.615, 0.700, s), control1: P(0.500, 0.520, s), control2: P(0.570, 0.610, s))
    let L = s / 1024
    let cross = CGMutablePath()                          // the stretch of the arm through the crossing
    cross.move(to: P(0.440, 0.470, s))
    cross.addCurve(to: P(0.615, 0.700, s), control1: P(0.500, 0.520, s), control2: P(0.570, 0.610, s))
    rope(cross.copy(dashingWithPhase: 0, lengths: [150 * L, 10000]), hex(HEMLOCK), w + 0.026 * s)
    rope(arm, hex(GOLD), w)
    // coarse salt: 6 cream crystals, 44 px, on the rope
    c.setFillColor(hex(CREAM))
    for (x, y) in [(0.255, 0.345), (0.745, 0.345), (0.165, 0.480), (0.835, 0.480), (0.330, 0.715), (0.670, 0.715)] {
        let d = 0.043 * s, q = P(x, y, s)
        c.fillEllipse(in: CGRect(x: q.x - d / 2, y: q.y - d / 2, width: d, height: d))
    }
}

// MARK: B, the pierogi. A half-moon on its flat side (front view of a half): dough cream, a darker underside, and the fork
// crimp as 7 notches cut through the curved rim to the ground colour.
func pierogi(_ c: CGContext, _ s: CGFloat) {
    let cx: CGFloat = 0.5, base: CGFloat = 0.668, rx: CGFloat = 0.335, ry: CGFloat = 0.335
    let body = CGMutablePath()
    body.move(to: P(cx - rx, base, s))
    body.addArc(center: P(cx, base, s), radius: rx * s, startAngle: .pi, endAngle: 0, clockwise: true)
    body.addLine(to: P(cx - rx, base, s))
    body.closeSubpath()
    // soften the two corners: a round-join stroke of the dough under the fill
    for (col, above) in [(hex(CREAM), true), (tone(CREAM, -0.16), false)] {   // each tone's band stays on its side of the edge
        c.saveGState()
        c.clip(to: above ? CGRect(x: 0, y: (1 - 0.590) * s, width: s, height: 0.590 * s) : CGRect(x: 0, y: 0, width: s, height: (1 - 0.590) * s))
        c.setStrokeColor(col); c.setLineJoin(.round); c.setLineWidth(0.06 * s); c.addPath(body); c.strokePath()
        c.restoreGState()
    }
    c.saveGState(); c.addPath(body); c.clip()
    c.setFillColor(hex(CREAM)); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    c.setFillColor(tone(CREAM, -0.16)); c.fill(CGRect(x: 0, y: 0, width: s, height: (1 - 0.590) * s))
    c.restoreGState()
    c.setStrokeColor(hex(HEMLOCK)); c.setLineCap(.round); c.setLineWidth(0.036 * s)
    for i in 0..<7 {
        let t = CGFloat.pi * (0.10 + 0.80 * CGFloat(i) / 6)
        let r0 = rx + 0.035, r1 = rx - 0.045
        c.move(to: P(cx - cos(t) * r0, base - sin(t) * r0, s)); c.addLine(to: P(cx - cos(t) * r1, base - sin(t) * r1, s)); c.strokePath()
    }
    _ = ry
}

// MARK: C, the cheesesteak. A split roll seen from the side, chopped steak heaped in it, a cheese ribbon on top.
func cheesesteak(_ c: CGContext, _ s: CGFloat) {
    let x0: CGFloat = 0.14, x1: CGFloat = 0.86
    // steak heap (behind the roll's front lip): barn red, three soft mounds
    let meat = CGMutablePath()
    meat.move(to: P(x0 + 0.05, 0.540, s))
    meat.addCurve(to: P(0.40, 0.340, s), control1: P(x0 + 0.06, 0.400, s), control2: P(0.28, 0.330, s))
    meat.addCurve(to: P(0.62, 0.335, s), control1: P(0.48, 0.300, s), control2: P(0.55, 0.300, s))
    meat.addCurve(to: P(x1 - 0.05, 0.540, s), control1: P(0.74, 0.330, s), control2: P(x1 - 0.06, 0.400, s))
    meat.closeSubpath()
    c.setFillColor(hex(BARN)); c.addPath(meat); c.fillPath()
    // cheese: one cream ribbon over the steak, round caps
    let cheese = CGMutablePath()
    cheese.move(to: P(0.24, 0.425, s))
    cheese.addCurve(to: P(0.50, 0.395, s), control1: P(0.32, 0.360, s), control2: P(0.42, 0.450, s))
    cheese.addCurve(to: P(0.76, 0.425, s), control1: P(0.58, 0.340, s), control2: P(0.68, 0.360, s))
    c.setStrokeColor(hex(CREAM)); c.setLineCap(.round); c.setLineJoin(.round); c.setLineWidth(0.040 * s); c.addPath(cheese); c.strokePath()
    // the roll: front half, a soft rounded slab with a lighter crust top and a darker base
    let roll = CGPath(roundedRect: CGRect(x: x0 * s, y: (1 - 0.680) * s, width: (x1 - x0) * s, height: 0.200 * s),
                      cornerWidth: 0.085 * s, cornerHeight: 0.085 * s, transform: nil)
    c.saveGState(); c.addPath(roll); c.clip()
    c.setFillColor(hex(GOLD)); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    c.setFillColor(tone(GOLD, 0.30)); c.fill(CGRect(x: 0, y: (1 - 0.530) * s, width: s, height: 0.050 * s))
    c.setFillColor(tone(GOLD, -0.18)); c.fill(CGRect(x: 0, y: 0, width: s, height: (1 - 0.630) * s))
    c.restoreGState()
}

func drawIcon(_ c: CGContext, size s: CGFloat, _ food: (CGContext, CGFloat) -> Void) {
    c.setFillColor(hex(HEMLOCK)); c.fill(CGRect(x: 0, y: 0, width: s, height: s))
    food(c, s)
}

let sRGB = CGColorSpace(name: CGColorSpace.sRGB)!
func opaque(_ n: Int) -> CGContext {
    let c = CGContext(data: nil, width: n, height: n, bitsPerComponent: 8, bytesPerRow: 0, space: sRGB, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    c.setAllowsAntialiasing(true); c.setShouldAntialias(true); c.interpolationQuality = .high
    return c
}
func savePNG(_ img: CGImage, _ path: String) {
    let d = CGImageDestinationCreateWithURL(URL(fileURLWithPath: path) as CFURL, UTType.png.identifier as CFString, 1, nil)!
    CGImageDestinationAddImage(d, img, nil)
    guard CGImageDestinationFinalize(d) else { fatalError("could not write \(path)") }
    print("wrote", path)
}
let out = FileManager.default.currentDirectoryPath + "/playbook/brand"
try? FileManager.default.createDirectory(atPath: out, withIntermediateDirectories: true)
let concepts: [(String, String, (CGContext, CGFloat) -> Void)] = [("a", "A  Soft pretzel", pretzel), ("b", "B  Pierogi", pierogi), ("c", "C  Cheesesteak", cheesesteak)]
var masters: [CGImage] = []
for (k, _, f) in concepts {
    let m = opaque(1024); drawIcon(m, size: 1024, f); let img = m.makeImage()!
    savePNG(img, "\(out)/concept-\(k)-1024.png"); masters.append(img)
}
// sheet: each concept at 512, 180 and 60 px with the iOS corner mask, on cream
let W = 3 * 560, H = 900
let sheet = opaque(W)
let sh = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: 0, space: sRGB, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
sh.setFillColor(hex(CREAM)); sh.fill(CGRect(x: 0, y: 0, width: W, height: H))
_ = sheet
for (i, img) in masters.enumerated() {
    let x0 = CGFloat(i * 560 + 24)
    for (sz, y) in [(CGFloat(512), CGFloat(H - 24 - 512)), (180, 120), (60, 40)] {
        let small = opaque(Int(sz)); small.draw(img, in: CGRect(x: 0, y: 0, width: sz, height: sz))
        let r = CGRect(x: x0 + (sz == 512 ? 0 : (sz == 180 ? 40 : 300)), y: y, width: sz, height: sz)
        sh.saveGState(); sh.addPath(CGPath(roundedRect: r, cornerWidth: sz * 0.2237, cornerHeight: sz * 0.2237, transform: nil)); sh.clip()
        sh.draw(small.makeImage()!, in: r); sh.restoreGState()
    }
    let label = concepts[i].1 as NSString
    let ctx = NSGraphicsContext(cgContext: sh, flipped: false)
    NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = ctx
    label.draw(at: CGPoint(x: x0 + 300, y: 140), withAttributes: [.font: NSFont.boldSystemFont(ofSize: 30), .foregroundColor: NSColor(cgColor: hex(HEMLOCK))!])
    NSGraphicsContext.restoreGraphicsState()
}
savePNG(sh.makeImage()!, "\(out)/concepts.png")
