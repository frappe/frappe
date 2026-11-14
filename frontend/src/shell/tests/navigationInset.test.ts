// The inset the corner floats add to their right offset, and the toast viewport's rule for it.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("the toast viewport", () => {
	it("adds the navigation's inset to sonner's right offset", () => {
		const css = readFileSync("src/index.css", "utf8");
		expect(css).toMatch(
			/\[data-sonner-toaster\]\[data-x-position="right"\]\s*\{\s*right: calc\(var\(--offset-right\) \+ var\(--shell-nav-inset-right, 0px\)\);/
		);
	});
});
