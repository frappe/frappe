// One value per user and name in this browser: users stay apart, a broken store reads as
// nothing, a refused write is dropped, and a former key moves over once.
import { afterEach, describe, expect, it, vi } from "vitest";
import { browserMemory } from "@/browserMemory";

afterEach(() => {
	vi.unstubAllGlobals();
	localStorage.clear();
});

describe("browserMemory", () => {
	it("keeps two users on one browser apart", () => {
		browserMemory("widths", "ann@example.com").remember({ panel: 400 });
		browserMemory("widths", "bob@example.com").remember({ panel: 600 });
		expect(browserMemory("widths", "ann@example.com").recall()).toEqual({ panel: 400 });
		expect(browserMemory("widths", "bob@example.com").recall()).toEqual({ panel: 600 });
		expect(browserMemory("height", "ann@example.com").recall()).toBeUndefined();
		expect(JSON.parse(localStorage.getItem("frappe:desk:widths")!)).toEqual({
			"ann@example.com": { panel: 400 },
			"bob@example.com": { panel: 600 },
		});
	});

	it("reads a store it cannot parse as nothing, and writes over it", () => {
		localStorage.setItem("frappe:desk:widths", "{not json");
		const memory = browserMemory<number>("widths", "ann@example.com");
		expect(memory.recall()).toBeUndefined();
		memory.remember(7);
		expect(memory.recall()).toBe(7);
	});

	it("drops a write the browser refuses", () => {
		vi.stubGlobal("localStorage", {
			getItem: () => null,
			setItem: () => {
				throw new DOMException("full", "QuotaExceededError");
			},
		});
		const memory = browserMemory<number>("widths", "ann@example.com");
		expect(() => memory.remember(7)).not.toThrow();
		expect(memory.recall()).toBeUndefined();
	});

	it("moves a value from its former key once, for that user only", () => {
		localStorage.setItem("old:ann", "320");
		expect(browserMemory("height", "bob@example.com", "old:bob").recall()).toBeUndefined();
		expect(browserMemory("height", "ann@example.com", "old:ann").recall()).toBe(320);
		expect(localStorage.getItem("old:ann")).toBeNull();
		expect(browserMemory("height", "ann@example.com").recall()).toBe(320);
	});
});
