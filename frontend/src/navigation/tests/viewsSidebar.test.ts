// Which rail items get the DocType sidebar of views, and which view the address shows.
import { describe, expect, it } from "vitest";
import type { NavigationItem } from "@/boot";
import { openViewKey, viewsSidebarFor } from "../viewsSidebar";

const item = (over: Partial<NavigationItem>): NavigationItem => ({ label: "", item_type: "DocType", ...over }) as NavigationItem;
const notSingle = () => false;

describe("viewsSidebarFor", () => {
	it("gives a DocType rail item the views sidebar, titled by its label", () => {
		expect(viewsSidebarFor(item({ label: "To Do", link_to: "ToDo" }), notSingle)).toEqual({
			doctype: "ToDo",
			title: "To Do",
		});
	});

	it("titles an unlabelled DocType item by the doctype", () => {
		expect(viewsSidebarFor(item({ link_to: "ToDo" }), notSingle)?.title).toBe("ToDo");
	});

	it.each(["Module", "View", "Page", "Workspace", "URL"])("leaves a %s rail item to its own sidebar", (type) => {
		expect(viewsSidebarFor(item({ item_type: type as any, link_to: "ToDo" }), notSingle)).toBeNull();
	});

	it("leaves a single alone: it has no list, so no views", () => {
		expect(viewsSidebarFor(item({ link_to: "System Settings" }), (name) => name === "System Settings")).toBeNull();
	});

	it("needs a rail item and a doctype", () => {
		expect(viewsSidebarFor(undefined, notSingle)).toBeNull();
		expect(viewsSidebarFor(item({}), notSingle)).toBeNull();
	});
});

describe("openViewKey", () => {
	it("is the saved view's key on its route", () => {
		expect(openViewKey({ name: "saved-view", params: { key: "mine" } })).toBe("mine");
	});

	it.each(["list", "standard-list"])("is the plain list on the %s route", (name) => {
		expect(openViewKey({ name, params: {} })).toBe("list");
	});

	it("is none on a page that is no view", () => {
		expect(openViewKey({ name: "record", params: {} })).toBeNull();
		expect(openViewKey({ params: {} })).toBeNull();
	});
});
