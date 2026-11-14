import { describe, expect, it } from "vitest";
import { Addresses } from "@/addresses";
import { RAIL } from "../draft";
import { addTypes, buildRow, missing, startValues } from "../addTypes";
import { thisPage } from "../thisPage";

const addresses = new Addresses({
	doctypes: { ToDo: ["todo", "desk"] },
	modules: { desk: "Desk" },
	singles: [],
});

describe("add forms", () => {
	it("builds a Record row on its doctype and name", () => {
		const values = { ...startValues(), doctype: "ToDo", name: "TD-1" };
		expect(missing("Record", values)).toBeNull();
		expect(buildRow("Record", "user:abc123", values)).toEqual({
			key: "user:abc123",
			item_type: "Record",
			link_doctype: "ToDo",
			link_to: "TD-1",
		});
	});

	it("asks for the record before it adds one", () => {
		const values = { ...startValues(), doctype: "ToDo" };
		expect(missing("Record", values)?.field).toBe("name");
	});

	it("builds a Page row that names the Page doctype", () => {
		const values = { ...startValues(), page: "deals", label: " Deals " };
		expect(buildRow("Page", "k", values)).toEqual({
			key: "k",
			item_type: "Page",
			link_doctype: "Page",
			link_to: "deals",
			label: "Deals",
		});
		expect(missing("Page", startValues())?.field).toBe("page");
	});

	it("offers Record and Page on the rail, and Section only in a sidebar", () => {
		const rail = addTypes(RAIL).map((entry) => entry.type);
		expect(rail).toEqual(["DocType", "Record", "Page", "Link"]);
		expect(addTypes("sidebar:x").map((entry) => entry.type)).toContain("Section");
	});
});

describe("this page", () => {
	it("is a DocType row on a list", () => {
		const page = thisPage({ name: "list", params: { doctype: "todo" } }, addresses, "desk");
		expect(page?.fields).toEqual({ item_type: "DocType", link_doctype: "DocType", link_to: "ToDo" });
		expect(startValues(page?.fields).doctype).toBe("ToDo");
	});

	it("is a Record row on a record", () => {
		const page = thisPage({ name: "record", params: { doctype: "todo", name: "TD-1" } }, addresses, "desk");
		expect(page).toMatchObject({ type: "Record", label: "TD-1" });
		expect(startValues(page?.fields)).toMatchObject({ doctype: "ToDo", name: "TD-1" });
	});

	it("is a Page row on a contributed page, titled by the page", () => {
		const page = thisPage({ name: "page:desk:deals", params: {}, meta: { title: "Deals" } }, addresses, "desk");
		expect(page).toMatchObject({ type: "Page", label: "Deals" });
		expect(startValues(page?.fields).page).toBe("deals");
	});

	it("offers nothing on a saved view or an unknown route", () => {
		expect(thisPage({ name: "saved-view", params: { doctype: "todo" } }, addresses, "desk")).toBeNull();
		expect(thisPage({ name: "home", params: {} }, addresses, "desk")).toBeNull();
	});
});
