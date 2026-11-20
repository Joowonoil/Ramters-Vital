import Foundation

struct UsageTracking: Sendable {
    private(set) var enabled: Set<AccountProvider>
    private var revisions: [AccountProvider: Int] = [:]

    init(defaults: UserDefaults = .standard) {
        enabled = Set(AccountProvider.allCases.filter {
            defaults.object(forKey: Self.key($0)) as? Bool ?? true
        })
    }

    private static func key(_ provider: AccountProvider) -> String {
        "\(provider.rawValue)TrackingEnabled" // Includes the original Gemini preference.
    }

    mutating func set(_ value: Bool, for provider: AccountProvider, defaults: UserDefaults = .standard) {
        guard enabled.contains(provider) != value else { return }
        if value { enabled.insert(provider) } else { enabled.remove(provider) }
        revisions[provider, default: 0] += 1
        defaults.set(value, forKey: Self.key(provider))
    }

    func loadIfEnabled<T>(_ provider: AccountProvider, _ load: () async -> T) async -> T? {
        guard enabled.contains(provider) else { return nil }
        return await load()
    }

    // A request started before an off/on cycle is stale even when tracking is on again.
    func accepts(_ provider: AccountProvider, from start: Self) -> Bool {
        enabled.contains(provider) && start.enabled.contains(provider)
            && revisions[provider] == start.revisions[provider]
    }
}
