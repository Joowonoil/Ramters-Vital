import Foundation

enum AppInfo {
    static let name = "Ramter's Vital"
    static let homepageURL = URL(string: "https://ramterstudio.com/codex-vitals/")!
    static let repositoryURL = URL(string: "https://github.com/Joowonoil/Ramters-Vital")!
    static let releasesURL = repositoryURL.appendingPathComponent("releases")
    static let studioURL = URL(string: "https://ramterstudio.com")!
    static let feedbackURL = URL(string: "mailto:ramterstudio@gmail.com?subject=Ramter%27s%20Vital%20Feedback")!

    static var versionText: String {
        guard let version = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String,
              !version.isEmpty else {
            return "Unknown"
        }
        return version.hasPrefix("v") ? version : "v\(version)"
    }
}
