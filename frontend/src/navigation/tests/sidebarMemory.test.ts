// What this tab remembers about which sidebar an address opened in.
import { beforeEach, describe, expect, it, vi } from "vitest";

import { recallSidebar, rememberSidebar } from "@/navigation/sidebarMemory";

beforeEach(() => {
	sessionStorage.clear();
	vi.restoreAllMocks();
});

describe("remembering a sidebar", () => {
	it("reads back what it recorded", () => {
		rememberSidebar("/item", "module_def_stock");
		expect(recallSidebar("/item")).toBe("module_def_stock");
	});

	it("remembers per address, not one sidebar for the whole tab", () => {
		rememberSidebar("/item", "module_def_stock");
		rememberSidebar("/supplier", "module_def_buying");

		expect(recallSidebar("/item")).toBe("module_def_stock");
		expect(recallSidebar("/supplier")).toBe("module_def_buying");
	});

	it("keeps the latest answer for an address", () => {
		rememberSidebar("/item", "module_def_stock");
		rememberSidebar("/item", "module_def_selling");
		expect(recallSidebar("/item")).toBe("module_def_selling");
	});

	it("knows nothing about an address it has not seen", () => {
		expect(recallSidebar("/item")).toBeUndefined();
	});
});

describe("the cap on how much it keeps", () => {
	// Records get their own entry, so browsing alone fills this.
	it("keeps the most recent addresses and drops the oldest", () => {
		for (let index = 0; index < 120; index += 1) {
			rememberSidebar(`/item/ITEM-${index}`, "module_def_stock");
		}

		expect(recallSidebar("/item/ITEM-119")).toBe("module_def_stock");
		expect(recallSidebar("/item/ITEM-20")).toBe("module_def_stock");
		// The first twenty fell off, costing those addresses continuity and nothing else.
		expect(recallSidebar("/item/ITEM-0")).toBeUndefined();
		expect(Object.keys(JSON.parse(sessionStorage.getItem("frappe:desk:sidebar")!))).toHaveLength(
			100
		);
	});

	it("counts re-resolving an address as recent, so browsing does not evict it", () => {
		rememberSidebar("/item", "module_def_stock");
		for (let index = 0; index < 99; index += 1) {
			rememberSidebar(`/other/${index}`, "module_def_buying");
		}
		// Back to it, then fill the rest of the cap again.
		rememberSidebar("/item", "module_def_selling");
		for (let index = 0; index < 99; index += 1) {
			rememberSidebar(`/more/${index}`, "module_def_buying");
		}

		expect(recallSidebar("/item")).toBe("module_def_selling");
	});
});

describe("when storage will not cooperate", () => {
	// A tab that cannot remember resolves off the address, so none of this may throw.
	it("recalls nothing rather than throwing when reading is forbidden", () => {
		vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
			throw new Error("SecurityError");
		});

		expect(() => recallSidebar("/item")).not.toThrow();
		expect(recallSidebar("/item")).toBeUndefined();
	});

	it("swallows a write that is over quota", () => {
		vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
			throw new Error("QuotaExceededError");
		});

		expect(() => rememberSidebar("/item", "module_def_stock")).not.toThrow();
	});

	it("ignores a value that is not the record it wrote", () => {
		// Storage is shared, and a half-written value is not worth a broken shell.
		sessionStorage.setItem("frappe:desk:sidebar", "not json at all");
		expect(recallSidebar("/item")).toBeUndefined();

		sessionStorage.setItem("frappe:desk:sidebar", JSON.stringify(["an", "array"]));
		expect(recallSidebar("/item")).toBeUndefined();

		sessionStorage.setItem("frappe:desk:sidebar", JSON.stringify({ "/item": 42 }));
		expect(recallSidebar("/item")).toBeUndefined();
	});
});
