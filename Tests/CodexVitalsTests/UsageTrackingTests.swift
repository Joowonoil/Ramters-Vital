import XCTest
@testable import CodexVitals

final class UsageTrackingTests: XCTestCase {
    func testDefaultsAndIndependentPersistence() throws {
        let suite = UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        XCTAssertEqual(UsageTracking(defaults: defaults).enabled, Set(AccountProvider.allCases))
        defaults.set(false, forKey: "geminiTrackingEnabled")
        var tracking = UsageTracking(defaults: defaults)
        XCTAssertEqual(tracking.enabled, [.codex, .claude])
        tracking.set(false, for: .codex, defaults: defaults)
        tracking.set(true, for: .gemini, defaults: defaults)
        XCTAssertEqual(UsageTracking(defaults: defaults).enabled, [.claude, .gemini])
    }

    func testDisabledLoadersNeverRunAndLateResultsAreRejected() async throws {
        let suite = UUID().uuidString
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        var tracking = UsageTracking(defaults: defaults)
        for provider in AccountProvider.allCases {
            let start = tracking
            tracking.set(false, for: provider, defaults: defaults)
            let result: Int? = await tracking.loadIfEnabled(provider) {
                XCTFail("Disabled provider was queried")
                return 1
            }
            XCTAssertNil(result)
            XCTAssertFalse(tracking.accepts(provider, from: start))
            tracking.set(true, for: provider, defaults: defaults)
            XCTAssertFalse(tracking.accepts(provider, from: start))
            for other in AccountProvider.allCases where other != provider {
                XCTAssertTrue(tracking.accepts(other, from: start))
            }
            let enabledResult = await tracking.loadIfEnabled(provider) { 1 }
            XCTAssertEqual(enabledResult, 1)
            XCTAssertTrue(tracking.accepts(provider, from: tracking))
        }
    }
}
