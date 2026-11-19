// One value per user and name, in the browser or one tab: users stay apart, a broken store
// reads as nothing, a refused write is dropped, and a former key moves over once.
import { afterEach, describe, expect, it, vi } from "vitest";
import { browserMemory, tabMemory } from "@/browserMemory";

const isNumber = (value: unknown): value is number => typeof value === "number";
const isString = (value: unknown): value is string => typeof value === "string";
const isObject = (value: unknown): value is Record<string, number> =>
	!!value && typeof value === "object";

afterEach(() => {
	vi.unstubAllGlobals();
	localStorage.clear();
	sessionStorage.clear();
});

describe("browserMemory", () => {
	it("keeps two users on one browser apart", () => {
		browserMemory("widths", "ann@example.com", isObject).remember({ panel: 400 });
		browserMemory("widths", "bob@example.com", isObject).remember({ panel: 600 });
		expect(browserMemory("widths", "ann@example.com", isObject).recall()).toEqual({ panel: 400 });
		expect(browserMemory("widths", "bob@example.com", isObject).recall()).toEqual({ panel: 600 });
		expect(browserMemory("height", "ann@example.com", isNumber).recall()).toBeUndefined();
		expect(JSON.parse(localStorage.getItem("frappe:desk:widths")!)).toEqual({
			"ann@example.com": { panel: 400 },
			"bob@example.com": { panel: 600 },
		});
	});

	it("reads a store it cannot parse as nothing, and writes over it", () => {
		localStorage.setItem("frappe:desk:widths", "{not json");
		const memory = browserMemory("widths", "ann@example.com", isNumber);
		expect(memory.recall()).toBeUndefined();
		memory.remember(7);
		expect(memory.recall()).toBe(7);
	});

	it("reads a value of the wrong shape as nothing", () => {
		localStorage.setItem("frappe:desk:height", '{"ann@example.com":"tall"}');
		expect(browserMemory("height", "ann@example.com", isNumber).recall()).toBeUndefined();
	});

	it("drops a write the browser refuses", () => {
		vi.stubGlobal("localStorage", {
			getItem: () => null,
			setItem: () => {
				throw new DOMException("full", "QuotaExceededError");
			},
		});
		expect(() => browserMemory("widths", "ann@example.com", isNumber).remember(7)).not.toThrow();
	});

	it("moves a value from its former key once, for that user only", () => {
		localStorage.setItem("old:ann", "320");
		expect(browserMemory("height", "bob@example.com", isNumber, "old:bob").recall()).toBeUndefined();
		expect(browserMemory("height", "ann@example.com", isNumber, "old:ann").recall()).toBe(320);
		expect(localStorage.getItem("old:ann")).toBeNull();
		expect(browserMemory("height", "ann@example.com", isNumber).recall()).toBe(320);
	});

	it("keeps the former key when the move cannot be written", () => {
		const removed: string[] = [];
		vi.stubGlobal("localStorage", {
			getItem: (key: string) => (key === "old:ann" ? "320" : null),
			setItem: () => {
				throw new DOMException("full", "QuotaExceededError");
			},
			removeItem: (key: string) => removed.push(key),
		});
		expect(browserMemory("height", "ann@example.com", isNumber, "old:ann").recall()).toBe(320);
		expect(removed).toEqual([]);
	});

	it("drops a former key that does not parse", () => {
		localStorage.setItem("old:ann", "NaN");
		expect(browserMemory("height", "ann@example.com", isNumber, "old:ann").recall()).toBeUndefined();
		expect(localStorage.getItem("old:ann")).toBeNull();
	});

	it("moves a former key that holds a bare string", () => {
		localStorage.setItem("old:ann", "floating");
		expect(browserMemory("window", "ann@example.com", isString, "old:ann").recall()).toBe("floating");
		expect(localStorage.getItem("old:ann")).toBeNull();
	});

	it("drops a former key that fails the shape", () => {
		localStorage.setItem("old:ann", '"tall"');
		expect(browserMemory("height", "ann@example.com", isNumber, "old:ann").recall()).toBeUndefined();
		expect(localStorage.getItem("old:ann")).toBeNull();
		expect(localStorage.getItem("frappe:desk:height")).toBeNull();
	});
});

describe("tabMemory", () => {
	it("keeps two users in one tab apart, in sessionStorage", () => {
		tabMemory("sidebars", "ann@example.com", isString).remember("stock");
		tabMemory("sidebars", "bob@example.com", isString).remember("buying");
		expect(tabMemory("sidebars", "ann@example.com", isString).recall()).toBe("stock");
		expect(tabMemory("sidebars", "bob@example.com", isString).recall()).toBe("buying");
		expect(localStorage.getItem("frappe:desk:sidebars")).toBeNull();
	});

	it("drops a write the tab refuses", () => {
		vi.stubGlobal("sessionStorage", {
			getItem: () => null,
			setItem: () => {
				throw new DOMException("full", "QuotaExceededError");
			},
		});
		expect(() => tabMemory("sidebars", "ann@example.com", isString).remember("stock")).not.toThrow();
	});
});
