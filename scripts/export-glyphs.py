"""Exports the app's food glyphs (PennsylvaniaEats/Design/Glyphs.swift) as SVG path data for the website: scripts/glyphs.json, one even-odd
path per classic guide in a 48 x 48 box. Run it after changing a glyph, then scripts/make-site.py.

    .venv/bin/python scripts/export-glyphs.py
"""
import os, subprocess, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(f"{ROOT}/PennsylvaniaEats/Design/Glyphs.swift").read().split("struct GuideGlyph")[0]   # FoodGlyph and FoodGlyphShape only
src = src.replace("import SwiftUI\n", "").replace("    static func of(_ guide: Guide) -> FoodGlyph? {", "    static func _unused(_ guide: Guide) -> FoodGlyph? {")
main = r'''
enum Guide { case cheesesteaks, tomatoPie, pierogies, dutch, pretzels, diners, other }
func svg(_ p: Path) -> String {
    var out = ""
    func f(_ v: CGFloat) -> String { String(format: "%.2f", Double(v)).replacingOccurrences(of: ".00", with: "") }
    p.cgPath.applyWithBlock { el in
        let e = el.pointee, pts = e.points
        switch e.type {
        case .moveToPoint: out += "M\(f(pts[0].x)) \(f(pts[0].y))"
        case .addLineToPoint: out += "L\(f(pts[0].x)) \(f(pts[0].y))"
        case .addQuadCurveToPoint: out += "Q\(f(pts[0].x)) \(f(pts[0].y)) \(f(pts[1].x)) \(f(pts[1].y))"
        case .addCurveToPoint: out += "C\(f(pts[0].x)) \(f(pts[0].y)) \(f(pts[1].x)) \(f(pts[1].y)) \(f(pts[2].x)) \(f(pts[2].y))"
        case .closeSubpath: out += "Z"
        @unknown default: break
        }
    }
    return out
}
let names: [(String, FoodGlyph)] = [("steak", .cheesesteak), ("pie", .tomatoPie), ("pierogi", .pierogi), ("dutch", .whoopiePie), ("pretzel", .pretzel)]
var d: [String: String] = [:]
for (k, g) in names { d[k] = svg(g.path(in: CGRect(x: 0, y: 0, width: 48, height: 48))) }
let data = try! JSONSerialization.data(withJSONObject: d, options: [.sortedKeys, .prettyPrinted])
try! data.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
'''
with tempfile.TemporaryDirectory() as tmp:
    f = os.path.join(tmp, "glyphs.swift")
    open(f, "w").write("import SwiftUI\n" + src + main)
    subprocess.run(["swift", f, f"{ROOT}/scripts/glyphs.json"], check=True)
print("wrote scripts/glyphs.json")
