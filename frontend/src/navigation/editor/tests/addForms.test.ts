import { describe, expect, it, vi } from "vitest";
import { Addresses } from "@/addresses";
import { RAIL } from "../draft";
import { addable, addTypes, buildRow, missing, servedPages, startValues } from "../addTypes";
import { thisPage } from "../thisPage";

vi.mock("@/contributions/registry", async (original) => ({
	...(await original<object>()),
	pages: [
		{ app: "frappe", slug: "flow-builder", title: "Flow Builder" },
		{ app: "frappe", slug: "dropped" },
		{ app: "erpnext", slug: "pos" },
	],
}));

const addresses = new Addresses({
	doctypes: { ToDo: ["todo", "desk"] },
	modules: { desk: "Desk" },
	singles: [],
});

describe("add forms", () => {
	it("builds a Record row on its doctype and name", () => {
		const values = { ...startValues(), doctype: "ToDo", name: "TD-1" };
		expect(missing("Record", values)).toBeNull();
		expect(buildRow("Record", values)).toEqual({
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
		expect(buildRow("Page", values)).toEqual({
			item_type: "Page",
			link_doctype: "Page",
			link_to: "deals",
			label: "Deals",
		});
		expect(missing("Page", startValues())?.field).toBe("page");
	});

	it("offers Record and Page on the rail, and Section only in a sidebar", () => {
		const rail = addTypes(RAIL).map((entry) => entry.type);
		expect(rail).toEqual(["DocType", "Record", "Page", "Link", "Act"]);
		expect(addTypes("sidebar:x").map((entry) => entry.type)).toContain("Section");
	});

	it("offers only the pages the app's router serves", () => {
		expect(servedPages(() => true, "no-such-app")).toEqual([]);
		expect(servedPages(() => false, "frappe")).toEqual([]);
		const served = servedPages((name) => name === "page:frappe:flow-builder", "frappe");
		expect(served).toEqual([{ label: "Flow Builder", value: "flow-builder" }]);
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

describe("Link url", () => {
	it("takes a path or an http(s) address, as the server does", () => {
		const link = (url: string) => missing("Link", { ...startValues(), url })?.field ?? null;
		expect(link("/app/todo")).toBeNull();
		expect(link("HTTPS://example.com")).toBeNull();
		expect(link("//evil.com")).toBe("url");
		expect(link("/\\evil.com")).toBe("url");
		expect(link("javascript:alert(1)")).toBe("url");
		expect(link("/a b")).toBe("url");
	});

	it("knows the addable kinds from the picker's list", () => {
		expect(addable("Section")).toBe(true);
		expect(addable("Module")).toBe(false);
		expect(addable("Sidebar")).toBe(false);
	});
});
