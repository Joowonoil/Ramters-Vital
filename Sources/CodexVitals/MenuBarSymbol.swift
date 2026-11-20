import AppKit

enum MenuBarSymbol: String, CaseIterable {
    case pixelV, openGauge, classic, hamster, standingHamster, frontHamster

    var title: String {
        switch self {
        case .pixelV: return "Pixel V"
        case .openGauge: return "Open Gauge"
        case .classic: return "Classic Waveform"
        case .hamster: return "Hamster Face"
        case .standingHamster: return "Standing Hamster (Three-Quarter)"
        case .frontHamster: return "Standing Hamster (Front)"
        }
    }

    static func stored(in defaults: UserDefaults = .standard) -> Self {
        defaults.string(forKey: "menuBarSymbol").flatMap(Self.init(rawValue:)) ?? .pixelV
    }

    func save(in defaults: UserDefaults = .standard) {
        defaults.set(rawValue, forKey: "menuBarSymbol")
    }

    @MainActor var image: NSImage {
        switch self {
        case .pixelV: return Self.pixelImage
        case .openGauge: return Self.gaugeImage
        case .classic: return Self.classicImage
        case .hamster: return Self.hamsterImage
        case .standingHamster: return Self.standingHamsterImage
        case .frontHamster: return Self.frontHamsterImage
        }
    }

    @MainActor private static let pixelImage = template("PixelV")
    @MainActor private static let gaugeImage = template("OpenGauge")
    @MainActor private static let hamsterImage = template("Hamster")
    @MainActor private static let standingHamsterImage = template("StandingHamster")
    @MainActor private static let frontHamsterImage = template("FrontHamster")
    @MainActor private static let classicImage: NSImage = {
        let image = NSImage(systemSymbolName: "waveform.path.ecg", accessibilityDescription: nil)!
        image.isTemplate = true
        return image
    }()

    @MainActor private static func template(_ name: String) -> NSImage {
        let developmentURL = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
            .appendingPathComponent("Support/\(name).pdf")
        let url = Bundle.main.url(forResource: name, withExtension: "pdf") ?? developmentURL
        guard let image = NSImage(contentsOf: url) else { return classicImage }
        image.size = NSSize(width: 16, height: 16)
        image.isTemplate = true
        return image
    }
}
