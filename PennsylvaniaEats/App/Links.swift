import Foundation

/// The app's web pages, the agencies' own lookups and the support address, in one place.
/// The site is GitHub Pages. Until the pennsylvania.eatsranked.com DNS record exists, links use the github.io address; once it resolves
/// (dig shows the CNAME) and Pages serves it, switch these with scripts/make-site.py's CUSTOM_DOMAIN. GitHub forwards the old
/// address, so builds that shipped with it keep working.
enum Links {
    static let appName = "Pennsylvania Eats"
    static let base = "https://nickstrom5.github.io/pennsylvania-eats"
    static let site = URL(string: base + "/")!
    /// The app's data updates: scripts/publish_app_data.py writes docs/data/app/ (OTA-DATA.md).
    static let appData = URL(string: site.absoluteString + "data/app/")!
    static let privacy = URL(string: base + "/privacy.html")!
    static let terms = URL(string: base + "/terms.html")!
    static let supportEmail = "nick@eatsranked.com"
    /// The agencies' own search pages (linked, never scraped). Each one checked to render with curl.
    static let achdInspections = URL(string: "https://www.alleghenycounty.us/Services/Health-Department/Food-Safety")!
    static let phillyInspections = URL(string: "https://philadelphia-pa.healthinspections.us/philadelphia/")!
    static let bucksInspections = URL(string: "https://bucks-pa.healthinspections.us/")!
    static let montgomeryInspections = URL(string: "https://pa.healthinspections.us/montgomery/")!
    static let pdaInspections = URL(string: "https://www.pafoodsafety.pa.gov/Web/Inspection/PublicInspectionSearch.aspx")!

    static var correctionEmail: URL {
        URL(string: "mailto:\(supportEmail)?subject=Pennsylvania%20Eats%20correction")!
    }
}
