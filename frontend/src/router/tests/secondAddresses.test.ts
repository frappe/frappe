// The standard list and record pages each have a second address, `/view/list` and `/record`,
// and a saved view lives under the list kind, under both route shapes.
import { describe, expect, it, vi } from "vitest";

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { createShellRouter } from "@/router";
import { registerShell, urlFor } from "@/router/routeFor";
import List from "@/pages/List.vue";
import Record from "@/pages/Record.vue";

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Record.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

const addresses = new Addresses({
	doctypes: {
		"Sales Invoice": ["sales-invoice", "accounts"],
		"Accounts Settings": ["accounts-settings", "accounts"],
	},
	modules: { accounts: "Accounts", selling: "Selling" },
	singles: ["Accounts Settings"],
});

function boot(modular: boolean): Boot {
	return {
		app: "erpnext",
		shell_base: "/apps/erpnext",
		prefixes: { erpnext: { app: "erpnext", modular } },
	} as unknown as Boot;
}

describe.each([
	{ shape: "flat", modular: false, prefix: "" },
	{ shape: "modular", modular: true, prefix: "/accounts" },
])("second addresses on a $shape app", ({ modular, prefix }) => {
	const module = modular ? { module: "accounts" } : {};

	async function open(path: string) {
		const router = createShellRouter(boot(modular), addresses);
		await router.push(prefix + path);
		return router;
	}

	it("opens the standard list page at /view/list", async () => {
		const router = await open("/sales-invoice/view/list");
		const route = router.currentRoute.value;

		expect(route.name).toBe("standard-list");
		expect(route.params).toEqual({ ...module, doctype: "sales-invoice" });
		expect(route.matched[0].components?.default).toBe(List);
	});

	it("opens the standard record page at /:name/record", async () => {
		const router = await open("/sales-invoice/SI-001/record");
		const route = router.currentRoute.value;

		expect(route.name).toBe("standard-record");
		expect(route.params).toEqual({ ...module, doctype: "sales-invoice", name: "SI-001" });
		expect(route.matched[0].components?.default).toBe(Record);
	});

	it("opens a saved view under the list kind", async () => {
		const router = await open("/sales-invoice/view/list/open-invoices");
		const route = router.currentRoute.value;

		expect(route.name).toBe("saved-view");
		expect(route.params).toEqual({
			...module,
			doctype: "sales-invoice",
			viewName: "open-invoices",
		});
	});

	it.each(["/sales-invoice/view/open-invoices", "/sales-invoice/view/calendar"])(
		"shows not-found at %s",
		async (path) => {
			const router = await open(path);

			expect(router.currentRoute.value.name).toBe("not-found");
		}
	);

	it("keeps /view alone as the record named view", async () => {
		const router = await open("/sales-invoice/view");
		const route = router.currentRoute.value;

		expect(route.name).toBe("record");
		expect(route.params).toEqual({ ...module, doctype: "sales-invoice", name: "view" });
	});

	it("reads /view/record as the standard record page of the record named view", async () => {
		const router = await open("/sales-invoice/view/record");
		const route = router.currentRoute.value;

		expect(route.name).toBe("standard-record");
		expect(route.params).toEqual({ ...module, doctype: "sales-invoice", name: "view" });
	});

	it("lets a single through at /:name/record", async () => {
		const router = await open("/accounts-settings/Accounts%20Settings/record");
		const route = router.currentRoute.value;

		expect(route.name).toBe("standard-record");
		expect(route.params).toEqual({
			...module,
			doctype: "accounts-settings",
			name: "Accounts Settings",
		});
	});

	it("sends a single's /view/list to its record", async () => {
		const router = await open("/accounts-settings/view/list");
		const route = router.currentRoute.value;

		expect(route.name).toBe("record");
		expect(route.params).toEqual({
			...module,
			doctype: "accounts-settings",
			name: "Accounts Settings",
		});
	});

	it("builds a saved view's address under the list kind", () => {
		const router = createShellRouter(boot(modular), addresses);
		registerShell({ boot: boot(modular), addresses, router });

		expect(urlFor("Sales Invoice", null, { view: "open" })).toBe(
			`/apps/erpnext${prefix}/sales-invoice/view/list/open`
		);
	});
});

describe("second addresses on a modular app only", () => {
	async function open(path: string) {
		const router = createShellRouter(boot(true), addresses);
		await router.push(path);
		return router;
	}

	it.each(["/sales-invoice/SI-001/record", "/sales-invoice/view/list"])(
		"shows not-found at the flat shape %s",
		async (path) => {
			const router = await open(path);

			expect(router.currentRoute.value.name).toBe("not-found");
		}
	);

	it("moves the standard list page to the doctype's own module", async () => {
		const router = await open("/selling/sales-invoice/view/list");
		const route = router.currentRoute.value;

		expect(route.name).toBe("standard-list");
		expect(route.params).toEqual({ module: "accounts", doctype: "sales-invoice" });
	});

	it("shows not-found under a module that does not exist", async () => {
		const router = await open("/wrong-module/sales-invoice/view/list");

		expect(router.currentRoute.value.name).toBe("not-found");
	});
});
