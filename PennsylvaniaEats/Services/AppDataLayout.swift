import Foundation

/// Pennsylvania Eats' side of the data updates (OTA-DATA.md): Data/index.json and the region files it names, checked with the loaders
/// launch uses. Every file the index names must read; a file it doesn't name is ignored.
extension DataLayout {
    static let app = DataLayout(kind: .regions, bundled: Bundle.main.url(forResource: "Data", withExtension: nil)!, head: "index") { folder in
        let index = try AppModel.readIndex(folder)
        var rows = ["index": 0], places = 0
        for file in index.files.map(\.file) {
            guard file.hasSuffix(".json"), DataManifest.validName(String(file.dropLast(5))) else { throw Mismatch(description: "index names \(file)") }
            let n = try AppModel.readRegion(folder.appendingPathComponent(file), index: index).count
            rows[String(file.dropLast(5)), default: 0] += n
            places += n
        }
        return DataSummary(generated: index.generated, rows: rows, places: places)
    }
}
