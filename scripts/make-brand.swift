// Regenerates the brand images: the app icon (a salted soft pretzel in gold on hemlock green; Nick's pick, Oct 19, 2026, drawn in
// the shared Eats Ranked flat style, ../state-prompts/ICON-STYLE.md), docs/brand/, and the site's og.png, favicons and manifest icons.
// The pretzel is the same drawing as scripts/icon-concepts.swift concept A.
// Usage: swift scripts/make-brand.swift   (run from pa-eats/)
//        swift scripts/make-brand.swift og ["<tagline>"]   redraws docs/og.png only, never the icons. scripts/make-site.py runs
//        this whenever the restaurant or town count changes; without a tagline it reads og_line from playbook/site-numbers.json.
import AppKit
import CoreGraphics
let root = FileManager.default.currentDirectoryPath
func rgb(_ hex: UInt32, _ a: CGFloat = 1) -> CGColor {
    CGColor(srgbRed: CGFloat((hex >> 16) & 0xFF) / 255, green: CGFloat((hex >> 8) & 0xFF) / 255, blue: CGFloat(hex & 0xFF) / 255, alpha: a)
}
let ground = rgb(0x2E4E3F), goldC = rgb(0xE8A33D), white = rgb(0xFFFFFF), creamC = rgb(0xF6F1E7)

func canvas(_ w: Int, _ h: Int, _ draw: (CGContext) -> Void) -> CGImage {
    let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    ctx.setShouldAntialias(true); ctx.interpolationQuality = .high
    draw(ctx)
    return ctx.makeImage()!
}
func save(_ img: CGImage, _ path: String) {
    let url = URL(fileURLWithPath: root + "/" + path)
    try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
    try! NSBitmapImageRep(cgImage: img).representation(using: .png, properties: [:])!.write(to: url)
    print("wrote", path)
}

// ---- the app icon's food: the salted soft pretzel (P() is y-from-top in fractions of the canvas)
func rgbT(_ h: UInt32) -> (CGFloat, CGFloat, CGFloat) { (CGFloat((h >> 16) & 255) / 255, CGFloat((h >> 8) & 255) / 255, CGFloat(h & 255) / 255) }
func hex(_ h: UInt32) -> CGColor { let (r, g, b) = rgbT(h); return CGColor(srgbRed: r, green: g, blue: b, alpha: 1) }
/// A tone of one material: the hex mixed `t` toward white (t > 0) or black (t < 0).
func tone(_ h: UInt32, _ t: CGFloat) -> CGColor {
    let (r, g, b) = rgbT(h)
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


func icon(_ size: Int) -> CGImage {
    canvas(size, size) { c in c.setFillColor(ground); c.fill(CGRect(x: 0, y: 0, width: size, height: size)); pretzel(c, CGFloat(size)) }
}
/// Opaque: the App Store icon may not have an alpha channel.
func opaque(_ img: CGImage) -> CGImage {
    let ctx = CGContext(data: nil, width: img.width, height: img.height, bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
    ctx.draw(img, in: CGRect(x: 0, y: 0, width: img.width, height: img.height))
    return ctx.makeImage()!
}
func text(_ c: CGContext, _ str: String, font: NSFont, color: CGColor, at p: CGPoint) {
    let attr = NSAttributedString(string: str, attributes: [.font: font, .foregroundColor: NSColor(cgColor: color)!])
    c.textPosition = p; CTLineDraw(CTLineCreateWithAttributedString(attr), c)
}
func heavy(_ size: CGFloat) -> NSFont { NSFont(name: "HelveticaNeue-CondensedBlack", size: size) ?? NSFont.systemFont(ofSize: size, weight: .black) }

let args = Array(CommandLine.arguments.dropFirst())
let ogOnly = args.first == "og"
if !ogOnly {
    let appIcon = opaque(icon(1024))
    save(appIcon, "PennsylvaniaEats/Resources/Assets.xcassets/AppIcon.appiconset/icon-1024.png")
    save(appIcon, "docs/brand/icon-1024.png")
    save(opaque(icon(512)), "docs/icon-512.png")
    save(opaque(icon(192)), "docs/icon-192.png")
    save(opaque(icon(180)), "docs/apple-touch-icon.png")
    save(opaque(icon(32)), "docs/favicon-32.png")
}
/// The tagline carries the directory's real counts (from the data), never "every restaurant".
func ogLine() -> String? {
    if ogOnly && args.count > 1 { return args[1] }
    let url = URL(fileURLWithPath: root + "/playbook/site-numbers.json")
    guard let data = try? Data(contentsOf: url), let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
          let line = json["og_line"] as? String else { return nil }
    return line
}
if let tagline = ogLine() {
    let og = canvas(1200, 630) { c in
        c.setFillColor(ground); c.fill(CGRect(x: 0, y: 0, width: 1200, height: 630))
        c.setFillColor(rgb(0xA23B2A)); c.fill(CGRect(x: 72, y: 470, width: 90, height: 12))
        text(c, "PENNSYLVANIA", font: heavy(104), color: white, at: CGPoint(x: 66, y: 335))
        text(c, "EATS", font: heavy(118), color: goldC, at: CGPoint(x: 66, y: 215))
        text(c, tagline, font: NSFont.systemFont(ofSize: 30, weight: .semibold), color: white, at: CGPoint(x: 70, y: 150))
        text(c, "Free for iPhone and iPad", font: NSFont.systemFont(ofSize: 28, weight: .regular), color: creamC, at: CGPoint(x: 70, y: 98))
        c.saveGState(); c.translateBy(x: 800, y: 110); pretzel(c, 360); c.restoreGState()
    }
    save(opaque(og), "docs/og.png")
} else {
    print("no og_line in playbook/site-numbers.json yet: run scripts/make-site.py, then make-brand.swift og")
}
