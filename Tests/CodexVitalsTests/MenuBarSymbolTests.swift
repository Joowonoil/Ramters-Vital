import XCTest
@testable import CodexVitals

final class MenuBarSymbolTests: XCTestCase {
    func testDefaultAndRestoredSelections() throws {
        let suite = "MenuBarSymbolTests.\(UUID().uuidString)"
        let defaults = try XCTUnwrap(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        XCTAssertEqual(MenuBarSymbol.stored(in: defaults), .pixelV)
        for symbol in MenuBarSymbol.allCases {
            symbol.save(in: defaults)
            XCTAssertEqual(MenuBarSymbol.stored(in: try XCTUnwrap(UserDefaults(suiteName: suite))), symbol)
        }
        defaults.set("unknown", forKey: "menuBarSymbol")
        XCTAssertEqual(MenuBarSymbol.stored(in: defaults), .pixelV)
    }
}
