// vue-sonner sets its own font stack on the toaster; the app's sheet must override it (#47444).
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("toast font", () => {
	it("takes the app's font instead of sonner's system stack", () => {
		const css = readFileSync("src/index.css", "utf8");
		expect(css).toMatch(/:root \[data-sonner-toaster\]\s*\{\s*font-family: inherit;/);
	});
});
