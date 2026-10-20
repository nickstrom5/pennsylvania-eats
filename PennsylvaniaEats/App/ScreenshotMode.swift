import Foundation
import CoreLocation
import UIKit

/// `-screenshot <name>` opens one screen with fixed state for App Store screenshots (scripts/capture-screenshots.sh).
/// Names: home, cheesesteaks, pierogies, dutch, detail, map, icons, saved, about.
enum ScreenshotMode {
    /// Debug builds only: an App Store build ignores the launch argument, so no one can reach seeded screens or fake locations.
    static var name: String? {
        #if DEBUG
        let args = ProcessInfo.processInfo.arguments
        guard let i = args.firstIndex(of: "-screenshot"), i + 1 < args.count else { return nil }
        return args[i + 1]
        #else
        return nil
        #endif
    }
    static var isActive: Bool { name != nil }

    @MainActor
    static func apply(to model: AppModel) {
        guard let name, model.isLoaded else { return }
        model.filters = Filters()
        // Philadelphia City Hall, so "nearest" lists have distances without a permission prompt
        model.screenshotLocation = CLLocation(latitude: 39.9524, longitude: -75.1636)
        // the first hand-checked place with this name (a branch never stands in for the original)
        let named = { (p: Place, n: String) in p.name.lowercased().hasPrefix(n.lowercased()) }
        let pick = { (n: String) in model.places.first { named($0, n) && $0.handChecked && $0.branchOf == nil } ?? model.places.first { named($0, n) } }
        for n in ["Oyster House", "Dalessandro's", "Kalaya", "Pizzeria Beddia"] {
            if let p = pick(n), !model.isSaved(p) { model.toggleSaved(p) }
        }
        let open = { (g: Guide) in model.tab = .guides; model.selectedGuide = g; model.guidesPath = [.guide(g)] }
        switch name {
        case "cheesesteaks": open(.cheesesteaks)
        case "pierogies":   // Pittsburgh's pierogies from Market Square, not 300 miles away in Philadelphia
            model.screenshotLocation = CLLocation(latitude: 40.4406, longitude: -79.9959)
            open(.pierogies)
        case "dutch":   // Lancaster County's dining rooms from Lancaster's Penn Square
            model.screenshotLocation = CLLocation(latitude: 40.0379, longitude: -76.3055)
            open(.dutch)
        case "icons": open(.icons)
        case "detail":
            open(.icons)
            if let p = pick("Oyster House") ?? model.places.first { model.selectedPlace = p; model.guidesPath.append(.place(p)) }
        case "map": model.tab = .map
        case "saved": model.tab = .saved
        case "about": model.tab = .about
        default: model.tab = .guides; model.selectedGuide = nil
        }
        // iPad shows the place column next to every list, so give each shot a place instead of "Pick a place".
        guard UIDevice.current.userInterfaceIdiom == .pad, model.selectedPlace == nil else { return }
        let place: Place? = switch name {
        case "cheesesteaks": pick("Dalessandro's")
        case "icons": pick("Kalaya")
        case "saved": pick("Pizzeria Beddia")
        case "about": nil
        case "map": pick("Dalessandro's")
        default: pick("Oyster House")
        }
        model.selectedPlace = place
    }
}
