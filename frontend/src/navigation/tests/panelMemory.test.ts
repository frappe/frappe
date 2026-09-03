// What this tab remembers about which panel an address opened in (#42464).
import { beforeEach, describe, expect, it, vi } from "vitest";

import { recallPanel, rememberPanel } from "@/navigation/panelMemory";

beforeEach(() => {
	sessionStorage.clear();
	vi.restoreAllMocks();
});

describe("remembering a panel", () => {
	it("reads back what it recorded", () => {
		rememberPanel("/item", "module_def_stock");
		expect(recallPanel("/item")).toBe("module_def_stock");
	});

	it("remembers per address, not one panel for the whole tab", () => {
		rememberPanel("/item", "module_def_stock");
		rememberPanel("/supplier", "module_def_buying");

		expect(recallPanel("/item")).toBe("module_def_stock");
		expect(recallPanel("/supplier")).toBe("module_def_buying");
	});

	it("keeps the latest answer for an address", () => {
		rememberPanel("/item", "module_def_stock");
		rememberPanel("/item", "module_def_selling");
		expect(recallPanel("/item")).toBe("module_def_selling");
	});

	it("knows nothing about an address it has not seen", () => {
		expect(recallPanel("/item")).toBeUndefined();
	});
});

describe("the cap on how much it keeps", () => {
	// Every address that opens a panel is recorded, records included, so an uncapped record
	// grows for as long as the tab lives and every navigation re-serialises all of it.
	it("keeps the most recent addresses and drops the oldest", () => {
		for (let index = 0; index < 120; index += 1) {
			rememberPanel(`/item/ITEM-${index}`, "module_def_stock");
		}

		expect(recallPanel("/item/ITEM-119")).toBe("module_def_stock");
		expect(recallPanel("/item/ITEM-20")).toBe("module_def_stock");
		// The first twenty fell off, which costs those addresses their continuity and nothing
		// else: they resolve off the address again.
		expect(recallPanel("/item/ITEM-0")).toBeUndefined();
		expect(Object.keys(JSON.parse(sessionStorage.getItem("frappe:desk:panel")!))).toHaveLength(
			100
		);
	});

	it("counts re-resolving an address as recent, so browsing does not evict it", () => {
		rememberPanel("/item", "module_def_stock");
		for (let index = 0; index < 99; index += 1) {
			rememberPanel(`/other/${index}`, "module_def_buying");
		}
		// Back to it, then fill the rest of the cap again.
		rememberPanel("/item", "module_def_selling");
		for (let index = 0; index < 99; index += 1) {
			rememberPanel(`/more/${index}`, "module_def_buying");
		}

		expect(recallPanel("/item")).toBe("module_def_selling");
	});
});

describe("when storage will not cooperate", () => {
	// A tab that cannot remember falls back to resolving off the address alone, which is what
	// shipped before this — never wrong, only less continuous. So none of this may throw.
	it("recalls nothing rather than throwing when reading is forbidden", () => {
		vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
			throw new Error("SecurityError");
		});

		expect(() => recallPanel("/item")).not.toThrow();
		expect(recallPanel("/item")).toBeUndefined();
	});

	it("swallows a write that is over quota", () => {
		vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
			throw new Error("QuotaExceededError");
		});

		expect(() => rememberPanel("/item", "module_def_stock")).not.toThrow();
	});

	it("ignores a value that is not the record it wrote", () => {
		// `sessionStorage` is shared with anything else on the tab, and a half-written value is
		// not worth a broken shell.
		sessionStorage.setItem("frappe:desk:panel", "not json at all");
		expect(recallPanel("/item")).toBeUndefined();

		sessionStorage.setItem("frappe:desk:panel", JSON.stringify(["an", "array"]));
		expect(recallPanel("/item")).toBeUndefined();

		sessionStorage.setItem("frappe:desk:panel", JSON.stringify({ "/item": 42 }));
		expect(recallPanel("/item")).toBeUndefined();
	});
});
