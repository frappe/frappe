// What this tab remembers, per reader, about which sidebar an address opened in.
import { beforeEach, describe, expect, it, vi } from "vitest";

import { sidebarMemory } from "@/navigation/sidebarMemory";

const READER = "reader@example.com";

function recallSidebar(path: string, user = READER) {
	return sidebarMemory(user).recall(path);
}

function rememberSidebar(path: string, sidebar: string, user = READER) {
	sidebarMemory(user).remember(path, sidebar);
}

function stored() {
	return JSON.parse(sessionStorage.getItem("frappe:desk:sidebars")!);
}

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

describe("whose record this is", () => {
	it("keeps two readers in one tab apart", () => {
		rememberSidebar("/item", "module_def_stock");
		rememberSidebar("/item", "module_def_selling", "colleague@example.com");

		expect(recallSidebar("/item")).toBe("module_def_stock");
		expect(recallSidebar("/item", "colleague@example.com")).toBe("module_def_selling");
		expect(recallSidebar("/item", "third@example.com")).toBeUndefined();
	});

	it("does not read the record kept before it was per reader", () => {
		sessionStorage.setItem("frappe:desk:sidebar", JSON.stringify({ "/item": "module_def_stock" }));
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
		expect(Object.keys(stored()[READER])).toHaveLength(100);
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
		sessionStorage.setItem("frappe:desk:sidebars", "not json at all");
		expect(recallSidebar("/item")).toBeUndefined();

		sessionStorage.setItem("frappe:desk:sidebars", JSON.stringify({ [READER]: ["an", "array"] }));
		expect(recallSidebar("/item")).toBeUndefined();

		sessionStorage.setItem("frappe:desk:sidebars", JSON.stringify({ [READER]: { "/item": 42 } }));
		expect(recallSidebar("/item")).toBeUndefined();
	});
});
