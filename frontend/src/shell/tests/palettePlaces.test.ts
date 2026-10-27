// The palette's places read: once the tab holds a reply it asks no more, and each read retries on its own.
// Go to draws a sidebar row in place of its doctype's row at one address, and tells two addresses apart.
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";

import { Addresses } from "@/addresses";
import type { Boot, NavigationItem } from "@/boot";
import { registerContributions } from "@/contributions/registry";
import { registerShell } from "@/router/routeFor";
import type { PaletteContext } from "../paletteGroups";
import { goTo, loadPlaces, openPlace } from "../palettePlaces";

const server = vi.hoisted(() => ({ places: vi.fn(), panes: vi.fn() }));

vi.mock("@framework/ui/api", async (importOriginal) => ({
	...(await importOriginal<typeof import("@framework/ui/api")>()),
	runMethod: (method: string) =>
		method === "frappe.shell.palette.places" ? server.places() : server.panes(),
}));

const boot = {
	app: "crm",
	app_title: "CRM",
	shell_base: "/apps/crm",
	metadata_version: "1",
	prefixes: { crm: { app: "crm", modular: false }, desk: { app: "frappe", modular: false } },
	session: { user: { name: "reader@example.com" } },
} as unknown as Boot;

// As `canonical_path` writes it, under the app that owns ToDo.
const deskBase = "/apps/desk";

const placesReply = {
	doctypes: [
		{ name: "ToDo", app: "frappe", route: `${deskBase}/todo`, can_create: true },
		{ name: "CRM Deal", app: "crm", route: `${boot.shell_base}/crm-deal`, can_create: true },
	],
	apps: [],
	titles: { frappe: "Desk", crm: "CRM" },
	recent: [],
};

const panesReply = {
	panes: [{ app: "frappe", key: "users", label: "Users", blocks: [] }],
	index: [],
	titles: { frappe: "Desk" },
};

const page = { render: () => null };
const router = createRouter({
	history: createMemoryHistory(boot.shell_base),
	routes: [
		{ path: "/", name: "home", component: page },
		{ path: "/:doctype", name: "list", component: page },
		{ path: "/:doctype/:name", name: "record", component: page },
	],
});
const context: PaletteContext = {
	boot,
	router,
	addresses: new Addresses({
		doctypes: { ToDo: ["todo", "desk"], "CRM Deal": ["crm-deal", "fcrm"] },
		modules: { desk: "Desk", fcrm: "FCRM" },
	}),
};

async function settle() {
	for (let turn = 0; turn < 3; turn++) await new Promise((resolve) => setTimeout(resolve, 0));
}

function labels(query: string) {
	return goTo.rows(query, context).map((row) => row.label);
}

beforeAll(async () => {
	await registerContributions(["frappe"]);
});

beforeEach(() => {
	vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("reading the places", () => {
	it("keeps the panes when the places fail, asks for the places again, then asks for nothing", async () => {
		server.places.mockRejectedValueOnce(new Error("offline"));
		server.panes.mockResolvedValue({ data: panesReply });

		loadPlaces(boot);
		await settle();
		expect(labels("users")).toEqual(["Users"]);
		expect(labels("todo")).toEqual([]);

		server.places.mockResolvedValue({ data: placesReply });
		loadPlaces(boot);
		await settle();
		expect(labels("todo")).toEqual(["ToDo"]);

		loadPlaces(boot);
		await settle();
		expect(server.places).toHaveBeenCalledTimes(2);
		expect(server.panes).toHaveBeenCalledTimes(1);
	});
});

describe("a sidebar row and a doctype row", () => {
	const deals: NavigationItem = { key: "deals", item_type: "DocType", link_to: "CRM Deal", label: "Deals" };
	const open: NavigationItem = {
		key: "open",
		item_type: "Link",
		label: "CRM Deal",
		url: `${boot.shell_base}/crm-deal?status=Open`,
	};

	function goToRows(rail: NavigationItem[], query: string) {
		const withSidebar = { ...context, boot: { ...boot, navigation: { rail, sidebars: {} } } };
		registerShell(withSidebar);
		return goTo.rows(query, withSidebar).map((row) => [row.id, row.label, row.description]);
	}

	beforeEach(async () => {
		server.places.mockResolvedValue({ data: placesReply });
		server.panes.mockResolvedValue({ data: panesReply });
		loadPlaces(boot);
		await settle();
	});

	it("draws one row for one address, the sidebar's, still found by the doctype's name", () => {
		const deal = [`sidebar:${boot.shell_base}/crm-deal`, "Deals", "CRM"];
		expect(goToRows([deals], "deal")).toEqual([deal]);
		expect(goToRows([deals], "crm deal")).toEqual([deal]);
	});

	it("keeps the doctype row's Tab narrowing on a link row that stands in for it", () => {
		const link: NavigationItem = { key: "link", item_type: "Link", label: "Deals", url: `${boot.shell_base}/crm-deal` };
		const withSidebar = { ...context, boot: { ...boot, navigation: { rail: [link], sidebars: {} } } };
		registerShell(withSidebar);
		expect(goTo.rows("deal", withSidebar).map((row) => [row.id, row.doctype])).toEqual([
			[`sidebar:${link.url}`, "CRM Deal"],
		]);
	});

	it("names the app that owns the place on a link row to another app's doctype", () => {
		const todo: NavigationItem = { key: "todo", item_type: "Link", label: "My ToDos", url: `${deskBase}/todo` };
		expect(goToRows([todo], "todo")).toEqual([[`sidebar:${todo.url}`, "My ToDos", "Desk"]]);
	});

	it("keeps both rows for two addresses, and the sidebar's says so", () => {
		expect(goToRows([open], "deal")).toEqual([
			[`sidebar:${open.url}`, "CRM Deal", "Sidebar"],
			["doctype:CRM Deal", "CRM Deal", "CRM"],
		]);
	});
});

describe("opening a place", () => {
	it("routes to this app's own address instead of loading it again", async () => {
		const assign = vi.spyOn(window.location, "assign").mockImplementation(() => {});
		await router.push("/todo");

		openPlace(boot.shell_base, context);
		await settle();

		expect(router.currentRoute.value.fullPath).toBe("/");
		expect(assign).not.toHaveBeenCalled();
		assign.mockRestore();
	});
});
