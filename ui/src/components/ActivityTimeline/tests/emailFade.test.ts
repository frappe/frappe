import { describe, expect, it } from "vitest";
import { bottomFade } from "../utils";

// Geometry below is measured from a real clipped email (3598px of content in
// the 500px box) rather than invented, so the end-of-scroll case is exact.
describe("bottomFade", () => {
  it("fades while there is more email below the fold", () => {
    expect(bottomFade({ scrollTop: 0, clientHeight: 500, scrollHeight: 3598 })).toBe("18px");
    expect(bottomFade({ scrollTop: 1500, clientHeight: 500, scrollHeight: 3598 })).toBe("18px");
  });

  it("drops the fade once the last line is reached", () => {
    expect(bottomFade({ scrollTop: 3098, clientHeight: 500, scrollHeight: 3598 })).toBe("0px");
  });

  it("drops the fade when the scroll lands fractionally short of the end", () => {
    // scrollTop goes fractional on HiDPI/zoom; without the tolerance the fade
    // would survive at the bottom, which is the bug this guards.
    expect(bottomFade({ scrollTop: 3097.5, clientHeight: 500, scrollHeight: 3598 })).toBe("0px");
  });

  it("never fades content that fits", () => {
    expect(bottomFade({ scrollTop: 0, clientHeight: 301, scrollHeight: 301 })).toBe("0px");
  });
});
