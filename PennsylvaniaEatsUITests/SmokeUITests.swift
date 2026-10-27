import XCTest
import CoreLocation

/// Taps through every screen and control a reviewer is likely to touch, on iPhone (tabs) and iPad (split view).
/// Pass = nothing crashes and each screen shows what it should. Slow (network place cards, map tiles), so CI runs
/// only the unit tests; run this before every App Store submission:
/// xcodebuild test -scheme PennsylvaniaEats -only-testing:PennsylvaniaEatsUITests -destination 'id=<sim>'
final class SmokeUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUp() {
        continueAfterFailure = false
        app = XCUIApplication()
        // the location prompt can appear on Near Me or the Nearest sort; answer it like a first-time user would
        addUIInterruptionMonitor(withDescription: "Location") { alert in
            for b in ["Allow While Using App", "Allow Once", "Don’t Allow", "Don't Allow"] where alert.buttons[b].exists {
                alert.buttons[b].tap(); return true
            }
            return false
        }
        app.launch()
    }

    private func button(containing text: String) -> XCUIElement {
        app.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@", text)).firstMatch
    }

    private func text(containing text: String) -> XCUIElement {
        app.staticTexts.matching(NSPredicate(format: "label CONTAINS[c] %@", text)).firstMatch
    }

    private func waitFor(_ e: XCUIElement, _ seconds: TimeInterval = 10, _ what: String) {
        XCTAssertTrue(e.waitForExistence(timeout: seconds), "missing: \(what)")
    }

    private func scrollTo(_ e: XCUIElement, max: Int = 8) {
        var n = 0
        while !e.isHittable && n < max { app.swipeUp(); n += 1 }
    }

    private var isPad: Bool { UIDevice.current.userInterfaceIdiom == .pad }

    /// A map layer chip: the row scrolls sideways (six layers don't fit on a phone), so bring the chip into view first.
    /// (isHittable throws for a chip scrolled off the screen, so this reads the chip's frame instead.)
    private func tapLayer(_ name: String) {
        let chip = app.buttons[name]
        waitFor(chip, 5, "map layer \(name)")
        let row = app.scrollViews["layers"], screen = app.windows.firstMatch.frame
        for _ in 0..<6 {
            let mid = chip.frame.midX
            if mid > screen.minX + 20 && mid < screen.maxX - 20 { break }
            if mid >= screen.maxX - 20 { row.swipeLeft() } else { row.swipeRight() }
            Thread.sleep(forTimeInterval: 0.4)
        }
        chip.tap()
    }

    /// Place detail: Apple Maps card (or the "not on Apple Maps" fallback), save, share.
    private func exerciseDetail(named name: String) {
        waitFor(text(containing: name), 10, "detail for \(name)")
        let card = button(containing: "Ratings, hours")
        waitFor(card, 5, "Apple Maps button")
        card.tap()
        // either Apple's place card sheet or our fallback alert
        let fallback = app.alerts["Not on Apple Maps"]
        let deadline = Date().addingTimeInterval(15)
        var opened = false
        while Date() < deadline && !opened {
            if fallback.exists { fallback.buttons["OK"].tap(); opened = true; break }
            let close = app.buttons.matching(NSPredicate(format: "label ==[c] 'Close' OR identifier ==[c] 'Close'")).firstMatch
            if close.exists && close.isHittable { close.tap(); opened = true; break }
            Thread.sleep(forTimeInterval: 0.5)
        }
        if !opened { app.swipeDown(velocity: .fast) }   // dismiss the sheet if its close button isn't labelled
        XCTAssertEqual(app.state, .runningForeground)
        let save = app.buttons["Save"]
        if save.waitForExistence(timeout: 3) {
            save.tap()
            // on iPad Apple's card is a centered sheet that a tap outside dismisses; that first tap may only close it
            if !app.buttons["Saved"].waitForExistence(timeout: 2) && app.buttons["Save"].exists { app.buttons["Save"].tap() }
            waitFor(app.buttons["Saved"], 3, "heart turns to Saved")
        }
        let share = app.buttons["Share"]
        if share.exists {
            share.tap()
            Thread.sleep(forTimeInterval: 1.5)
            let close = app.buttons.matching(NSPredicate(format: "label ==[c] 'Close' OR label ==[c] 'Cancel'")).firstMatch
            if close.exists { close.tap() } else { app.swipeDown(velocity: .fast) }
        }
        XCTAssertEqual(app.state, .runningForeground)
    }

    /// A clean start for each section, so one screen's navigation state can't strand the next (also proves saved places persist).
    private func fresh() {
        app.terminate()
        app.launch()
        waitFor(text(containing: "Restaurants statewide, from Philadelphia to Pittsburgh and Erie"), 15, "home header")
    }

    func testTourEveryScreen() throws {
        if isPad { try padTour(); return }
        waitFor(text(containing: "Restaurants statewide, from Philadelphia to Pittsburgh and Erie"), 15, "home header")

        // Cheesesteaks: sort, filters, search
        button(containing: "Cheesesteaks, Roast Pork & Hoagies").tap()
        waitFor(app.navigationBars["Cheesesteaks, Roast Pork & Hoagies"], 5, "cheesesteaks list")
        waitFor(text(containing: "places ·"), 5, "list count header")
        app.buttons["Sort"].tap()
        waitFor(app.buttons["Oldest first"], 3, "sort menu"); app.buttons["Oldest first"].tap()
        waitFor(text(containing: "Oldest first"), 3, "sorted header")
        app.buttons["Filters"].tap()
        waitFor(app.navigationBars["Filters"], 3, "filters sheet")
        // tap the switch itself (its right edge); a tap on the middle of a Toggle row lands on the label
        let hide = app.switches.matching(NSPredicate(format: "label CONTAINS 'Hide chains'")).firstMatch
        waitFor(hide, 3, "hide-chains toggle")
        hide.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap()
        XCTAssertEqual(hide.value as? String, "1", "toggle switched on")
        app.buttons["Done"].tap()
        waitFor(text(containing: "1 filter on"), 3, "active-filter row")
        button(containing: "Clear").tap()
        XCTAssertFalse(text(containing: "filter on").waitForExistence(timeout: 1), "filters cleared")
        let search = app.searchFields.firstMatch
        if !search.exists { app.swipeDown() }
        waitFor(search, 3, "search field"); search.tap(); search.typeText("tomato pie")
        waitFor(text(containing: "places ·"), 3, "search results header")

        // the full directory → a known place → Apple Maps card, save, share
        fresh()
        button(containing: "Search every restaurant").tap()
        let search2 = app.searchFields.firstMatch
        waitFor(search2, 5, "directory search"); search2.tap(); search2.typeText("oyster")
        let oyster = button(containing: "Oyster House")
        waitFor(oyster, 5, "Oyster House in results"); oyster.tap()
        exerciseDetail(named: "OYSTER HOUSE")

        // every other guide on Home opens with a list (Home leaves out classics with fewer than 4 hand-checked places: today pierogies,
        // pretzels and diners, which the iPad sidebar still lists)
        for g in ["Tomato Pie & Old Forge Pizza", "Pennsylvania Dutch", "Pennsylvania Icons", "Oldest Taverns & Places", "Near Me", "All Restaurants"] {
            fresh()
            let card = button(containing: g)
            scrollTo(card)
            card.tap()
            if g == "Near Me" { app.swipeDown() }   // any interaction lets the monitor answer the location prompt (a tap could open a row)
            waitFor(app.navigationBars[g], 5, "\(g) list")
            if g != "Near Me" {   // "1 place · …" or "12 places · …"
                waitFor(app.staticTexts.matching(NSPredicate(format: "label MATCHES %@", #"^[\d,]+ places? · .*"#)).firstMatch, 5, "\(g) count header")
            }
        }

        // surprise me
        fresh()
        let surprise = button(containing: "Surprise me")
        scrollTo(surprise); surprise.tap()
        waitFor(button(containing: "Ratings, hours"), 5, "a random Pennsylvania classic")

        // Map: every layer
        fresh()
        app.tabBars.buttons["Map"].tap()
        for l in ["Tomato pie", "Pierogies", "PA Dutch", "Pretzels", "Diners", "Icons", "Everything", "Cheesesteaks"] {
            tapLayer(l)
            // statewide, Everything asks you to zoom in instead of drawing 24,000 pins
            waitFor(text(containing: l == "Everything" ? "Zoom in to a neighborhood" : "tap a pin"), 5, "map hint for \(l)")
        }

        // Saved: Oyster House saved earlier survived relaunches; remove it
        app.tabBars.buttons["Saved"].tap()
        let saved = button(containing: "Oyster House")
        waitFor(saved, 5, "saved place")
        saved.swipeLeft()
        if app.buttons["Remove"].waitForExistence(timeout: 2) { app.buttons["Remove"].tap() }

        // About
        app.tabBars.buttons["About"].tap()
        waitFor(text(containing: "PENNSYLVANIA EATS"), 5, "about header")
        let privacy = app.buttons["Privacy policy"].exists ? app.buttons["Privacy policy"] : app.links["Privacy policy"]
        scrollTo(privacy)
        XCTAssertTrue(privacy.exists, "privacy link")
        XCTAssertEqual(app.state, .runningForeground)
    }

    /// iPad sidebar row. The rows themselves carry no label; the name is a text inside the "Sidebar" list.
    private func sidebarItem(_ name: String) -> XCUIElement {
        app.collectionViews["Sidebar"].staticTexts[name]
    }

    private func padTour() throws {
        // iPad opens on Home in portrait, and a Home card opens its guide
        waitFor(text(containing: "Restaurants statewide, from Philadelphia to Pittsburgh and Erie"), 15, "Home at launch in portrait")
        button(containing: "Cheesesteaks, Roast Pork & Hoagies").tap()
        waitFor(app.navigationBars["Cheesesteaks, Roast Pork & Hoagies"], 5, "a Home card opens its guide on iPad")
        XCUIDevice.shared.orientation = .landscapeLeft     // all three columns
        Thread.sleep(forTimeInterval: 1.5)
        for g in ["Tomato Pie & Old Forge Pizza", "Pennsylvania Icons", "Pennsylvania Dutch", "Oldest Taverns & Places", "All Restaurants", "Cheesesteaks, Roast Pork & Hoagies"] {
            let item = sidebarItem(g)
            waitFor(item, 5, "sidebar \(g)"); item.tap()
            waitFor(app.navigationBars[g], 5, "\(g) list")
        }
        let search = app.searchFields.firstMatch
        if !search.exists { app.swipeDown() }
        waitFor(search, 5, "search"); search.tap(); search.typeText("dalessandro")
        let row = button(containing: "Dalessandro's Steaks")
        waitFor(row, 5, "Dalessandro's in results"); row.tap()
        exerciseDetail(named: "DALESSANDRO'S STEAKS")
        for s in ["Map", "Saved", "About"] {
            let item = sidebarItem(s)
            waitFor(item, 5, "sidebar \(s)"); item.tap()
        }
        waitFor(text(containing: "PENNSYLVANIA EATS"), 5, "about header")
        XCUIDevice.shared.orientation = .portrait
        Thread.sleep(forTimeInterval: 1.5)
        XCTAssertEqual(app.state, .runningForeground)
    }

    /// The Bib Gourmand switch turns the MICHELIN guide into Bib Gourmands only: no starred place is left on screen.
    func testBibGourmandFilter() throws {
        if isPad { throw XCTSkip("iPhone flow; the filter itself is covered by BibGourmandFilterTests") }
        waitFor(text(containing: "Restaurants statewide, from Philadelphia to Pittsburgh and Erie"), 15, "home header")
        let card = app.buttons.matching(NSPredicate(format: "label CONTAINS[c] %@ AND NOT (label CONTAINS[c] 'Surprise')", "Pennsylvania Icons")).firstMatch
        scrollTo(card)
        card.tap()
        waitFor(text(containing: "places ·"), 5, "honors list")
        app.buttons["Filters"].tap()
        waitFor(app.navigationBars["Filters"], 3, "filters sheet")
        let bib = app.switches.matching(NSPredicate(format: "label BEGINSWITH 'Bib Gourmand ('")).firstMatch
        for _ in 0..<6 where !(bib.exists && bib.isHittable) { app.swipeUp() }   // below Hide chains, under the half-height sheet's fold
        waitFor(bib, 3, "Bib Gourmand switch with its count")
        bib.coordinate(withNormalizedOffset: CGVector(dx: 0.93, dy: 0.5)).tap()
        XCTAssertEqual(bib.value as? String, "1", "switch turned on")
        app.buttons["Done"].tap()
        waitFor(text(containing: "1 filter on"), 3, "active-filter row")
        waitFor(text(containing: "Bib Gourmand"), 5, "a Bib Gourmand row")
        XCTAssertFalse(text(containing: "MICHELIN Star").exists, "a starred place is still listed")
        button(containing: "Clear").tap()
        XCTAssertTrue(text(containing: "MICHELIN Star").waitForExistence(timeout: 5), "cleared: the starred places are back")
    }

    func testEverythingLayerFillsInWhenZoomed() {
        if isPad {
            XCUIDevice.shared.orientation = .landscapeLeft
            waitFor(sidebarItem("Map"), 15, "sidebar Map"); sidebarItem("Map").tap()
        } else {
            waitFor(text(containing: "Restaurants statewide, from Philadelphia to Pittsburgh and Erie"), 15, "home header")
            app.tabBars.buttons["Map"].tap()
        }
        tapLayer("Everything")
        waitFor(text(containing: "Zoom in to a neighborhood"), 5, "zoom hint statewide")
        let map = app.maps.firstMatch
        // seven doublings from the statewide view get under the Everything layer's 0.08° span (six leave ~0.13° of longitude)
        for _ in 0..<7 { map.doubleTap(); Thread.sleep(forTimeInterval: 0.8) }
        waitFor(text(containing: "places here"), 10, "restaurants appear once zoomed in")
        XCTAssertEqual(app.state, .runningForeground)
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    /// "My location" moves the map to you at town level, which also fills in the Everything layer.
    /// The simulator's own location resets to Apple's campus, so each location test sets where "you" are.
    private func openMapEverything(at here: CLLocation) {
        // a clean slate: scripts/capture-screenshots.sh revokes location, and the last test left the simulator somewhere else.
        // Resetting asks again (the interruption monitor allows it), and relaunching makes the app's first fix this one.
        app.resetAuthorizationStatus(for: .location)
        XCUIDevice.shared.location = XCUILocation(location: here)
        app.terminate(); app.launch()
        if isPad {
            XCUIDevice.shared.orientation = .landscapeLeft
            waitFor(sidebarItem("Map"), 15, "sidebar Map"); sidebarItem("Map").tap()
        } else {
            waitFor(text(containing: "Restaurants statewide, from Philadelphia to Pittsburgh and Erie"), 15, "home header")
            app.tabBars.buttons["Map"].tap()
        }
        tapLayer("Everything")
        waitFor(text(containing: "Zoom in to a neighborhood"), 5, "zoom hint statewide")
        app.buttons["My location"].tap()
        tapLayer("Everything")    // an interaction, so the monitor can answer the permission prompt if it appears
    }

    func testMyLocationCentersTheMap() {
        openMapEverything(at: CLLocation(latitude: 40.0379, longitude: -76.3055))   // downtown Lancaster (Center City holds too many pins at town zoom)
        waitFor(text(containing: "places here"), 15, "map moved to the simulated location and filled in")
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    /// App Review is usually in California: the map says so and stays on Pennsylvania rather than showing an empty map.
    func testMyLocationOutsidePennsylvania() {
        openMapEverything(at: CLLocation(latitude: 37.3349, longitude: -122.009))
        waitFor(text(containing: "outside Pennsylvania"), 15, "the outside-Pennsylvania note")
        XCTAssertTrue(text(containing: "Zoom in to a neighborhood").waitForExistence(timeout: 8), "the map stayed statewide")
        if isPad { XCUIDevice.shared.orientation = .portrait }
    }

    /// Apple's accessibility audit on the main iPhone screens. Prints every issue (prefixed AUDIT) instead of failing,
    /// so a run lists them all; read the log and fix what's ours (system bars and Apple's place card aren't).
    func testAccessibilityAudit() throws {
        if isPad { return }
        waitFor(text(containing: "Restaurants statewide, from Philadelphia to Pittsburgh and Erie"), 15, "home header")
        func audit(_ screen: String) throws {
            try app.performAccessibilityAudit { issue in
                let el = issue.element.map { "\($0.elementType.rawValue) '\($0.label.prefix(40))'" } ?? "-"
                print("AUDIT [\(screen)] \(issue.auditType.rawValue) | \(issue.compactDescription) | \(el)")
                return true
            }
        }
        try audit("home")
        button(containing: "Cheesesteaks, Roast Pork & Hoagies").tap()
        waitFor(text(containing: "places ·"), 5, "cheesesteaks list")
        try audit("cheesesteaks")
        app.buttons.matching(NSPredicate(format: "label CONTAINS ' · '")).firstMatch.tap()
        waitFor(button(containing: "Ratings, hours"), 5, "a place")
        try audit("detail")
        app.tabBars.buttons["About"].tap()
        try audit("about")
        // not the Map tab: auditing thousands of MapKit annotations times out, and those views are Apple's
    }

    func testLaunchIsQuick() {
        // the bundled data decodes off the main thread; the home screen should be up well within a few seconds
        app.terminate()
        let start = Date()
        app.launch()
        let ready = isPad ? app.staticTexts.matching(NSPredicate(format: "label CONTAINS 'places ·' OR label CONTAINS 'Restaurants statewide, from Philadelphia to Pittsburgh and Erie'")).firstMatch
                          : text(containing: "Restaurants statewide, from Philadelphia to Pittsburgh and Erie")
        XCTAssertTrue(ready.waitForExistence(timeout: 8), "home didn't appear")
        let secs = Date().timeIntervalSince(start)
        print("launch to home: \(String(format: "%.2f", secs)) s")
        XCTAssertLessThan(secs, 6)
    }
}
