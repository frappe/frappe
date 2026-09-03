// What this browser remembers about the sections one reader has opened or shut.
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { NavigationItem } from "@/boot";
import { sectionMemory } from "@/navigation/sectionMemory";

const READER = "reader@example.com";
const PANEL = "Sidebar:doctype_crm_lead";

function section(key: string, keepClosed?: 1): NavigationItem {
	return { key, item_type: "Section", collapsible: 1, ...(keepClosed ? { keep_closed: 1 } : {}) };
}

const shipped = [section("leads-configure", 1), section("leads-more")];

function memory(items = shipped, user = READER) {
	return sectionMemory(user, PANEL, items);
}

function stored() {
	return JSON.parse(localStorage.getItem("frappe:desk:sections") ?? "null");
}

beforeEach(() => {
	localStorage.clear();
	vi.restoreAllMocks();
});

describe("remembering a toggle", () => {
	it("knows nothing until somebody decides something", () => {
		expect(memory().recall("leads-configure")).toBeUndefined();
	});

	it("reads back a section opened against what the app ships", () => {
		memory().remember("leads-configure", true);
		expect(memory().recall("leads-configure")).toBe(true);
	});

	it("reads back a section shut against what the app ships", () => {
		memory().remember("leads-more", false);
		expect(memory().recall("leads-more")).toBe(false);
	});

	it("forgets a section toggled back to what the app ships", () => {
		const kept = memory();
		kept.remember("leads-configure", true);
		kept.remember("leads-configure", false);

		expect(memory().recall("leads-configure")).toBeUndefined();
		expect(stored()).toEqual({});
	});
});

describe("whose disclosures these are", () => {
	it("does not hand one reader's toggle to another on the same browser", () => {
		memory().remember("leads-configure", true);
		expect(memory(shipped, "colleague@example.com").recall("leads-configure")).toBeUndefined();
	});

	it("does not hand one container's toggle to another", () => {
		memory().remember("leads-configure", true);
		expect(sectionMemory(READER, "Rail:crm", shipped).recall("leads-configure")).toBeUndefined();
	});

	it("keeps a second container's entries when the first writes", () => {
		sectionMemory(READER, "Rail:crm", shipped).remember("leads-more", false);
		memory().remember("leads-configure", true);

		expect(sectionMemory(READER, "Rail:crm", shipped).recall("leads-more")).toBe(false);
		expect(memory().recall("leads-configure")).toBe(true);
	});
});

describe("what an upgrade does to it", () => {
	it("stops counting an entry for a section that is gone", () => {
		memory().remember("leads-configure", true);
		expect(memory([section("leads-more")]).recall("leads-configure")).toBeUndefined();
	});

	it("lets a new shipped keep_closed beat what the reader had toggled", () => {
		// Opened against a section that shipped shut. The app now ships it open, so the entry
		// says nothing either way and the shipped value is what is left.
		memory().remember("leads-configure", true);
		expect(memory([section("leads-configure")]).recall("leads-configure")).toBeUndefined();
	});

	it("clears a stale entry out of storage at the next write", () => {
		memory().remember("leads-configure", true);

		const upgraded = memory([section("leads-more")]);
		upgraded.remember("leads-more", false);

		expect(stored()[READER][PANEL]).toEqual({ "leads-more": false });
	});
});

describe("a browser that cannot store", () => {
	it("keeps working when reading throws", () => {
		vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
			throw new Error("denied");
		});

		expect(() => memory().recall("leads-configure")).not.toThrow();
	});

	it("keeps working when writing throws", () => {
		vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
			throw new Error("quota");
		});

		const kept = memory();
		expect(() => kept.remember("leads-configure", true)).not.toThrow();
		// The page still shows the section open; only the reload loses it.
		expect(kept.recall("leads-configure")).toBe(true);
	});

	it("ignores a stored value that is not the shape it wrote", () => {
		localStorage.setItem("frappe:desk:sections", '"a string"');
		expect(memory().recall("leads-configure")).toBeUndefined();
	});
});
