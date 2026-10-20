import SwiftUI
import MapKit

struct MapScreen: View {
    @Environment(AppModel.self) private var model
    @Environment(LocationService.self) private var location
    var selection: Binding<Place?>? = nil

    @State private var layer: Layer = .cheesesteaks
    @State private var pushed: Place?
    @State private var region: MKCoordinateRegion?
    /// "My location": where to move the map (a new object each tap, so a second tap re-centers after panning away)
    @State private var centerOn: CLLocation?
    @State private var centerWhenFound = false
    @State private var notice: String?
    @State private var askSettings = false

    /// All 24,000 restaurants at once would keep the map busy (16,000 pins took over a minute in Wisconsin's QA), so the Everything
    /// layer fills in only once you zoom to about neighborhood size (this many degrees on screen), only for what's in view, and only
    /// while that's under `maxPins` (Center City Philadelphia holds thousands of places in a few blocks).
    private static let everythingSpan = 0.08
    private static let maxPins = 600
    /// "My location" on Everything zooms to about a neighborhood (downtown Pittsburgh or Lancaster a few hundred places); the guide layers keep town zoom.
    private static let everythingCenterSpan = 0.03

    enum Layer: String, CaseIterable, Identifiable {
        case cheesesteaks = "Cheesesteaks", tomatoPie = "Tomato pie", pierogies = "Pierogies", dutch = "PA Dutch", pretzels = "Pretzels",
             diners = "Diners", icons = "Icons", all = "Everything"
        var id: String { rawValue }
        var guide: Guide {
            switch self {
            case .cheesesteaks: .cheesesteaks
            case .tomatoPie: .tomatoPie
            case .pierogies: .pierogies
            case .dutch: .dutch
            case .pretzels: .pretzels
            case .diners: .diners
            case .icons: .icons
            case .all: .all
            }
        }
    }

    var body: some View {
        let layerPlaces = model.places.filter { layer.guide.includes($0) && model.filters.allows($0) && $0.coordinate != nil }
        // the smaller side decides: a tall, narrow iPad column shows a lot of latitude even at town zoom
        let farOut = layer == .all && min(region?.span.latitudeDelta ?? .infinity, region?.span.longitudeDelta ?? .infinity) > Self.everythingSpan
        let visible = layer != .all || farOut ? [] : layerPlaces.filter(inView)
        let zoomedOut = farOut || visible.count > Self.maxPins
        let places = layer != .all ? layerPlaces : zoomedOut ? [] : visible
        ZStack(alignment: .top) {
            ClusteredMap(places: places, showsUser: location.location != nil, center: centerOn, centerSpan: layer == .all ? Self.everythingCenterSpan : 0.12,
                         onRegion: { region = $0 }) { p in
                if let selection { selection.wrappedValue = p } else { pushed = p }
            }
            .ignoresSafeArea(edges: .bottom)
            VStack(spacing: 6) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(Layer.allCases) { l in
                            Button { layer = l } label: {
                                Text(l.rawValue).font(.subheadline.weight(.semibold))
                                    .padding(.horizontal, 12).padding(.vertical, 8)
                                    .foregroundStyle(layer == l ? .white : Theme.navy)
                                    .background(Capsule().fill(layer == l ? Theme.navy : Theme.surface))
                                    .overlay(Capsule().strokeBorder(Theme.rule2, lineWidth: layer == l ? 0 : 1))
                            }
                            .accessibilityAddTraits(layer == l ? .isSelected : [])
                        }
                    }
                    .padding(.horizontal, 12)
                }
                .accessibilityIdentifier("layers")
                Text(notice ?? (zoomedOut ? (farOut ? "Zoom in to a neighborhood or town to see all \(layerPlaces.count.formatted()) places"
                                                    : "Zoom in further: \(visible.count.formatted()) places in view")
                               : "\(places.count.formatted()) \(layer == .all ? "places here" : "places") · tap a pin, then its name"))
                    .font(.caption).foregroundStyle(Theme.ink2)
                    .padding(.horizontal, 10).padding(.vertical, 4).background(Capsule().fill(.thinMaterial))
            }
            .padding(.top, 8)
        }
        .navigationTitle("Map")
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(item: $pushed) { PlaceDetailView(place: $0) }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    if location.isDenied {
                        askSettings = true
                    } else {
                        // a fix from launch may be miles out of date, so always ask for a fresh one; a very recent fix moves the map now
                        if let here = location.location, here.timestamp.timeIntervalSinceNow > -60 { center(on: here) }
                        centerWhenFound = true
                        location.request()
                    }
                } label: { Label("My location", systemImage: "location") }
            }
        }
        .onChange(of: location.location) { _, here in
            guard centerWhenFound, let here else { return }
            centerWhenFound = false
            center(on: here)
        }
        .onChange(of: location.failed) { _, failed in
            guard failed && centerWhenFound else { return }
            centerWhenFound = false
            // the map already moved to a fix from the last minute or so; only say so when there was nothing to go on
            if (location.location?.timestamp.timeIntervalSinceNow ?? -.infinity) < -90 {
                flash("Couldn't find your location. Check that Location Services is on.")
            }
        }
        .alert("Location is off", isPresented: $askSettings) {
            Button("Open Settings") { LocationService.openSettings() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Turn on location for \(Links.appName) in Settings to center the map on you. It stays on your device.")
        }
    }
}

extension MapScreen {
    /// Town-level zoom on the reader, unless they're outside Pennsylvania: then the map stays on the state and says why.
    private func center(on here: CLLocation) {
        if location.isOutsidePennsylvania {
            flash("You're outside Pennsylvania, so the map stays on the state.")
        } else {
            centerOn = CLLocation(latitude: here.coordinate.latitude, longitude: here.coordinate.longitude)
        }
    }

    private func flash(_ text: String) {
        notice = text
        Task { try? await Task.sleep(for: .seconds(5)); if notice == text { notice = nil } }
    }

    /// On screen, with half a screen of margin so panning doesn't show empty edges.
    private func inView(_ p: Place) -> Bool {
        guard let r = region, let c = p.coordinate else { return false }
        return abs(c.latitude - r.center.latitude) <= r.span.latitudeDelta && abs(c.longitude - r.center.longitude) <= r.span.longitudeDelta
    }
}

/// MKMapView with clustering: SwiftUI's Map can't cluster thousands of pins.
struct ClusteredMap: UIViewRepresentable {
    let places: [Place]
    let showsUser: Bool
    /// move the map here (town-level zoom) whenever a new location object arrives
    var center: CLLocation? = nil
    var centerSpan = 0.12
    var onRegion: (MKCoordinateRegion) -> Void = { _ in }
    let onSelect: (Place) -> Void

    func makeUIView(context: Context) -> MKMapView {
        let map = MKMapView()
        map.delegate = context.coordinator
        map.pointOfInterestFilter = .excludingAll
        map.register(PlaceMarker.self, forAnnotationViewWithReuseIdentifier: PlaceMarker.id)
        map.register(ClusterMarker.self, forAnnotationViewWithReuseIdentifier: MKMapViewDefaultClusterAnnotationViewReuseIdentifier)
        map.setRegion(MKCoordinateRegion(center: CLLocationCoordinate2D(latitude: 41.0, longitude: -77.6),
                                         span: MKCoordinateSpan(latitudeDelta: 3.2, longitudeDelta: 6.6)), animated: false)
        let start = map.region
        DispatchQueue.main.async { onRegion(start) }
        return map
    }

    func updateUIView(_ map: MKMapView, context: Context) {
        context.coordinator.onSelect = onSelect
        context.coordinator.onRegion = onRegion
        map.showsUserLocation = showsUser
        if let c = center, c !== context.coordinator.centered {
            context.coordinator.centered = c
            map.setRegion(MKCoordinateRegion(center: c.coordinate, span: MKCoordinateSpan(latitudeDelta: centerSpan, longitudeDelta: centerSpan)), animated: true)
        }
        let want = Set(places.map(\.id))
        let have = map.annotations.compactMap { $0 as? PlaceAnnotation }
        let haveIds = Set(have.map(\.place.id))
        guard want != haveIds else { return }
        map.removeAnnotations(have.filter { !want.contains($0.place.id) })
        map.addAnnotations(places.filter { !haveIds.contains($0.id) }.map(PlaceAnnotation.init))
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, MKMapViewDelegate {
        var onSelect: ((Place) -> Void)?
        var onRegion: ((MKCoordinateRegion) -> Void)?
        var centered: CLLocation?

        func mapView(_ map: MKMapView, regionDidChangeAnimated animated: Bool) {
            let r = map.region
            DispatchQueue.main.async { self.onRegion?(r) }   // not during a SwiftUI view update
        }

        func mapView(_ map: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            if annotation is MKUserLocation { return nil }
            if annotation is MKClusterAnnotation { return nil }   // the registered ClusterMarker
            return map.dequeueReusableAnnotationView(withIdentifier: PlaceMarker.id, for: annotation)
        }

        func mapView(_ map: MKMapView, annotationView view: MKAnnotationView, calloutAccessoryControlTapped control: UIControl) {
            if let a = view.annotation as? PlaceAnnotation { onSelect?(a.place) }
        }

        func mapView(_ map: MKMapView, didSelect annotation: MKAnnotation) {
            if let cluster = annotation as? MKClusterAnnotation {
                map.showAnnotations(cluster.memberAnnotations, animated: true)
                map.deselectAnnotation(cluster, animated: false)
            }
        }
    }
}

final class PlaceAnnotation: NSObject, MKAnnotation {
    let place: Place
    let coordinate: CLLocationCoordinate2D
    var title: String? { place.name }
    var subtitle: String? { place.townLine }
    init(_ p: Place) { place = p; coordinate = p.coordinate! }
}

final class PlaceMarker: MKMarkerAnnotationView {
    static let id = "place"
    override var annotation: MKAnnotation? { didSet { configure() } }

    private func configure() {
        clusteringIdentifier = "places"
        canShowCallout = true
        let info = UIButton(type: .detailDisclosure)
        info.accessibilityLabel = "Details"
        rightCalloutAccessoryView = info
        guard let p = (annotation as? PlaceAnnotation)?.place else { return }
        let classic = p.handChecked
        markerTintColor = UIColor(classic ? Theme.markerAccent : Theme.navy)
        glyphTintColor = .white
        glyphImage = UIImage(systemName: MarkerGlyph.symbol(for: p))
        displayPriority = classic ? .defaultHigh : .defaultLow
    }
}

final class ClusterMarker: MKMarkerAnnotationView {
    override var annotation: MKAnnotation? {
        didSet {
            markerTintColor = UIColor(Theme.navy)
            glyphText = (annotation as? MKClusterAnnotation).map { "\($0.memberAnnotations.count)" }
            displayPriority = .defaultHigh
        }
    }
}
