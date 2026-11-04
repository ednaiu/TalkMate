import CoreText
import XCTest
@testable import TalkMate

final class BrandTypographyTests: XCTestCase {
    func testWordmarkUsesBundledManropeAtSelectedWeight() {
        let font = BrandType.font(34)
        XCTAssertTrue((CTFontCopyPostScriptName(font) as String).hasPrefix("Manrope"))
        let variations = CTFontCopyVariation(font) as? [NSNumber: NSNumber]
        XCTAssertEqual(variations?[NSNumber(value: 2003265652)]?.doubleValue, 650)
    }
}
